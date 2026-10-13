"""model.py - the ODE function: given current state, return rate of change."""

import numpy as np
from src.constants import RHO_AIR, CP_AIR
from src.lighting import lamp_electrical_power, thermal_fraction
from src.envelope import transmission_loss, ventilation_mass_flow, ventilation_sensible

from src.constants import RHO_WATER, LAMBDA
from src.psychro import rh_from_chi, abs_humidity
from src.crop import transpiration
from src.hvac import dehumidifier

from src.storage import tank_capacitance, tank_standing_loss, charge_rate, discharge_rate



def thermal_capacitance(p):
    """Effective thermal capacitance of the space [J/K]"""
    air = RHO_AIR * p['volume'] * CP_AIR
    return air * p['capacitance_multiplier']

def model_temperature_only(t, y, p, weather):
    """Stage 2: temperature only, y = [T_air]. Returns [dT_dt]."""
    T_air, = y
    T_out = weather['T_out'](t)

    P_lamp = lamp_electrical_power(t, p['P_lamp'], p['floor_area'],
                                        p['photoperiod_on'], p['photoperiod_off'])
    Q_lamp = P_lamp * thermal_fraction(p['efficacy'])

    Q_trans = transmission_loss(T_air, T_out, p['U_envelope'], p['area_env'])
    m_dot = ventilation_mass_flow(p['ACH'], p['volume'])
    Q_vent = ventilation_sensible(m_dot, T_air, T_out)

    Q_cool = max(0.0, p['cool_gain'] * (T_air - p['T_setpoint']))
    Q_cool = min(Q_cool, p['cool_capacity'])

    Q_net = Q_lamp - Q_trans - Q_vent - Q_cool
    dT_dt = Q_net / thermal_capacitance(p)
    return [dT_dt]


# ADD 1

def model_coupled(t, y, p, weather):
    """Stage 3: temperature + humidity + recovered water.
    y = [T_air, chi_air, V_recovered]
    """
    T_air, chi_air, V_recovered = y
    T_out = weather['T_out'](t)
    RH = rh_from_chi(T_air, chi_air)

    # --- lighting ---
    P_lamp = lamp_electrical_power(t, p['P_lamp'], p['floor_area'],
                                    p['photoperiod_on'], p['photoperiod_off'])
    f_therm = thermal_fraction(p['efficacy'])
    Q_lamp = P_lamp * f_therm
    R_net = P_lamp * (1.0 - f_therm) / p['floor_area']   # W/m2 to canopy

    # --- crop ---
    E = transpiration(R_net, T_air, RH, p['LAI'])         # kg/m2/s
    M_crop = E * p['floor_area']                          # kg/s total
    Q_latent = M_crop * LAMBDA                             # W, cools the air

    # --- envelope ---
    Q_trans = transmission_loss(T_air, T_out, p['U_envelope'], p['area_env'])
    m_air = ventilation_mass_flow(p['ACH'], p['volume'])
    Q_vent = ventilation_sensible(m_air, T_air, T_out)
    chi_out = abs_humidity(T_out, weather['RH_out'](t))
    M_vent = m_air / RHO_AIR * (chi_air - chi_out)        # kg/s moisture out

    # --- dehumidification (only if recovery enabled) ---
    if p['water_recovery']:
        M_dehum = dehumidifier(RH, p['RH_setpoint'], p['dehum_capacity'])
    else:
        M_dehum = 0.0
    Q_dehum_latent = M_dehum * LAMBDA

    # --- cooling ---
    Q_cool = max(0.0, p['cool_gain'] * (T_air - p['T_setpoint']))
    Q_cool = min(Q_cool, p['cool_capacity'])

    # --- balances ---
    Q_net = Q_lamp - Q_trans - Q_vent - Q_latent - Q_cool + Q_dehum_latent
    dT = Q_net / thermal_capacitance(p)
    dchi = (M_crop - M_dehum - M_vent) / p['volume']
    dV = M_dehum / RHO_WATER                              # m3/s of recovered condensate

    return [dT, dchi, dV]

# ADD 2: AFTER storage.py

def model_full(t, y, p, weather):
    """Stage 4: temperature + humidity + recovered water + thermal tank
    y = [T_air, chi_air, V_recovered, T_tank]"""

    T_air, chi_air, V_recovered, T_tank = y
    T_out = weather['T_out'](t)
    RH = rh_from_chi(T_air, chi_air)

    # --- lighting ---
    P_lamp = lamp_electrical_power(t, p['P_lamp'], p['floor_area'],
                                    p['photoperiod_on'], p['photoperiod_off'])
    f_therm = thermal_fraction(p['efficacy'])
    Q_lamp = P_lamp * f_therm
    R_net = P_lamp * (1.0 - f_therm) / p['floor_area']

    # --- crop ---
    E = transpiration(R_net, T_air, RH, p['LAI'])
    M_crop = E * p['floor_area']
    Q_latent = M_crop * LAMBDA

    # --- envelope ---
    Q_trans = transmission_loss(T_air, T_out, p['U_envelope'], p['area_env'])
    m_air = ventilation_mass_flow(p['ACH'], p['volume'])
    Q_vent = ventilation_sensible(m_air, T_air, T_out)
    chi_out = abs_humidity(T_out, weather['RH_out'](t))
    M_vent = m_air / RHO_AIR * (chi_air - chi_out)

    # --- dehumidification ---
    if p['water_recovery']:
            M_dehum = dehumidifier(RH, p['RH_setpoint'], p['dehum_capacity'])
    else:
            M_dehum = 0.0
    Q_dehum_latent = M_dehum * LAMBDA

    # --- cooling ---
    Q_cool = max(0.0, p['cool_gain'] * (T_air - p['T_setpoint']))
    Q_cool = min(Q_cool, p['cool_capacity'])

    # --- heating demand ---
    Q_heat = max(0.0, p['heat_gain'] * (p['T_heat_setpoint'] - T_air))
    Q_heat = min(Q_heat, p['heat_capacity'])

    # --- thermal tank ---
    if p['heat_recovery']:
            Q_charge = charge_rate(Q_cool, T_tank, p['T_tank_max'])
            Q_discharge = discharge_rate(Q_heat, T_tank, p['T_tank_min'])
            Q_tank_loss = tank_standing_loss(T_tank, T_air, p['tank_UA'])
    else:
            Q_charge = 0.0
            Q_discharge = 0.0
            Q_tank_loss = 0.0

    # --- balances ---
    Q_net = (Q_lamp + Q_heat + Q_dehum_latent + Q_tank_loss
            - Q_trans - Q_vent - Q_latent - Q_cool)
    dT = Q_net / thermal_capacitance(p)
    dchi = (M_crop - M_dehum - M_vent) / p['volume']
    dV = M_dehum / RHO_WATER
    dT_tank = (Q_charge - Q_discharge - Q_tank_loss) / tank_capacitance(p['tank_volume'])

    return (dT, dchi, dV, dT_tank)
