"""Physical constants and unit conversions (SI units internally).

Values are standard engineering approximations for air near 20-25 C at sea
level. They are constants of the model, not scenario parameters.
"""

RHO_AIR = 1.20            # kg/m3   dry-air density near 20 C, 101.325 kPa
CP_AIR = 1006.0           # J/kg/K  specific heat of air
H_FG = 2.45e6             # J/kg    latent heat of vaporisation of water near 20 C
P_ATM = 101325.0          # Pa      atmospheric pressure (sea level)
EPSILON = 0.622           # -       ratio of molar masses, water vapour / dry air
J_PER_UMOL_PAR = 0.22     # J/umol  approximate energy of PAR photons (spectrum dependent)

SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86400.0
HOURS_PER_DAY = 24.0
J_PER_KWH = 3.6e6


def fahrenheit_to_celsius(temp_f):
    """Convert degrees Fahrenheit to degrees Celsius."""
    return (temp_f - 32.0) * 5.0 / 9.0
