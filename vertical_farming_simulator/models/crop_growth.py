"""Model 5: lettuce growth (logistic with environmental modifiers) and transpiration.

State: B = dry biomass per plant [g dry / plant].

    dB/dt = r_eff * B * (1 - B / K),   r_eff = r_base * f_T * f_L * f_CO2 * f_VPD

Every modifier lies in [0, 1], so growth is never negative. f_CO2 and f_VPD
are placeholders fixed at 1 (not yet modelled). This is a transparent
comparative model, NOT a calibrated or validated crop model.
"""

from __future__ import annotations

import math
from typing import Any

from models.constants import H_FG, J_PER_UMOL_PAR, P_ATM, EPSILON, SECONDS_PER_DAY


def temperature_modifier(temp_c: float, t_min: float, t_opt: float, t_max: float) -> float:
    """Cardinal-temperature (beta) response, 0 at T_min and T_max, 1 at T_opt.

        f_T = ((T_max - T)/(T_max - T_opt)) * ((T - T_min)/(T_opt - T_min))^((T_opt - T_min)/(T_max - T_opt))

    Smooth, single-peaked, and zero outside [T_min, T_max].
    """
    if temp_c <= t_min or temp_c >= t_max:
        return 0.0
    exponent = (t_opt - t_min) / (t_max - t_opt)
    value = ((t_max - temp_c) / (t_max - t_opt)) * ((temp_c - t_min) / (t_opt - t_min)) ** exponent
    return min(1.0, max(0.0, value))


def light_modifier(ppfd: float, half_saturation_ppfd: float) -> float:
    """Saturating light response f_L = PPFD / (PPFD + K_L), in [0, 1)."""
    if ppfd <= 0.0:
        return 0.0
    return ppfd / (ppfd + half_saturation_ppfd)


def co2_modifier() -> float:
    """Placeholder: CO2 is not modelled, so f_CO2 = 1."""
    return 1.0


def vpd_modifier() -> float:
    """Placeholder: VPD stress on growth is not modelled, so f_VPD = 1."""
    return 1.0


def effective_growth_rate(crop: dict[str, Any], temp_c: float, ppfd_when_lit: float, lit_fraction: float) -> float:
    """r_eff [1/day], averaged over a step in which the lights are on for ``lit_fraction``.

    With the light modifier enabled there is no growth in darkness
    (f_L(0) = 0), so r_base is the relative growth rate under saturating
    light at the optimum temperature.
    """
    f_t = temperature_modifier(temp_c, crop["temp_min_c"], crop["temp_opt_c"], crop["temp_max_c"]) \
        if crop["use_temperature_modifier"] else 1.0
    f_l = lit_fraction * light_modifier(ppfd_when_lit, crop["light_half_saturation_ppfd"]) \
        if crop["use_light_modifier"] else 1.0
    return crop["base_growth_rate_per_day"] * f_t * f_l * co2_modifier() * vpd_modifier()


def logistic_step(biomass: float, rate_per_day: float, capacity: float, dt_s: float) -> float:
    """Exact solution of the logistic equation over one step (rate held constant).

        B(t+dt) = K * B / (B + (K - B) * exp(-r * dt))

    Exact, so B stays within [0, K] for any time step.
    """
    if biomass <= 0.0 or rate_per_day <= 0.0:
        return max(0.0, biomass)
    decay = math.exp(-rate_per_day * dt_s / SECONDS_PER_DAY)
    return capacity * biomass / (biomass + (capacity - biomass) * decay)


def logistic_analytical(initial: float, rate_per_day: float, capacity: float, time_days: float) -> float:
    """Closed-form logistic solution B(t) for constant r, used for verification."""
    return capacity / (1.0 + (capacity / initial - 1.0) * math.exp(-rate_per_day * time_days))


def leaf_area_index(biomass: float, crop: dict[str, Any]) -> float:
    """LAI = LAI_max * B / K  (canopy grows in proportion to biomass; assumption)."""
    return crop["max_leaf_area_index"] * biomass / crop["max_dry_mass_g"]


def transpiration_coefficients(crop: dict[str, Any], biomass: float, ppfd: float, lit_fraction: float,
                               e_sat_pa: float, w_now: float, occupied_area_m2: float) -> tuple[float, float]:
    """Transpiration as a linear function of humidity ratio: m = m0 - g * w  [kg/s].

    Latent flux per m2 of crop (simplified Penman-Monteith-type form, carried
    over from the Circular CEA model in this repository):

        lambda*E = a * R_PAR * (1 - exp(-k*LAI)) + b * LAI * s_dark * VPD     [W/m2]

    R_PAR = PPFD * 0.22 J/umol, s_dark reduces the VPD term in darkness
    (stomatal closure). VPD = e_sat(T) - e, and e is linearised in w
    (e ~ w * P / (0.622 + w_now)) so the moisture balance stays linear.
    """
    if not crop["transpiration_enabled"] or occupied_area_m2 <= 0.0:
        return 0.0, 0.0
    lai = leaf_area_index(biomass, crop)
    interception = 1.0 - math.exp(-crop["light_extinction_coeff"] * lai)
    light_term = crop["transpiration_light_coeff"] * ppfd * J_PER_UMOL_PAR * interception
    dark = crop["dark_transpiration_factor"]
    vpd_coeff = crop["transpiration_vpd_coeff_w_m2_pa"] * lai * (dark + (1.0 - dark) * lit_fraction)
    slope = P_ATM / (EPSILON + w_now)
    m0 = occupied_area_m2 * (light_term + vpd_coeff * e_sat_pa) / H_FG
    g = occupied_area_m2 * vpd_coeff * slope / H_FG
    if m0 - g * w_now <= 0.0:
        return 0.0, 0.0  # no condensation onto leaves: transpiration is floored at zero
    return m0, g


def harvest(biomass_per_plant_g: float, n_plants: float, dry_matter_fraction: float,
            marketable_fraction: float) -> dict[str, float]:
    """Convert dry biomass per plant into farm totals [kg].

    fresh = dry / dry_matter_fraction;  marketable = fresh * marketable_fraction.
    Dry, fresh and marketable mass are reported separately on purpose.
    """
    dry_kg = biomass_per_plant_g * n_plants / 1000.0
    fresh_kg = dry_kg / dry_matter_fraction
    return {
        "dry_mass_per_plant_g": biomass_per_plant_g,
        "fresh_mass_per_plant_g": biomass_per_plant_g / dry_matter_fraction,
        "total_dry_mass_kg": dry_kg,
        "total_fresh_mass_kg": fresh_kg,
        "marketable_fresh_mass_kg": fresh_kg * marketable_fraction,
    }
