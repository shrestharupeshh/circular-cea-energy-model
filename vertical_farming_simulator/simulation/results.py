"""Container for simulation output and export helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class SimulationResult:
    """Output of one run.

    timeseries : one row per time step. State columns (temperature, humidity,
                 biomass) are values at the START of the step; power and flow
                 columns are step means; cumulative columns are at the END of
                 the step.
    summary    : scalar results (energies in kWh, masses in kg, ...).
    final_state: state at the end of the last step.
    derived    : geometry and lighting quantities derived from the inputs.
    warnings   : things the user should know (unmet load, condensation, ...).
    """

    config: dict[str, Any]
    timeseries: pd.DataFrame
    summary: dict[str, Any]
    final_state: dict[str, float]
    derived: dict[str, float]
    warnings: list[str] = field(default_factory=list)

    def to_csv(self) -> str:
        """Complete time series as CSV text."""
        return self.timeseries.to_csv(index=False, float_format="%.6g")

    def config_json(self) -> str:
        """Scenario configuration (all parameters and assumptions) as JSON text."""
        return json.dumps(self.config, indent=2)

    def daily(self) -> pd.DataFrame:
        """Daily totals and means (energy in kWh/day, DLI in mol/m2/day)."""
        ts = self.timeseries
        dt_h = self.summary["time_step_s"] / 3600.0
        day = ts["day"].astype(int)
        power_cols = [c for c in ts.columns if c.startswith("power_") and c.endswith("_w")]
        out = pd.DataFrame(index=sorted(day.unique()))
        out.index.name = "day"
        for col in power_cols:
            out[col.replace("power_", "energy_").replace("_w", "_kwh")] = ts.groupby(day)[col].sum() * dt_h / 1000.0
        out["dli_mol_m2_day"] = ts.groupby(day)["ppfd_umol_m2_s"].sum() * self.summary["time_step_s"] / 1e6
        out["indoor_temp_mean_c"] = ts.groupby(day)["indoor_temp_c"].mean()
        out["indoor_rh_mean_percent"] = ts.groupby(day)["indoor_rh_percent"].mean()
        biomass_end = ts.groupby(day)["biomass_dry_g_per_plant"].last()
        out["growth_g_dry_per_plant_day"] = biomass_end.diff().fillna(
            biomass_end.iloc[0] - ts["biomass_dry_g_per_plant"].iloc[0])
        out["cost_per_day"] = out["energy_total_kwh"] * self.config["economics"]["electricity_price_per_kwh"]
        return out.reset_index()
