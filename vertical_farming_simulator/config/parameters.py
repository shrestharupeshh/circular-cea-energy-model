"""Parameter management: load, validate and derive quantities from a scenario.

A scenario is a plain nested dict (JSON-serialisable). Nothing in the models
reads a hard-coded parameter: every number comes from this dict or from
``models/constants.py``. ``docs/assumptions.md`` gives the rationale for each
default value.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).with_name("default_config.json")

CONTROL_MODES = ("ideal", "capacity_limited", "thermostat")
WEATHER_MODES = ("constant", "daily_profile", "csv")
LIGHTING_INPUT_MODES = ("ppfd", "power_density", "installed_power")
SCHEDULE_TYPES = ("photoperiod", "custom")


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Read a scenario JSON file (the baseline if ``path`` is None)."""
    with open(path or DEFAULT_CONFIG_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def save_config(config: dict[str, Any], path: str | Path) -> None:
    """Write a scenario to JSON."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)


def default_config() -> dict[str, Any]:
    """A fresh copy of the baseline scenario."""
    return load_config()


def with_overrides(config: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of ``config`` with nested ``overrides`` applied."""
    result = copy.deepcopy(config)

    def _merge(target: dict, source: dict) -> None:
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                _merge(target[key], value)
            else:
                target[key] = value

    _merge(result, overrides)
    return result


def _check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_config(config: dict[str, Any]) -> None:
    """Raise ValueError listing every physically invalid input."""
    e: list[str] = []
    farm, crop, light = config["farm"], config["crop"], config["lighting"]
    env, envl, hvac = config["environment"], config["envelope"], config["hvac"]
    eq, sim, lim = config["equipment"], config["simulation"], config["limits"]

    _check(farm["footprint_area_m2"] > 0, "Footprint area must be > 0.", e)
    _check(farm["room_height_m"] > 0, "Room height must be > 0.", e)
    _check(int(farm["n_layers"]) >= 1, "Number of layers must be >= 1.", e)

    _check(crop["plant_density_per_m2"] >= 0, "Plant density must be >= 0.", e)
    _check(0 <= crop["occupied_fraction"] <= 1, "Occupied fraction must be in [0, 1].", e)
    _check(crop["max_dry_mass_g"] > 0, "Maximum dry mass K must be > 0.", e)
    _check(0 <= crop["initial_dry_mass_g"] <= crop["max_dry_mass_g"],
           "Initial dry mass must be between 0 and the maximum dry mass K.", e)
    _check(crop["base_growth_rate_per_day"] >= 0, "Growth rate must be >= 0.", e)
    _check(crop["temp_min_c"] < crop["temp_opt_c"] < crop["temp_max_c"],
           "Crop temperatures must satisfy T_min < T_opt < T_max.", e)
    _check(crop["light_half_saturation_ppfd"] > 0, "Light half-saturation K_L must be > 0.", e)
    _check(0 < crop["dry_matter_fraction"] <= 1, "Dry matter fraction must be in (0, 1].", e)
    _check(0 <= crop["marketable_fraction"] <= 1, "Marketable fraction must be in [0, 1].", e)
    _check(0 <= crop["dark_transpiration_factor"] <= 1,
           "Dark transpiration factor must be in [0, 1].", e)
    for key in ("transpiration_light_coeff", "transpiration_vpd_coeff_w_m2_pa",
                "max_leaf_area_index", "light_extinction_coeff"):
        _check(crop[key] >= 0, f"crop.{key} must be >= 0.", e)

    _check(light["input_mode"] in LIGHTING_INPUT_MODES, "Unknown lighting input mode.", e)
    _check(light["photon_efficacy_umol_j"] > 0, "LED photon efficacy must be > 0.", e)
    _check(0 < light["utilisation_factor"] <= 1, "Utilisation factor must be in (0, 1].", e)
    _check(0 <= light["heat_fraction_to_room"] <= 1, "LED heat fraction must be in [0, 1].", e)
    _check(light["schedule_type"] in SCHEDULE_TYPES, "Unknown lighting schedule type.", e)
    _check(0 <= light["photoperiod_h"] <= 24, "Photoperiod must be in [0, 24] h.", e)
    _check(0 <= light["start_hour"] < 24, "Lighting start hour must be in [0, 24).", e)
    _check(0 <= light["dimming_level"] <= 1, "Dimming level must be in [0, 1].", e)
    fractions = light["custom_hourly_fractions"]
    _check(len(fractions) == 24 and all(0 <= f <= 1 for f in fractions),
           "Custom schedule needs 24 hourly fractions in [0, 1].", e)
    active = {"ppfd": "ppfd_umol_m2_s", "power_density": "power_density_w_m2",
              "installed_power": "installed_power_w"}.get(light["input_mode"])
    if active:
        _check(light[active] is not None and light[active] >= 0, f"lighting.{active} must be >= 0.", e)

    _check(env["weather_mode"] in WEATHER_MODES, "Unknown weather mode.", e)
    _check(-60 <= env["outdoor_temp_c"] <= 60, "Outdoor temperature must be in [-60, 60] C.", e)
    _check(env["outdoor_temp_amplitude_k"] >= 0, "Outdoor temperature amplitude must be >= 0.", e)
    _check(0 <= env["outdoor_rh_percent"] <= 100, "Outdoor RH must be in [0, 100] %.", e)
    _check(env["csv_temperature_unit"] in ("C", "F"), "CSV temperature unit must be 'C' or 'F'.", e)
    if env["weather_mode"] == "csv":
        _check(bool(env["weather_csv_path"]), "Weather mode 'csv' needs a weather_csv_path.", e)

    for key in ("u_wall_w_m2k", "u_roof_w_m2k", "u_floor_w_m2k", "air_changes_per_hour"):
        _check(envl[key] >= 0, f"envelope.{key} must be >= 0.", e)
    _check(envl["thermal_mass_multiplier"] >= 1, "Thermal mass multiplier must be >= 1.", e)

    _check(hvac["control_mode"] in CONTROL_MODES, "Unknown HVAC control mode.", e)
    _check(hvac["cooling_capacity_kw"] >= 0, "Cooling capacity must be >= 0.", e)
    _check(hvac["cooling_cop"] > 0, "Cooling COP must be > 0.", e)
    _check(hvac["heating_cop"] > 0, "Heating COP must be > 0.", e)
    _check(hvac["heating_capacity_kw"] >= 0, "Heating capacity must be >= 0.", e)
    _check(hvac["thermostat_deadband_k"] > 0, "Thermostat deadband must be > 0.", e)
    _check(0 < hvac["rh_setpoint_percent"] <= 100, "RH setpoint must be in (0, 100] %.", e)
    _check(hvac["max_moisture_removal_kg_h"] >= 0, "Moisture removal capacity must be >= 0.", e)
    if hvac["heating_enabled"]:
        _check(hvac["heating_setpoint_c"] < hvac["temp_setpoint_c"],
               "Heating setpoint must be below the cooling setpoint.", e)

    for key, value in eq.items():
        _check(value >= 0, f"equipment.{key} must be >= 0.", e)
        if key.endswith("heat_fraction"):
            _check(value <= 1, f"equipment.{key} must be <= 1.", e)

    _check(sim["duration_days"] > 0, "Simulation duration must be > 0.", e)
    _check(0 < sim["time_step_min"] <= 60, "Time step must be in (0, 60] minutes.", e)
    _check(0 < sim["initial_rh_percent"] <= 100, "Initial RH must be in (0, 100] %.", e)
    _check(config["economics"]["electricity_price_per_kwh"] >= 0, "Electricity price must be >= 0.", e)
    _check(lim["temp_min_c"] < lim["temp_max_c"], "Temperature limits must satisfy min < max.", e)
    _check(lim["rh_min_percent"] < lim["rh_max_percent"], "RH limits must satisfy min < max.", e)

    if e:
        raise ValueError("Invalid configuration:\n- " + "\n- ".join(e))


def derive_geometry(config: dict[str, Any]) -> dict[str, float]:
    """Geometry derived from the farm and envelope inputs.

    Room volume = footprint x height (NOT multiplied by the number of layers).
    Growing area = footprint x layers. Wall area defaults to that of a square
    footprint, 4 * sqrt(A) * h, unless the user overrides it.
    """
    farm, envl, crop = config["farm"], config["envelope"], config["crop"]
    footprint = float(farm["footprint_area_m2"])
    height = float(farm["room_height_m"])
    layers = int(farm["n_layers"])
    growing_area = footprint * layers
    wall = envl["wall_area_m2"] if envl["wall_area_m2"] is not None else 4.0 * math.sqrt(footprint) * height
    roof = envl["roof_area_m2"] if envl["roof_area_m2"] is not None else footprint
    floor = envl["floor_area_m2"] if envl["floor_area_m2"] is not None else footprint
    ua = envl["u_wall_w_m2k"] * wall + envl["u_roof_w_m2k"] * roof + envl["u_floor_w_m2k"] * floor
    occupied_area = growing_area * crop["occupied_fraction"]
    return {
        "footprint_area_m2": footprint,
        "room_volume_m3": footprint * height,
        "n_layers": layers,
        "growing_area_m2": growing_area,
        "occupied_area_m2": occupied_area,
        "n_plants": occupied_area * crop["plant_density_per_m2"],
        "wall_area_m2": wall,
        "roof_area_m2": roof,
        "floor_area_m2": floor,
        "envelope_ua_w_k": ua,
    }
