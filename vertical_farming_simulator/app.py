"""Vertical Farming Energy Simulator - Streamlit interface.

    streamlit run app.py

The interface only edits a scenario (a nested dict) and displays results.
All physics is in ``models/`` and ``simulation/`` and runs without it.
"""

from __future__ import annotations

import copy
import json
import math
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from analysis import scenario_comparison as sc
from config.parameters import default_config, derive_geometry, validate_config
from models import lighting as lighting_model
from models import weather as weather_model
from simulation.engine import run_simulation
from visualization import plots

st.set_page_config(page_title="Vertical Farming Energy Simulator", layout="wide")

PAGES = ["1. Farm configuration", "2. Environmental conditions", "3. Lighting system", "4. HVAC system",
         "5. Crop growth", "6. Simulation results", "7. Scenario comparison", "8. Optimization", "Model notes"]
DOCS = Path(__file__).parent / "docs"

if "config" not in st.session_state:
    st.session_state.config = default_config()
    st.session_state.result = None
    st.session_state.result_key = None
    st.session_state.compare = {}
cfg = st.session_state.config


def num(section: dict, key: str, label: str, **kwargs) -> None:
    """Number input bound to one configuration value."""
    value = section[key]
    if isinstance(value, int) and not isinstance(value, bool) and kwargs.get("step") in (None, 1):
        section[key] = int(st.number_input(label, value=int(value), step=1, **{k: v for k, v in kwargs.items() if k != "step"}))
    else:
        section[key] = float(st.number_input(label, value=float(value), **kwargs))


def config_key(config: dict) -> str:
    return json.dumps(config, sort_keys=True)


def run_current() -> None:
    try:
        validate_config(cfg)
        with st.spinner("Running simulation..."):
            st.session_state.result = run_simulation(cfg)
        st.session_state.result_key = config_key(cfg)
    except (ValueError, OSError) as error:
        st.session_state.result = None
        st.error(str(error))


def current_result():
    """The result for the current inputs, or None with a prompt to run."""
    result = st.session_state.result
    if result is None:
        st.info("No results yet. Press **Run simulation** in the sidebar.")
        return None
    if st.session_state.result_key != config_key(cfg):
        st.warning("Inputs have changed since the last run. The results below are for the previous inputs; "
                   "press **Run simulation** to update them.")
    for note in result.warnings:
        st.warning(note)
    return result


# ---------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("Vertical Farming Energy Simulator")
    st.caption("Conceptual physics-based model of an indoor lettuce farm. Not calibrated against a real farm.")
    page = st.radio("Page", PAGES, label_visibility="collapsed")
    cfg["scenario_name"] = st.text_input("Scenario name", cfg["scenario_name"])
    if st.button("Run simulation", type="primary", width="stretch"):
        run_current()
    with st.expander("Load / save scenario"):
        examples = sc.example_scenarios()
        pick = st.selectbox("Example scenario", list(examples))
        if st.button("Load example", width="stretch"):
            st.session_state.config = examples[pick]
            st.rerun()
        saved = sc.list_scenarios()
        if saved:
            chosen = st.selectbox("Saved scenario", saved, format_func=lambda p: p.stem)
            if st.button("Load saved", width="stretch"):
                st.session_state.config = sc.load_scenario(chosen)
                st.rerun()
        upload = st.file_uploader("Import scenario JSON", type="json")
        if upload is not None and st.button("Load imported", width="stretch"):
            try:
                imported = json.load(upload)
                validate_config(imported)
                st.session_state.config = imported
                st.rerun()
            except (ValueError, KeyError, TypeError) as error:
                st.error(f"Could not load scenario: {error}")
        if st.button("Save current scenario", width="stretch"):
            st.success(f"Saved to {sc.save_scenario(cfg).name}")
        st.download_button("Export scenario JSON", json.dumps(cfg, indent=2),
                           file_name=f"{cfg['scenario_name']}.json", mime="application/json",
                           width="stretch")
        if st.button("Reset to baseline", width="stretch"):
            st.session_state.config = default_config()
            st.rerun()

geo = derive_geometry(cfg)
lit = lighting_model.derive_lighting(cfg["lighting"], geo["growing_area_m2"])

