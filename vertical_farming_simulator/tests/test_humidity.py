"""Model 4: psychrometrics and the moisture balance."""

import numpy as np
import pytest

from config.parameters import with_overrides
from models import humidity
from models.constants import H_FG
from simulation.engine import run_simulation


def test_saturation_pressure_reference_values():
    # Standard table values: 0 C 611 Pa, 20 C 2339 Pa, 25 C 3169 Pa, 40 C 7384 Pa
    for temp_c, expected in [(0.0, 611.0), (20.0, 2339.0), (25.0, 3169.0), (40.0, 7384.0)]:
        assert humidity.saturation_vapor_pressure(temp_c) == pytest.approx(expected, rel=0.003)


def test_humidity_ratio_reference_value():
    # 25 C, 50 % RH at sea level: about 9.9 g/kg
    assert humidity.humidity_ratio(25.0, 0.5) == pytest.approx(0.0099, rel=0.01)


@pytest.mark.parametrize("temp_c", [5.0, 18.0, 22.0, 30.0])
@pytest.mark.parametrize("rh", [0.1, 0.5, 0.7, 1.0])
def test_rh_round_trip(temp_c, rh):
    w = humidity.humidity_ratio(temp_c, rh)
    assert w > 0.0
    assert humidity.relative_humidity(temp_c, w) == pytest.approx(rh, rel=1e-12)


def test_warming_lowers_rh_at_constant_humidity_ratio():
    w = humidity.humidity_ratio(20.0, 0.7)
    assert humidity.relative_humidity(25.0, w) < 0.7 < humidity.relative_humidity(16.0, w)


def test_vpd_zero_at_saturation():
    assert humidity.vapor_pressure_deficit(22.0, humidity.humidity_ratio(22.0, 1.0)) == pytest.approx(0.0, abs=1e-9)


def test_humidity_stays_physical(baseline_result):
    ts = baseline_result.timeseries
    assert ts["indoor_w_kg_kg"].min() > 0.0
    assert ts["indoor_rh_percent"].min() > 0.0
    assert ts["indoor_rh_percent"].max() <= 100.0 + 1e-6
    assert ts["transpiration_kg_s"].min() >= 0.0


def test_water_mass_balance_closes_every_step(baseline_result):
    """M_da dw/dt = ventilation + transpiration - removal - condensation."""
    ts, r = baseline_result.timeseries, baseline_result
    w = np.append(ts["indoor_w_kg_kg"].to_numpy(), r.final_state["indoor_w_kg_kg"])
    stored = r.derived["dry_air_mass_kg"] * np.diff(w) / r.summary["time_step_s"]
    flows = (ts["moisture_ventilation_kg_s"] + ts["transpiration_kg_s"]
             - ts["moisture_removed_kg_s"] - ts["condensation_kg_s"])
    assert np.allclose(stored, flows, atol=1e-9 * ts["transpiration_kg_s"].max() + 1e-15)


def test_dehumidification_lowers_humidity_ratio(fast_config):
    on = run_simulation(with_overrides(fast_config, {"crop": {"initial_dry_mass_g": 8.0}}))
    off = run_simulation(with_overrides(fast_config, {"crop": {"initial_dry_mass_g": 8.0},
                                                      "hvac": {"dehumidification_enabled": False}}))
    assert on.summary["moisture_removed_kg"] > 0.0 and off.summary["moisture_removed_kg"] == 0.0
    assert on.timeseries["indoor_w_kg_kg"].mean() < off.timeseries["indoor_w_kg_kg"].mean()
    # the RH target is evaluated at the start-of-step temperature, so RH can sit
    # slightly above the setpoint while the room is cooling down
    assert on.summary["indoor_rh_max_percent"] <= 70.0 + 0.5


def test_latent_cooling_equals_moisture_removed_times_latent_heat(baseline_result):
    s = baseline_result.summary
    assert s["cooling_latent_kwh_th"] * 3.6e6 == pytest.approx(s["moisture_removed_kg"] * H_FG, rel=1e-12)


def test_constant_source_no_removal_matches_analytical_solution(config):
    """Sealed room at constant temperature with outdoor air exchange only:
    w(t) = w_out + (w0 - w_out) exp(-ACH * t)."""
    cfg = with_overrides(config, {
        "crop": {"transpiration_enabled": False},
        "lighting": {"input_mode": "ppfd", "ppfd_umol_m2_s": 0.0},
        "equipment": {"circulation_fan_power_w": 0.0, "pump_power_w": 0.0, "auxiliary_power_w": 0.0,
                      "ventilation_fan_sfp_w_per_m3s": 0.0},
        "environment": {"weather_mode": "constant", "outdoor_temp_c": 22.0, "outdoor_rh_percent": 30.0},
        "envelope": {"air_changes_per_hour": 1.0},
        "hvac": {"dehumidification_enabled": False, "heating_enabled": False},
        "simulation": {"initial_temp_c": 22.0, "initial_rh_percent": 80.0, "duration_days": 1.0},
    })
    result = run_simulation(cfg)
    w0, w_out = humidity.humidity_ratio(22.0, 0.8), humidity.humidity_ratio(22.0, 0.3)
    hours = result.timeseries["time_h"].to_numpy()
    exact = w_out + (w0 - w_out) * np.exp(-1.0 * hours)
    assert np.allclose(result.timeseries["indoor_w_kg_kg"], exact, rtol=1e-10)


def test_saturated_room_condenses_instead_of_exceeding_100_percent(fast_config):
    wet = with_overrides(fast_config, {"crop": {"initial_dry_mass_g": 10.0},
                                       "hvac": {"dehumidification_enabled": False},
                                       "envelope": {"air_changes_per_hour": 0.0}})
    result = run_simulation(wet)
    assert result.summary["indoor_rh_max_percent"] <= 100.0 + 1e-6
    assert any("saturation" in note for note in result.warnings) or result.summary["condensation_kg"] == 0.0
