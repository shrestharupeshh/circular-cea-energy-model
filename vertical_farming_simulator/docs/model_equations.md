# Model equations

Every equation the simulator solves, with units and the file that implements it.
SI units are used internally (W, J, kg, s, Pa, °C for temperatures and K for
differences). Energy is reported in kWh (electrical) or kWh thermal; the two
are never added. Parameter values and their rationale are in `assumptions.md`.

Symbols marked *(input)* are scenario parameters in `config/default_config.json`.
Constants are in `models/constants.py`.

## 0. Geometry and time

| Equation | Units | Code |
|---|---|---|
| V_room = A_footprint × h_room | m³ | `config/parameters.py: derive_geometry` |
| A_g = A_footprint × n_layers (growing area) | m² | same |
| A_crop = A_g × f_occupied | m² | same |
| N_plants = A_crop × plant density | plants | same |
| A_wall = 4 √A_footprint × h_room (square footprint, unless overridden) | m² | same |

Room volume is not multiplied by the number of layers. Time runs from t = 0
(00:00 on day 1) in n equal steps of Δt (`simulation/time_manager.py`).
Step-mean powers are stored, so every energy is E = Σ P Δt exactly.

## 1. Lighting (`models/lighting.py`)

**Photon balance, uniform light on the growing area**

    P_LED  = A_g × P_density                         [W electrical]
    PPFD   = P_density × η × f_u                     [µmol/m²/s]
    Φ      = P_LED × η                               [µmol/s emitted]

η = photon efficacy [µmol/J] *(input)*, f_u = utilisation factor, the fraction of
emitted photons that lands on the growing area *(input)*. The user specifies
one of PPFD, P_density or P_LED; the other two follow from these equations
(`derive_lighting`). There is no universal PPFD-to-watt conversion: it depends
on η and f_u.

**Schedule and power**

    P_lighting(t) = P_LED × u_LED(t),   0 ≤ u_LED ≤ 1
    u_LED = dimming level inside the daily on-window, 0 outside

The on-window is [start, start + photoperiod), wraps past midnight and
repeats every 24 h; alternatively 24 hourly fractions can be given. u_LED is
averaged exactly over each time step (`schedule_fractions`), so lighting
energy does not depend on the time step.

**Energy, DLI, heat**

    E_lighting = Σ P_lighting Δt / 3.6e6                         [kWh]
    DLI = PPFD × photoperiod[s] / 10⁶ = Σ_day PPFD Δt / 10⁶      [mol/m²/day]
    Q_LED = f_LED,heat × P_lighting                              [W thermal]

f_LED,heat *(input)* is the fraction of LED electricity that ends up as
sensible heat in the room. Limitation: radiant and convective paths, and the
delay between light absorption and air heating, are not distinguished; the
delay is partly represented by the lumped thermal mass.

## 2. Indoor temperature (`models/thermal.py`, `simulation/engine.py`)

Single well-mixed zone:

    C_eff dT_in/dt = Q_internal + Q_envelope + Q_ventilation − Q_transpiration − Q_cool + Q_heat     [W]

| Term | Equation | Notes |
|---|---|---|
| C_eff | m_C × ρ_air × V_room × c_p,air  [J/K] | m_C = thermal mass multiplier *(input)* |
| Q_internal | Q_LED + Σ P_i × f_i | fans, pumps, other equipment, each with its own heat fraction f_i *(input)* |
| Q_envelope | Σ U_j A_j × (T_out − T_in) | walls, roof, floor; U_j *(input)*; all surfaces see outdoor air temperature |
| Q_ventilation | ρ_air c_p,air V̇ (T_out − T_in) | V̇ = ACH × V_room / 3600  [m³/s] |
| Q_transpiration | ṁ_transp × h_fg | sensible heat the crop converts to latent heat (section 4) |
| Q_cool, Q_heat | from the controller (section 3) | thermal W, ≥ 0 |

Positive Q_envelope and Q_ventilation are gains to the room.

**Numerical method.** With inputs held constant over a step the balance is
dT/dt = a − kT with k = (ΣUA + ρ c_p V̇)/C_eff. It is advanced with its exact
solution (`models/numerics.py: linear_step`):

    T(t+Δt) = T + (a − kT) φ,    φ = (1 − e^(−kΔt)) / k

This is unconditionally stable. The only discretisation error is holding the
inputs (weather, schedule, transpiration, control action) constant within a
step. The step-mean temperature T̄ is also returned so the stored heat flows
satisfy C_eff ΔT/Δt = Σ Q exactly for every step.

Analytical reference: with constant gain Q and no HVAC,
T_ss = T_out + Q / (ΣUA + ρ c_p V̇), reached with time constant τ = C_eff / (ΣUA + ρ c_p V̇).

## 3. HVAC (`models/hvac.py`)

**Control (thermal).** Because the step is linear, the cooling that returns
the room to a target temperature by the end of the step is

    Q = C_eff (T_free − T_target) / φ

where T_free is the end-of-step temperature without cooling.

| Mode | Cooling delivered |
|---|---|
| Ideal | Q_cool = max(0, Q), no capacity limit. Idealised reference. |
| Capacity-limited | Q_cool = min(max(0, Q), Q_max − Q_latent) |
| Thermostat | Off until T ≥ T_set + δ/2, then full capacity until T_set − δ/2 would be crossed. Cycles shorter than Δt are replaced by their average. |

