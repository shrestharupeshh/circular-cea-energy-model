"""envelope.py - conduction through the envelope and ventilation heat exchange."""

from src.constants import RHO_AIR, CP_AIR

def transmission_loss(T_in, T_out, U, area):
    """Conduction/convection heat loss through the envelope [W]."""
    return U * area * (T_in - T_out)


def ventilation_mass_flow(ACH, volume):
    """Air mass flow rate from air changes per hour [kg/s]."""
    return ACH * volume * RHO_AIR / 3600.0


def ventilation_sensible(m_dot, T_in, T_out):
    """Sensible heat carried out by ventilation air [W]."""
    return m_dot * CP_AIR * (T_in - T_out)