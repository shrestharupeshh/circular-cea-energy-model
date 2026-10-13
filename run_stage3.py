"""run_stage3.py - run the coupled temperature + humidity model over 24 hours."""

import numpy as np
from scipy.integrate import solve_ivp
from src.model import model_coupled
from src.psychro import abs_humidity, rh_from_chi

params = {
    'volume': 300.0, 'floor_area': 100.0, 'area_env': 160.0,
    'U_envelope': 0.4, 'ACH': 0.5,
    'P_lamp': 200.0, 'efficacy': 3.0,
    'photoperiod_on': 6, 'photoperiod_off': 22,
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

T0 = 22.0
RH0 = 0.60
chi0 = abs_humidity(T0, RH0)
V0 = 0.0
y0 = [T0, chi0, V0]

sol = solve_ivp(
    model_coupled,
    t_span=(0, 86400),
    y0=y0,
    method='BDF',
    t_eval=np.arange(0, 86400, 60),
    args=(params, weather),
    rtol=1e-6,
    atol=1e-8,
)

T_air = sol.y[0]
chi_air = sol.y[1]
V_recovered = sol.y[2]
RH = rh_from_chi(T_air, chi_air)

print('solved:', sol.success)
print('T range: %.1f to %.1f C' % (T_air.min(), T_air.max()))
print('RH range: %.1f to %.1f %%' % (RH.min() * 100, RH.max() * 100))
print('Water recovered over 24h: %.2f L' % (V_recovered[-1] * 1000))