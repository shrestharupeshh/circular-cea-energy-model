"""Outdoor weather input: constant, synthetic daily profile, or imported CSV.

No internet connection or weather API is used. Outdoor temperature is in
deg C and relative humidity in percent throughout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from models.constants import SECONDS_PER_DAY, SECONDS_PER_HOUR, fahrenheit_to_celsius

REQUIRED_COLUMNS = ("timestamp", "outdoor_temperature", "outdoor_relative_humidity")
OPTIONAL_COLUMNS = ("solar_radiation", "wind_speed", "outdoor_co2")


def daily_profile(time_s: np.ndarray, mean: float, amplitude: float, peak_hour: float) -> np.ndarray:
    """Sinusoid with a 24 h period: mean + amplitude * cos(2*pi*(hour - peak_hour)/24)."""
    hour = np.asarray(time_s, dtype=float) / SECONDS_PER_HOUR
    return mean + amplitude * np.cos(2.0 * np.pi * (hour - peak_hour) / 24.0)


def load_weather_csv(path: str | Path, temperature_unit: str) -> tuple[pd.DataFrame, list[str]]:
    """Read and validate a weather CSV. Returns (data, warnings).

    Required columns: timestamp, outdoor_temperature, outdoor_relative_humidity [%].
    ``temperature_unit`` must be stated explicitly as "C" or "F"; it is never guessed.
    Raises ValueError for problems that would make the simulation wrong
    (missing columns, unparseable or duplicate timestamps, mixed time zones,
    missing or out-of-range values). Irregular spacing only produces a warning
    because values are interpolated linearly in time.
    """
    if temperature_unit not in ("C", "F"):
        raise ValueError("Temperature unit must be given explicitly as 'C' or 'F'.")
    warnings: list[str] = []
    data = pd.read_csv(path)
    data.columns = [str(c).strip().lower() for c in data.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in data.columns]
    if missing:
        raise ValueError(f"Weather CSV is missing required column(s): {', '.join(missing)}.")
    if len(data) < 2:
        raise ValueError("Weather CSV needs at least two rows.")

    try:
        stamps = pd.to_datetime(data["timestamp"], utc=False)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Timestamps could not be parsed, or mix time zones: {exc}") from exc
    if stamps.isna().any():
        raise ValueError("Weather CSV has missing timestamps.")
    if stamps.dtype == object:
        raise ValueError("Timestamps mix time zones or time-zone-aware and naive values.")
    if getattr(stamps.dt, "tz", None) is not None:
        warnings.append(f"Timestamps carry time zone {stamps.dt.tz}; clock times are used as given.")
        stamps = stamps.dt.tz_localize(None)
    if stamps.duplicated().any():
        raise ValueError(f"Weather CSV has {int(stamps.duplicated().sum())} duplicate timestamp(s).")
    if not stamps.is_monotonic_increasing:
        raise ValueError("Timestamps must be in increasing order.")

    temp = pd.to_numeric(data["outdoor_temperature"], errors="coerce")
    rh = pd.to_numeric(data["outdoor_relative_humidity"], errors="coerce")
    if temp.isna().any() or rh.isna().any():
        raise ValueError("Weather CSV has missing or non-numeric temperature or humidity values.")
    if temperature_unit == "F":
        temp = fahrenheit_to_celsius(temp)
    elif temp.max() > 60.0:
        warnings.append("Temperatures above 60 C found with unit 'C'. Is the file in Fahrenheit?")
    if temp.min() < -60.0 or temp.max() > 60.0:
        raise ValueError("Outdoor temperature outside the plausible range of -60 to 60 C after conversion.")
    if rh.min() < 0.0 or rh.max() > 100.0:
        raise ValueError("Relative humidity must be in percent, between 0 and 100.")
    if rh.max() <= 1.0:
        warnings.append("All humidity values are <= 1. Relative humidity is expected in percent, not as a fraction.")

    spacing = stamps.diff().dropna().dt.total_seconds()
    if spacing.max() > 1.5 * spacing.median():
        warnings.append(f"Irregular time spacing: {int((spacing > 1.5 * spacing.median()).sum())} gap(s) "
                        "longer than the usual interval were filled by linear interpolation.")

    elapsed = (stamps - stamps.iloc[0].normalize()).dt.total_seconds().to_numpy()
    result = pd.DataFrame({"time_s": elapsed, "outdoor_temp_c": temp.to_numpy(float),
                           "outdoor_rh_percent": rh.to_numpy(float)})
    return result, warnings


def build_weather(environment: dict[str, Any], time_s: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Outdoor temperature [C] and RH [%] at the requested simulation times.

    Simulation time zero is 00:00 on day 1. For CSV input, time zero is 00:00
    on the date of the first row; if the file is shorter than the simulation
    it is repeated from its start and a warning is returned.
    """
    time_s = np.asarray(time_s, dtype=float)
    warnings: list[str] = []
    mode = environment["weather_mode"]
    if mode == "constant":
        temp = np.full(time_s.shape, float(environment["outdoor_temp_c"]))
        rh = np.full(time_s.shape, float(environment["outdoor_rh_percent"]))
    elif mode == "daily_profile":
        peak = float(environment["outdoor_temp_peak_hour"])
        temp = daily_profile(time_s, environment["outdoor_temp_c"], environment["outdoor_temp_amplitude_k"], peak)
        # RH is lowest when temperature peaks (anti-phase), as on a typical clear day.
        rh = daily_profile(time_s, environment["outdoor_rh_percent"],
                           -environment["outdoor_rh_amplitude_percent"], peak)
        rh = np.clip(rh, 1.0, 100.0)
    elif mode == "csv":
        data, warnings = load_weather_csv(environment["weather_csv_path"], environment["csv_temperature_unit"])
        start, end = data["time_s"].iloc[0], data["time_s"].iloc[-1]
        lookup = time_s
        if time_s.max() > end:
            span_days = max(1.0, np.floor((end - start) / SECONDS_PER_DAY))
            warnings.append(f"Weather file covers {(end - start) / SECONDS_PER_DAY:.1f} days, shorter than the "
                            f"simulation; its first {span_days:.0f} day(s) are repeated.")
            lookup = start + np.mod(time_s - start, span_days * SECONDS_PER_DAY)
        temp = np.interp(lookup, data["time_s"], data["outdoor_temp_c"])
        rh = np.interp(lookup, data["time_s"], data["outdoor_rh_percent"])
    else:
        raise ValueError(f"Unknown weather mode: {mode}")
    return temp, rh, warnings
