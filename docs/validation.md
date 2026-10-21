# Verification and validation

This page records how the model was checked, what the checks show, and where the model disagrees with published work. Two different questions are kept apart:

- **Verification:** does the code solve the stated equations correctly? (conservation, convergence, known values)
- **Validation:** do the stated equations and inputs describe something like a real growing room? (comparison with published ranges)

The model has **not** been compared with measurements from a real facility. Agreement with published ranges is a plausibility check, not proof of accuracy.

## 1. Verification

### 1.1 Test suite

Run with `pytest` (8 tests, about 30 seconds). The tests fall into three groups:

- **Psychrometrics:** saturation pressure, humidity ratio and vapour pressure deficit are checked against known values and round trips.
- **Conservation:** the water balance and the tank energy balance must close to within 0.1 %.
- **Pinned reference results:** the day-1 tank energy flows (341.8 MJ in, 32.3 MJ out, 26.8 MJ lost, 282.7 MJ stored) and the steady-state indicators of all three scenarios are fixed to the values in this document.

The pinned reference tests exist because conservation alone is weak: a balance closes even when the inputs are wrong (the first version of this model closed perfectly with a lamp power twice too high). Pinning the reference values means a change that moves the headline numbers fails the suite and has to be explained.

### 1.2 Conservation

Both balances close to well within the required tolerance. The stage-check scripts report residuals of 0.0002 % for water (`check_water_balance.py`) and 0.0002 % for the tank energy (`check_energy_balance.py`), against a test requirement of 0.1 %.

### 1.3 Numerical convergence

`run_convergence.py` re-runs all three scenarios with tighter solver tolerances and a finer output interval. The largest change in any indicator is **0.0006 %**. The reported energy and water intensities are therefore independent of the numerical settings at the digits quoted.

### 1.4 Steady state

Results are read from the last day of a 60-day run. In the base case the room and tank settle within about 3 days; 60 days is a margin. Day-1 values include a start-up transient and are not used for conclusions.

## 2. Plausibility against the literature

Values are from `data/literature/literature_values.csv`, which records how each was verified. Model values are for the steady-state base case.

| Quantity | Model | Published | Comment |
|---|---|---|---|
| Daily light integral | 17.3 mol/m2/day | 13.7 (Weidner et al. 2021, basket lettuce); 17 (study with citation pending) | Consistent with lettuce practice |
| Electricity per kg fresh produce | A 15.3, B 14.5, C 16.4 kWh/kg | 7.8 to 23.8 (Ceccanti et al. 2025, preprint); about 10 to 12 (my conversion of Graamans et al. 2018, 247 kWh/kg dry weight at 4 to 5 % dry matter); 6.2 to 12.0 (study with citation pending) | Inside the widest range, above the lowest values (see section 3) |
| Electricity per floor area per year | A 740, B 703, C 795 kWh/m2/year | 517 to 773 (Semenchuk 2025, pilot farm) | A and B inside; C about 3 % above. The area basis of the thesis (floor or lit area) was not confirmed |
| Lighting share of electricity | 78.5 % (scenario A) | about 70 % (Ceccanti, citing Engler and Krarti, second-hand); about 80 % (Avgoustaki and Xydis, citing Kozai, second-hand); 46 to 75 % (Semenchuk); 58 to 88 % (study with citation pending) | At the top of the commonly quoted 70 to 80 %, and slightly above the pilot-farm range (46 to 75 %) |
| Cooling plus dehumidification share | about 27 % (scenario C) | 12 to 42 % (study with citation pending) | Inside the range; this comparison rests on the pending source |
| Fresh water per kg | A 4.24, C 2.65 L/kg | 1.5 (NREL poster, vertical farm); 0.88 net (my conversion of Ceccanti's best case); 2.0 to 9.8 (study with citation pending); 20 (Barbosa et al. 2015, greenhouse) | Model A is within the pending range and above the best vertical-farm values; the water definitions differ between sources |

Notes on sources: "citation pending" is a plant-factory modelling study whose PDF was provided without a title page; its numbers are used only as a cross-check and it is not cited until its title and authors are confirmed. "Second-hand" means the figure is quoted in a review whose original source I did not read. The Ceccanti work is a preprint.

## 3. Where the model disagrees, and why

**Energy per kg is higher than the lowest published values.** The lamps alone use 160 kWh/day to grow 13.33 kg/day, which is 12.0 kWh/kg before any cooling. Energy per kg is set mainly by yield per lit area, and the model uses a modest, fixed 4 kg/m2 per 30-day cycle. A back-calculation from the pending study's own numbers suggests it assumes a higher yield per lit area (an estimate of mine, not a published value). Energy per floor area, which does not depend on the yield assumption, is close to the one pilot-farm range available (Semenchuk): two scenarios inside it, one about 3 % above. I therefore read the model's energy per kg as plausible but conservative.

**Lighting share is at the high end.** Real facilities have fans, pumps, control and building loads that this model omits. Adding them would lower the lighting share and raise total energy.

**Fresh water is above the best published vertical-farm values.** The model counts transpiration only and recovers 68 % of it in scenario C. Published values come from different system boundaries (net versus gross water, with or without cleaning and drainage), so this comparison is the least precise of the set.

## 4. What validation changed

Two assumptions were corrected because of these comparisons (details in `assumptions.md`, section 5):

1. Lamp power density was reduced from 200 to 100 W/m2, after the daily light integral (34.6 mol/m2/day) and the energy per kg (25 kWh/kg) were found to be well outside lettuce practice and published ranges.
2. Lamp light was added to the room heat balance. Before this correction the cooling load was understated and heat recovery appeared to save nothing; the corrected model has a realistic cooling load and heat recovery saves about 5 %.

Both errors were invisible to the conservation tests, which is why the literature comparison is part of the process.

## 5. What is not validated

- No comparison with measured data from a real or pilot facility. This is the most important gap.
- The three scenarios were not compared against any published circular-versus-linear study; the sizes of the heat-recovery and water-recovery effects are model results.
- Scenarios A and B have no humidity control, which affects the size of C's energy penalty (see `assumptions.md`, section 6).
- Yield is independent of light, so the model cannot say whether a different lamp power or efficacy would change production.
- One site and one synthetic day of weather.

## 6. Suggested next steps

1. Calibrate against measured data from a pilot vertical farm (energy by end use, humidity, water balance).
2. Replace fixed yield with a light-response (daily light integral) model.
3. Add a dehumidifier to scenarios A and B so humidity is controlled in all three.
4. Add fans, pumps and other loads; test their effect on the lighting share.
5. Add seasonal weather, and a sensitivity case for the fraction of lamp input stored in biomass.

## 7. Reproduce

```
pytest
python run_multiday.py
python run_convergence.py
python run_sensitivity.py
```
