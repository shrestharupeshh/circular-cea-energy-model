# Verification and validation

**Verification** asks whether the code solves its equations correctly.
**Validation** asks whether those equations and parameters represent a real
farm. This project has been verified. It has **not** been validated or
calibrated: no measured farm data have been used.

## Verification (automated, `pytest`)

116 tests; run with `pytest` from this folder.

### Analytical cases

| Model | Case | Expected | Result |
|---|---|---|---|
| Lighting | 400 m² × 250/(2.8 × 0.85) W/m² × 16 h × 30 d | 20 168.07 kWh | matches to 1e-9 |
| Lighting | DLI at 250 µmol/m²/s, 16 h | 14.4 mol/m²/day | matches |
| Thermal | Dry box, 1 kW constant heat, no HVAC | T(t) = T_ss + (T₀ − T_ss)e^(−t/τ) | matches to 1e-9 K at every step |
| Thermal | Same, after 30 days | T_ss = T_out + Q/(UA + ρc_pV̇) | within 1e-3 K |
| Thermal | No heat sources, T_in = T_out | no change | exact |
| HVAC | Cooling electricity | thermal energy / COP | matches to 1e-12 |
| Moisture | Air exchange only, constant outdoor air | w(t) = w_out + (w₀ − w_out)e^(−ACH·t) | matches to 1e-10 |
| Psychrometrics | e_sat at 0, 20, 25, 40 °C | 611, 2339, 3169, 7384 Pa | within 0.3 % |
| Crop | Modifiers off, r = 0.2/day, 30 days | closed-form logistic | matches to 1e-9 |

### Conservation

- **Energy:** for every step of the 30-day baseline, C_eff ΔT/Δt equals the sum of stored heat flows (internal + envelope + ventilation − transpiration − cooling + heating).
- **Water:** for every step, M_da Δw/Δt equals ventilation + transpiration − removal − condensation.
- **Latent heat:** latent cooling energy equals moisture removed × h_fg.
- **Electricity:** total equals the sum of the seven components; cumulative and daily series end at the same totals; thermal cooling is excluded from the electrical total.

### Behaviour

Zero light gives zero lighting energy; doubling power, photoperiod or dimming
scales energy exactly; cooling never exceeds capacity or goes negative; more
capacity never increases unmet demand; undersized cooling lets the room heat
up and is reported; RH stays between 0 and 100 %; biomass stays between its
initial value and K; zero harvest gives an undefined (NaN) intensity and a
warning instead of a division error; identical inputs give identical outputs.

### Numerical

Stable at 1, 5, 15 and 60 minute steps. For the baseline, total electricity
(29 011.9 kWh), HVAC electricity (7 031.8 kWh) and harvest (1 333.2 kg) are
identical to six significant figures at 1, 5 and 15 minute steps. That is
expected, not suspicious: the room is held at its setpoint, and each balance
is advanced with its exact solution. Step size matters when the room leaves
the setpoint (undersized cooling, thermostat mode) and for anything that
depends on within-hour dynamics.

Thermostat on/off cycling at the baseline thermal mass has a period of a few
minutes, so it is only resolved with a 1-minute step. With longer steps that
mode returns the cycle average.

## Plausibility against published ranges (not validation)

Baseline, compared with the literature table already in this repository
(`data/literature/literature_values.csv` in the repository root):

| Quantity | Baseline | Published range |
|---|---|---|
| Lighting share of electricity | 70 % | 46 to 88 % |
| HVAC share of electricity | 24 % | 12 to 52 % |
| Electricity per kg fresh | 21.8 kWh/kg marketable (18.5 per kg total fresh) | 6 to 24 kWh/kg |
| Water transpired per kg fresh | 1.4 L/kg | 1.5 to 10 L/kg |
| Electricity per growing area | about 880 kWh/m²/yr | 517 to 773 kWh/m²/yr (one pilot farm; area basis uncertain) |

The baseline sits at the energy-intensive end. That is consistent with a
modest tuned yield (3.9 kg fresh per m² of growing area per cycle) and 24-hour
fans and pumps. Agreement in order of magnitude says the inputs are not
absurd. It does not show the model predicts any particular farm.

## Known limitations

See `assumptions.md`. The ones that most affect conclusions:

1. Crop parameters are tuned, so absolute yield and kWh/kg are not predictive.
2. Constant COP: shifting lights to the night changes electricity by less than 0.01 % in this model. A real system would gain from cooler night-time condensing temperatures, and a time-of-use tariff would change cost.
3. Sensible and latent cooling are decoupled and there is no reheat, which understates dehumidification energy in humid conditions.
4. Single air node: no layer-to-layer gradients.

## What calibration would need

| Sub-model | Measurements | Parameters to fit |
|---|---|---|
| Thermal | Indoor/outdoor temperature and lighting power at ≤ 5 min, with HVAC off for part of the record | UA, thermal mass multiplier, LED heat fraction |
| HVAC | Electrical power and delivered cooling (or supply/return air states and flow) | COP as a function of outdoor temperature and load |
| Moisture | Indoor humidity, condensate mass, ventilation rate | Transpiration coefficients a and b, dark factor |
| Crop | Destructive dry and fresh mass samples through a cycle at known PPFD and temperature | r, K, K_L, cardinal temperatures, dry matter fraction |

No calibration should be claimed until such data have been used.
