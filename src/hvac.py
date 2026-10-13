"""hvac.py - dehumidification control."""

def dehumidifier(RH, RH_setpoint, capacity_kg_s, gain=50.0):
    """Proportional dehumidifier control.
    Returns moisture removal rate [ks/s], which is also the recovered condensate rate."""

    error = RH - RH_setpoint
    if error <= 0:
        return 0.0
    demand = gain * error * capacity_kg_s
    return min(demand, capacity_kg_s)