# ---------------------------------------------------------------------------- pages
if page == PAGES[0]:
    st.header("Farm configuration")
    left, right = st.columns([1, 1.3])
    with left:
        st.subheader("Geometry")
        num(cfg["farm"], "footprint_area_m2", "Cultivation footprint [m²]", min_value=1.0, step=10.0)
        num(cfg["farm"], "room_height_m", "Room height [m]", min_value=1.0, step=0.5)
        num(cfg["farm"], "n_layers", "Number of growing layers", min_value=1, max_value=20, step=1)
        st.subheader("Crop occupancy")
        st.text_input("Crop type", cfg["crop"]["crop_type"], disabled=True,
                      help="Only lettuce is parameterised in this version.")
        num(cfg["crop"], "plant_density_per_m2", "Plant density [plants per m² growing area]", min_value=0.0, step=1.0)
        num(cfg["crop"], "occupied_fraction", "Fraction of growing area planted [-]", min_value=0.0, max_value=1.0,
            step=0.05, help="1.0 = every layer fully planted for the whole cycle (single batch). "
                            "Staggered planting is not modelled yet.")
        st.subheader("Simulation")
        num(cfg["simulation"], "duration_days", "Duration [days]", min_value=1.0, max_value=120.0, step=1.0)
        cfg["simulation"]["time_step_min"] = float(st.select_slider(
            "Time step [min]", options=[1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0],
            value=float(cfg["simulation"]["time_step_min"]) if cfg["simulation"]["time_step_min"] in
            (1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0) else 5.0))
        num(cfg["economics"], "electricity_price_per_kwh", "Electricity price [currency/kWh]", min_value=0.0, step=0.01)
    geo = derive_geometry(cfg)
    with right:
        st.subheader("Derived quantities")
        a, b, c = st.columns(3)
        a.metric("Room volume", f"{geo['room_volume_m3']:.0f} m³")
        b.metric("Growing area", f"{geo['growing_area_m2']:.0f} m²")
        c.metric("Plants", f"{geo['n_plants']:,.0f}")
        st.caption("Room volume = footprint × height and is **not** multiplied by the number of layers. "
                   "HVAC loads follow the room (volume, envelope, air flow); lighting and crop production "
                   "follow the growing area (footprint × layers).")
        st.plotly_chart(plots.farm_schematic(geo["n_layers"], geo["footprint_area_m2"],
                                             cfg["farm"]["room_height_m"]), width="stretch")
        st.caption("Conceptual side view, not to scale.")

