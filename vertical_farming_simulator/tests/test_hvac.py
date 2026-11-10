"""Model 3: HVAC control, capacity limits and electricity."""

import numpy as np
import pytest

from config.parameters import with_overrides
from models import hvac
from simulation.engine import run_simulation


def run(config, **hvac_overrides):
    return run_simulation(with_overrides(config, {"hvac": hvac_overrides}))


def test_electricity_equals_thermal_over_cop(baseline_result):
    s = baseline_result.summary
    assert s["energy_kwh"]["hvac_cooling"] == pytest.approx(s["cooling_thermal_kwh_th"] / 3.0, rel=1e-12)
    assert s["cooling_thermal_kwh_th"] == pytest.approx(
        s["cooling_sensible_kwh_th"] + s["cooling_latent_kwh_th"], rel=1e-12)


def test_higher_cop_same_cooling_less_electricity(fast_config):
    low, high = run(fast_config, cooling_cop=3.0), run(fast_config, cooling_cop=4.5)
    assert high.summary["cooling_thermal_kwh_th"] == pytest.approx(low.summary["cooling_thermal_kwh_th"])
    assert high.summary["energy_kwh"]["hvac_cooling"] == pytest.approx(
        low.summary["energy_kwh"]["hvac_cooling"] * 3.0 / 4.5)


def test_cooling_and_hvac_power_are_never_negative(baseline_result):
    ts = baseline_result.timeseries
    for col in ("cooling_sensible_w", "cooling_latent_w", "cooling_unmet_w", "heating_w",
                "power_hvac_cooling_w", "power_hvac_heating_w"):
        assert ts[col].min() >= 0.0


@pytest.mark.parametrize("mode", ["capacity_limited", "thermostat"])
def test_capacity_is_never_exceeded(fast_config, mode):
    result = run(fast_config, control_mode=mode, cooling_capacity_kw=25.0)
    assert result.timeseries["cooling_total_w"].max() <= 25000.0 + 1e-6


def test_undersized_cooling_lets_temperature_rise_and_reports_unmet(fast_config):
    ok, small = run(fast_config, cooling_capacity_kw=60.0), run(fast_config, cooling_capacity_kw=25.0)
    assert ok.summary["cooling_unmet_kwh_th"] == 0.0
    assert ok.summary["indoor_temp_max_c"] == pytest.approx(22.0, abs=1e-6)
    assert small.summary["cooling_unmet_kwh_th"] > 0.0
    assert small.summary["indoor_temp_max_c"] > 24.0          # setpoint is NOT artificially held
    assert any("undersized" in note for note in small.warnings)


def test_more_capacity_never_increases_unmet_demand(fast_config):
    unmet = [run(fast_config, cooling_capacity_kw=c).summary["cooling_unmet_kwh_th"]
             for c in (10.0, 20.0, 30.0, 40.0, 60.0)]
    assert all(a >= b for a, b in zip(unmet, unmet[1:]))
    assert unmet[0] > 0.0 and unmet[-1] == 0.0


def test_ideal_control_holds_setpoint_exactly(fast_config):
    result = run(fast_config, control_mode="ideal", cooling_capacity_kw=1.0)
    assert result.summary["indoor_temp_max_c"] == pytest.approx(22.0, abs=1e-6)
    assert result.summary["cooling_unmet_kwh_th"] == 0.0
    assert any("idealised" in note for note in result.warnings)


def test_thermostat_cycles_inside_deadband(config):
    """With a 1-minute step the on/off cycle is resolved: full capacity, then off."""
    cfg = with_overrides(config, {"simulation": {"duration_days": 1.0, "time_step_min": 1.0},
                                  "hvac": {"control_mode": "thermostat", "thermostat_deadband_k": 1.0}})
    ts = run_simulation(cfg).timeseries
    lit = ts[(ts["led_schedule_fraction"] == 1.0) & (ts["time_h"] > 8.0)]
    assert lit["indoor_temp_c"].max() <= 22.5 + 0.7      # overshoot of at most one step of free rise
    assert lit["indoor_temp_c"].min() >= 21.5 - 1e-6
    at_capacity = np.isclose(lit["cooling_total_w"], 60000.0)
    part_load = lit["cooling_total_w"] < 30000.0
    assert at_capacity.any() and part_load.any()             # full capacity, then mostly off
    assert lit["indoor_temp_c"].std() > 0.1


def test_thermostat_with_coarse_step_reduces_to_cycle_average(fast_config):
    thermostat = run(fast_config, control_mode="thermostat")
    limited = run(fast_config, control_mode="capacity_limited")
    assert thermostat.summary["cooling_thermal_kwh_th"] == pytest.approx(
        limited.summary["cooling_thermal_kwh_th"], rel=0.02)


def test_cooling_decision_unit():
    kwargs = dict(temp_now_c=22.0, setpoint_c=22.0, q_hold_w=5000.0, capacitance_j_k=4e6, phi_s=300.0,
                  deadband_k=1.0, cooling_on=False)
    idle = hvac.cooling_control("capacity_limited", temp_free_c=21.9, capacity_available_w=1e4, **kwargs)
    assert idle.q_cool_w == 0.0 and idle.q_required_w == 0.0
    capped = hvac.cooling_control("capacity_limited", temp_free_c=23.0, capacity_available_w=3000.0, **kwargs)
    assert capped.q_cool_w == 3000.0 and capped.q_unmet_w == pytest.approx(2000.0)
    with pytest.raises(ValueError):
        hvac.cooling_control("magic", temp_free_c=23.0, capacity_available_w=1.0, **kwargs)


def test_heating_holds_minimum_temperature_in_cold_weather(fast_config):
    cold = {"environment": {"weather_mode": "constant", "outdoor_temp_c": -10.0},
            "lighting": {"input_mode": "ppfd", "ppfd_umol_m2_s": 0.0},
            "envelope": {"air_changes_per_hour": 2.0}}
    result = run_simulation(with_overrides(fast_config, cold))
    assert result.summary["heating_thermal_kwh_th"] > 0.0
    assert result.final_state["indoor_temp_c"] == pytest.approx(18.0, abs=1e-6)
    assert np.all(result.timeseries["cooling_sensible_w"] == 0.0)
