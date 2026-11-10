"""Model 2: single-zone (well-mixed) thermal balance of the growing room.

    C_eff * dT_in/dt = Q_internal + Q_envelope + Q_ventilation
                       - Q_transpiration - Q_cool + Q_heat          [W]

Sign convention: every Q on the right is a GAIN to room air when positive.
Q_transpiration is the sensible heat that the crop converts to latent heat
(water vapour); it reappears as the latent load of the dehumidifier and is
not counted twice.
"""

from __future__ import annotations

from models.constants import CP_AIR, RHO_AIR, SECONDS_PER_HOUR


def effective_capacitance(room_volume_m3: float, thermal_mass_multiplier: float) -> float:
    """C_eff = multiplier * rho_air * V_room * cp_air  [J/K].

    The multiplier lumps racks, water, plants and surfaces in with the air.
    """
    return thermal_mass_multiplier * RHO_AIR * room_volume_m3 * CP_AIR


def envelope_heat_gain(ua_w_k: float, temp_out_c: float, temp_in_c: float) -> float:
    """Q_envelope = U * A * (T_out - T_in)  [W]; positive = gain to the room."""
    return ua_w_k * (temp_out_c - temp_in_c)


def ventilation_flow_m3_s(air_changes_per_hour: float, room_volume_m3: float) -> float:
    """V_dot = ACH * V_room / 3600  [m3/s]."""
    return air_changes_per_hour * room_volume_m3 / SECONDS_PER_HOUR


def ach_from_flow(flow_m3_s: float, room_volume_m3: float) -> float:
    """ACH = V_dot * 3600 / V_room  [1/h]."""
    return flow_m3_s * SECONDS_PER_HOUR / room_volume_m3


def ventilation_conductance(flow_m3_s: float) -> float:
    """rho_air * cp_air * V_dot  [W/K]."""
    return RHO_AIR * CP_AIR * flow_m3_s


def ventilation_heat_gain(flow_m3_s: float, temp_out_c: float, temp_in_c: float) -> float:
    """Q_ventilation = rho_air * cp_air * V_dot * (T_out - T_in)  [W]."""
    return ventilation_conductance(flow_m3_s) * (temp_out_c - temp_in_c)


def internal_sensible_heat(led_heat_w: float, circulation_fan_w: float, fan_heat_fraction: float,
                           ventilation_fan_w: float, vent_fan_heat_fraction: float,
                           pump_w: float, pump_heat_fraction: float,
                           auxiliary_w: float, auxiliary_heat_fraction: float) -> float:
    """Sensible heat released in the room by equipment [W].

    Each electrical load has its own heat fraction: electricity consumed and
    heat delivered to room air are not assumed to be equal.
    """
    return (led_heat_w
            + circulation_fan_w * fan_heat_fraction
            + ventilation_fan_w * vent_fan_heat_fraction
            + pump_w * pump_heat_fraction
            + auxiliary_w * auxiliary_heat_fraction)


def steady_state_temperature(q_gain_w: float, conductance_w_k: float, temp_out_c: float,
                             q_cool_w: float = 0.0) -> float:
    """Analytical equilibrium: T_ss = T_out + (Q_gain - Q_cool) / (UA + rho*cp*V_dot)."""
    return temp_out_c + (q_gain_w - q_cool_w) / conductance_w_k
