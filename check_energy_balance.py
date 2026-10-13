"""check_energy_balance.py - does the thermal tank obey conservation of energy?"""

import numpy as np
from scipy.integrate import solve_ivp
from src.model import model_full
from src.psychro import abs_humidity
from src.storage import tank_capacitance

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
t_eval = np.arange(0, 86401, 60)
sol = solve_ivp(model_full, (0, 86400), y0, method='BDF', t_eval=t_eval,
                args=(params, weather), rtol=1e-8, atol=1e-10)
T_air, chi_air, V_rec, T_tank = sol.y
t = sol.t

Q_cool = np.minimum(np.maximum(0.0, params['cool_gain'] * (T_air - params['T_setpoint'])),
                    params['cool_capacity'])
Q_heat = np.minimum(np.maximum(0.0, params['heat_gain'] * (params['T_heat_setpoint'] - T_air)),
                   params['heat_capacity'])
Q_charge = np.where(T_tank >= params['T_tank_max'], 0.0, 0.85 * Q_cool)
Q_discharge = np.where(T_tank <= params['T_tank_min'], 0.0, Q_heat)
Q_loss = params['tank_UA'] * (T_tank - T_air)

E_in = np.trapezoid(Q_charge, t)
E_out = np.trapezoid(Q_discharge, t)
E_loss = np.trapezoid(Q_loss, t)
C_tank = tank_capacitance(params['tank_volume'])
E_stored = C_tank * (T_tank[-1] - T_tank[0])

residual = E_in - E_out - E_loss - E_stored
print('Heat charged into tank:  %.1f MJ' % (E_in / 1e6))
print('Heat discharged to room: %.1f MJ' % (E_out / 1e6))
print('Tank standing loss:      %.1f MJ' % (E_loss / 1e6))
print('Tank energy change:      %.1f MJ' % (E_stored / 1e6))
print('Residual:                %.4f MJ (%.4f %%)' % (residual / 1e6, 100 * abs(residual) / E_in))
assert abs(residual) / E_in < 0.01, 'Energy balance violated!'
print('PASS: tank energy balance closes within 1 %')