"""Energy accounting: sums, units, intensity, cost."""

import math

import pytest

from analysis import energy_analysis
from config.parameters import with_overrides
from simulation.engine import run_simulation


def test_total_is_sum_of_components(baseline_result):
    e = baseline_result.summary["energy_kwh"]
    parts = ["lighting", "hvac_cooling", "hvac_heating", "circulation_fans", "ventilation_fans",
             "pumps", "auxiliary"]
    assert e["total"] == pytest.approx(sum(e[p] for p in parts), rel=1e-12)
    assert e["total"] == pytest.approx(e["lighting"] + e["hvac"] + e["fans"] + e["pumps"] + e["auxiliary"])
    ts = baseline_result.timeseries
    assert ts["cum_energy_total_kwh"].iloc[-1] == pytest.approx(e["total"], rel=1e-12)
    assert ts["cum_energy_lighting_kwh"].iloc[-1] == pytest.approx(e["lighting"], rel=1e-12)
    assert baseline_result.daily()["energy_total_kwh"].sum() == pytest.approx(e["total"], rel=1e-12)


def test_constant_loads_match_hand_calculation(baseline_result):
    e = baseline_result.summary["energy_kwh"]
    assert e["circulation_fans"] == pytest.approx(1.5 * 720)
    assert e["pumps"] == pytest.approx(0.5 * 720)
    assert e["auxiliary"] == pytest.approx(0.5 * 720)
    assert e["ventilation_fans"] == pytest.approx(1000 * (0.2 * 300 / 3600) * 720 / 1000)


def test_thermal_cooling_is_not_part_of_electrical_total(baseline_result):
    s = baseline_result.summary
    e = s["energy_kwh"]
    non_hvac = e["lighting"] + e["fans"] + e["pumps"] + e["auxiliary"]
    assert e["total"] - non_hvac == pytest.approx(s["cooling_thermal_kwh_th"] / 3.0 + e["hvac_heating"])
    assert e["total"] < non_hvac + s["cooling_thermal_kwh_th"]


def test_shares_sum_to_100(baseline_result):
    assert sum(baseline_result.summary["energy_shares_percent"].values()) == pytest.approx(100.0)


def test_energy_intensity(baseline_result):
    s = baseline_result.summary
    harvest = s["crop"]["marketable_fresh_mass_kg"]
    assert s["energy_intensity_kwh_per_kg"]["total"] == pytest.approx(s["energy_kwh"]["total"] / harvest)
    assert sum(s["energy_intensity_kwh_per_kg"][k] for k in ("lighting", "hvac", "auxiliary_loads")) == \
        pytest.approx(s["energy_intensity_kwh_per_kg"]["total"])
    assert energy_analysis.energy_intensity(100.0, 4.0) == 25.0


def test_zero_harvest_gives_nan_not_an_error(fast_config):
    assert math.isnan(energy_analysis.energy_intensity(100.0, 0.0))
    result = run_simulation(with_overrides(fast_config, {"crop": {"plant_density_per_m2": 0.0}}))
    assert math.isnan(result.summary["energy_intensity_kwh_per_kg"]["total"])
    assert math.isnan(result.summary["cost"]["per_kg"])
    assert any("undefined" in note for note in result.warnings)


def test_cost(baseline_result):
    s = baseline_result.summary
    assert s["cost"]["total"] == pytest.approx(s["energy_kwh"]["total"] * 0.15)
    assert s["cost"]["per_day"] == pytest.approx(s["cost"]["total"] / 30.0)
    assert baseline_result.daily()["cost_per_day"].sum() == pytest.approx(s["cost"]["total"])
