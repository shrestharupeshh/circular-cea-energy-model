"""plot_daily_profile.py - three-panel picture of one simulated day (scenario C)."""

import os
import numpy as np
import matplotlib.pyplot as plt
from src.scenarios import make_scenarios, run_scenario, WEATHER

p = make_scenarios()['C_heat_water']
r = run_scenario(p)

time_h = r['t'] / 3600.0
T_out = WEATHER['T_out'](r['t'])

fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

axes[0].plot(time_h, r['T_air'], label='Air temperature')
axes[0].plot(time_h, T_out, linestyle='--', label='Outdoor temperature')
axes[0].axhline(p['T_setpoint'], color='gray', linestyle=':', label='Cooling setpoint')
axes[0].set_ylabel('Temperature (C)')
axes[0].legend(loc='center left')

axes[1].plot(time_h, r['RH'] * 100, color='tab:blue', label='Room RH')
axes[1].axhline(p['RH_setpoint'] * 100, color='gray', linestyle=':', label='Dehumidifier setpoint')
axes[1].set_ylabel('Relative humidity (%)')
axes[1].legend(loc='lower right')

axes[2].plot(time_h, r['P_lamp'] / 1000.0, label='Lighting')
axes[2].plot(time_h, r['P_cool'] / 1000.0, label='Cooling (electric)')
axes[2].plot(time_h, r['P_dehum'] / 1000.0, label='Dehumidifier (electric)')
axes[2].set_ylabel('Electrical power (kW)')
axes[2].set_xlabel('Time of day (h)')
axes[2].set_xlim(0, 24)
axes[2].legend(loc='center left')

fig.suptitle('Scenario C: one simulated day')
fig.tight_layout()

os.makedirs('figures', exist_ok=True)
fig.savefig('figures/daily_profile.png', dpi=200)
print('Saved figures/daily_profile.png')
plt.show()