elif page == PAGES[1]:
    st.header("Environmental conditions")
    env, envl = cfg["environment"], cfg["envelope"]
    left, right = st.columns(2)
    with left:
        st.subheader("Outdoor weather")
        labels = {"constant": "Constant", "daily_profile": "Synthetic daily profile", "csv": "Imported CSV"}
        env["weather_mode"] = st.radio("Weather input", list(labels), format_func=labels.get,
                                       index=list(labels).index(env["weather_mode"]), horizontal=True)
        if env["weather_mode"] != "csv":
            mean = " (daily mean)" if env["weather_mode"] == "daily_profile" else ""
            num(env, "outdoor_temp_c", f"Outdoor temperature{mean} [°C]", min_value=-40.0, max_value=50.0, step=1.0)
            num(env, "outdoor_rh_percent", f"Outdoor relative humidity{mean} [%]", min_value=1.0, max_value=100.0, step=5.0)
        if env["weather_mode"] == "daily_profile":
            num(env, "outdoor_temp_amplitude_k", "Temperature amplitude, ± [K]", min_value=0.0, max_value=20.0, step=1.0)
            num(env, "outdoor_temp_peak_hour", "Hour of peak temperature [h]", min_value=0.0, max_value=23.9, step=1.0)
            num(env, "outdoor_rh_amplitude_percent", "Humidity amplitude, ± [% RH]", min_value=0.0, max_value=40.0, step=5.0,
                help="Humidity is lowest when temperature peaks.")
        if env["weather_mode"] == "csv":
            st.markdown("Columns required: `timestamp`, `outdoor_temperature`, `outdoor_relative_humidity` (in %). "
                        "An example is in `data/weather/example_weather.csv`.")
            env["csv_temperature_unit"] = st.radio("Temperature unit in the file (must be stated, never guessed)",
                                                   ["C", "F"], index=["C", "F"].index(env["csv_temperature_unit"]),
                                                   horizontal=True)
            uploaded = st.file_uploader("Weather CSV", type="csv")
            if uploaded is not None:
                target = Path(tempfile.gettempdir()) / f"vfs_weather_{uploaded.name}"
                target.write_bytes(uploaded.getvalue())
                env["weather_csv_path"] = str(target)
            env["weather_csv_path"] = st.text_input("CSV path", env["weather_csv_path"] or "") or None
        st.subheader("Initial indoor state")
        num(cfg["simulation"], "initial_temp_c", "Initial indoor temperature [°C]", step=1.0)
        num(cfg["simulation"], "initial_rh_percent", "Initial indoor relative humidity [%]", min_value=1.0, max_value=100.0, step=5.0)
    with right:
        st.subheader("Envelope and air exchange")
        num(envl, "u_wall_w_m2k", "Wall U-value [W/m²/K]", min_value=0.0, step=0.05)
        num(envl, "u_roof_w_m2k", "Roof U-value [W/m²/K]", min_value=0.0, step=0.05)
        num(envl, "u_floor_w_m2k", "Floor U-value [W/m²/K]", min_value=0.0, step=0.05,
            help="0 = adiabatic floor. A non-zero value couples the floor to outdoor AIR temperature, "
                 "which is a simplification of ground coupling.")
        num(envl, "air_changes_per_hour", "Outdoor air exchange [air changes per hour]", min_value=0.0, step=0.1)
        num(envl, "thermal_mass_multiplier", "Thermal mass multiplier [× heat capacity of room air]", min_value=1.0, step=1.0,
            help="Lumps racks, water, plants and surfaces with the air into one effective capacitance.")
        geo = derive_geometry(cfg)
        flow = envl["air_changes_per_hour"] * geo["room_volume_m3"] / 3600.0
        st.caption(f"Envelope areas (square footprint assumed): walls {geo['wall_area_m2']:.0f} m², roof "
                   f"{geo['roof_area_m2']:.0f} m², floor {geo['floor_area_m2']:.0f} m². Effective UA = "
                   f"{geo['envelope_ua_w_k']:.0f} W/K. Outdoor air flow = {flow * 1000:.1f} L/s "
                   f"({flow * 3600:.0f} m³/h).")
    try:
        import numpy as np
        hours = np.arange(0, 72.01, 0.25)
        temp, rh, notes = weather_model.build_weather(env, hours * 3600.0)
        for note in notes:
            st.warning(note)
        preview = pd.DataFrame({"Outdoor temperature [°C]": temp, "Outdoor relative humidity [%]": rh}, index=hours)
        preview.index.name = "Time [h]"
        st.subheader("Outdoor profile, first 3 days")
        a, b = st.columns(2)
        a.line_chart(preview[["Outdoor temperature [°C]"]], height=220, color=plots.COLORS["outdoor"])
        b.line_chart(preview[["Outdoor relative humidity [%]"]], height=220, color=plots.COLORS["outdoor"])
    except (ValueError, OSError, TypeError) as error:
        st.error(f"Weather input problem: {error}")

