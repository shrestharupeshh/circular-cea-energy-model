"""psychro.py - psychrometric relations: saturation vapor pressure,
vapor pressure deficit, and absolute humidity."""

import numpy as np

M_WATER = 0.018016   # kg/mol, molar mass of water
R_GAS = 8.314        # J/(mol K), universal gas constant


def e_sat(T_C):
    """Saturation vapor pressure [Pa] via the Tetens equation. T_C in Celsius."""
    return 610.78 * np.exp(17.27 * T_C / (T_C + 237.3))


def vpd(T_C, RH):
    """Vapor pressure deficit [Pa]. RH as a fraction, 0 to 1."""
    return e_sat(T_C) * (1.0 - RH)


def abs_humidity(T_C, RH):
    """Absolute humidity [kg water / m3 air], via the ideal gas law."""
    e = RH * e_sat(T_C)
    T_K = T_C + 273.15
    return e * M_WATER / (R_GAS * T_K)


def rh_from_chi(T_C, chi):
    """Invert: relative humidity from absolute humidity."""
    T_K = T_C + 273.15
    e = chi * R_GAS * T_K / M_WATER
    return np.clip(e / e_sat(T_C), 0.0, 1.0)