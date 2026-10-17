"""run_multiday.py - run several days so start-up effect fade, then compare the last day."""

from src.scenarios import make_scenarios, run_scenario
from src.indicators import summarise, select_day

N_DAYS = 7

final = {}
for name, p in make_scenarios().items():
    r = run_scenario(p, duration_s=N_DAYS * 86400)
    print('%s solved: %s' % (name, r['success']))
    eui_by_day = []
    for day in range(N_DAYS):
        s = summarise(select_day(r, day), p)
        eui_by_day.append(s['EUI_kWh_per_kg'])
        print('   day %d: EUI %.3f kWh/kg, WUI %.3f L/kg, tank end %.1f C' % (
            day + 1, s['EUI_kWh_per_kg'], s['WUI_L_per_kg'], select_day(r, day)['T_tank'][-1]))
    drift = 100 * abs(eui_by_day[-1] - eui_by_day[-2]) / eui_by_day[-2]
    print('   change in EUI between the last two days: %.3f %%' % drift)
    final[name] = summarise(select_day(r, N_DAYS - 1), p)

base = final['A_linear']
print()
print('Last day (day %d) compared with scenario A:' % N_DAYS)
print('%-14s %12s %12s %10s' % ('scenario', 'EUI kWh/kg', 'WUI L/kg', 'recovered'))
for name, s in final.items():
    d_eui = 100 * (s['EUI_kWh_per_kg'] - base['EUI_kWh_per_kg']) / base['EUI_kWh_per_kg']
    d_wui = 100 * (s['WUI_L_per_kg'] - base['WUI_L_per_kg']) / base['WUI_L_per_kg']
    print('%-14s %7.2f (%+5.1f%%) %6.2f (%+5.1f%%) %9.1f %%' % (
          name, s['EUI_kWh_per_kg'], d_eui, s['WUI_L_per_kg'], d_wui, s['water_recovered'] * 100))