elif page == PAGES[2]:
    st.header("Lighting system")
    light = cfg["lighting"]
    left, right = st.columns(2)
    with left:
        st.subheader("Intensity and power")
        labels = {"ppfd": "PPFD on the crop", "power_density": "LED power density", "installed_power": "Installed LED power"}
        light["input_mode"] = st.radio("Which quantity do you specify?", list(labels), format_func=labels.get,
                                       index=list(labels).index(light["input_mode"]),
                                       help="The other two are calculated, so the three can never disagree.")
        light["ppfd_umol_m2_s"] = lit["ppfd_full_umol_m2_s"]
        light["power_density_w_m2"] = lit["power_density_w_m2"]
        light["installed_power_w"] = lit["installed_power_w"]
        if light["input_mode"] == "ppfd":
            num(light, "ppfd_umol_m2_s", "PPFD at full power [µmol/m²/s]", min_value=0.0, step=10.0)
        elif light["input_mode"] == "power_density":
            num(light, "power_density_w_m2", "LED electrical power density [W per m² growing area]", min_value=0.0, step=5.0)
        else:
            num(light, "installed_power_w", "Installed LED electrical power [W]", min_value=0.0, step=500.0)
        num(light, "photon_efficacy_umol_j", "LED photon efficacy [µmol/J]", min_value=0.5, max_value=4.5, step=0.1)
        num(light, "utilisation_factor", "Utilisation factor [-]", min_value=0.05, max_value=1.0, step=0.05,
            help="Fraction of emitted photons that reaches the growing area (uniform-light assumption).")
        num(light, "heat_fraction_to_room", "Fraction of LED electricity released as heat in the room [-]",
            min_value=0.0, max_value=1.0, step=0.01,
            help="Light absorbed by leaves and surfaces also becomes heat, so in a closed room this is close "
                 "to 1. Lower it for water-cooled fixtures or remote drivers.")
    with right:
        st.subheader("Schedule (repeats daily)")
        presets = {"18 h on / 6 h off": 18.0, "16 h on / 8 h off": 16.0, "12 h on / 12 h off": 12.0}
        kinds = list(presets) + ["Other photoperiod", "Custom hourly schedule"]
        if light["schedule_type"] == "custom":
            default = kinds[-1]
        else:
            default = next((k for k, v in presets.items() if v == light["photoperiod_h"]), "Other photoperiod")
        kind = st.selectbox("Schedule", kinds, index=kinds.index(default))
        light["schedule_type"] = "custom" if kind == kinds[-1] else "photoperiod"
        if kind in presets:
            light["photoperiod_h"] = presets[kind]
        elif kind == "Other photoperiod":
            num(light, "photoperiod_h", "Photoperiod [h/day]", min_value=0.0, max_value=24.0, step=0.5)
        if light["schedule_type"] == "photoperiod":
            num(light, "start_hour", "Lights-on time [hour of day]", min_value=0.0, max_value=23.99, step=0.5)
            end = (light["start_hour"] + light["photoperiod_h"]) % 24
            st.caption(f"Lights on {light['start_hour']:05.2f} h to {end:05.2f} h (decimal hours).")
        else:
            table = st.data_editor(pd.DataFrame({"Hour": range(24), "Fraction of full power": light["custom_hourly_fractions"]}),
                                   hide_index=True, height=240, disabled=["Hour"])
            light["custom_hourly_fractions"] = [float(min(1.0, max(0.0, v))) for v in table["Fraction of full power"]]
        num(light, "dimming_level", "Dimming level [fraction of full power]", min_value=0.0, max_value=1.0, step=0.05)
    lit = lighting_model.derive_lighting(light, geo["growing_area_m2"])
    import numpy as np
    u, _ = lighting_model.schedule_fractions(light, np.arange(1440) * 60.0, 60.0)
    dli = lit["ppfd_full_umol_m2_s"] * u.sum() * 60.0 / 1e6
    st.subheader("Derived quantities")
    a, b, c, d, e = st.columns(5)
    a.metric("Installed LED power", f"{lit['installed_power_w'] / 1000:.1f} kW")
    b.metric("Power density", f"{lit['power_density_w_m2']:.0f} W/m²")
    c.metric("PPFD when on", f"{lit['ppfd_full_umol_m2_s'] * light['dimming_level']:.0f} µmol/m²/s")
    d.metric("Daily light integral", f"{dli:.1f} mol/m²/day")
    e.metric("Lighting energy", f"{lit['installed_power_w'] * u.sum() / 60 / 1000:.0f} kWh/day")
    st.caption("PPFD = power density × photon efficacy × utilisation factor. There is no universal conversion "
               "between PPFD and electrical power: it depends on the two fixture parameters above.")

