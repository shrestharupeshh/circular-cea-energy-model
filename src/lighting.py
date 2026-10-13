"""lighting.py  - LED electrical load and thermal fraction."""

import numpy as np
from src.constants import J_PER_UMOL


def thermal_fraction(efficacy_umol_per_J):
    """Fraction of LED electrical input that becomes heat."""
    f_optical = efficacy_umol_per_J * J_PER_UMOL
    return float(np.clip(1.0 - f_optical, 0.0, 1.0))

def lamp_electrical_power(t_s, P_density, floor_area, on_h=6, off_h=22, sharp=30.0):
    """Total lamp electrical power [W], with a smoothed photoperiod switch."""
    hour = (t_s / 3600.0) % 24.0
    on = 1.0 / (1.0 + np.exp(-sharp * (hour - on_h)))
    off = 1.0 / (1.0 + np.exp(-sharp * (hour - off_h)))
    return P_density * floor_area * (on - off)