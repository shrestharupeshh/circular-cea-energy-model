"""plot_scenario_comparison.py - headline figure: energy and water for the three scenarios."""

import os
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from src.scenarios import make_scenarios, run_scenario, N_DAYS
from src.indicators import summarise, select_day


names = ['A_linear', 'B_heat', 'C_heat_water']
labels = ['A', 'B', 'C']
legend_text = ['A: no recovery', 'B: heat recovery', 'C: heat + water recovery']
colors = ['#2a78d6', '#eb6834', '#1baf7a']

scenarios = make_scenarios()

def steady_state_summary(p):
    r = run_scenario(p, duration_s=N_DAYS * 86400)
    return summarise(select_day(r, N_DAYS - 1), p)

summaries = {n: steady_state_summary(scenarios[n]) for n in names}

eui = [summaries[n]['EUI_kWh_per_kg'] for n in names]
wui = [summaries[n]['WUI_L_per_kg'] for n in names]

INK = '#0b0b0b'
MUTED = '#52514e'
GRID = '#e4e3df'
SURFACE = '#fcfcfb'

fig, axes = plt.subplots(1, 2, figsize=(10,5), facecolor=SURFACE)

panels = [
    (axes[0], eui, 'Energy use intensity (kWh per kg of produce)', 'Electricity'),
    (axes[1], wui, 'Water use intensity (L fresh water per kg of produce)', 'Fresh water'),
]
for ax, values, ylabel, title in panels:
    ax.set_facecolor(SURFACE)
    ax.bar(labels, values, color=colors, width=0.5, edgecolor='none', zorder=3)
    base = values[0]
    for i, v in enumerate(values):
        pct = round(100 * (v - base) / base, 1) + 0.0      # +0.0 turns -0.0 into 0.0
        text = '%.1f' % v if i == 0 else '%.1f (%+.1f%%)' % (v, pct)
        ax.text(i, v + max(values) * 0.02, text, ha='center', va='bottom',
                color=INK, fontsize=10)
    ax.set_ylim(0, max(values) * 1.18)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.set_title(title, color=INK, fontsize=11, loc='left')
    ax.grid(axis='y', color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)

handles = [Patch(facecolor=c, edgecolor='none') for c in colors]
fig.legend(handles, legend_text, loc='lower center', ncol=3, frameon=False,
           labelcolor=INK, fontsize=10)
fig.suptitle('Circularity trade-off: heat recovery saves almost nothing; water recovery costs energy but cuts fresh water use',
              color=INK, fontsize=11)
fig.text(0.5, 0.925, 'Steady state: day %d of a %d-day simulation' % (N_DAYS, N_DAYS),
         ha='center', va='bottom', color=MUTED, fontsize=9)
fig.tight_layout(rect=(0, 0.07, 1, 0.95))

os.makedirs('figures', exist_ok=True)
fig.savefig('figures/scenario_comparison.png', dpi=200, facecolor=SURFACE)
print('Saved figures/scenario_comparison.png')
plt.show()