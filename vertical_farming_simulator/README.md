# Vertical Farming Energy Simulator

A physics-based simulation of a 100 m² indoor lettuce farm: lighting, room
temperature, humidity, HVAC, crop growth and electricity over a 30-day cycle.
Built on the modelling approach of the Circular CEA Energy Model in the
repository root (lumped balances, conservation checks, literature comparison),
with a crop that now responds to light and temperature.

**Status: first milestone.** The coupled simulation, interface, scenario
comparison, export and tests work. Optimization and PDF reports are not
implemented yet.

**This is a conceptual model with assumed parameters. It has not been
calibrated or validated against a real farm.** Use it to compare scenarios,
not to predict a specific facility.

## Run it

**Windows, no typing:** double-click `Start Simulator.bat` in this folder. It
installs what is missing the first time and opens the app in your browser.

**Any system, from a terminal:**

```bash
cd vertical_farming_simulator
pip install -r requirements.txt
```

```bash
streamlit run app.py
```

```bash
pytest
```

```bash
python run_baseline.py
```

`run_baseline.py` runs the engine without the interface (add `--csv out.csv`
for the time series, or pass a scenario JSON).

## Baseline result

100 m² footprint, 4 layers (400 m² growing area), 250 µmol/m²/s for 16 h/day,
22 °C setpoint, COP 3, 10 000 plants.

| | |
|---|---|
| Installed LED power | 42.0 kW (105 W per m² growing area) |
| Daily light integral | 14.4 mol/m²/day |
| Total electricity, 30 days | 29 000 kWh (lighting 70 %, HVAC 24 %, fans/pumps/other 6 %) |
| Cooling delivered | 21 100 kWh thermal, peak 44 kW |
| Harvest | 157 g fresh per plant; 1 330 kg marketable |
| Energy intensity | 22 kWh per kg marketable lettuce |

Example scenarios (same model, one or two inputs changed):

| Scenario | Electricity [kWh] | Marketable harvest [kg] | kWh/kg |
|---|---|---|---|
| A Baseline | 29 012 | 1 333 | 21.8 |
| B High lighting (350 µmol, 18 h) | 44 393 | 1 870 | 23.7 |
| C Reduced lighting (180 µmol, 12 h) | 16 711 | 352 | 47.5 |
| D Night lighting (20:00 start) | 29 010 | 1 333 | 21.8 |
| E Improved HVAC (COP 4.5) | 26 668 | 1 333 | 20.0 |
| F Warmer setpoint (25 °C) | 28 913 | 1 106 | 26.1 |

Two things these already show. Cutting light saves energy but costs far more
yield, so energy per kg doubles. And moving the lights to the night changes
almost nothing here, because the room is well insulated and the COP is
constant; that result would change with a temperature-dependent COP or a
time-of-use tariff, neither of which is modelled yet.

## Structure

```
app.py                     Streamlit interface (no physics in here)
run_baseline.py            command-line run
config/
  default_config.json      baseline scenario: every parameter
  parameters.py            load, validate, derive geometry
models/
  constants.py             physical constants
  numerics.py              exact step for dx/dt = a - kx
  lighting.py              power, schedule, PPFD, DLI, heat
  thermal.py               capacitance, envelope, ventilation, internal heat
  hvac.py                  control modes, capacity, COP
  humidity.py              psychrometrics
  crop_growth.py           logistic growth, modifiers, transpiration, harvest
  weather.py               constant / daily profile / CSV with validation
simulation/
  time_manager.py          one clock for all models
  engine.py                coupled time loop
  results.py               result container, CSV/JSON export, daily table
analysis/
  energy_analysis.py       component energy, intensity, cost
  scenario_comparison.py   example scenarios, save/load, comparison tables
visualization/plots.py     Plotly figures and farm schematic
visualization/farm_view.py 3D view of the farm at a chosen time
data/weather/              example (synthetic) weather CSV
data/scenarios/            scenarios saved from the app
tests/                     116 pytest tests
docs/                      model_equations.md, assumptions.md, validation.md
```

Data flow: scenario dict → `validate_config` → `run_simulation` →
`SimulationResult` (time series + summary) → plots, tables, export.

## Interface pages

1. Farm configuration, with schematic
2. Environmental conditions (constant, daily profile or CSV weather; envelope)
3. Lighting (specify PPFD, power density or installed power; the others are derived)
4. HVAC (ideal, capacity-limited or thermostat; dehumidification; heating; fans and pumps)
5. Crop growth (parameters, biomass, limitations)
6. Simulation results (energy table and breakdown, temperature, humidity, cooling, export)
7. Scenario comparison (examples A to F plus your own)
8. Optimization (placeholder)
9. Farm view (3D): rotatable view of the room at any day and hour of the run

## Documentation

- [`docs/model_equations.md`](docs/model_equations.md): every equation, units, and where it is coded
- [`docs/assumptions.md`](docs/assumptions.md): every default value and where it comes from
- [`docs/validation.md`](docs/validation.md): what has been verified, and what has not been validated

## Next steps

1. Grid-search optimization over PPFD, photoperiod and setpoint with a minimum-harvest constraint and a Pareto plot.
2. COP as a function of outdoor temperature, and time-of-use pricing (this is what makes night lighting interesting).
3. Coupled sensible/latent coil with reheat.
4. DLI- or photosynthesis-based growth with respiration; staggered planting.
5. PDF report; sensitivity analysis (the tornado approach from the Circular CEA model applies directly).
