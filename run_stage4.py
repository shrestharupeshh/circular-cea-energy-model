"""run_stage4.py - run the full model (with thermal tank) over 24 hours, once with heat recovery ON and once OFF."""

import numpy as np
from scipy.integrate import solve_ivp
from src.model import model_full
from src.psychro import abs_humidity, rh_from_chi

params = {
    'volume': 300.0, 'floor_area': 100.0, 'area_env': 160.0,
    'U_envelope': 0.4, 'ACH': 0.5,
    'P_lamp': 100.0, 'efficacy': 3.0,
    'photoperiod_on': 6, 'photoperiod_off': 22,
    'f_biomass': 0.02,
    'T_setpoint': 24.0, 'cool_gain': 4000.0, 'cool_capacity': 15000.0,
    'capacitance_multiplier': 12.0,
    'LAI': 2.5,
    'RH_setpoint': 0.75, 'dehum_capacity': 0.004,
    'water_recovery': True,
    'heat_gain': 4000.0, 'T_heat_setpoint': 20.0, 'heat_capacity': 10000.0,
    'heat_recovery': True,
    'tank_volume': 5.0, 'tank_UA': 15.0,
    'T_tank_max': 60.0, 'T_tank_min': 30.0,
}

weather = {
    'T_out': lambda t: 10.0 - 5.0 * np.cos(2 * np.pi * t / 86400.0),
    'RH_out': lambda t: 0.70,
}

T0, RH0, T_tank0 = 22.0, 0.60, 40.0
y0 = [T0, abs_humidity(T0, RH0), 0.0, T_tank0]

for recovery in (True, False):
    params['heat_recovery'] = recovery
    sol = solve_ivp(model_full, (0, 86400), y0, method='BDF',
                    t_eval=np.arange(0, 86400, 60), args=(params, weather),
                    rtol=1e-6, atol=1e-8)
    T_air, chi_air, V_recovered, T_tank = sol.y
    RH = rh_from_chi(T_air, chi_air)

    print('--- heat_recovery =', recovery, '---')
    print('solved:', sol.success)
    print('T_air range: %.1f to %.1f C' % (T_air.min(), T_air.max()))
    print('RH range: %.1f to %.1f %%' % (RH.min() * 100, RH.max() * 100))
    print('Water recovered: %.2f L' % (V_recovered[-1] * 1000))
    print('Tank at 06:00: %.1f C, at 22:00: %.1f C' % (T_tank[360], T_tank[1320]))
