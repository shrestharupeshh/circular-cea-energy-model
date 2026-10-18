"""run_convergence.py - do the results depend on the numerical settings?"""

from src.scenarios import make_scenarios, run_scenario
from src.indicators import summarise, select_day

N_DAYS = 7

# (label, solver relative tolerance, solver absolute tolerance, output interval is s)
SETTINGS = [
    ('baseline',    1e-6, 1e-8, 60),
    ('tight solver', 1e-9, 1e-11, 60),
    ('fine output',  1e-6, 1e-8, 10),
    ('both',         1e-9, 1e-11, 10),
]

worst = 0.0
print('%-14s %-13s %11s %10s %10s %10s' %('scenario', 'setting', 'EUI kWh/kg', 'WUI L/kg', 'dEUI %', 'dWUI %'))
for name, p in make_scenarios().items():
    results = {}
    for label, rtol, atol, dt in SETTINGS:
        r = run_scenario(p, duration_s=N_DAYS * 86400, rtol=rtol, atol=atol, dt=dt)
        assert r['success'], '%s / %s did not solve' % (name, label)
        s = summarise(select_day(r, N_DAYS - 1), p)
        results[label] = (s['EUI_kWh_per_kg'], s['WUI_L_per_kg'])

    base_eui, base_wui = results['baseline']
    for label, (eui, wui) in results.items():
        d_eui = 100 * (eui - base_eui) / base_eui
        d_wui = 100 * (wui - base_wui) / base_wui
        worst = max(worst, abs(d_eui), abs(d_wui))
        print('%-14s %-13s %11.4f %10.4f %+10.4f %+10.4f' % (name, label, eui, wui, d_eui, d_wui))

print()
print('Largest change in any indicator: %.4f %%' % worst)