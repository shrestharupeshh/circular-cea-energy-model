"""tests/test_psychro.py - the humidity functions against known values."""

from src.psychro import e_sat, vpd, abs_humidity, rh_from_chi


def test_esat_known_values():
    assert abs(e_sat(20.0) - 2339.0) < 15.0
    assert abs(e_sat(25.0) - 3169.0) < 20.0
    assert abs(e_sat(30.0) - 4245.0) < 30.0


def test_vpd_saturated_is_zero():
    assert abs(vpd(24.0, 1.0)) < 1e-9


def test_abs_humidity_known_value():
    chi = abs_humidity(24.0, 0.70)
    assert abs(chi - 0.0152) < 0.001


def test_roundtrip_humidity():
    T, RH = 24.0, 0.70
    chi = abs_humidity(T, RH)
    assert abs(rh_from_chi(T, chi) - RH) < 1e-6