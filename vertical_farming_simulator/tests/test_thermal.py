"""Model 2: thermal balance, verified against analytical solutions."""

import math

import numpy as np
import pytest

from config.parameters import with_overrides
from models import thermal
from models.numerics import linear_step
from simulation.engine import run_simulation

# A "dry box": no crop water, no HVAC, constant weather. Reduces the model to
# C dT/dt = Q + K (T_out - T), which has a closed-form solution.
DRY_BOX = {
    "crop": {"transpiration_enabled": False},
    "environment": {"weather_mode": "constant", "outdoor_temp_c": 20.0, "outdoor_rh_percent": 50.0},
    "hvac": {"control_mode": "capacity_limited", "cooling_capacity_kw": 0.0, "heating_enabled": False,
             "dehumidification_enabled": False},
    "simulation": {"initial_temp_c": 20.0, "initial_rh_percent": 50.0, "duration_days": 5.0,
                   "time_step_min": 5.0},
}
NO_INTERNAL_HEAT = {
    "lighting": {"input_mode": "ppfd", "ppfd_umol_m2_s": 0.0},
    "equipment": {"circulation_fan_power_w": 0.0, "pump_power_w": 0.0, "auxiliary_power_w": 0.0,
                  "ventilation_fan_sfp_w_per_m3s": 0.0},
}


def test_no_temperature_difference_no_envelope_heat():
    assert thermal.envelope_heat_gain(64.0, 22.0, 22.0) == 0.0
    assert thermal.ventilation_heat_gain(0.05, 22.0, 22.0) == 0.0


def test_room_stays_at_outdoor_temperature_without_heat_sources(config):
    result = run_simulation(with_overrides(config, {**DRY_BOX, **NO_INTERNAL_HEAT}))
    assert np.allclose(result.timeseries["indoor_temp_c"], 20.0, atol=1e-9)
    assert np.allclose(result.timeseries["heat_envelope_w"], 0.0, atol=1e-6)


def test_hotter_outdoors_increases_envelope_gain():
    assert thermal.envelope_heat_gain(64.0, 35.0, 22.0) > thermal.envelope_heat_gain(64.0, 30.0, 22.0) > 0.0


def test_ach_flow_conversion_round_trip():
    flow = thermal.ventilation_flow_m3_s(0.5, 300.0)
    assert flow == pytest.approx(0.5 * 300.0 / 3600.0)
    assert thermal.ach_from_flow(flow, 300.0) == pytest.approx(0.5)


def test_linear_step_matches_analytical_solution():
    x, a, k, dt = 3.0, 0.4, 0.05, 7.0
    x_next, x_mean = linear_step(x, a, k, dt)
    assert x_next == pytest.approx(a / k + (x - a / k) * math.exp(-k * dt), rel=1e-12)
    assert (x_next - x) / dt == pytest.approx(a - k * x_mean, rel=1e-12)
    assert linear_step(x, a, 0.0, dt)[0] == pytest.approx(x + a * dt)


def test_step_response_matches_analytical_solution(config):
    """Constant internal heat in a dry box: T(t) = T_ss + (T0 - T_ss) exp(-t/tau)."""
    cfg = with_overrides(config, {**DRY_BOX, **NO_INTERNAL_HEAT,
                                  "equipment": {**NO_INTERNAL_HEAT["equipment"], "auxiliary_power_w": 1000.0}})
    result = run_simulation(cfg)
    d = result.derived
    t_ss = thermal.steady_state_temperature(1000.0, d["total_conductance_w_k"], 20.0)
    tau_s = d["thermal_capacitance_j_k"] / d["total_conductance_w_k"]
    t_s = result.timeseries["time_h"].to_numpy() * 3600.0
    exact = t_ss + (20.0 - t_ss) * np.exp(-t_s / tau_s)
    assert np.allclose(result.timeseries["indoor_temp_c"], exact, atol=1e-9)


def test_approaches_expected_steady_state(config):
    cfg = with_overrides(config, {**DRY_BOX, **NO_INTERNAL_HEAT,
                                  "equipment": {**NO_INTERNAL_HEAT["equipment"], "auxiliary_power_w": 1000.0},
                                  "simulation": {**DRY_BOX["simulation"], "duration_days": 30.0}})
    result = run_simulation(cfg)
    expected = 20.0 + 1000.0 / result.derived["total_conductance_w_k"]
    assert result.final_state["indoor_temp_c"] == pytest.approx(expected, abs=1e-3)


def test_lighting_heat_raises_indoor_temperature(config):
    dark = run_simulation(with_overrides(config, {**DRY_BOX, **NO_INTERNAL_HEAT}))
    lit = run_simulation(with_overrides(config, {**DRY_BOX, "lighting": {"input_mode": "ppfd",
                                                                          "ppfd_umol_m2_s": 50.0}}))
    assert lit.summary["indoor_temp_max_c"] > dark.summary["indoor_temp_max_c"] + 1.0
    # temperature rises while the lights are on and falls back when they are off
    day2 = lit.timeseries[lit.timeseries["day"] == 2]
    lights_on = day2[day2["led_schedule_fraction"] == 1.0]["indoor_temp_c"]
    assert lights_on.iloc[-1] > lights_on.iloc[0]


def test_energy_balance_closes_every_step(baseline_result):
    """C dT/dt = sum of the stored heat flows, step by step (first law)."""
    ts, r = baseline_result.timeseries, baseline_result
    dt = r.summary["time_step_s"]
    temps = np.append(ts["indoor_temp_c"].to_numpy(), r.final_state["indoor_temp_c"])
    stored = r.derived["thermal_capacitance_j_k"] * np.diff(temps) / dt
    flows = (ts["heat_internal_w"] + ts["heat_envelope_w"] + ts["heat_ventilation_w"]
             - ts["heat_transpiration_w"] - ts["cooling_sensible_w"] + ts["heating_w"])
    assert np.allclose(stored, flows, atol=1e-5 * ts["heat_internal_w"].max())


def test_thermal_mass_does_not_change_steady_state_load(config):
    """Over whole days at a held setpoint, cooling energy is independent of C_eff."""
    base = {**DRY_BOX, "hvac": {**DRY_BOX["hvac"], "control_mode": "ideal"},
            "simulation": {**DRY_BOX["simulation"], "initial_temp_c": 22.0}}
    light = run_simulation(with_overrides(config, {**base, "envelope": {"thermal_mass_multiplier": 2.0}}))
    heavy = run_simulation(with_overrides(config, {**base, "envelope": {"thermal_mass_multiplier": 30.0}}))
    assert light.summary["cooling_thermal_kwh_th"] == pytest.approx(heavy.summary["cooling_thermal_kwh_th"],
                                                                    rel=0.02)
