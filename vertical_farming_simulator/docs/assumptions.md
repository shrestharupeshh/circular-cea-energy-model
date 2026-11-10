# Assumptions

Every default below is an editable modelling assumption for a hypothetical
farm. None is a measurement, a recommendation or a validated specification.
"Source" says where the number comes from: **user spec** (the project brief),
**physics** (follows from conservation or a standard constant), **typical**
(a round value in the range commonly quoted for plant factories; not tied to
one citation), **carried over** (from the Circular CEA model in this
repository), or **tuned** (chosen so the baseline gives a plausible result).

## Farm and geometry

| Parameter | Default | Source | Note |
|---|---|---|---|
| Footprint | 100 m² | user spec | |
| Room height | 3 m | user spec | Volume 300 m³ |
| Layers | 4 | user spec | Growing area 400 m² |
| Footprint shape | square | assumption | Sets wall area (120 m²) |
| Occupied fraction | 1.0 | assumption | Whole area planted as one batch for the whole run. Staggered planting is not modelled. |

## Lighting

| Parameter | Default | Source | Note |
|---|---|---|---|
| PPFD at full power | 250 µmol/m²/s | typical | Lettuce is commonly grown at about 200 to 300 |
| Photoperiod, start | 16 h, 06:00 | typical | DLI 14.4 mol/m²/day |
| Photon efficacy | 2.8 µmol/J | typical | Current horticultural LEDs are roughly 2.5 to 3.5 |
| Utilisation factor | 0.85 | assumption | Photons reaching the canopy / photons emitted; uniform PPFD assumed |
| Heat fraction to room | 0.98 | carried over | In a closed room absorbed light becomes heat; about 2 % is stored as chemical energy in biomass. Lower it for water-cooled fixtures. |

Resulting power density is 105 W per m² of growing area (42 kW installed).

## Envelope and air exchange

| Parameter | Default | Source | Note |
|---|---|---|---|
| Wall and roof U | 0.4 W/m²/K | carried over | Insulated panel construction |
| Floor U | 0 | assumption | Adiabatic floor; ground coupling not modelled |
| Air changes | 0.2 per hour | assumption | Nearly closed room. Real plant factories can be much tighter. |
| Thermal mass multiplier | 12 | carried over | Effective capacitance = 12 × room air (4.3 MJ/K). Affects dynamics, not daily energy. |
| Air density, c_p, pressure | 1.20 kg/m³, 1006 J/kg/K, 101.325 kPa | physics | Constant; sea level |

## Weather

| Parameter | Default | Source | Note |
|---|---|---|---|
| Outdoor temperature | 20 ± 6 °C sinusoid, peak 15:00 | assumption | Synthetic mild day, repeated |
| Outdoor RH | 50 ± 10 %, lowest at the temperature peak | assumption | |
| Solar gain, wind | none | simplification | Windowless room |

## HVAC and equipment

| Parameter | Default | Source | Note |
|---|---|---|---|
| Cooling setpoint | 22 °C | assumption | Equal to the crop optimum |
| Cooling capacity | 60 kW thermal | assumption | Sized above the baseline peak (44 kW) |
| Cooling COP | 3.0 | carried over | Constant; no part-load or outdoor-temperature dependence |
| Control mode | capacity-limited | assumption | Holds the setpoint when capacity allows |
| Heating | 18 °C, 10 kW, COP 1 | assumption | Electric resistance |
| RH setpoint (upper) | 70 % | typical | Dehumidify above this; no humidification |
| Moisture removal capacity | 40 kg/h | assumption | |
| Circulation fans | 1.5 kW, all heat to room | assumption | Constant, 24 h |
| Ventilation fan | 1000 W per m³/s | typical | Specific fan power; 17 W here |
| Pumps | 0.5 kW, half the heat to room | assumption | |
| Other equipment | 0.5 kW, all heat to room | assumption | Controls, sensors |

## Crop

| Parameter | Default | Source | Note |
|---|---|---|---|
| Plant density | 25 per m² | typical | |
| Initial dry mass | 0.05 g | assumption | About 1 g fresh transplant |
| Maximum dry mass K | 12 g | tuned | About 240 g fresh head |
| Base growth rate r | 0.55 per day | tuned | Chosen so the baseline reaches about 150 g fresh in 30 days. Not fitted to data. |
| T_min, T_opt, T_max | 4, 22, 32 °C | typical | Cool-season crop; cultivar dependent |
| Light half-saturation K_L | 200 µmol/m²/s | assumption | |
| Dry matter fraction | 0.05 | typical | Lettuce is roughly 4 to 6 % dry matter |
| Marketable fraction | 0.85 | assumption | Roots and trim removed |
| Transpiration a, b | 0.30, 0.010 W/m²/Pa | carried over | Uncalibrated |
| Max LAI, extinction | 2.5, 0.7 | carried over, typical | LAI proportional to biomass |
| Dark transpiration factor | 0.3 | assumption | Stomatal closure in darkness |

## Simplifications to keep in mind

- One well-mixed air node: no vertical gradients between layers, no air-distribution model.
- All envelope surfaces see outdoor air temperature.
- Constant COP; sensible and latent cooling independent; no reheat, no humidifier, no defrost.
- The crop responds to temperature and light only. No CO₂, VPD, nutrient, root-zone, spacing or disease effects.
- Growth stops in darkness and there is no respiration loss.
- Whole crop planted on day 0 and harvested at the end.
- Constant electricity price.
- Weather is synthetic unless a CSV is imported.

## What the results can and cannot support

Comparisons between scenarios that differ in one or two inputs are the
intended use. Absolute values (kWh/kg, kg per cycle) depend directly on tuned
or assumed crop parameters and should not be quoted as predictions for a real
farm.
