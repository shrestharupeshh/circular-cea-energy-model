"""Energy accounting: electrical energy by component, intensity and cost.

Electrical energy (kWh) and thermal energy (kWh_th) are never added
together. Total electricity is the sum of the electrical components only:

    E_total = E_lighting + E_cooling + E_heating + E_fans + E_pumps + E_auxiliary
"""

from __future__ import annotations

import math

import pandas as pd

from models.constants import J_PER_KWH

# column in the time series -> label of the electrical component
ELECTRICAL_COMPONENTS = {
    "power_lighting_w": "lighting",
    "power_hvac_cooling_w": "hvac_cooling",
    "power_hvac_heating_w": "hvac_heating",
    "power_circulation_fans_w": "circulation_fans",
    "power_ventilation_fans_w": "ventilation_fans",
    "power_pumps_w": "pumps",
    "power_auxiliary_w": "auxiliary",
}


def kwh(power_series_w: pd.Series, dt_s: float) -> float:
    """E = sum(P * dt) for step-mean powers, in kWh."""
    return float(power_series_w.sum() * dt_s / J_PER_KWH)


def component_energy_kwh(timeseries: pd.DataFrame, dt_s: float) -> dict[str, float]:
    """Electrical energy per component [kWh], plus 'hvac' (cooling + heating) and 'total'."""
    energy = {label: kwh(timeseries[col], dt_s) for col, label in ELECTRICAL_COMPONENTS.items()}
    energy["hvac"] = energy["hvac_cooling"] + energy["hvac_heating"]
    energy["fans"] = energy["circulation_fans"] + energy["ventilation_fans"]
    energy["total"] = sum(energy[label] for label in ELECTRICAL_COMPONENTS.values())
    return energy


def component_power_stats(timeseries: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Peak and average electrical power per component [W]."""
    stats = {label: {"peak_w": float(timeseries[col].max()), "average_w": float(timeseries[col].mean())}
             for col, label in ELECTRICAL_COMPONENTS.items()}
    stats["total"] = {"peak_w": float(timeseries["power_total_w"].max()),
                      "average_w": float(timeseries["power_total_w"].mean())}
    return stats


def energy_intensity(energy_kwh: float, harvest_kg: float) -> float:
    """E / M_harvest [kWh/kg]. Returns NaN (not an error, not infinity) when there is no harvest."""
    if harvest_kg is None or not harvest_kg > 0.0:
        return math.nan
    return energy_kwh / harvest_kg


def shares_percent(energy: dict[str, float]) -> dict[str, float]:
    """Share of total electricity per component [%]."""
    total = energy["total"]
    labels = ["lighting", "hvac", "fans", "pumps", "auxiliary"]
    return {label: (100.0 * energy[label] / total if total > 0 else math.nan) for label in labels}


def cost(energy_kwh: float, price_per_kwh: float) -> float:
    """Electricity cost at a constant rate (currency units)."""
    return energy_kwh * price_per_kwh
