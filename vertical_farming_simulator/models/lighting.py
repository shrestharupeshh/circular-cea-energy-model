"""Model 1: LED lighting - installed power, schedule, PPFD, DLI and heat.

Three quantities are kept distinct:
  * electrical power drawn by the fixtures            [W]
  * photon output of the fixtures                     [umol/s]
  * PPFD incident on the growing area                 [umol/m2/s]

They are linked by one photon balance under a uniform-light assumption:

    PPFD = P_density * efficacy * utilisation

where utilisation is the fraction of emitted photons that reaches the
growing area. The user fixes ONE of PPFD, power density or installed power
(``input_mode``); the other two are derived, so they cannot disagree.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from models.constants import HOURS_PER_DAY, SECONDS_PER_HOUR


def derive_lighting(lighting: dict[str, Any], growing_area_m2: float) -> dict[str, float]:
    """Resolve installed power, power density and full-power PPFD.

    Equations (A_g = growing area, eta = photon efficacy, f_u = utilisation):
        P_LED = A_g * P_density                         [W]
        PPFD  = P_density * eta * f_u                   [umol/m2/s]
    """
    efficacy = lighting["photon_efficacy_umol_j"]
    utilisation = lighting["utilisation_factor"]
    mode = lighting["input_mode"]
    if mode == "ppfd":
        ppfd = float(lighting["ppfd_umol_m2_s"])
        density = ppfd / (efficacy * utilisation)
    elif mode == "power_density":
        density = float(lighting["power_density_w_m2"])
        ppfd = density * efficacy * utilisation
    elif mode == "installed_power":
        density = float(lighting["installed_power_w"]) / growing_area_m2 if growing_area_m2 > 0 else 0.0
        ppfd = density * efficacy * utilisation
    else:
        raise ValueError(f"Unknown lighting input mode: {mode}")
    installed = density * growing_area_m2
    return {
        "installed_power_w": installed,
        "power_density_w_m2": density,
        "ppfd_full_umol_m2_s": ppfd,
        "photon_output_umol_s": installed * efficacy,
    }


def _cumulative_on_hours(hour_of_day: np.ndarray, start_hour: float, photoperiod_h: float) -> np.ndarray:
    """Lit hours between 00:00 and ``hour_of_day`` (0..24) for a window that may wrap midnight."""
    s, p = start_hour, photoperiod_h
    return (np.clip(hour_of_day - s, 0.0, p)
            + np.clip(hour_of_day + HOURS_PER_DAY - s, 0.0, p)
            - np.clip(HOURS_PER_DAY - s, 0.0, p))


def _cumulative(time_h: np.ndarray, daily_total: float, within_day) -> np.ndarray:
    days = np.floor(time_h / HOURS_PER_DAY)
    return days * daily_total + within_day(time_h - days * HOURS_PER_DAY)


def schedule_fractions(lighting: dict[str, Any], t_start_s: np.ndarray, dt_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Step-averaged lighting schedule u_LED and lit fraction for each step.

    Returns (u, lit):
      u   - mean power fraction over the step, 0..1 (includes dimming)
      lit - fraction of the step during which the lights are on at all

    Averages are exact (computed from the cumulative schedule), so lighting
    energy does not depend on how the time step lines up with switch times.
    The schedule repeats every 24 h.
    """
    t0 = np.asarray(t_start_s, dtype=float) / SECONDS_PER_HOUR
    t1 = t0 + dt_s / SECONDS_PER_HOUR
    dt_h = dt_s / SECONDS_PER_HOUR

    if lighting["schedule_type"] == "photoperiod":
        s, p = float(lighting["start_hour"]), float(lighting["photoperiod_h"])

        def within(x):
            return _cumulative_on_hours(x, s, p)

        lit = (_cumulative(t1, p, within) - _cumulative(t0, p, within)) / dt_h
        u = lit * float(lighting["dimming_level"])
    elif lighting["schedule_type"] == "custom":
        levels = np.asarray(lighting["custom_hourly_fractions"], dtype=float) * float(lighting["dimming_level"])
        edges = np.arange(25.0)
        cum_power = np.concatenate([[0.0], np.cumsum(levels)])
        cum_lit = np.concatenate([[0.0], np.cumsum(levels > 0)])
        u = (_cumulative(t1, cum_power[-1], lambda x: np.interp(x, edges, cum_power))
             - _cumulative(t0, cum_power[-1], lambda x: np.interp(x, edges, cum_power))) / dt_h
        lit = (_cumulative(t1, cum_lit[-1], lambda x: np.interp(x, edges, cum_lit))
               - _cumulative(t0, cum_lit[-1], lambda x: np.interp(x, edges, cum_lit))) / dt_h
    else:
        raise ValueError(f"Unknown schedule type: {lighting['schedule_type']}")
    # rounding removes 1e-16-level noise so that 'fully on' is exactly 1.0
    return np.clip(np.round(u, 12), 0.0, 1.0), np.clip(np.round(lit, 12), 0.0, 1.0)


def lighting_power(installed_power_w: float, u_led):
    """P_lighting(t) = P_LED * u_LED(t)  [W electrical]."""
    return installed_power_w * u_led


def led_heat_to_room(lighting_power_w, heat_fraction: float):
    """Q_LED = f_LED_heat * P_lighting  [W thermal released in the room]."""
    return heat_fraction * lighting_power_w


def energy_kwh(power_w: np.ndarray, dt_s: float) -> float:
    """E = sum(P * dt), converted from J to kWh."""
    return float(np.sum(power_w) * dt_s / 3.6e6)


def daily_light_integral(ppfd_umol_m2_s: float, photoperiod_h: float) -> float:
    """DLI = PPFD * photoperiod[s] / 1e6  [mol/m2/day] for constant PPFD."""
    return ppfd_umol_m2_s * photoperiod_h * SECONDS_PER_HOUR / 1e6


def light_integral_mol_m2(ppfd_series: np.ndarray, dt_s: float) -> float:
    """Integral of PPFD over time / 1e6  [mol/m2] for a variable PPFD series."""
    return float(np.sum(ppfd_series) * dt_s / 1e6)
