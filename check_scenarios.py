import numpy as np
from scipy.integrate import solve_ivp
from src.scenarios import BASE, make_scenarios
from src.model import model_full
from src.psychro import abs_humidity

scenarios = make_scenarios()
for name, p in scenarios.items():
    print(name, 'heat_recovery =', p['heat_recovery'], ', water_recovery =', p['water_recovery'])

print('BASE untouched:', BASE['heat_recovery'], BASE['water_recovery'])

weather = {'T_out': lambda t: 10.0 - 5.0 * np.cos(2 * np.pi * t / 86400.0),
           'RH_out': lambda t: 0.70}

y0 = [22.0, abs_humidity(22.0, 0.60), 0.0, 40.0]
for name, p in scenarios.items():
    sol = solve_ivp(model_full, (0, 86400), y0, method='BDF', t_eval=np.arange(0, 86400, 60),
                    args=(p, weather), rtol=1e-6, atol=1e-8)
    print(name, 'solved:', sol.success, ', water recovered: %.2f L' % (sol.y[2][-1] * 1000))