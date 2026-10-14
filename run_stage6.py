"""run_stage6.py - compare the three scenarios on the nexus indicators."""

from src.scenarios import make_scenarios, run_scenario
from src.indicators import summarise, simulated_yield_kg

summaries= {}
for name, p in make_scenarios().items():
    r = run_scenario(p)
    summaries[name] = summarise(r, p)

print('Yield over the simulated day: %.2f kg' % simulated_yield_kg(p, r['t'][-1]))
print()
print('%-14s %12s %12s %10s' % ('scenario', 'EUI kWh/kg', 'WUI L/kg', 'recovered'))
for name, s in summaries.items():
    print('%-14s %12.2f %12.2f %9.1f %%' % (
        name, s['EUI_kWh_per_kg'], s['WUI_L_per_kg'], s['water_recovered'] * 100))

base = summaries['A_linear']
print()
print('Change relative to A_linear:')
for name, s in summaries.items():
    d_eui = 100 * (s['EUI_kWh_per_kg'] - base['EUI_kWh_per_kg']) / base['EUI_kWh_per_kg']
    d_wui = 100 * (s['WUI_L_per_kg'] - base['WUI_L_per_kg']) / base['WUI_L_per_kg']
    print('%-14s EUI %+6.1f %%   WUI %+6.1f %%' % (name, d_eui, d_wui))