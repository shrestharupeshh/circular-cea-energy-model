# Circular CEA Energy Model

A coupled energy and water balance simulation of a closed, lit, controlled-environment growing room, written in Python. It asks one question: **what does it cost, in electricity and in water, to make a vertical-farm growing room circular?**

> **Status: work in progress.** The model, tests and sensitivity study are working. The written assumptions, the validation document and some figures are still being finished, and all numbers below are preliminary.

## The question

A closed growing room turns almost all of its lighting electricity into heat, and its crop transpires several litres of water per kilogram of produce. A conventional ("linear") room cools the air, vents the humid air and throws both the heat and the water away. A circular room can capture both. Capturing them is not free, so the interesting question is the trade-off:

- **A, linear:** no recovery. Waste heat is rejected, transpired water is vented, and the room is heated from the grid when it is cold.
- **B, heat recovery:** heat removed by the cooling system is stored in a thermal buffer tank and later used to heat the room.
- **C, heat and water recovery:** as B, plus a dehumidifier that condenses transpired water for reuse in irrigation.

All three scenarios see the same weather, the same lights and the same crop.

## Preliminary results

Steady state (last day of a 60-day run), one 100 m² room, 100 W/m² of LED lighting (daily light integral about 17 mol/m²/day), fixed yield of 13.3 kg/day.

| Scenario | Electricity (kWh per kg) | Fresh water (L per kg) |
|---|---|---|
| A: no recovery | 15.28 | 4.24 |
| B: heat recovery | 14.53 (-4.9 %) | 4.27 (+0.6 %) |
| C: heat and water recovery | 16.43 (+7.5 %) | 2.65 (-37.4 %), 68 % of transpired water recovered |

![Scenario comparison](figures/scenario_comparison.png)

In words: heat recovery saves a few percent of electricity because it replaces the room's night-time grid heating. Water recovery cuts fresh water use by more than a third, at a cost of a few percent more electricity, because dehumidifying is not free. The saving from heat recovery is limited by how much heating the room needs, not by how much heat is available.

![Daily profile of scenario C](figures/daily_profile.png)

## The model

Four states are integrated in time with a stiff ODE solver (`scipy`, BDF):

```
Room air temperature   C_sys dT/dt = Q_lamp + Q_heat + Q_dehum_latent + Q_tank_loss
                                     - Q_envelope - Q_ventilation - Q_transpiration - Q_cool
Room humidity ratio    V dchi/dt   = M_crop - M_dehum - M_vent
Recovered water        dV_rec/dt   = M_dehum / rho_water
Tank temperature       C_tank dT_tank/dt = Q_charge - Q_discharge - Q_tank_loss
```

- **Lighting:** electrical power density, 16 h photoperiod. Nearly all lamp input (98 %) becomes heat in the room; a small fraction is stored in biomass. The light share drives transpiration.
- **Crop water use:** a simplified Penman-Monteith-type form, latent flux = a * absorbed light + b * LAI * vapour pressure deficit.
- **Envelope and ventilation:** conduction (U * A * dT) and infiltration (air changes per hour), against a sinusoidal outdoor temperature.
- **Climate control:** proportional cooling, heating and dehumidification with capacity limits.
- **Thermal buffer tank:** charge and discharge rates that taper smoothly near the temperature limits, plus a standing heat loss.
- **Electricity:** `P_total = P_lamp + Q_cool / COP_cool + M_dehum * latent_heat / COP_dehum + grid heating`.
- **Indicators:** energy use intensity (kWh per kg of produce), water use intensity (L of fresh water per kg), and the fraction of transpired water recovered.

## Repository layout

```
src/            model code
  constants.py    physical constants
  psychro.py      saturation pressure, humidity, VPD
  lighting.py     lamp power and photoperiod
  envelope.py     conduction and ventilation
  crop.py         transpiration
  hvac.py         dehumidifier
  storage.py      thermal buffer tank
  model.py        the coupled ODE system
  scenarios.py    base case, the three scenarios, the runner
  indicators.py   energy and water indicators
tests/          pytest suite (psychrometrics, conservation, reference results)
data/           sensitivity results (and literature values, in progress)
figures/        generated figures
run_*.py        scenario and analysis scripts
plot_*.py       figure scripts
check_*.py      stage-by-stage balance checks used while building the model
```

