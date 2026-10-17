"""indicators.py - turn simulation curves into the numbers that matter."""

import numpy as np

def simulated_yield_kg(params, duration_s):
    """Produce harvested during the simulated period (kg).
    The guide gives yield per 30-day cycle, so we scale it to the length of the run."""

    cycle_yield = params['floor_area'] * params['yield_kg_per_m2_per_cycle']
    cycle_s = params['cycle_days'] * 86400.0
    return cycle_yield * duration_s / cycle_s

def energy_use_intensity(P_total_W, t_s, yield_kg):
    """kWh of electricity per kg of produce."""
    energy_J = np.trapezoid(P_total_W, t_s)
    return (energy_J / 3.6e6) / yield_kg

def water_use_intensity(M_fresh_kg_s, t_s, yield_kg):
    """Liters of fresh water per kg of produce."""
    water_kg = np.trapezoid(M_fresh_kg_s, t_s)
    return water_kg / yield_kg

def recovery_fraction(M_recovered_kg_s, M_transpired_kg_s, t_s):
    """Fraction of transpired water captured as condensate."""
    rec = np.trapezoid(M_recovered_kg_s, t_s)
    tot = np.trapezoid(M_transpired_kg_s, t_s)
    return rec / tot if tot > 0 else 0.0

def summarise(results, params):
    t = results['t']
    yield_kg = simulated_yield_kg(params, t[-1] - t[0])
    return {
        'EUI_kWh_per_kg': energy_use_intensity(results['P_total'], t, yield_kg),
        'WUI_L_per_kg': water_use_intensity(results['M_fresh'], t, yield_kg),
        'water_recovered': recovery_fraction(results['M_dehum'], results['M_crop'], t)
    }

def select_day(results, day):
    """Return the part of a multi-day run that falls in day number `day` (0 = first day)."""
    t = results['t']
    mask = (t >= day * 86400.0) & (t <= (day + 1) * 86400.0)
    return {key: (value[mask] if isinstance(value, np.ndarray) else value)
            for key, value in results.items()}