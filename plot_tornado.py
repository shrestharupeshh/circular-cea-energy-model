"""plot_tornado.py - tornado diagram from data/sensitivity.csv."""

import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

df = pd.read_csv('data/sensitivity.csv')
df['penalty'] = 100 * (df['EUI_C'] / df['EUI_A'] - 1)

base = df[df['parameter'] == 'baseline'].iloc[0]
df = df[df['parameter'] != 'baseline'].copy()
df['d_EUI'] = 100 * (df['EUI_C'] - base['EUI_C']) / base['EUI_C']          # % change in EUI of C
df['d_pen'] = df['penalty'] - (100 * (base['EUI_C'] / base['EUI_A'] - 1))  # change in C-vs-A penalty, points

names = {'P_lamp': 'Lamp power', 'U_envelope': 'Wall U-value', 'ACH': 'Air changes (ACH)', 'efficacy': 'Lamp efficacy',
         'LAI': 'Leaf area index', 'capacitance_multiplier': 'Thermal mass multiplier',
         'COP_cool': 'Cooling COP', 'COP_dehum': 'Dehumidifier COP', 'RH_setpoint': 'RH setpoint',
         'tank_volume': 'Tank volume', 'tank_UA': 'Tank heat loss (UA)',
         'T_out_mean': 'Outdoor temperature (±5 K)'}

low = df[df['level'].isin([0.8, -5.0])].set_index('parameter')
high = df[df['level'].isin([1.2, 5.0])].set_index('parameter')
order = (low['d_EUI'].abs().combine(high['d_EUI'].abs(), max)).sort_values().index     # smallest first

INK, MUTED, GRID, SURFACE = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
C_LOW, C_HIGH = '#2a78d6', '#eb6834'

fig, axes = plt.subplots(1,2, figsize=(11, 5.5), sharey=True, facecolor=SURFACE)
panels = [(axes[0], 'd_EUI', 'Change in energy use intensity of Scenario C (%)', '%+.1f'),
           (axes[1], 'd_pen', 'Change in the energy penalty of C vs A (percentage points)', '%+.1f')]
ypos = range(len(order))          
for ax, col, xlabel, fmt in panels:
    ax.set_facecolor(SURFACE)
    for y, key in zip(ypos, order):
        for row, colour, shift in ((low.loc[key], C_LOW, 0.17), (high.loc[key], C_HIGH, -0.17)):
            v = round(row[col], 1) + 0.0
            ax.barh(y + shift, v, color=colour, height=0.3, edgecolor='none', zorder=3)
            ax.text(v + (0.12 if v >= 0 else -0.12), y + shift, fmt % v,
                    ha='left' if v >= 0 else 'right', va='center', color=INK, fontsize=8)
    ax.axvline(0, color=MUTED, linewidth=1, zorder=4)
    ax.set_xlabel(xlabel, color=MUTED)
    ax.grid(axis='x', color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)

axes[0].set_yticks(list(ypos))
axes[0].set_yticklabels([names[k] for k in order], color = INK)
axes[0].margins(x=0.18)
axes[1].margins(x=0.18)

fig.legend([Patch(facecolor=C_LOW), Patch(facecolor=C_HIGH)],
            ['Input lowered (-20 %, or outdoor -5 K)', 'Input raised (+20 %, or outdoor +5 K)'],
            loc='lower center', ncol=2, frameon=False, labelcolor=INK, fontsize=10)
fig.suptitle('Which assumptions matter? One-at-a-time sensitivity of scenario C (steady state, day 60)',
            color=INK, fontsize=11)
fig.tight_layout(rect=(0, 0.07, 1, 0.95))
os.makedirs('figures', exist_ok=True)
fig.savefig('figures/tornado.png', dpi=150, facecolor=SURFACE)
print('saved figures/tornado.png')