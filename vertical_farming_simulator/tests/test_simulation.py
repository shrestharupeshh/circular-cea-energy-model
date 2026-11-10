"""Coupled simulation: stability, reproducibility, coupling, export, scenarios, weather."""

import io
import json

import numpy as np
import pandas as pd
import pytest

from analysis import scenario_comparison
from config.parameters import default_config, derive_geometry, validate_config, with_overrides
from models import weather
from simulation.engine import run_simulation
from simulation.time_manager import TimeGrid


def test_runs_30_days_with_consistent_time_steps(baseline_result):
    ts = baseline_result.timeseries
    assert len(ts) == 30 * 24 * 12
    assert np.allclose(np.diff(ts["time_h"]), 5.0 / 60.0)
    assert ts["day"].min() == 1 and ts["day"].max() == 30


def test_no_nan_or_infinite_values(baseline_result):
    numeric = baseline_result.timeseries.drop(columns=["cooling_capacity_w"]).to_numpy(dtype=float)
    assert np.isfinite(numeric).all()


def test_reproducible(config, baseline_result):
    again = run_simulation(config)
    pd.testing.assert_frame_equal(again.timeseries, baseline_result.timeseries)
    assert again.summary["energy_kwh"] == baseline_result.summary["energy_kwh"]


def test_input_config_is_not_modified(config):
    before = json.dumps(config, sort_keys=True)
    run_simulation(with_overrides(config, {"simulation": {"duration_days": 1.0}}))
    assert json.dumps(config, sort_keys=True) == before


@pytest.mark.parametrize("dt_min", [1.0, 5.0, 15.0, 60.0])
def test_stable_for_all_supported_time_steps(config, dt_min):
    result = run_simulation(with_overrides(config, {"simulation": {"duration_days": 4.0, "time_step_min": dt_min}}))
    ts = result.timeseries
    assert np.isfinite(ts.drop(columns=["cooling_capacity_w"]).to_numpy(dtype=float)).all()
    assert 15.0 < ts["indoor_temp_c"].min() and ts["indoor_temp_c"].max() < 30.0


def test_results_converge_as_time_step_shrinks(config):
    def run(dt_min):
        s = run_simulation(with_overrides(config, {"simulation": {"time_step_min": dt_min}})).summary
        return s["energy_kwh"]["total"], s["crop"]["marketable_fresh_mass_kg"]
    coarse, base, fine = run(15.0), run(5.0), run(1.0)
    for i in range(2):
        assert base[i] == pytest.approx(fine[i], rel=0.005)
        assert abs(base[i] - fine[i]) <= abs(coarse[i] - fine[i]) + 1e-9


def test_geometry_volume_not_multiplied_by_layers(config):
    geo4 = derive_geometry(config)
    geo8 = derive_geometry(with_overrides(config, {"farm": {"n_layers": 8}}))
    assert geo4["room_volume_m3"] == geo8["room_volume_m3"] == 300.0
    assert geo4["growing_area_m2"] == 400.0 and geo8["growing_area_m2"] == 800.0


def test_coupling_lights_drive_heat_cooling_and_growth(baseline_result):
    day = baseline_result.timeseries[baseline_result.timeseries["day"] == 20]
    on, off = day[day["led_schedule_fraction"] == 1.0], day[day["led_schedule_fraction"] == 0.0]
    assert on["power_lighting_w"].mean() > 0.0 == off["power_lighting_w"].mean()
    assert on["heat_internal_w"].mean() > off["heat_internal_w"].mean()
    assert on["cooling_total_w"].mean() > off["cooling_total_w"].mean()
    assert on["power_hvac_cooling_w"].mean() > off["power_hvac_cooling_w"].mean()
    assert on["growth_rate_per_day"].mean() > 0.0 == off["growth_rate_per_day"].mean()


def test_hotter_outdoor_air_needs_more_cooling(fast_config):
    def cooling(temp_out):
        cfg = with_overrides(fast_config, {"environment": {"weather_mode": "constant", "outdoor_temp_c": temp_out}})
        return run_simulation(cfg).summary["cooling_thermal_kwh_th"]
    assert cooling(35.0) > cooling(20.0) > cooling(5.0)


def test_invalid_configuration_is_rejected(config):
    bad = with_overrides(config, {"hvac": {"cooling_cop": 0.0}, "crop": {"dry_matter_fraction": 0.0},
                                  "lighting": {"photoperiod_h": 30.0}})
    with pytest.raises(ValueError) as error:
        validate_config(bad)
    assert "COP" in str(error.value) and "Dry matter" in str(error.value) and "Photoperiod" in str(error.value)


def test_time_grid():
    grid = TimeGrid.from_config({"duration_days": 30.0, "time_step_min": 15.0})
    assert grid.n_steps == 2880 and grid.dt_s == 900.0 and grid.duration_days == 30.0


