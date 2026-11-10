"""Model 6: the coupled simulation engine.

Runs independently of the user interface:

    from config.parameters import default_config
    from simulation.engine import run_simulation
    result = run_simulation(default_config())

Order of calculation in every time step (states T_in, w_in, B):
  1. lighting schedule            u_LED
  2. LED electrical power         P_lighting = P_LED * u_LED
  3. PPFD on the crop             PPFD = PPFD_full * u_LED
  4. internal sensible heat       LED + fans + pumps + auxiliary (heat fractions)
  5. ventilation                  sensible conductance and moisture mass flow
  6. moisture balance             transpiration, ventilation, dehumidification -> w_in
  7. thermal balance and HVAC     envelope, ventilation, transpiration, cooling/heating -> T_in
  8. crop growth                  logistic step with f_T and f_L -> B
  9. electrical power             per component
 10. store results

Coupling is only through shared physical variables: the light that grows the
crop is the same light that heats the room; the water the crop transpires is
the same water the dehumidifier removes.
"""

from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np
import pandas as pd

from analysis import energy_analysis
from config.parameters import derive_geometry, validate_config
from models import crop_growth, humidity, hvac, lighting, thermal, weather
from models.constants import H_FG, J_PER_KWH, SECONDS_PER_DAY, SECONDS_PER_HOUR
from models.numerics import linear_step, response_factor
from simulation.results import SimulationResult
from simulation.time_manager import TimeGrid