## How to run

```
pip install numpy scipy pandas matplotlib pytest
pytest                      # 8 tests, about 30 seconds
python run_multiday.py      # steady-state comparison of A, B and C
python run_sensitivity.py   # one-at-a-time sensitivity (several minutes)
python plot_tornado.py
python plot_scenario_comparison.py
python plot_daily_profile.py
```

## Verification and validation

- **Conservation.** Tests check that the water balance and the tank energy balance close to within 0.1 %. These only prove the bookkeeping is consistent; they pass even with wrong inputs, so reference values are also pinned.
- **Reference results.** The steady-state indicators of all three scenarios are pinned in a test, so a change that moves the headline numbers fails loudly.
- **Numerical convergence.** Tightening the solver tolerances and refining the output interval changes no indicator by more than 0.001 %.
- **Literature.** The baseline was checked against published plant-factory and vertical-farm work, which led to two corrections during development: the lamp power density was reduced from 200 to 100 W/m² (the original gave a daily light integral about 2.5 times typical for lettuce), and lamp light is now counted as room heat. Current agreement: lighting is about 79 % of electricity (published 46-88 %), cooling plus dehumidification about 27 % of scenario C (published 12-42 %), 740 kWh/m²/year (published 517-773 for a pilot farm), and fresh water of 2.7-4.2 L/kg (published 2-10). Energy per kg, 15.3 kWh/kg, is above the lowest published values, mainly because the assumed yield per lit area is modest.

## Sensitivity

One-at-a-time changes of +/-20 % (outdoor temperature +/-5 K), reported as the change in scenario C's energy use and in its penalty relative to A.

![Tornado diagram](figures/tornado.png)

The relative-humidity setpoint, outdoor temperature, air-change rate and the dehumidifier and cooling COPs matter most for the energy penalty of recovering water. Lamp power dominates absolute energy use, as expected at a fixed yield. Tank size and thermal mass barely matter.

## Limitations

- Yield is fixed and independent of light, so lamp power and lamp efficacy cannot change production. Energy per kg is therefore sensitive to the assumed yield.
- One well-mixed room: no spatial variation, no CO2 model, no fans or pumps, no real HVAC equipment curves.
- Proportional control leaves the air about 2 K above the cooling setpoint during the light period.
- Scenarios A and B have no humidity control, so room humidity can reach saturation, while C has a dehumidifier. C's energy penalty therefore compares a controlled room with an uncontrolled one.
- Synthetic weather (a single sinusoidal day), a single site, and no economics or carbon accounting.
- The thermal tank is oversized for this room (a tank about a tenth of the size gives the same saving).

## Planned

Written assumptions and validation documents, a literature table in `data/literature/`, an environment file, and a system schematic.

## Selected references

- Graamans L., Baeza E., van den Dobbelsteen A., Tsafaras I., Stanghellini C. (2018). Plant factories versus greenhouses: comparison of resource use efficiency. *Agricultural Systems* 160, 31-43.
- Weidner T., Yang A., Hamm M.W. (2021). Energy optimisation of plant factories and greenhouses for different climatic conditions. *Energy Conversion and Management* 243, 114336.
- Barbosa G.L. et al. (2015). Comparison of land, water, and energy requirements of lettuce grown using hydroponic vs. conventional agricultural methods. *International Journal of Environmental Research and Public Health* 12(6), 6879-6891.
- Semenchuk (2025). *Energy modelling and analysis of vertical farming for vegetable production*. MSc thesis, University of Manitoba.

## Author

Rupesh Shrestha, mechanical engineer (MEng, UC Berkeley). [shrestharupesh.com](https://www.shrestharupesh.com)

Project designed with the help of AI for the purpose of self training to learn system dynamic modeling in CEA. Built as a self-directed project on dynamic systems modelling for controlled-environment agriculture. The model structure follows a self-study guide. An AI assistant was used for explanation and code review; the code was written and run by the author.

