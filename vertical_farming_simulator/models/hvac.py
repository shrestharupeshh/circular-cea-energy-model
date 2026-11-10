"""Model 3: HVAC control (thermal W) and HVAC electricity (electrical W).

Thermal cooling delivered and electrical power consumed are different
quantities linked by the coefficient of performance:

    P_HVAC = Q_HVAC / COP

Control is evaluated once per time step. Because the room balance is linear
over a step, the cooling that brings the room exactly to a target by the end
of the step can be computed directly ("deadbeat" control):

    Q = C_eff * (T_free - T_target) / phi

where T_free is the end-of-step temperature with no cooling and phi is the
response factor from ``models.numerics``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CoolingDecision:
    q_cool_w: float          # sensible cooling delivered (step mean) [W thermal]
    q_required_w: float      # sensible cooling needed to HOLD the setpoint [W thermal]
    q_unmet_w: float         # part of q_required the equipment cannot deliver [W thermal]
    cooling_on: bool         # thermostat state carried to the next step


def cooling_control(mode: str, temp_now_c: float, temp_free_c: float, setpoint_c: float,
                    q_hold_w: float, capacitance_j_k: float, phi_s: float,
                    capacity_available_w: float, deadband_k: float, cooling_on: bool) -> CoolingDecision:
    """Decide the sensible cooling for one step.

    mode
      "ideal"             - holds the setpoint exactly with unlimited capacity
                            (an idealised reference, not achievable equipment)
      "capacity_limited"  - same controller, capped at the available capacity
      "thermostat"        - on/off with hysteresis: starts above setpoint+db/2,
                            runs at full capacity, stops near setpoint-db/2.
                            Cycles shorter than the time step cannot be
                            resolved; they are replaced by their average,
                            which is the capacity-limited result.

    q_hold_w is the net sensible gain evaluated at the setpoint, i.e. the load
    the system must remove to keep the room there. Cooling is never negative.
    """
    deadbeat = capacitance_j_k * (temp_free_c - setpoint_c) / phi_s
    calling = deadbeat > 0.0
    required = max(0.0, q_hold_w) if calling else 0.0

    if mode == "ideal":
        return CoolingDecision(max(0.0, deadbeat), required, 0.0, calling)

    if mode == "capacity_limited":
        q_cool = min(max(0.0, deadbeat), capacity_available_w)
        return CoolingDecision(q_cool, required, max(0.0, required - capacity_available_w), calling)

    if mode == "thermostat":
        if temp_now_c >= setpoint_c + 0.5 * deadband_k or temp_free_c >= setpoint_c + 0.5 * deadband_k:
            cooling_on = True
        elif temp_now_c <= setpoint_c - 0.5 * deadband_k:
            cooling_on = False
        q_cool = 0.0
        if cooling_on:
            temp_at_full_capacity = temp_free_c - capacity_available_w * phi_s / capacitance_j_k
            if temp_at_full_capacity > setpoint_c - 0.5 * deadband_k:
                q_cool = capacity_available_w            # runs flat out for the whole step
            else:
                # The lower band would be crossed inside this step, i.e. the unit
                # switches off part-way through. The step-mean cooling is then the
                # duty-cycle average that brings the room back to the setpoint.
                q_cool = min(max(0.0, deadbeat), capacity_available_w)
                cooling_on = False
        return CoolingDecision(q_cool, required, max(0.0, required - capacity_available_w), cooling_on)

    raise ValueError(f"Unknown HVAC control mode: {mode}")


def heating_control(temp_free_c: float, setpoint_c: float, capacitance_j_k: float,
                    phi_s: float, capacity_w: float) -> float:
    """Heating [W thermal] that lifts the room to the heating setpoint, capped at capacity."""
    deadbeat = capacitance_j_k * (setpoint_c - temp_free_c) / phi_s
    return min(max(0.0, deadbeat), capacity_w)


def electrical_power(thermal_power_w, cop: float):
    """P_electrical = Q_thermal / COP  [W electrical]. Constant COP (documented limitation)."""
    return thermal_power_w / cop
