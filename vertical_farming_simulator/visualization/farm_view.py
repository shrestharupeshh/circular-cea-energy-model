"""3D view of the farm at one moment of a simulation.

Geometry is schematic (square footprint, racks filling most of the floor),
but everything that changes is taken from the simulation results at the
selected time: canopy height and colour follow crop biomass, the LED panels
are lit only when the schedule has them on, and the room outline is coloured
by indoor air temperature.
"""

from __future__ import annotations

import math

import plotly.graph_objects as go

from simulation.results import SimulationResult

_I = [0, 0, 4, 4, 0, 0, 1, 1, 0, 0, 3, 3]
_J = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 2, 6]
_K = [2, 3, 6, 7, 5, 4, 6, 5, 7, 4, 6, 7]


def _box(x0, x1, y0, y1, z0, z1, color, opacity=1.0, name="") -> go.Mesh3d:
    x = [x0, x1, x1, x0, x0, x1, x1, x0]
    y = [y0, y0, y1, y1, y0, y0, y1, y1]
    z = [z0, z0, z0, z0, z1, z1, z1, z1]
    return go.Mesh3d(x=x, y=y, z=z, i=_I, j=_J, k=_K, color=color, opacity=opacity, flatshading=True,
                     name=name, hoverinfo="name", showlegend=False)


def _temperature_color(temp_c: float, low: float, high: float) -> str:
    """Blue below the acceptable range, green inside it, red above."""
    if temp_c < low:
        return "#0072b2"
    if temp_c > high:
        return "#c0392b"
    return "#2c3e50"


def _canopy_color(fraction: float) -> str:
    """Pale to deep green as biomass approaches its maximum."""
    f = min(1.0, max(0.0, fraction))
    r, g, b = int(190 - 150 * f), int(225 - 95 * f), int(160 - 95 * f)
    return f"rgb({r},{g},{b})"


def farm_3d(result: SimulationResult, step: int) -> go.Figure:
    """Build the 3D scene for time-step index ``step`` of ``result``."""
    cfg, geo = result.config, result.derived
    row = result.timeseries.iloc[step]
    side = math.sqrt(geo["footprint_area_m2"])
    height = cfg["farm"]["room_height_m"]
    layers = int(geo["n_layers"])
    lights_on = row["led_schedule_fraction"] > 0
    growth = row["biomass_dry_g_per_plant"] / cfg["crop"]["max_dry_mass_g"]
    limits = cfg["limits"]

    fig = go.Figure()
    # room outline, coloured by air temperature
    c = _temperature_color(row["indoor_temp_c"], limits["temp_min_c"], limits["temp_max_c"])
    corners = [(0, 0), (side, 0), (side, side), (0, side), (0, 0)]
    xs, ys, zs = [], [], []
    for z in (0, height):
        xs += [p[0] for p in corners] + [None]
        ys += [p[1] for p in corners] + [None]
        zs += [z] * 5 + [None]
    for px, py in corners[:4]:
        xs += [px, px, None]; ys += [py, py, None]; zs += [0, height, None]
    fig.add_trace(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", line=dict(color=c, width=5),
                               name="Room", hoverinfo="name", showlegend=False))
    fig.add_trace(_box(0, side, 0, side, -0.03, 0.0, "#b0b0b0", 0.5, "Floor"))

    # two rack rows with an aisle between them
    margin, aisle = 0.08 * side, 0.12 * side
    rack_w = (side - 2 * margin - aisle) / 2
    rows = [(margin, margin + rack_w), (side - margin - rack_w, side - margin)]
    gap = (height - 0.3) / layers
    for y0, y1 in rows:
        x0, x1 = margin + 0.12 * side, side - margin
        for i in range(layers):
            z = 0.15 + i * gap
            fig.add_trace(_box(x0, x1, y0, y1, z, z + 0.04, "#8d6e63", 1.0, f"Tray, layer {i + 1}"))
            canopy = max(0.01, 0.45 * gap * growth)
            fig.add_trace(_box(x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, z + 0.04, z + 0.04 + canopy,
                               _canopy_color(growth), 1.0,
                               f"Crop, layer {i + 1}: {row['biomass_dry_g_per_plant']:.2f} g dry/plant"))
            led_z = z + 0.80 * gap
            fig.add_trace(_box(x0, x1, y0, y1, led_z, led_z + 0.03,
                               "#ffb000" if lights_on else "#6f6f6f", 1.0,
                               f"LED, layer {i + 1}: {'on' if lights_on else 'off'}"))
            if lights_on:   # light cone between fixture and canopy
                fig.add_trace(_box(x0, x1, y0, y1, z + 0.04 + canopy, led_z, "#ffe08a", 0.12, "Light"))
        for px in (x0, x1):
            for py in (y0, y1):
                fig.add_trace(go.Scatter3d(x=[px, px], y=[py, py], z=[0, 0.15 + layers * gap], mode="lines",
                                           line=dict(color="#555555", width=3), hoverinfo="skip", showlegend=False))

    # HVAC unit on the wall; blue when cooling, orange when heating, grey when idle
    cooling, heating = row["cooling_total_w"] > 0, row["heating_w"] > 0
    hvac_color = "#0072b2" if cooling else ("#d55e00" if heating else "#9a9a9a")
    state = (f"cooling {row['cooling_total_w'] / 1000:.1f} kW thermal" if cooling
             else f"heating {row['heating_w'] / 1000:.1f} kW thermal" if heating else "idle")
    fig.add_trace(_box(0.02, 0.1 * side, 0.3 * side, 0.7 * side, height - 0.9, height - 0.2, hvac_color, 1.0,
                       f"HVAC: {state}"))

    fig.update_layout(
        scene=dict(xaxis=dict(title="Length [m]"), yaxis=dict(title="Width [m]"),
                   zaxis=dict(title="Height [m]", range=[-0.05, max(height, 0.1)]),
                   aspectmode="data", camera=dict(eye=dict(x=1.5, y=-1.6, z=0.9))),
        height=620, margin=dict(l=0, r=0, t=10, b=0), template="simple_white")
    return fig
