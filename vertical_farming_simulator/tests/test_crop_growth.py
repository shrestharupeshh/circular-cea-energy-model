"""Model 5: logistic growth and environmental modifiers."""

import numpy as np
import pytest

from config.parameters import with_overrides
from models import crop_growth
from simulation.engine import run_simulation


def test_logistic_step_matches_analytical_solution():
    b, r, k = 0.05, 0.3, 12.0
    for _ in range(30 * 24):
        b = crop_growth.logistic_step(b, r, k, 3600.0)
    assert b == pytest.approx(crop_growth.logistic_analytical(0.05, r, k, 30.0), rel=1e-10)


def test_simulation_matches_analytical_logistic_when_modifiers_are_off(config):
    cfg = with_overrides(config, {"crop": {"use_temperature_modifier": False, "use_light_modifier": False,
                                           "base_growth_rate_per_day": 0.2}})
    result = run_simulation(cfg)
    expected = crop_growth.logistic_analytical(0.05, 0.2, 12.0, 30.0)
    assert result.final_state["biomass_dry_g_per_plant"] == pytest.approx(expected, rel=1e-9)


def test_zero_growth_rate_gives_no_growth(fast_config):
    result = run_simulation(with_overrides(fast_config, {"crop": {"base_growth_rate_per_day": 0.0}}))
    assert np.all(result.timeseries["biomass_dry_g_per_plant"] == 0.05)
    assert result.final_state["biomass_dry_g_per_plant"] == 0.05


def test_no_light_no_growth(fast_config):
    result = run_simulation(with_overrides(fast_config, {"lighting": {"photoperiod_h": 0.0}}))
    assert result.final_state["biomass_dry_g_per_plant"] == pytest.approx(0.05)


def test_biomass_bounded_and_monotonic(baseline_result):
    b = baseline_result.timeseries["biomass_dry_g_per_plant"]
    assert b.min() >= 0.05 and b.max() <= 12.0
    assert (np.diff(b) >= 0.0).all()
    long_run = crop_growth.logistic_step(11.99, 5.0, 12.0, 30 * 86400.0)
    assert long_run <= 12.0


def test_temperature_modifier_shape():
    f = lambda t: crop_growth.temperature_modifier(t, 4.0, 22.0, 32.0)
    assert f(22.0) == pytest.approx(1.0)
    assert f(4.0) == 0.0 and f(32.0) == 0.0 and f(-5.0) == 0.0 and f(40.0) == 0.0
    temps = np.linspace(-10.0, 45.0, 221)
    values = np.array([f(t) for t in temps])
    assert values.min() >= 0.0 and values.max() <= 1.0
    assert f(12.0) < f(18.0) < f(22.0) > f(27.0) > f(31.0)


def test_light_modifier_saturates():
    f = lambda p: crop_growth.light_modifier(p, 200.0)
    assert f(0.0) == 0.0 and f(200.0) == pytest.approx(0.5)
    assert f(100.0) < f(300.0) < f(1000.0) < 1.0
    assert f(400.0) < 2 * f(200.0)                          # less than proportional


def test_more_light_grows_more_but_growth_rate_saturates(config):
    def run(ppfd):
        # ideal control keeps the room at 22 C so that only the light changes
        cfg = with_overrides(config, {"lighting": {"input_mode": "ppfd", "ppfd_umol_m2_s": ppfd},
                                      "hvac": {"control_mode": "ideal"}})
        result = run_simulation(cfg)
        return result.summary["crop"]["fresh_mass_per_plant_g"], result.timeseries["growth_rate_per_day"].max()
    (m_low, r_low), (m_mid, r_mid), (m_high, r_high) = run(150.0), run(300.0), run(600.0)
    assert m_low < m_mid < m_high <= 12.0 / 0.05
    assert r_low < r_mid < r_high < 0.55                     # never above the base rate
    assert r_mid / r_low < 2.0 and r_high / r_mid < r_mid / r_low   # doubling light less than doubles growth rate


def test_overheated_room_stops_growth(config):
    """600 PPFD with the baseline 60 kW cooling: the room overheats and the crop fails.
    Nothing in the code forces this; it follows from the heat balance and f_T."""
    cfg = with_overrides(config, {"lighting": {"input_mode": "ppfd", "ppfd_umol_m2_s": 600.0}})
    result = run_simulation(cfg)
    assert result.summary["cooling_unmet_kwh_th"] > 0.0
    assert result.summary["indoor_temp_max_c"] > 32.0
    assert result.summary["crop"]["fresh_mass_per_plant_g"] < 5.0
    assert any("validity" in note for note in result.warnings)


def test_totals_consistent_with_density_and_area(baseline_result):
    s, d = baseline_result.summary, baseline_result.derived
    assert d["n_plants"] == pytest.approx(25.0 * 100.0 * 4)
    crop = s["crop"]
    assert crop["total_dry_mass_kg"] == pytest.approx(crop["dry_mass_per_plant_g"] * 10000 / 1000)
    assert crop["total_fresh_mass_kg"] == pytest.approx(crop["total_dry_mass_kg"] / 0.05)
    assert crop["marketable_fresh_mass_kg"] == pytest.approx(crop["total_fresh_mass_kg"] * 0.85)
    assert crop["total_dry_mass_kg"] < crop["marketable_fresh_mass_kg"]   # dry is never reported as fresh


def test_occupied_fraction_scales_plants(config):
    half = run_simulation(with_overrides(config, {"crop": {"occupied_fraction": 0.5},
                                                  "simulation": {"duration_days": 1.0}}))
    assert half.derived["n_plants"] == pytest.approx(5000.0)


def test_transpiration_grows_with_canopy(baseline_result):
    daily = baseline_result.timeseries.groupby("day")["transpiration_kg_s"].mean()
    assert daily.iloc[-1] > 10 * daily.iloc[0] > 0.0