def run_simulation(config: dict[str, Any]) -> SimulationResult:
    """Run one scenario and return its time series and summary. Deterministic."""
    config = copy.deepcopy(config)
    validate_config(config)
    crop, light_cfg, hv = config["crop"], config["lighting"], config["hvac"]
    envl, eq, sim = config["envelope"], config["equipment"], config["simulation"]

    grid = TimeGrid.from_config(sim)
    dt, n = grid.dt_s, grid.n_steps
    geo = derive_geometry(config)
    lit = lighting.derive_lighting(light_cfg, geo["growing_area_m2"])
    # keep the three linked lighting inputs consistent in the stored scenario
    light_cfg["ppfd_umol_m2_s"] = lit["ppfd_full_umol_m2_s"]
    light_cfg["power_density_w_m2"] = lit["power_density_w_m2"]
    light_cfg["installed_power_w"] = lit["installed_power_w"]

    # ---- inputs known in advance -------------------------------------------------
    u_led, lit_frac = lighting.schedule_fractions(light_cfg, grid.t_start_s, dt)
    temp_out, rh_out_pct, warnings = weather.build_weather(config["environment"], grid.t_mid_s)
    w_out = humidity.humidity_ratio(temp_out, rh_out_pct / 100.0)

    volume = geo["room_volume_m3"]
    capacitance = thermal.effective_capacitance(volume, envl["thermal_mass_multiplier"])
    flow = thermal.ventilation_flow_m3_s(envl["air_changes_per_hour"], volume)
    conductance = geo["envelope_ua_w_k"] + thermal.ventilation_conductance(flow)      # W/K
    k_thermal = conductance / capacitance                                              # 1/s
    phi_t = response_factor(k_thermal, dt)
    m_da = humidity.dry_air_mass(volume)
    m_vent = humidity.ventilation_mass_flow(flow)

    p_circ = float(eq["circulation_fan_power_w"])
    p_vent_fan = float(eq["ventilation_fan_sfp_w_per_m3s"]) * flow
    p_pump = float(eq["pump_power_w"])
    p_aux = float(eq["auxiliary_power_w"])

    mode = hv["control_mode"]
    q_cap = math.inf if mode == "ideal" else hv["cooling_capacity_kw"] * 1000.0
    removal_cap = min(hv["max_moisture_removal_kg_h"] / SECONDS_PER_HOUR, q_cap / H_FG) \
        if mode != "ideal" else math.inf
    rh_set = hv["rh_setpoint_percent"] / 100.0
    t_set = float(hv["temp_setpoint_c"])
    k_cap = float(crop["max_dry_mass_g"])
    area_crop = geo["occupied_area_m2"]

    # ---- states --------------------------------------------------------------------
    temp = float(sim["initial_temp_c"])
    w = float(humidity.humidity_ratio(temp, sim["initial_rh_percent"] / 100.0))
    biomass = float(crop["initial_dry_mass_g"])
    cooling_on = False

    names = ["indoor_temp_c", "indoor_w_kg_kg", "biomass_dry_g_per_plant", "ppfd_umol_m2_s",
             "power_lighting_w", "heat_led_w", "heat_internal_w", "heat_envelope_w", "heat_ventilation_w",
             "heat_transpiration_w", "cooling_sensible_w", "cooling_latent_w", "cooling_required_w",
             "cooling_unmet_w", "heating_w", "transpiration_kg_s", "moisture_removed_kg_s",
             "moisture_ventilation_kg_s", "condensation_kg_s", "growth_rate_per_day"]
    out = {name: np.zeros(n) for name in names}

    for i in range(n):
        u = float(u_led[i])
        t_out = float(temp_out[i])

        # 1-4: lighting, PPFD, internal heat
        p_light = lighting.lighting_power(lit["installed_power_w"], u)
        ppfd = lit["ppfd_full_umol_m2_s"] * u
        q_led = lighting.led_heat_to_room(p_light, light_cfg["heat_fraction_to_room"])
        q_internal = thermal.internal_sensible_heat(
            q_led, p_circ, eq["circulation_fan_heat_fraction"], p_vent_fan, eq["ventilation_fan_heat_fraction"],
            p_pump, eq["pump_heat_fraction"], p_aux, eq["auxiliary_heat_fraction"])

        # 6: moisture balance  M_da dw/dt = m_vent (w_out - w) + (m0 - g w) - removal
        e_sat = float(humidity.saturation_vapor_pressure(temp))
        m0, g = crop_growth.transpiration_coefficients(crop, biomass, ppfd, float(lit_frac[i]), e_sat, w, area_crop)
        a_w = (m_vent * float(w_out[i]) + m0) / m_da
        k_w = (m_vent + g) / m_da
        w_free, _ = linear_step(w, a_w, k_w, dt)
        removal = 0.0
        latent_required = 0.0
        if hv["dehumidification_enabled"]:
            w_target = float(humidity.humidity_ratio(temp, rh_set))
            if w_free > w_target:
                removal = min(m_da * (w_free - w_target) / response_factor(k_w, dt), removal_cap)
                # moisture gain with the room held at the RH setpoint = load to hold it
                latent_required = max(0.0, m_vent * (float(w_out[i]) - w_target) + m0 - g * w_target) * H_FG
        w_next, w_mean = linear_step(w, a_w - removal / m_da, k_w, dt)
        transpiration = m0 - g * w_mean
        q_latent = humidity.latent_power(removal, H_FG)
        q_transp = humidity.latent_power(transpiration, H_FG)

        # 7: thermal balance  C dT/dt = Q_gain + K (T_out - T) - Q_cool + Q_heat
        q_gain = q_internal - q_transp
        a_t = (q_gain + conductance * t_out) / capacitance
        t_free, _ = linear_step(temp, a_t, k_thermal, dt)
        q_hold = q_gain + conductance * (t_out - t_set)
        decision = hvac.cooling_control(mode, temp, t_free, t_set, q_hold, capacitance, phi_t,
                                        max(0.0, q_cap - q_latent), hv["thermostat_deadband_k"], cooling_on)
        cooling_on = decision.cooling_on
        q_cool = decision.q_cool_w
        q_heat = 0.0
        if hv["heating_enabled"] and q_cool == 0.0:
            q_heat = hvac.heating_control(t_free, hv["heating_setpoint_c"], capacitance, phi_t,
                                          hv["heating_capacity_kw"] * 1000.0)
        t_next, t_mean = linear_step(temp, a_t + (q_heat - q_cool) / capacitance, k_thermal, dt)

        # moisture cannot exceed saturation: the excess condenses on surfaces
        condensation = 0.0
        w_sat = float(humidity.humidity_ratio(t_next, 1.0))
        if w_next > w_sat:
            condensation = m_da * (w_next - w_sat) / dt
            w_next = w_sat

        # 8: crop growth (mean temperature of the step, PPFD while lit)
        ppfd_lit = ppfd / lit_frac[i] if lit_frac[i] > 0 else 0.0
        rate = crop_growth.effective_growth_rate(crop, t_mean, ppfd_lit, float(lit_frac[i]))
        biomass_next = crop_growth.logistic_step(biomass, rate, k_cap, dt)

        # 10: store (states at start of step, flows as step means)
        o = out
        o["indoor_temp_c"][i] = temp
        o["indoor_w_kg_kg"][i] = w
        o["biomass_dry_g_per_plant"][i] = biomass
        o["ppfd_umol_m2_s"][i] = ppfd
        o["power_lighting_w"][i] = p_light
        o["heat_led_w"][i] = q_led
        o["heat_internal_w"][i] = q_internal
        o["heat_envelope_w"][i] = thermal.envelope_heat_gain(geo["envelope_ua_w_k"], t_out, t_mean)
        o["heat_ventilation_w"][i] = thermal.ventilation_heat_gain(flow, t_out, t_mean)
        o["heat_transpiration_w"][i] = q_transp
        o["cooling_sensible_w"][i] = q_cool
        o["cooling_latent_w"][i] = q_latent
        o["cooling_required_w"][i] = decision.q_required_w + latent_required
        o["cooling_unmet_w"][i] = decision.q_unmet_w + max(0.0, latent_required - removal_cap * H_FG)
        o["heating_w"][i] = q_heat
        o["transpiration_kg_s"][i] = transpiration
        o["moisture_removed_kg_s"][i] = removal
        o["moisture_ventilation_kg_s"][i] = m_vent * (float(w_out[i]) - w_mean)
        o["condensation_kg_s"][i] = condensation
        o["growth_rate_per_day"][i] = rate

        temp, w, biomass = t_next, w_next, biomass_next

    # ---- 9: electrical power per component (W electrical) ---------------------------
    ts = pd.DataFrame({"time_h": grid.t_start_s / SECONDS_PER_HOUR})
    ts["day"] = np.floor(grid.t_start_s / SECONDS_PER_DAY).astype(int) + 1
    ts["hour_of_day"] = np.mod(ts["time_h"], 24.0)
    ts["outdoor_temp_c"] = temp_out
    ts["outdoor_rh_percent"] = rh_out_pct
    ts["temp_setpoint_c"] = t_set
    ts["rh_setpoint_percent"] = hv["rh_setpoint_percent"]
    ts["led_schedule_fraction"] = u_led
    for name in names:
        ts[name] = out[name]
    ts["indoor_rh_percent"] = 100.0 * humidity.relative_humidity(ts["indoor_temp_c"], ts["indoor_w_kg_kg"])
    ts["cooling_total_w"] = ts["cooling_sensible_w"] + ts["cooling_latent_w"]
    ts["cooling_capacity_w"] = q_cap if math.isfinite(q_cap) else np.nan
    ts["power_hvac_cooling_w"] = hvac.electrical_power(ts["cooling_total_w"], hv["cooling_cop"])
    ts["power_hvac_heating_w"] = hvac.electrical_power(ts["heating_w"], hv["heating_cop"])
    ts["power_circulation_fans_w"] = p_circ
    ts["power_ventilation_fans_w"] = p_vent_fan
    ts["power_pumps_w"] = p_pump
    ts["power_auxiliary_w"] = p_aux
    ts["power_total_w"] = sum(ts[col] for col in energy_analysis.ELECTRICAL_COMPONENTS)
    ts["biomass_total_dry_kg"] = ts["biomass_dry_g_per_plant"] * geo["n_plants"] / 1000.0
    to_kwh = dt / J_PER_KWH
    ts["cum_energy_lighting_kwh"] = ts["power_lighting_w"].cumsum() * to_kwh
    ts["cum_energy_hvac_kwh"] = (ts["power_hvac_cooling_w"] + ts["power_hvac_heating_w"]).cumsum() * to_kwh
    ts["cum_energy_total_kwh"] = ts["power_total_w"].cumsum() * to_kwh

    final_state = {"indoor_temp_c": temp, "indoor_w_kg_kg": w, "biomass_dry_g_per_plant": biomass,
                   "indoor_rh_percent": 100.0 * float(humidity.relative_humidity(temp, w))}
    derived = {**geo, **lit, "thermal_capacitance_j_k": capacitance, "ventilation_flow_m3_s": flow,
               "total_conductance_w_k": conductance, "dry_air_mass_kg": m_da,
               "thermal_time_constant_h": (1.0 / k_thermal / SECONDS_PER_HOUR) if k_thermal > 0 else math.inf}
    summary = summarise(config, ts, final_state, derived, grid)
    warnings += build_warnings(summary, mode)
    return SimulationResult(config=config, timeseries=ts, summary=summary, final_state=final_state,
                            derived=derived, warnings=warnings)


