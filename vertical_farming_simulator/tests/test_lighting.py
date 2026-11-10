"""Model 1: lighting energy, schedule, PPFD and DLI."""

import numpy as np
import pytest

from config.parameters import with_overrides
from models import lighting
from simulation.engine import run_simulation


def lighting_kwh(config, **overrides):
    return run_simulation(with_overrides(config, {"lighting": overrides})).summary["energy_kwh"]["lighting"]


def test_hand_calculated_lighting_energy(baseline_result):
    # 400 m2 * 250 / (2.8 * 0.85) W/m2 = 42 016.8 W; 16 h/day for 30 days
    expected_kwh = 400 * 250 / (2.8 * 0.85) * 16 * 30 / 1000
    assert baseline_result.summary["energy_kwh"]["lighting"] == pytest.approx(expected_kwh, rel=1e-9)


def test_zero_lighting_gives_zero_energy(fast_config):
    assert lighting_kwh(fast_config, input_mode="ppfd", ppfd_umol_m2_s=0.0) == 0.0
    assert lighting_kwh(fast_config, photoperiod_h=0.0) == 0.0


def test_doubling_installed_power_doubles_energy(fast_config):
    one = lighting_kwh(fast_config, input_mode="installed_power", installed_power_w=20000.0)
    two = lighting_kwh(fast_config, input_mode="installed_power", installed_power_w=40000.0)
    assert two == pytest.approx(2 * one, rel=1e-12)


def test_doubling_photoperiod_doubles_energy(fast_config):
    assert lighting_kwh(fast_config, photoperiod_h=16.0) == pytest.approx(
        2 * lighting_kwh(fast_config, photoperiod_h=8.0), rel=1e-12)


def test_dimming_scales_energy(fast_config):
    assert lighting_kwh(fast_config, dimming_level=0.6) == pytest.approx(
        0.6 * lighting_kwh(fast_config, dimming_level=1.0), rel=1e-12)


def test_dli_formula():
    assert lighting.daily_light_integral(250.0, 16.0) == pytest.approx(14.4)
    assert lighting.daily_light_integral(200.0, 12.0) == pytest.approx(8.64)


def test_simulated_dli_matches_formula(baseline_result):
    assert baseline_result.summary["dli_mean_mol_m2_day"] == pytest.approx(14.4, rel=1e-9)
    assert baseline_result.summary["cumulative_light_mol_m2"] == pytest.approx(14.4 * 30, rel=1e-9)
    assert np.allclose(baseline_result.daily()["dli_mol_m2_day"], 14.4)


def test_three_input_modes_are_consistent(config):
    area = 400.0
    from_ppfd = lighting.derive_lighting(config["lighting"], area)
    by_density = dict(config["lighting"], input_mode="power_density",
                      power_density_w_m2=from_ppfd["power_density_w_m2"])
    by_power = dict(config["lighting"], input_mode="installed_power",
                    installed_power_w=from_ppfd["installed_power_w"])
    for other in (lighting.derive_lighting(by_density, area), lighting.derive_lighting(by_power, area)):
        for key, value in from_ppfd.items():
            assert other[key] == pytest.approx(value, rel=1e-12)
    assert from_ppfd["installed_power_w"] == pytest.approx(area * from_ppfd["power_density_w_m2"])


@pytest.mark.parametrize("start,photoperiod", [(6.0, 16.0), (20.0, 16.0), (0.0, 24.0), (13.25, 7.5)])
@pytest.mark.parametrize("dt_min", [1.0, 7.0, 15.0, 60.0])
def test_schedule_average_is_exact_for_any_time_step(config, start, photoperiod, dt_min):
    """Lit hours per day equal the photoperiod even when switch times fall inside a step."""
    cfg = dict(config["lighting"], start_hour=start, photoperiod_h=photoperiod)
    dt_s = dt_min * 60.0
    n = int(round(7 * 86400 / dt_s))
    u, lit = lighting.schedule_fractions(cfg, np.arange(n) * dt_s, dt_s)
    assert u.sum() * dt_s / 3600.0 == pytest.approx(photoperiod * n * dt_s / 86400.0, rel=1e-9)
    assert u.min() >= 0.0 and u.max() <= 1.0


def test_night_schedule_wraps_midnight(config):
    cfg = dict(config["lighting"], start_hour=20.0, photoperiod_h=16.0)
    u, _ = lighting.schedule_fractions(cfg, np.arange(24) * 3600.0, 3600.0)
    assert list(np.flatnonzero(u == 0.0)) == [12, 13, 14, 15, 16, 17, 18, 19]


def test_custom_schedule(config):
    levels = [0.0] * 24
    levels[8], levels[9] = 1.0, 0.5
    cfg = dict(config["lighting"], schedule_type="custom", custom_hourly_fractions=levels)
    u, lit = lighting.schedule_fractions(cfg, np.arange(48) * 1800.0, 1800.0)
    assert u.sum() * 0.5 == pytest.approx(1.5)
    assert lit.sum() * 0.5 == pytest.approx(2.0)


def test_led_heat_uses_heat_fraction():
    assert lighting.led_heat_to_room(1000.0, 0.8) == pytest.approx(800.0)