def test_csv_and_json_export(baseline_result):
    exported = pd.read_csv(io.StringIO(baseline_result.to_csv()))
    required = ["time_h", "indoor_temp_c", "outdoor_temp_c", "indoor_rh_percent", "outdoor_rh_percent",
                "power_lighting_w", "cooling_total_w", "power_hvac_cooling_w", "power_circulation_fans_w",
                "power_pumps_w", "biomass_dry_g_per_plant", "cum_energy_lighting_kwh", "cum_energy_hvac_kwh",
                "cum_energy_total_kwh"]
    assert set(required) <= set(exported.columns) and len(exported) == 8640
    rerun = run_simulation(json.loads(baseline_result.config_json()))
    assert rerun.summary["energy_kwh"]["total"] == baseline_result.summary["energy_kwh"]["total"]


def test_scenarios_save_load_compare(tmp_path):
    base = with_overrides(default_config(), {"simulation": {"duration_days": 2.0, "time_step_min": 15.0}})
    scenarios = scenario_comparison.example_scenarios(base)
    assert len(scenarios) == 6
    path = scenario_comparison.save_scenario(scenarios["B - High lighting"], tmp_path)
    assert scenario_comparison.load_scenario(path) == scenarios["B - High lighting"]
    assert scenario_comparison.duplicate_scenario(base, "Copy")["scenario_name"] == "Copy"
    results = scenario_comparison.run_scenarios(scenarios)
    table = scenario_comparison.comparison_table(results)
    row = table.loc["Total electricity [kWh]"]
    assert row["B - High lighting"] > row["A - Baseline"] > row["C - Reduced lighting"]
    assert row["E - Improved HVAC"] < row["A - Baseline"]
    assert table.loc["Lighting electricity [kWh]", "D - Night lighting"] == pytest.approx(
        table.loc["Lighting electricity [kWh]", "A - Baseline"])
    diff = scenario_comparison.difference_table(table, "A - Baseline")
    assert "A - Baseline" not in diff.columns and diff.loc["Total electricity [kWh]", "B - High lighting"] > 0


# ---- weather ---------------------------------------------------------------------------

def write_csv(tmp_path, rows, header="timestamp,outdoor_temperature,outdoor_relative_humidity"):
    path = tmp_path / "weather.csv"
    path.write_text(header + "\n" + "\n".join(rows))
    return path


def test_daily_profile_peaks_at_the_chosen_hour(config):
    t = np.arange(24) * 3600.0
    temp, rh, _ = weather.build_weather(config["environment"], t)
    assert int(np.argmax(temp)) == 15 and temp.max() == pytest.approx(26.0) and temp.min() == pytest.approx(14.0)
    assert int(np.argmin(rh)) == 15


def test_weather_csv_fahrenheit_is_converted(tmp_path):
    rows = [f"2025-07-01 {h:02d}:00,{68 + h},{50}" for h in range(24)]
    data, _ = weather.load_weather_csv(write_csv(tmp_path, rows), "F")
    assert data["outdoor_temp_c"].iloc[0] == pytest.approx(20.0)


def test_weather_csv_validation(tmp_path):
    good = [f"2025-07-01 {h:02d}:00,{20 + h % 5},{60}" for h in range(24)]
    with pytest.raises(ValueError, match="explicitly"):
        weather.load_weather_csv(write_csv(tmp_path, good), "K")
    with pytest.raises(ValueError, match="missing required"):
        weather.load_weather_csv(write_csv(tmp_path, good, header="timestamp,temp,rh"), "C")
    with pytest.raises(ValueError, match="duplicate"):
        weather.load_weather_csv(write_csv(tmp_path, good + [good[-1]]), "C")
    with pytest.raises(ValueError, match="between 0 and 100"):
        weather.load_weather_csv(write_csv(tmp_path, good[:-1] + ["2025-07-01 23:00,20,140"]), "C")
    with pytest.raises(ValueError, match="missing or non-numeric"):
        weather.load_weather_csv(write_csv(tmp_path, good[:-1] + ["2025-07-01 23:00,,60"]), "C")
    hot = [f"2025-07-01 {h:02d}:00,{90},{60}" for h in range(24)]
    with pytest.raises(ValueError, match="plausible range"):
        weather.load_weather_csv(write_csv(tmp_path, hot), "C")
    _, warnings = weather.load_weather_csv(write_csv(tmp_path, good[:10] + good[14:]), "C")
    assert any("Irregular" in w for w in warnings)


def test_simulation_with_weather_csv(tmp_path, fast_config):
    rows = [f"2025-07-{1 + h // 24:02d} {h % 24:02d}:00,{25 + 5 * np.sin(h / 24 * 2 * np.pi):.2f},55"
            for h in range(48)]
    cfg = with_overrides(fast_config, {"environment": {"weather_mode": "csv", "csv_temperature_unit": "C",
                                                       "weather_csv_path": str(write_csv(tmp_path, rows))}})
    result = run_simulation(cfg)
    assert any("repeated" in note for note in result.warnings)
    assert 19.0 < result.timeseries["outdoor_temp_c"].min() and result.timeseries["outdoor_temp_c"].max() < 31.0