def summarise(config: dict[str, Any], ts: pd.DataFrame, final_state: dict[str, float],
              derived: dict[str, float], grid: TimeGrid) -> dict[str, Any]:
    """Scalar results: energy [kWh electrical], cooling [kWh thermal], crop [kg], cost."""
    dt, dt_h = grid.dt_s, grid.dt_h
    crop, lim = config["crop"], config["limits"]
    price = config["economics"]["electricity_price_per_kwh"]
    energy = energy_analysis.component_energy_kwh(ts, dt)
    crop_out = crop_growth.harvest(final_state["biomass_dry_g_per_plant"], derived["n_plants"],
                                   crop["dry_matter_fraction"], crop["marketable_fraction"])
    harvest_kg = crop_out["marketable_fresh_mass_kg"]
    kwh_th = dt / J_PER_KWH
    temp, rh = ts["indoor_temp_c"], ts["indoor_rh_percent"]
    cooling_running = ts["cooling_total_w"] > 0

    summary: dict[str, Any] = {
        "scenario_name": config.get("scenario_name", ""),
        "duration_days": grid.duration_days,
        "time_step_s": dt,
        "n_steps": grid.n_steps,
        "energy_kwh": energy,
        "energy_shares_percent": energy_analysis.shares_percent(energy),
        "power_stats_w": energy_analysis.component_power_stats(ts),
        "energy_per_day_kwh": energy["total"] / grid.duration_days,
        # thermal quantities, reported separately from electricity
        "cooling_thermal_kwh_th": float(ts["cooling_total_w"].sum() * kwh_th),
        "cooling_sensible_kwh_th": float(ts["cooling_sensible_w"].sum() * kwh_th),
        "cooling_latent_kwh_th": float(ts["cooling_latent_w"].sum() * kwh_th),
        "heating_thermal_kwh_th": float(ts["heating_w"].sum() * kwh_th),
        "cooling_required_peak_kw": float(ts["cooling_required_w"].max() / 1000.0),
        "cooling_delivered_peak_kw": float(ts["cooling_total_w"].max() / 1000.0),
        "cooling_delivered_mean_kw": float(ts["cooling_total_w"].mean() / 1000.0),
        "cooling_unmet_kwh_th": float(ts["cooling_unmet_w"].sum() * kwh_th),
        "cooling_unmet_hours": float((ts["cooling_unmet_w"] > 1e-6).sum() * dt_h),
        "hvac_cooling_hours": float(cooling_running.sum() * dt_h),
        # indoor climate
        "indoor_temp_mean_c": float(temp.mean()),
        "indoor_temp_min_c": float(temp.min()),
        "indoor_temp_max_c": float(temp.max()),
        "indoor_rh_mean_percent": float(rh.mean()),
        "indoor_rh_min_percent": float(rh.min()),
        "indoor_rh_max_percent": float(rh.max()),
        "temp_violation_hours": float(((temp < lim["temp_min_c"] - 1e-9) | (temp > lim["temp_max_c"] + 1e-9)).sum() * dt_h),
        "rh_violation_hours": float(((rh < lim["rh_min_percent"] - 1e-9) | (rh > lim["rh_max_percent"] + 1e-9)).sum() * dt_h),
        # light
        "dli_mean_mol_m2_day": lighting.light_integral_mol_m2(ts["ppfd_umol_m2_s"].to_numpy(), dt) / grid.duration_days,
        "cumulative_light_mol_m2": lighting.light_integral_mol_m2(ts["ppfd_umol_m2_s"].to_numpy(), dt),
        # water
        "transpiration_kg": float(ts["transpiration_kg_s"].sum() * dt),
        "moisture_removed_kg": float(ts["moisture_removed_kg_s"].sum() * dt),
        "condensation_kg": float(ts["condensation_kg_s"].sum() * dt),
        # crop
        "n_plants": derived["n_plants"],
        "crop": crop_out,
        "yield_fresh_kg_per_m2_growing_area": (crop_out["total_fresh_mass_kg"] / derived["growing_area_m2"]),
        "target_fresh_mass_reached": crop_out["fresh_mass_per_plant_g"] >= crop["target_fresh_mass_g"],
    }
    summary["energy_intensity_kwh_per_kg"] = {
        key: energy_analysis.energy_intensity(energy[key], harvest_kg)
        for key in ("total", "lighting", "hvac")}
    summary["energy_intensity_kwh_per_kg"]["auxiliary_loads"] = energy_analysis.energy_intensity(
        energy["fans"] + energy["pumps"] + energy["auxiliary"], harvest_kg)
    summary["cost"] = {
        "price_per_kwh": price,
        "total": energy_analysis.cost(energy["total"], price),
        "lighting": energy_analysis.cost(energy["lighting"], price),
        "hvac": energy_analysis.cost(energy["hvac"], price),
        "per_day": energy_analysis.cost(energy["total"], price) / grid.duration_days,
        "per_kg": energy_analysis.energy_intensity(energy_analysis.cost(energy["total"], price), harvest_kg),
    }
    return summary


