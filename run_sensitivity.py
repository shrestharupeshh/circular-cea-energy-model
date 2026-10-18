"""run_sensitivity.py - one-at-a-time sensitivity: change one input by +/-20%, return A and C."""

import os 
import time
import numpy as np
import pandas as pd
from src.scenarios import BASE, WEATHER, run_scenario
from src.indicators import summarise, select_day

N_DAYS = 7

# model inputs to vary (each is multiplied by 0.8 and 1.2)
TARGETS = ['U_envelope', 'ACH', 'efficacy', 'LAI', 'capacitance_multiplier',
            'COP_cool', 'COP_dehum', 'RH_setpoint', 'tank_volume', 'tank_UA']

def weather_shifted(delta_T):
    """Same outdoor weather, but every outdoor temperature moved by delta_T kelvin."""
    return {'T_out': lambda t: WEATHER['T_out'](t) + delta_T,
           'RH_out': WEATHER['RH_out']}

def steady_state(p, weather):
    r = run_scenario(p, weather=weather, duration_s=N_DAYS * 86400)
    return summarise(select_day(r, N_DAYS - 1), p), r['success']

def run_pair(changes, weather):
    """Run scenario A and scenario C with the same changes; return the numbers we need."""
    pA =  dict(BASE, **changes)
    pC = dict(BASE, **changes, heat_recovery=True, water_recovery=True)
    sA, okA = steady_state(pA, weather)
    sC, okC = steady_state(pC, weather)
    return {'EUI_A': sA['EUI_kWh_per_kg'], 'EUI_C': sC['EUI_kWh_per_kg'],
            'WUI_A': sA['WUI_L_per_kg'], 'WUI_C': sC['WUI_L_per_kg'],
            'solved': okA and okC}

cases = [('baseline', 1.0, {}, WEATHER)]
for key in TARGETS:
    for factor in (0.8, 1.2):
        cases.append((key, factor, {key: BASE[key] * factor}, WEATHER))
for delta in (-5.0, 5.0):
    cases.append(('T_out_mean', delta, {}, weather_shifted(delta)))

rows = []
for name, level, changes, weather in cases:
    t0 = time.time()
    out = run_pair(changes, weather)
    out.update({'parameter': name, 'level': level})
    rows.append(out)
    print('%-24s %5.2f EUI_C %6.2f penalty %+6.1f %% WUI_C %5.2f solved %s (%.1f s)' % (
       name, level, out['EUI_C'], 100 * (out['EUI_C'] / out['EUI_A'] - 1),
       out['WUI_C'], out['solved'], time.time() - t0))

df = pd.DataFrame(rows)
os.makedirs('data', exist_ok=True)
df.to_csv('data/sensitivity.csv', index=False)
print('saved data/sensitivity.csv with', len(df), 'rows')