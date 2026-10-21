# Assumptions and model definitions

This page lists every input, every modelling choice and every known limitation of the Circular CEA Energy Model, so that a reader can judge which conclusions to trust. Numbers are those of the current base case in `src/scenarios.py`.

## 1. What the model is, and is not

The model is a **lumped (single well-mixed room) dynamic model** of a closed growing room. It integrates four states in time: room air temperature, room humidity ratio, recovered water volume, and thermal buffer tank temperature. It compares three scenarios under identical weather, lighting and crop.

It is **not** calibrated to, or validated against, measurements from a real facility. Its credibility rests on three checks: conservation of water and energy, numerical convergence, and agreement of the baseline with ranges published for plant factories and vertical farms (see `validation.md`). Input values are the author's choices, taken from the study guide's worked example and typical literature values, not fitted to data.

## 2. Base case inputs

| Group | Input | Value | Note |
|---|---|---|---|
| Room | Floor (growing) area | 100 m2 | Single layer of crop |
| | Volume | 300 m3 | 3 m height |
| | Envelope area | 160 m2 | Walls and ceiling |
| | Envelope U-value | 0.4 W/m2/K | Well-insulated room |
| | Air change rate | 0.5 per hour | Infiltration plus fresh air |
| Lighting | Installed power density | 100 W/m2 | See section 5 |
| | Photon efficacy | 3.0 umol/J | Modern horticultural LED |
| | Photoperiod | 06:00 to 22:00 (16 h) | Smooth switching |
| | Fraction stored in biomass | 0.02 | Rest of lamp input becomes room heat |
| Cooling | Setpoint, gain, capacity | 24 C, 4000 W/K, 15 kW | Proportional |
| | COP | 3.0 | Electrical efficiency of cooling |
| Heating | Setpoint, gain, capacity | 20 C, 4000 W/K, 10 kW | Proportional |
| Dehumidifier | RH setpoint | 75 % | Used in scenario C only |
| | Capacity, gain | 4 g/s, 50 per unit RH error | Reaches full capacity 2 % RH above setpoint |
| | COP | 2.5 | Electricity per latent heat removed |
| Crop | Leaf area index | 2.5 | |
| | Transpiration coefficients | a = 0.30, b = 0.010 | See section 3 |
| | Yield | 4 kg/m2 per 30-day cycle | 13.33 kg/day for the room |
| Thermal mass | Room multiplier | 12 | Air heat capacity times 12 (structure, plants, equipment) |
| Tank | Volume, standing loss | 5 m3, 15 W/K | |
| | Operating range | 30 to 60 C | Smooth taper over 5 K at each end |
| | Charging efficiency | 0.85 | |
| Weather | Outdoor temperature | 10 - 5 cos(2 pi t / 24 h) C | 5 C at midnight, 15 C at noon |
| | Outdoor relative humidity | 70 % (constant) | |
| Start | Air, humidity, tank | 22 C, 60 % RH, 40 C | |

Derived quantities worth knowing: the lights give 300 umol/m2/s while on, a daily light integral of 100 x 3.0 x 16 x 3600 / 10^6 = 17.3 mol/m2/day; the envelope plus air-change heat loss is about 114 W/K (64 + 50); the room thermal capacity is about 4.3 MJ/K and the tank's about 21 MJ/K.

## 3. Modelling choices

**Lamp heat.** Of the electricity drawn by the lamps, 98 % is treated as heat released in the room and 2 % as chemical energy stored in biomass. Light absorbed by leaves and surfaces becomes heat, so this is an energy-conservation statement, not a fitted number. The optical share of the lamp power (photon efficacy x 0.22 J/umol, about 66 %) also drives transpiration.

**Transpiration.** Latent flux (W/m2) = a x absorbed light + b x LAI x vapour pressure deficit, floored at zero, divided by the latent heat of vaporisation (2.45 MJ/kg). This is a simplified Penman-Monteith form, not a full canopy model. The transpired water removes latent heat from the room air.

**Envelope and ventilation.** Conduction is U x A x (T_in - T_out). Ventilation carries sensible heat and exchanges moisture with outdoor air (70 % RH). There is no heat recovery ventilator.

**Control.** Cooling, heating and dehumidification are proportional controllers with capacity limits. Proportional control leaves a steady offset: during the light period the air runs about 2 K above the 24 C cooling setpoint.