def build_warnings(summary: dict[str, Any], mode: str) -> list[str]:
    """Plain-language flags about the run."""
    notes = []
    if mode == "ideal":
        notes.append("Ideal control: cooling capacity is unlimited and the setpoint is held exactly. "
                     "This is an idealised reference, not achievable equipment behaviour.")
    if summary["cooling_unmet_hours"] > 0:
        notes.append(f"Cooling was undersized for {summary['cooling_unmet_hours']:.1f} h "
                     f"({summary['cooling_unmet_kwh_th']:.0f} kWh thermal unmet); the room left its setpoints.")
    if summary["indoor_temp_max_c"] > 45.0 or summary["indoor_temp_min_c"] < 0.0:
        notes.append(f"Indoor temperature reached {summary['indoor_temp_min_c']:.0f} to "
                     f"{summary['indoor_temp_max_c']:.0f} C, outside the 0 to 45 C validity range of the "
                     "humidity and crop equations. Treat this run as 'the room fails', not as a prediction.")
    if summary["condensation_kg"] > 0.01:
        notes.append(f"Room air reached saturation: {summary['condensation_kg']:.1f} kg of water condensed on "
                     "surfaces. The heat released by that condensation is not modelled.")
    if not summary["crop"]["marketable_fresh_mass_kg"] > 0:
        notes.append("No harvested biomass: energy and cost per kg are undefined.")
    return notes