elif page == PAGES[3]:
    st.header("HVAC system")
    hv, eq = cfg["hvac"], cfg["equipment"]
    left, right = st.columns(2)
    with left:
        st.subheader("Cooling")
        labels = {"ideal": "Ideal control (unlimited capacity, idealised)",
                  "capacity_limited": "Capacity-limited cooling", "thermostat": "On/off thermostat"}
        hv["control_mode"] = st.radio("Operating mode", list(labels), format_func=labels.get,
                                      index=list(labels).index(hv["control_mode"]))
        if hv["control_mode"] == "ideal":
            st.caption("Idealised reference: the setpoint is held exactly whatever the load. Real equipment cannot do this.")
        if hv["control_mode"] == "thermostat":
            num(hv, "thermostat_deadband_k", "Thermostat deadband [K]", min_value=0.1, step=0.1)
            st.caption("On/off cycles are only resolved with a time step of about 1 minute. With longer steps "
                       "the result is the cycle average.")
        num(hv, "temp_setpoint_c", "Cooling temperature setpoint [°C]", min_value=5.0, max_value=40.0, step=0.5)
        num(hv, "cooling_capacity_kw", "Cooling capacity, sensible + latent [kW thermal]", min_value=0.0, step=5.0,
            disabled=hv["control_mode"] == "ideal")
        num(hv, "cooling_cop", "Cooling COP [kW thermal per kW electrical]", min_value=0.5, max_value=10.0, step=0.1)
        st.subheader("Dehumidification")
        hv["dehumidification_enabled"] = st.checkbox("Dehumidify at the cooling coil", hv["dehumidification_enabled"])
        num(hv, "rh_setpoint_percent", "Maximum relative humidity setpoint [%]", min_value=20.0, max_value=100.0, step=5.0)
        num(hv, "max_moisture_removal_kg_h", "Moisture removal capacity [kg water/h]", min_value=0.0, step=5.0)
        st.caption("Removed moisture is a latent cooling load (mass × latent heat) on the same coil and at the "
                   "same COP. There is no reheat and no humidification in this version.")
    with right:
        st.subheader("Heating")
        hv["heating_enabled"] = st.checkbox("Heating enabled", hv["heating_enabled"])
        num(hv, "heating_setpoint_c", "Heating setpoint [°C]", step=0.5)
        num(hv, "heating_capacity_kw", "Heating capacity [kW thermal]", min_value=0.0, step=1.0)
        num(hv, "heating_cop", "Heating COP [-] (1 = electric resistance)", min_value=0.5, max_value=8.0, step=0.1)
        st.subheader("Fans, pumps and other loads")
        num(eq, "circulation_fan_power_w", "Air circulation fans [W electrical]", min_value=0.0, step=100.0)
        num(eq, "circulation_fan_heat_fraction", "Fan heat released in room [-]", min_value=0.0, max_value=1.0, step=0.1)
        num(eq, "ventilation_fan_sfp_w_per_m3s", "Ventilation specific fan power [W per m³/s]", min_value=0.0, step=100.0)
        num(eq, "pump_power_w", "Water pumps [W electrical]", min_value=0.0, step=100.0)
        num(eq, "pump_heat_fraction", "Pump heat released in room [-]", min_value=0.0, max_value=1.0, step=0.1)
        num(eq, "auxiliary_power_w", "Other equipment [W electrical]", min_value=0.0, step=100.0)
        num(eq, "auxiliary_heat_fraction", "Other equipment heat released in room [-]", min_value=0.0, max_value=1.0, step=0.1)
    st.subheader("Acceptable indoor range (used to count violations, not for control)")
    a, b, c, d = st.columns(4)
    with a: num(cfg["limits"], "temp_min_c", "Min temperature [°C]", step=1.0)
    with b: num(cfg["limits"], "temp_max_c", "Max temperature [°C]", step=1.0)
    with c: num(cfg["limits"], "rh_min_percent", "Min RH [%]", step=5.0)
    with d: num(cfg["limits"], "rh_max_percent", "Max RH [%]", step=5.0)

