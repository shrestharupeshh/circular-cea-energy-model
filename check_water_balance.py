"""check_water_balance.py - verify the Stage 3 run conserves water."""

import numpy as np
from scipy.integrate import solve_ivp
from src.model import model_coupled
from src.psychro import abs_humidity, rh_from_chi
from src.lighting import lamp_electrical_power, thermal_fraction
from src.crop import transpiration
from src.constants import RHO_WATER

params = {
    'volume': 300.0, 'floor_area': 100.0, 'area_env': 160.0,
    'U_envelope': 0.4, 'ACH': 0.5,
    'P_lamp': 200.0, 'efficacy': 3.0,
    'photoperiod_on': 6, 'photoperiod_off': 22,
    'f_biomass': 0.02,
    'T_setpoint': 24.0, 'cool_gain': 4000.0, 'cool_capacity': 15000.0,
    'capacitance_multiplier': 12.0,
    'LAI': 2.5,
    'RH_setpoint': 0.75, 'dehum_capacity': 0.004,
    'water_recovery': True,
}

weather = {
    'T_out': lambda t: 10.0 - 5.0 * np.cos(2 * np.pi * t / 86400.0),
    'RH_out': lambda t: 0.70,
}

T0, RH0 = 22.0, 0.60
y0 = [T0, abs_humidity(T0, RH0), 0.0]

sol = solve_ivp(model_coupled, (0,86400), y0, method='BDF',
                t_eval=np.arange(0, 86400, 60), args=(params, weather),
                rtol=1e-6, atol=1e-8)

t = sol.t
T_air, chi_air, V_recovered = sol.y
RH = rh_from_chi(T_air, chi_air)

# recompute the two flows the solver didn't already track for us
P_lamp = lamp_electrical_power(t, params['P_lamp'], params['floor_area'],
                               params['photoperiod_on'], params['photoperiod_off'])
f_therm = thermal_fraction(params['efficacy'])
R_net = P_lamp * (1.0 - f_therm) / params['floor_area']
M_crop = transpiration(R_net, T_air, RH, params['LAI']) * params['floor_area']

m_air = params['ACH'] * params['volume'] * 1.20 / 3600.0 #RHO_AIR, same as envelope
T_out = weather['T_out'](t)
chi_out = abs_humidity(T_out, weather['RH_out'](t))
M_vent = m_air / 1.20 * (chi_air - chi_out)

produced = np.trapezoid(M_crop, t)
removed_vent = np.trapezoid(M_vent, t)
removed_dehum = V_recovered[-1] * RHO_WATER
stored = params['volume'] * (chi_air[-1] - chi_air[0])

residual = produced - removed_dehum - removed_vent - stored
relative = abs(residual) / max(produced, 1e-9)

print('water produced (transpired): %.2f kg' % produced)
print('water recovered (dehum):     %.2f kg' % removed_dehum)
print('water vented out:            %.2f kg' % removed_vent)
print('water still stored in air:   %.2f kg' % stored)
print('residual: %.4f%%' % (100 * relative))
assert relative < 0.01, 'Water not conserved - check signs and terms'