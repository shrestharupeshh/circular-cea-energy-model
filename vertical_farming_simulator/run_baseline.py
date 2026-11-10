"""Run a scenario from the command line, without the interface.

    python run_baseline.py                      # baseline scenario
    python run_baseline.py my_scenario.json     # any saved scenario
    python run_baseline.py --csv results.csv    # also write the time series
"""

from __future__ import annotations

import argparse

from config.parameters import load_config
from simulation.engine import run_simulation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", default=None, help="scenario JSON (default: baseline)")
    parser.add_argument("--csv", default=None, help="write the full time series to this CSV file")
    args = parser.parse_args()

    result = run_simulation(load_config(args.scenario))
    s, d = result.summary, result.derived
    e, c = s["energy_kwh"], s["crop"]
    print(f"Scenario: {s['scenario_name']}  ({s['duration_days']:.0f} days, step {s['time_step_s'] / 60:.0f} min)")
    print(f"Growing area {d['growing_area_m2']:.0f} m2, room volume {d['room_volume_m3']:.0f} m3, "
          f"{d['n_plants']:.0f} plants")
    print(f"LED: {d['installed_power_w'] / 1000:.1f} kW installed, {d['power_density_w_m2']:.0f} W/m2, "
          f"PPFD {d['ppfd_full_umol_m2_s']:.0f} umol/m2/s, DLI {s['dli_mean_mol_m2_day']:.1f} mol/m2/day")
    print("Electricity [kWh]:")
    for key in ("lighting", "hvac_cooling", "hvac_heating", "circulation_fans", "ventilation_fans",
                "pumps", "auxiliary", "total"):
        print(f"  {key:<18}{e[key]:>10.0f}")
    print(f"Cooling delivered: {s['cooling_thermal_kwh_th']:.0f} kWh thermal "
          f"(sensible {s['cooling_sensible_kwh_th']:.0f}, latent {s['cooling_latent_kwh_th']:.0f}); "
          f"peak {s['cooling_delivered_peak_kw']:.1f} kW; unmet {s['cooling_unmet_kwh_th']:.0f} kWh thermal")
    print(f"Indoor temperature {s['indoor_temp_min_c']:.1f} to {s['indoor_temp_max_c']:.1f} C "
          f"(mean {s['indoor_temp_mean_c']:.1f}); RH {s['indoor_rh_min_percent']:.0f} to "
          f"{s['indoor_rh_max_percent']:.0f} % (mean {s['indoor_rh_mean_percent']:.0f})")
    print(f"Crop: {c['dry_mass_per_plant_g']:.2f} g dry/plant = {c['fresh_mass_per_plant_g']:.0f} g fresh/plant; "
          f"total fresh {c['total_fresh_mass_kg']:.0f} kg, marketable {c['marketable_fresh_mass_kg']:.0f} kg")
    print(f"Energy intensity: {s['energy_intensity_kwh_per_kg']['total']:.1f} kWh per kg marketable fresh; "
          f"cost {s['cost']['total']:.0f} total, {s['cost']['per_kg']:.2f} per kg")
    for note in result.warnings:
        print("NOTE:", note)
    if args.csv:
        with open(args.csv, "w", encoding="utf-8") as handle:
            handle.write(result.to_csv())
        print("Time series written to", args.csv)


if __name__ == "__main__":
    main()
