"""Scenario management: example scenarios, save/load, and comparison tables.

The example scenarios are operating configurations to explore, not
recommendations. No scenario is ranked as "best": that depends on the
objective and constraints the user cares about.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import pandas as pd

from config.parameters import default_config, load_config, save_config, with_overrides
from simulation.engine import run_simulation
from simulation.results import SimulationResult

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "data" / "scenarios"

EXAMPLE_OVERRIDES: dict[str, dict[str, Any]] = {
    "A - Baseline": {},
    "B - High lighting": {"lighting": {"input_mode": "ppfd", "ppfd_umol_m2_s": 350.0, "photoperiod_h": 18.0}},
    "C - Reduced lighting": {"lighting": {"input_mode": "ppfd", "ppfd_umol_m2_s": 180.0, "photoperiod_h": 12.0}},
    "D - Night lighting": {"lighting": {"start_hour": 20.0}},
    "E - Improved HVAC": {"hvac": {"cooling_cop": 4.5}},
    "F - Warmer setpoint": {"hvac": {"temp_setpoint_c": 25.0}},
}


def example_scenarios(base: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """The six example scenarios, each a full editable configuration."""
    base = base or default_config()
    scenarios = {}
    for name, overrides in EXAMPLE_OVERRIDES.items():
        scenario = with_overrides(base, overrides)
        scenario["scenario_name"] = name
        scenarios[name] = scenario
    return scenarios


def _file_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") + ".json"


def save_scenario(config: dict[str, Any], directory: Path | str = SCENARIO_DIR) -> Path:
    """Save a scenario as JSON, named after its scenario_name."""
    path = Path(directory) / _file_name(config["scenario_name"])
    save_config(config, path)
    return path


def list_scenarios(directory: Path | str = SCENARIO_DIR) -> list[Path]:
    return sorted(Path(directory).glob("*.json"))


def load_scenario(path: Path | str) -> dict[str, Any]:
    return load_config(path)


def duplicate_scenario(config: dict[str, Any], new_name: str) -> dict[str, Any]:
    """Copy a scenario under a new name (also used to rename)."""
    duplicate = copy.deepcopy(config)
    duplicate["scenario_name"] = new_name
    return duplicate


def run_scenarios(scenarios: dict[str, dict[str, Any]]) -> dict[str, SimulationResult]:
    return {name: run_simulation(config) for name, config in scenarios.items()}


COMPARISON_ROWS = [
    ("Total electricity [kWh]", lambda s: s["energy_kwh"]["total"]),
    ("Lighting electricity [kWh]", lambda s: s["energy_kwh"]["lighting"]),
    ("HVAC electricity [kWh]", lambda s: s["energy_kwh"]["hvac"]),
    ("Marketable fresh harvest [kg]", lambda s: s["crop"]["marketable_fresh_mass_kg"]),
    ("Fresh mass per plant [g]", lambda s: s["crop"]["fresh_mass_per_plant_g"]),
    ("Dry biomass [kg]", lambda s: s["crop"]["total_dry_mass_kg"]),
    ("Energy intensity [kWh/kg]", lambda s: s["energy_intensity_kwh_per_kg"]["total"]),
    ("Mean DLI [mol/m2/day]", lambda s: s["dli_mean_mol_m2_day"]),
    ("Mean indoor temperature [C]", lambda s: s["indoor_temp_mean_c"]),
    ("Temperature violations [h]", lambda s: s["temp_violation_hours"]),
    ("Mean indoor RH [%]", lambda s: s["indoor_rh_mean_percent"]),
    ("Humidity violations [h]", lambda s: s["rh_violation_hours"]),
    ("Peak cooling delivered [kW thermal]", lambda s: s["cooling_delivered_peak_kw"]),
    ("Unmet cooling [kWh thermal]", lambda s: s["cooling_unmet_kwh_th"]),
    ("Operating cost [currency]", lambda s: s["cost"]["total"]),
    ("Cost per kg [currency/kg]", lambda s: s["cost"]["per_kg"]),
]


def comparison_table(results: dict[str, SimulationResult]) -> pd.DataFrame:
    """One column per scenario, one row per metric."""
    return pd.DataFrame({name: {label: fn(r.summary) for label, fn in COMPARISON_ROWS}
                         for name, r in results.items()})


def difference_table(table: pd.DataFrame, reference: str) -> pd.DataFrame:
    """Percent change of every scenario relative to the reference scenario."""
    ref = table[reference]
    table = table.astype(float)
    ref = table[reference]
    diff = table.sub(ref, axis=0).div(ref.where(ref != 0), axis=0) * 100.0
    return diff.drop(columns=[reference]).astype(float)   # NaN where the reference is zero
