# Weather files

`example_weather.csv` is a **synthetic** 7-day hourly profile (a warm, dry
summer week generated from sinusoids). It is not measured data. It exists to
show the expected file format:

| column | meaning | unit |
|---|---|---|
| `timestamp` | date and time, increasing, no duplicates | any format pandas can parse |
| `outdoor_temperature` | dry-bulb temperature | °C or °F (you state which in the app) |
| `outdoor_relative_humidity` | relative humidity | % (0 to 100) |

Optional columns `solar_radiation`, `wind_speed` and `outdoor_co2` are accepted
but not used by the current model. A file shorter than the simulation is
repeated from its start, with a warning.