Heating, if enabled, uses the same form toward the heating setpoint, capped at
its capacity, and only when no cooling is delivered.

    Q_required = max(0, Q_gain + K (T_out − T_set))     load to HOLD the setpoint [W thermal]
    Q_unmet    = max(0, Q_required − capacity available)

When capacity is short the room temperature rises; the setpoint is not held artificially.

**Electricity.**

    P_cool = (Q_sensible + Q_latent) / COP_cool         [W electrical]
    P_heat = Q_heat / COP_heat                          [W electrical]
    E_HVAC = Σ (P_cool + P_heat) Δt

COP is constant *(input)*. Valid only as an average: real COP varies with
outdoor temperature and part load (future work).

## 4. Humidity (`models/humidity.py`, `models/crop_growth.py`)

State: humidity ratio w [kg water vapour / kg dry air]. Relative humidity is
derived, never integrated.

    e_sat(T) = 610.78 exp(17.27 T / (T + 237.3))        [Pa], T in °C  (Tetens; 0 to 50 °C)
    w  = 0.622 e / (P − e),   e = RH × e_sat(T)          P = 101 325 Pa
    e  = w P / (0.622 + w),   RH = e / e_sat(T),   VPD = e_sat(T) − e

**Moisture balance**

    M_da dw/dt = ṁ_vent (w_out − w) + ṁ_transp − ṁ_removed          [kg/s]
    M_da = ρ_air V_room,   ṁ_vent = ρ_air V̇

**Transpiration** (simplified Penman-Monteith-type form carried over from the
Circular CEA model in this repository), per m² of planted area:

    λE = a × R_PAR × (1 − e^(−k_ext LAI)) + b × LAI × s × VPD          [W/m²]
    R_PAR = PPFD × 0.22 J/µmol
    LAI = LAI_max × B / K
    s = s_dark + (1 − s_dark) × (fraction of the step with lights on)
    ṁ_transp = A_crop × λE / h_fg,   floored at 0

a, b, k_ext, LAI_max, s_dark are *(inputs)*. VPD is linearised in w within a
step, which keeps the balance in the form dw/dt = a − kw so it is integrated
with the same exact step as temperature.

**Dehumidification.** If RH would exceed the setpoint, moisture is removed at
the rate that brings w to w(T, RH_set) by the end of the step, capped by the
moisture-removal capacity and by Q_max / h_fg:

    Q_latent = ṁ_removed × h_fg                                       [W thermal]

Latent heat is counted once: transpiration takes Q_transpiration out of the
sensible balance, and the same water later appears as Q_latent on the coil.
If w still exceeds saturation, the excess is removed as condensation on
surfaces and reported (its heat release is not modelled).

Limitations: sensible and latent cooling are controlled independently (a real
coil has a coupled sensible heat ratio); no reheat; no humidification; the RH
target uses the start-of-step temperature, so RH can sit up to about 0.5 %
above the setpoint while the room cools.

## 5. Crop growth (`models/crop_growth.py`)

State: B = dry biomass per plant [g].

    dB/dt = r_eff B (1 − B/K)
    r_eff = r_base × f_T × f_L × f_CO2 × f_VPD                 [1/day]

    f_T = ((T_max − T)/(T_max − T_opt)) × ((T − T_min)/(T_opt − T_min))^((T_opt − T_min)/(T_max − T_opt))
          for T_min < T < T_max, else 0          (cardinal-temperature beta function)
    f_L = PPFD / (PPFD + K_L)   while lit, 0 in darkness
    f_CO2 = f_VPD = 1            (placeholders, not modelled)

All modifiers lie in [0, 1], so growth is never negative. Each step uses the
exact logistic solution with r_eff held constant:

    B(t+Δt) = K B / (B + (K − B) e^(−r_eff Δt))

**Harvest**

    M_dry = B × N_plants / 1000                      [kg dry]
    M_fresh = M_dry / f_DM                           [kg fresh]   f_DM = dry matter fraction (input)
    M_harvest = M_fresh × f_marketable               [kg marketable fresh]

Logistic growth alone carries no environmental limitation; the modifiers add
temperature and light only. See `assumptions.md` for what is left out.

## 6. Coupled sequence (`simulation/engine.py`)

Per step: schedule → LED power → PPFD → internal heat → ventilation →
moisture balance (transpiration, dehumidification) → thermal balance and HVAC
→ crop growth → electrical power → store. The models exchange only physical
variables (PPFD, T, w, B, heat and moisture flows).

## 7. Energy accounting (`analysis/energy_analysis.py`)

    E_total = E_lighting + E_cool + E_heat + E_circ.fans + E_vent.fans + E_pumps + E_aux        [kWh electrical]
    P_vent.fan = SFP × V̇                      SFP = specific fan power [W per m³/s] (input)
    Energy intensity = E_total / M_harvest    [kWh per kg marketable fresh]; undefined (NaN) if M_harvest = 0
    Cost = E × price                          constant price (input)

Thermal cooling energy (kWh thermal) is reported separately and is not part of E_total.

## References

- Tetens O. (1930), saturation vapour pressure formula, in the form given by Monteith & Unsworth, *Principles of Environmental Physics*.
- Cardinal-temperature beta function: Yin X. et al. (1995), *Agricultural and Forest Meteorology* 77, 1-16.
- Transpiration form and lamp-heat treatment: `docs/assumptions.md` of the Circular CEA Energy Model in the repository root, which follows Graamans et al. (2018), *Agricultural Systems* 160, 31-43, in spirit but is not calibrated.
