"""scenarios.py - the three experiments: no recovery, heat only, heat + water."""

import copy
import numpy as np
from scipy.integrate import solve_ivp
from src.constants import LAMBDA
from src.model import model_full
from src.psychro import abs_humidity, rh_from_chi
from src.lighting import lamp_electrical_power, thermal_fraction
from src.crop import transpiration
from src.hvac import dehumidifier
from src.storage import discharge_rate

BASE = {
    # room and envelope
    'volume': 300.0, 'floor_area': 100.0, 'area_env': 160.0,
    'U_envelope': 0.4, 'ACH': 0.5,
    # lighting
    'P_lamp': 200.0, 'efficacy': 3.0,
    'photoperiod_on': 6, 'photoperiod_off': 22,
    # climate control
    'T_setpoint': 24.0, 'RH_setpoint': 0.75,
    'cool_gain': 4000.0, 'cool_capacity': 15000.0,
    'heat_gain': 4000.0, 'T_heat_setpoint': 20.0, 'heat_capacity': 10000.0,
    'COP_cool': 3.0, 'COP_dehum': 2.5,
    'dehum_capacity': 0.004,
    # crop and thermal mass
    'LAI': 2.5, 'capacitance_multiplier': 12.0,
    # thermal tank
    'tank_volume': 5.0, 'tank_UA': 15.0,
    'T_tank_max': 60.0, 'T_tank_min': 30.0,
    # circular switches
    'heat_recovery': False,
    'water_recovery': False,
    # production
    'yield_kg_per_m2_per_cycle': 4.0,
    'cycle_days': 30,
}

def make_scenarios():
    s = {}
    s['A_linear'] = copy.deepcopy(BASE)

    s['B_heat'] = copy.deepcopy(BASE)
    s['B_heat']['heat_recovery'] = True

    s['C_heat_water'] = copy.deepcopy(BASE)
    s['C_heat_water']['heat_recovery'] = True
    s['C_heat_water']['water_recovery'] = True
    return s

# Shared inputs: every scenario sees the same weather and starts from the same state
WEATHER = {
    'T_out': lambda t: 10.0 - 5.0 * np.cos(2 * np.pi * t / 86400.0),
    'RH_out': lambda t: 0.70,
}

T0, RH0, T_TANK0 = 22.0, 0.60, 40.0
DURATION_S = 86400

def run_scenario(p, weather=WEATHER, duration_s=DURATION_S):
    """Simulate one scenario and return its time series (W, kg/s, C)."""
    y0 = [T0, abs_humidity(T0, RH0), 0.0, T_TANK0]
    t_eval = np.arange(0, duration_s + 1, 60)
    sol = solve_ivp(model_full, (0, duration_s), y0, method='BDF', t_eval=t_eval,
                    args=(p, weather), rtol=1e-6, atol=1e-8)
    t = sol.t
    T_air, chi_air, V_rec, T_tank = sol.y
    RH = rh_from_chi(T_air, chi_air)

    # Rebuild the flow from the solution
    P_lamp = lamp_electrical_power(t, p['P_lamp'], p['floor_area'],
                                   p['photoperiod_on'], p['photoperiod_off'])
    Q_cool = np.minimum(np.maximum(0.0, p['cool_gain'] * (T_air - p['T_setpoint'])),
                        p['cool_capacity'])
    Q_heat = np.minimum(np.maximum(0.0, p['heat_gain'] * (p['T_heat_setpoint'] - T_air)),
                        p['heat_capacity'])
    if p['heat_recovery']:
        Q_discharge = discharge_rate(Q_heat, T_tank, p['T_tank_min'])
    else:
        Q_discharge = np.zeros_like(t)
    if p['water_recovery']:
        M_dehum = np.array([dehumidifier(r, p['RH_setpoint'], p['dehum_capacity']) for r in RH])
    else:
        M_dehum = np.zeros_like(t)

    # Crop water use, as in the model
    f_therm = thermal_fraction(p['efficacy'])
    R_net = P_lamp * (1.0 - f_therm) / p['floor_area']
    M_crop = transpiration(R_net, T_air, RH, p['LAI']) * p['floor_area']

    # Electricity: lights + cooling + dehumidifier + grid heater (Tank covers the rest)
    P_cool = Q_cool / p['COP_cool']
    P_dehum = M_dehum * LAMBDA / p['COP_dehum']
    P_heat_grid = Q_heat - Q_discharge
    P_total = P_lamp + P_cool + P_dehum + P_heat_grid

    # Fresh water = what the crop uses minus what is recovered
    M_fresh = M_crop - M_dehum

    return {'success': sol.success, 't': t, 'T_air':  T_air, 'RH': RH, 'T_tank': T_tank,
            'P_lamp': P_lamp, 'P_cool': P_cool, 'P_dehum': P_dehum,
            'P_heat_grid': P_heat_grid, 'P_total': P_total,
            'M_crop': M_crop, 'M_dehum': M_dehum, 'M_fresh': M_fresh}