elif page == PAGES[4]:
    st.header("Crop growth")
    crop = cfg["crop"]
    with st.expander("Crop growth parameters", expanded=st.session_state.result is None):
        a, b, c = st.columns(3)
        with a:
            st.markdown("**Logistic growth**")
            num(crop, "initial_dry_mass_g", "Initial dry mass B₀ [g/plant]", min_value=0.0, step=0.01, format="%.3f")
            num(crop, "max_dry_mass_g", "Maximum dry mass K [g/plant]", min_value=0.1, step=0.5)
            num(crop, "base_growth_rate_per_day", "Base growth rate r [1/day]", min_value=0.0, step=0.05,
                help="Relative growth rate while lit, at saturating light and optimum temperature.")
            num(crop, "target_fresh_mass_g", "Target harvest fresh mass [g/plant]", min_value=0.0, step=10.0)
        with b:
            st.markdown("**Environmental modifiers**")
            crop["use_temperature_modifier"] = st.checkbox("Temperature modifier f_T", crop["use_temperature_modifier"])
            num(crop, "temp_min_c", "T_min [°C]", step=1.0)
            num(crop, "temp_opt_c", "T_opt [°C]", step=1.0)
            num(crop, "temp_max_c", "T_max [°C]", step=1.0)
            crop["use_light_modifier"] = st.checkbox("Light modifier f_L", crop["use_light_modifier"])
            num(crop, "light_half_saturation_ppfd", "Half-saturation K_L [µmol/m²/s]", min_value=1.0, step=10.0)
            st.caption("f_CO₂ and f_VPD are fixed at 1 (not modelled yet).")
        with c:
            st.markdown("**Mass conversion and transpiration**")
            num(crop, "dry_matter_fraction", "Dry matter fraction [g dry / g fresh]", min_value=0.01, max_value=1.0, step=0.005, format="%.3f")
            num(crop, "marketable_fraction", "Marketable fraction of fresh mass [-]", min_value=0.0, max_value=1.0, step=0.05)
            crop["transpiration_enabled"] = st.checkbox("Crop transpiration", crop["transpiration_enabled"])
            num(crop, "max_leaf_area_index", "Leaf area index at B = K [-]", min_value=0.0, step=0.5)
            num(crop, "transpiration_light_coeff", "Light coefficient a [-]", min_value=0.0, step=0.05)
            num(crop, "transpiration_vpd_coeff_w_m2_pa", "VPD coefficient b [W/m²/Pa]", min_value=0.0, step=0.002, format="%.3f")
            num(crop, "dark_transpiration_factor", "Dark factor [-]", min_value=0.0, max_value=1.0, step=0.1)
    result = current_result()
    if result:
        s, c = result.summary, result.summary["crop"]
        cols = st.columns(5)
        cols[0].metric("Dry mass per plant", f"{c['dry_mass_per_plant_g']:.1f} g")
        cols[1].metric("Fresh mass per plant", f"{c['fresh_mass_per_plant_g']:.0f} g")
        cols[2].metric("Total fresh biomass", f"{c['total_fresh_mass_kg']:,.0f} kg")
        cols[3].metric("Marketable harvest", f"{c['marketable_fresh_mass_kg']:,.0f} kg")
        cols[4].metric("Fresh yield", f"{s['yield_fresh_kg_per_m2_growing_area']:.1f} kg/m²")
        st.caption(f"Total dry biomass {c['total_dry_mass_kg']:.0f} kg. Fresh = dry ÷ dry matter fraction; "
                   f"marketable = fresh × marketable fraction. Target fresh mass "
                   f"{'reached' if s['target_fresh_mass_reached'] else 'not reached'}.")
        a, b = st.columns(2)
        a.plotly_chart(plots.biomass(result), width="stretch")
        b.plotly_chart(plots.daily_growth(result.daily()), width="stretch")
        ts = result.timeseries
        st.caption(f"Conditions seen by the crop: temperature {s['indoor_temp_min_c']:.1f} to {s['indoor_temp_max_c']:.1f} °C "
                   f"(mean {s['indoor_temp_mean_c']:.1f}), relative humidity mean {s['indoor_rh_mean_percent']:.0f} %, "
                   f"DLI {s['dli_mean_mol_m2_day']:.1f} mol/m²/day, mean effective growth rate "
                   f"{ts['growth_rate_per_day'].mean():.3f} per day.")
    st.info("**Limitations.** This is a logistic curve scaled by temperature and light. It is useful for comparing "
            "scenarios, not for predicting the yield of a real farm. It does not account for cultivar differences, "
            "nutrient availability, root-zone conditions, plant spacing, disease, crop stress, detailed "
            "photosynthesis, canopy development or CO₂, and it has not been calibrated against experiments.")