**Heat recovery (scenarios B and C).** Heat removed from the room by the cooling system charges the tank at 85 % efficiency. The heat available is taken as the cooling load itself, not including the compressor work, which makes recovery conservative. The tank supplies the room's heating demand, and only the remainder is bought as electricity. The tank loses heat to the room through its standing loss. There is no heat-exchanger temperature-difference penalty.

**Water recovery (scenario C).** A dehumidifier condenses room moisture. The condensate is counted as reusable irrigation water in full, with no treatment energy, nutrient-solution accounting or pumping. Latent heat released by condensation returns to the room air.

**Electricity.** P_total = P_lamp + Q_cool / COP_cool + M_dehum x latent heat / COP_dehum + grid heating. Heating that the tank supplies is not counted as electricity.

**Fresh water.** Fresh water = water transpired minus water recovered. Only transpiration is counted.

**Indicators.** Energy use intensity (EUI, kWh per kg of produce) = electricity used / yield. Water use intensity (WUI, L per kg) = fresh water / yield. Yield is the room's fixed production, scaled to the simulated time.

## 4. Numerical settings

BDF (stiff) integrator from `scipy`, relative tolerance 1e-6 and absolute tolerance 1e-8, output every 60 s. Tightening the tolerances and refining the output interval changes no indicator by more than 0.001 % (convergence study, `run_convergence.py`).

**Steady state.** Results are read from the last day of a 60-day run (`N_DAYS` in `src/scenarios.py`). With the current inputs the room and tank settle within about 3 days, because the tank fills to its upper limit; 60 days is a safety margin for sensitivity cases that settle more slowly. Day-1 values include a start-up transient (the tank starts at 40 C) and are not used for conclusions.

## 5. Changes made after checking against the literature

Two assumptions were revised after comparing the first results with published ranges:

1. **Lamp power density was reduced from 200 to 100 W/m2.** At 200 W/m2 the daily light integral was 34.6 mol/m2/day, about 2.5 times typical for lettuce, and energy per kg (25 kWh/kg) was above published ranges. At 200 W/m2 the cooling capacity is also exceeded, so the room overheats to about 34 C.
2. **Lamp light is now counted as room heat.** The first version added only the non-optical share (34 %) of lamp power as heat, which understated the cooling load. The study guide itself notes that the optical fraction "does not vanish". Correcting it changed heat recovery from saving about nothing to saving about 5 %.

## 6. Known limitations

- **Fixed yield.** Yield does not depend on light, temperature or CO2, so lamp power and efficacy cannot change production. Energy per kg is therefore driven by the yield assumption, and lamp power appears as the largest effect on absolute energy in the sensitivity study. Results are best read as ratios between scenarios.
- **Fixed lamp power.** No dimming, no daily-light-integral control.
- **Humidity control is asymmetric.** Scenarios A and B have no dehumidifier, so room humidity reaches saturation, while C holds 75 %. C's energy penalty therefore compares a humidity-controlled room with an uncontrolled one.
- **Single zone.** No spatial gradients, no air distribution, no fan or pump energy, no equipment curves, no defrost or part-load effects. Lighting is about 79 % of electricity in scenario A; the published range is wide (about 46 to 88 %).
- **Heat recovery.** The tank is oversized for this room: a tank about a tenth of the size gives the same saving. The saving is limited by the room's night-time heating demand. No exergy or heat-exchanger analysis.
- **Weather.** One synthetic sinusoidal day at a single mild site, no seasons, no solar gain. Warmer outdoor air raises C's energy penalty (from 7.5 % to 11.9 % for +5 K) and cooler air lowers it.
- **Water accounting.** Only transpiration; no drain, leakage, cleaning, or treatment of recovered water.
- **Not modelled:** CO2, nutrients, crop growth, economics, carbon emissions, equipment sizing.

## 7. Which conclusions are robust

- **Robust:** water recovery cuts fresh water use substantially (by 37 % in the base case) and costs extra electricity, because dehumidifying is not free. The water saving appeared in every sensitivity case, and the energy penalty stayed between 0.3 % and 15 %.
- **Moderately robust:** heat recovery saves a few percent at best, and the amount depends on how much heating the room needs.
- **Not robust:** absolute values of energy per kg, which scale with the assumed yield per lit area.
