"""run_Scenarios.py - run all three scenarios and print daily totals."""

import numpy as np
from src.scenarios import make_scenarios, run_scenario

print('%-14s %9s %9s %9s %9s %9s %9s' % ('scenario', 'lamps', 'cooling', 'dehum', 'grid heat', 'TOTAL', 'fresh H2O'))
print('%-14s %9s %9s %9s %9s %9s %9s' % ('', 'kWh', 'kWh', 'kWh', 'kWh', 'kWh', 'L')) 
for name, p in make_scenarios().items():
    r = run_scenario(p)
    t = r['t']
    kwh = lambda P: np.trapezoid(P, t) / 3.6e6
    fresh_L = np.trapezoid(r['M_fresh'], t)
    print('%-14s %9.1f %9.1f %9.1f %9.1f %9.1f %9.1f' % (
        name, kwh(r['P_lamp']), kwh(r['P_cool']), kwh(r['P_dehum']),
        kwh(r['P_heat_grid']), kwh(r['P_total']), fresh_L))