elif page == PAGES[5]:
    st.header("Simulation results")
    result = current_result()
    if result:
        s, e = result.summary, result.summary["energy_kwh"]
        intensity = s["energy_intensity_kwh_per_kg"]["total"]
        cols = st.columns(5)
        cols[0].metric("Total electricity", f"{e['total']:,.0f} kWh")
        cols[1].metric("Per day", f"{s['energy_per_day_kwh']:,.0f} kWh")
        cols[2].metric("Marketable harvest", f"{s['crop']['marketable_fresh_mass_kg']:,.0f} kg")
        cols[3].metric("Energy intensity", "undefined" if math.isnan(intensity) else f"{intensity:.1f} kWh/kg")
        cols[4].metric("Electricity cost", f"{s['cost']['total']:,.0f}")
        if math.isnan(intensity):
            st.warning("Harvested biomass is zero, so energy and cost per kilogram are undefined.")
        left, right = st.columns([1.7, 1])
        with left:
            stats, price = s["power_stats_w"], s["cost"]["price_per_kwh"]
            rows = [("LED lighting", "lighting"), ("HVAC cooling", "hvac_cooling"), ("HVAC heating", "hvac_heating"),
                    ("Air circulation fans", "circulation_fans"), ("Ventilation fans", "ventilation_fans"),
                    ("Water pumps", "pumps"), ("Other equipment", "auxiliary"), ("Total", "total")]
            st.dataframe(pd.DataFrame({
                "Component": [r[0] for r in rows],
                "Energy [kWh]": [e[r[1]] for r in rows],
                "Share [%]": [100 * e[r[1]] / e["total"] if e["total"] else float("nan") for r in rows],
                "Average power [kW]": [stats[r[1]]["average_w"] / 1000 for r in rows],
                "Peak power [kW]": [stats[r[1]]["peak_w"] / 1000 for r in rows],
                "Cost": [e[r[1]] * price for r in rows],
            }).style.format({"Energy [kWh]": "{:,.0f}", "Share [%]": "{:.1f}", "Average power [kW]": "{:.2f}",
                             "Peak power [kW]": "{:.2f}", "Cost": "{:,.0f}"}), hide_index=True, width="stretch")
            st.caption(f"Lighting + HVAC = {s['energy_shares_percent']['lighting'] + s['energy_shares_percent']['hvac']:.0f} % "
                       f"of electricity. Per kg of marketable lettuce: lighting "
                       f"{s['energy_intensity_kwh_per_kg']['lighting']:.1f}, HVAC {s['energy_intensity_kwh_per_kg']['hvac']:.1f}, "
                       f"other loads {s['energy_intensity_kwh_per_kg']['auxiliary_loads']:.1f} kWh/kg; cost "
                       f"{s['cost']['per_kg']:.2f} per kg, {s['cost']['per_day']:.0f} per day.")
        right.plotly_chart(plots.energy_breakdown(result), width="stretch")
        st.subheader("Cooling (thermal energy, reported separately from electricity)")
        cols = st.columns(5)
        cols[0].metric("Delivered [kWh thermal]", f"{s['cooling_thermal_kwh_th']:,.0f}")
        cols[1].metric("of which latent [kWh thermal]", f"{s['cooling_latent_kwh_th']:,.0f}")
        cols[2].metric("Peak delivered [kW thermal]", f"{s['cooling_delivered_peak_kw']:.1f}")
        cols[3].metric("Unmet [kWh thermal]", f"{s['cooling_unmet_kwh_th']:,.0f}")
        cols[4].metric("Cooling running [h]", f"{s['hvac_cooling_hours']:.0f}")
        st.caption(f"Peak cooling required to hold the setpoints: {s['cooling_required_peak_kw']:.1f} kW thermal. "
                   f"Average delivered: {s['cooling_delivered_mean_kw']:.1f} kW thermal. Crop transpiration "
                   f"{s['transpiration_kg']:,.0f} kg of water, of which {s['moisture_removed_kg']:,.0f} kg was "
                   "condensed by the dehumidifier.")
        days = st.slider("Days shown in time-series charts", 1.0, float(s["duration_days"]),
                         (0.0, float(s["duration_days"])), step=1.0) if s["duration_days"] > 1 else (0.0, 1.0)
        view = copy.copy(result)
        view.timeseries = result.timeseries[(result.timeseries["time_h"] >= days[0] * 24) &
                                            (result.timeseries["time_h"] < days[1] * 24)]
        a, b = st.columns(2)
        a.plotly_chart(plots.temperature(view), width="stretch")
        ratio = b.toggle("Show humidity ratio instead of relative humidity")
        b.plotly_chart(plots.humidity(view, ratio=ratio), width="stretch")
        a, b = st.columns(2)
        a.plotly_chart(plots.electrical_power(view), width="stretch")
        b.plotly_chart(plots.cooling(view), width="stretch")
        a, b = st.columns(2)
        a.plotly_chart(plots.lighting_schedule(result), width="stretch")
        b.plotly_chart(plots.biomass(result), width="stretch")
        a, b = st.columns(2)
        a.plotly_chart(plots.daily_energy(result.daily()), width="stretch")
        b.plotly_chart(plots.cumulative_energy(result), width="stretch")
        st.subheader("Export")
        a, b, c = st.columns(3)
        a.download_button("Time series (CSV)", result.to_csv(), file_name=f"{s['scenario_name']}_timeseries.csv", mime="text/csv")
        b.download_button("Scenario configuration (JSON)", result.config_json(), file_name=f"{s['scenario_name']}.json", mime="application/json")
        c.download_button("Daily summary (CSV)", result.daily().to_csv(index=False), file_name=f"{s['scenario_name']}_daily.csv", mime="text/csv")
        st.caption("These are outputs of a conceptual model with assumed parameters. They have not been validated "
                   "against a real farm; use them to compare scenarios.")

