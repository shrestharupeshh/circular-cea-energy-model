"""Model 4: psychrometrics and the room moisture balance.

The conserved state is the humidity ratio w [kg water vapour / kg dry air],
never relative humidity. RH is computed from w and temperature afterwards.

Moisture balance (M_da = dry-air mass in the room):

    M_da * dw/dt = m_vent * (w_out - w) + m_transpiration - m_removed   [kg/s]
"""

from __future__ import annotations

import numpy as np

from models.constants import EPSILON, P_ATM, RHO_AIR


def saturation_vapor_pressure(temp_c):
    """Saturation vapour pressure over liquid water [Pa], Tetens equation.

    e_sat = 610.78 * exp(17.27 * T / (T + 237.3)),  T in deg C.
    Accurate to about 0.1 % between 0 and 50 C; not for use below freezing.
    """
    return 610.78 * np.exp(17.27 * temp_c / (temp_c + 237.3))


def humidity_ratio(temp_c, rh_fraction, pressure_pa: float = P_ATM):
    """w = 0.622 * e / (P - e) with e = RH * e_sat(T)  [kg/kg dry air]."""
    e = rh_fraction * saturation_vapor_pressure(temp_c)
    return EPSILON * e / (pressure_pa - e)


def vapor_pressure(w, pressure_pa: float = P_ATM):
    """e = w * P / (0.622 + w)  [Pa]."""
    return w * pressure_pa / (EPSILON + w)


def relative_humidity(temp_c, w, pressure_pa: float = P_ATM):
    """RH = e / e_sat(T) as a fraction (can exceed 1 if w is supersaturated)."""
    return vapor_pressure(w, pressure_pa) / saturation_vapor_pressure(temp_c)


def vapor_pressure_deficit(temp_c, w, pressure_pa: float = P_ATM):
    """VPD = e_sat(T) - e  [Pa]."""
    return saturation_vapor_pressure(temp_c) - vapor_pressure(w, pressure_pa)


def dry_air_mass(room_volume_m3: float) -> float:
    """M_da = rho_air * V_room  [kg] (constant density approximation)."""
    return RHO_AIR * room_volume_m3


def ventilation_mass_flow(flow_m3_s: float) -> float:
    """m_vent = rho_air * V_dot  [kg dry air / s]."""
    return RHO_AIR * flow_m3_s


def latent_power(moisture_rate_kg_s, h_fg_j_kg: float):
    """Q_latent = m_water * h_fg  [W thermal]."""
    return moisture_rate_kg_s * h_fg_j_kg
