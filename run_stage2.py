"""run_stage2.py - run the temperature-only model over 24 hrs."""

import numpy as np
from scipy.integrate import solve_ivp
from src.model import model_temperature_only

params = {
    'volume': 300.0, 'floor_area': 100.0, 'area_env': 160.0,
    'U_envelope': 0.4, 'ACH': 0.5,
    'P_lamp': 200.0, 'efficacy': 3.0,
    'photoperiod_on': 6, 'photoperiod_off': 22,
    'T_setpoint': 24.0, 'cool_gain': 4000.0, 'cool_capacity': 15000.0,
    'capacitance_multiplier': 12.0,
}

weather = {'T_out': lambda t: 10.0 - 5.0 * np.cos(2 * np.pi * t / 86400.0)}

sol = solve_ivp(
    model_temperature_only,
    t_span=(0, 86400),
    y0=[22.0],
    method='BDF',
    t_eval=np.arange(0, 86400, 60),
    args=(params, weather),
    rtol=1e-6,
    atol=1e-8,
)

print('solved:', sol.success)
print('T range: %.1f to %.1f C' % (sol.y[0].min(), sol.y[0].max()))