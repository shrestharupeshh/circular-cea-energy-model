"""storage.py - the thermal buffer tank: charges from surplus heat, discharges when the room needs it."""

from src.constants import CP_WATER, RHO_WATER

def tank_capacitance(volume_m3):
    """Effective thermal capacitance of the tank [J/K]."""
    return volume_m3 * RHO_WATER * CP_WATER

def tank_standing_loss(T_tank, T_ambient, UA):
    """Heat lost from the tank to its surroundings [W]."""
    return UA * (T_tank - T_ambient)

def charge_rate(Q_available, T_tank, T_max, efficiency=0.85):
    """Heat flowing into the tank, limited by its maximum temperature."""
    if T_tank >= T_max:
        return 0.0
    return efficiency * max(Q_available, 0.0)

def discharge_rate(Q_demand, T_tank, T_min):
    """Heat flowing out of the tank, limited by useful temperature."""
    if T_tank <= T_min:
        return 0.0
    return max(Q_demand, 0.0)
