"""storage.py - thermal buffer tank."""

import numpy as np
from src.constants import CP_WATER, RHO_WATER

def tank_capacitance(volume_m3):
    return volume_m3 * RHO_WATER * CP_WATER

def tank_standing_loss(T_tank, T_ambient, UA):
    return UA * (T_tank - T_ambient)

def charge_rate(Q_available, T_tank, T_max, efficiency=0.85, band=5.0):
    """Heat sent to the tank (W). Fades smoothly to zero over the last `band` K below T_max."""
    taper = np.clip((T_max - T_tank) / band, 0.0, 1.0)
    return efficiency * np.maximum(Q_available, 0.0) * taper

def discharge_rate(Q_demand, T_tank, T_min, band=5.0):
    """Heat drawn from the tank (W). Fades smoothly to zero over the first `band` K above T_min."""
    taper = np.clip((T_tank - T_min) / band, 0.0, 1.0)
    return np.maximum(Q_demand, 0.0) * taper