elif page == PAGES[6]:
    st.header("Scenario comparison")
    store: dict = st.session_state.compare
    a, b, c = st.columns(3)
    if a.button("Add current scenario", width="stretch"):
        try:
            validate_config(cfg)
            store[cfg["scenario_name"]] = run_simulation(cfg)
        except (ValueError, OSError) as error:
            st.error(str(error))
    if b.button("Add the six example scenarios (A to F)", width="stretch"):
        with st.spinner("Running six scenarios..."):
            for name, scenario in sc.example_scenarios().items():
                scenario["simulation"] = copy.deepcopy(cfg["simulation"])
                store[name] = run_simulation(scenario)
    if c.button("Clear comparison", width="stretch"):
        store.clear()
    st.caption("To build your own variant: edit the inputs, change the scenario name in the sidebar, then add it here. "
               "Example scenarios use the baseline inputs with the current simulation duration and time step.")
    if len(store) < 1:
        st.info("Add scenarios to compare them.")
    else:
        table = sc.comparison_table(store)
        st.dataframe(table.style.format("{:,.1f}"), width="stretch", height=600)
        if len(store) > 1:
            reference = st.selectbox("Reference scenario for differences", list(store))
            st.markdown("**Change relative to the reference [%]**")
            st.dataframe(sc.difference_table(table, reference).style.format("{:+.1f}", na_rep="n/a"),
                         width="stretch", height=600)
            a, b = st.columns(2)
            a.plotly_chart(plots.scenario_energy_stack(store), width="stretch")
            b.plotly_chart(plots.scenario_tradeoff(store), width="stretch")
            metric = st.selectbox("Metric", list(table.index), index=6)
            st.plotly_chart(plots.scenario_bars(table, metric), width="stretch")
        st.download_button("Comparison table (CSV)", table.to_csv(), file_name="scenario_comparison.csv", mime="text/csv")
        st.caption("No scenario is marked as best: which one is preferable depends on your objective (energy, yield, "
                   "cost) and on which temperature and humidity violations you accept.")

elif page == PAGES[7]:
    st.header("Optimization")
    st.info("Not implemented yet, on purpose. Optimization comes after the coupled simulation has been reviewed. "
            "The planned first version is a grid search over PPFD, photoperiod and temperature setpoint that "
            "minimises total electricity subject to a minimum harvest and temperature/humidity limits, with a "
            "Pareto plot of energy against harvest. Until then, the Scenario comparison page covers manual exploration.")

else:
    st.header("Model notes")
    tabs = st.tabs(["Equations", "Assumptions", "Verification and validation"])
    for tab, name in zip(tabs, ["model_equations.md", "assumptions.md", "validation.md"]):
        with tab:
            path = DOCS / name
            st.markdown(path.read_text(encoding="utf-8") if path.exists() else f"`docs/{name}` not found.")
