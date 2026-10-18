"""tests/test_conservation.py - does the model obey conservation of water and energy?

Conservation only proves the bookkeeping is consistent. It passes even on wrong inputs,
so the last two tests also pin the reference numbers we validated by hand."""

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from src.constants import RHO_AIR
from src.model import model_full
from src.psychro import abs_humidity, rh_from_chi
from src.envelope import ventilation_mass_flow
from src.crop import transpiration
from src.hvac import dehumidifier
from src.lighting import lamp_electrical_power, thermal_fraction
from src.storage import tank_capacitance, charge_rate, discharge_rate
from src.scenarios import make_scenarios, run_scenario, WEATHER, T0, RH0, T_TANK0
from src.indicators import summarise, select_day

@pytest.fixture(scope='module')
def solution():
    """Scenario C for one day, solved tightly (rtol 1e-8) so errors are the model's, not the solver's."""
    p = make_scenarios()['C_heat_water']
    y0 =  [T0, abs_humidity(T0, RH0), 0.0, T_TANK0]
    t_eval = np.arange(0, 86401, 60)
    sol = solve_ivp(model_full, (0, 86400), y0, method='BDF', t_eval=t_eval,
                    args=(p, WEATHER), rtol=1e-8, atol=1e-10)
    assert sol.success
    return p, sol.t, sol.y


def test_water_balance_closes(solution):
    p, t, (T_air, chi_air, V_rec, T_tank) = solution
    RH = rh_from_chi(T_air, chi_air)
    P_lamp = lamp_electrical_power(t, p['P_lamp'], p['floor_area'],
                                    p['photoperiod_on'], p['photoperiod_off'])
    f_therm = thermal_fraction(p['efficacy'])
    R_net = P_lamp * (1.0 - f_therm) / p['floor_area']
    M_crop = transpiration(R_net, T_air, RH, p['LAI']) * p['floor_area']
    M_dehum = np.array([dehumidifier(r, p['RH_setpoint'], p['dehum_capacity']) for r in RH])
    m_air = ventilation_mass_flow(p['ACH'], p['volume'])
    chi_out = abs_humidity(WEATHER['T_out'](t), WEATHER['RH_out'](t))
    M_vent = m_air / RHO_AIR * (chi_air - chi_out)

    produced = np.trapezoid(M_crop, t)
    removed = np.trapezoid(M_dehum + M_vent, t)
    stored = p['volume'] * (chi_air[-1] - chi_air[0])
    residual = produced - removed - stored
    assert abs(residual) / produced < 0.001


def test_tank_energy_balance_closes(solution):
    p, t, (T_air, chi_air, V_rec, T_tank) = solution
    Q_cool = np.minimum(np.maximum(0.0, p['cool_gain'] * (T_air - p['T_setpoint'])),
                        p['cool_capacity'])
    Q_heat = np.minimum(np.maximum(0.0, p['heat_gain'] * (p['T_heat_setpoint'] - T_air)),
                        p['heat_capacity'])
    E_in = np.trapezoid(charge_rate(Q_cool, T_tank, p['T_tank_max']), t)
    E_out = np.trapezoid(discharge_rate(Q_heat, T_tank, p['T_tank_min']), t)
    E_loss = np.trapezoid(p['tank_UA'] *  (T_tank - T_air), t)
    E_stored = tank_capacitance(p['tank_volume']) * (T_tank[-1] - T_tank[0])
    residual = E_in - E_out - E_loss - E_stored
    assert abs(residual) / E_in < 0.001


def test_reference_tank_energies(solution):
    """The numbers we checked by hand on the first day (MJ). Guards against wrong inputs."""
    p, t, (T_air, chi_air, V_rec, T_tank) = solution
    Q_cool = np.minimum(np.maximum(0.0, p['cool_gain'] * (T_air - p['T_setpoint'])),
                        p['cool_capacity'])
    Q_heat = np.minimum(np.maximum(0.0, p['heat_gain'] * (p['T_heat_setpoint'] - T_air)),
                        p['heat_capacity'])
    E_in = np.trapezoid(charge_rate(Q_cool, T_tank, p['T_tank_max']), t) / 1e6
    E_out = np.trapezoid(discharge_rate(Q_heat, T_tank, p['T_tank_min']), t) / 1e6
    E_loss = np.trapezoid(p['tank_UA'] * (T_tank - T_air), t) / 1e6
    E_stored = tank_capacitance(p['tank_volume']) * (T_tank[-1] - T_tank[0]) / 1e6
    assert E_in == pytest.approx(202.0, abs=0.5)
    assert E_out == pytest.approx(32.4, abs=0.2)
    assert E_loss == pytest.approx(24.0, abs=0.2)
    assert E_stored == pytest.approx(145.5, abs=0.5)


def test_reference_scenario_results():
    """Steady-state results (day 7 of 7) that we validated and that the README QUOTES."""
    expected = {'A_linear': (25.34, 7.50), 'B_heat': (24.55, 7.51), 'C_heat_water': (28.22, 2.53)}
    for name, p in make_scenarios().items():
        r = run_scenario(p, duration_s=7 * 86400)
        assert r['success']
        s = summarise(select_day(r, 6), p)
        eui, wui = expected[name]
        assert s['EUI_kWh_per_kg'] == pytest.approx(eui, abs=0.02)
        assert s['WUI_L_per_kg'] == pytest.approx(wui, abs=0.02)