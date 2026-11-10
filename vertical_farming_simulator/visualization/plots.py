"""Plotly figures. Every figure is built from simulation output only.

Colours are fixed per quantity so the same thing looks the same on every
page (lighting amber, HVAC blue, indoor red, outdoor grey, ...).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from simulation.results import SimulationResult

COLORS = {
    "indoor": "#c0392b", "outdoor": "#7f8c8d", "setpoint": "#2c3e50",
    "lighting": "#e69f00", "hvac": "#0072b2", "fans": "#009e73", "pumps": "#cc79a7",
    "auxiliary": "#999999", "total": "#222222", "crop": "#2e8b57", "unmet": "#d55e00",
    "latent": "#56b4e9",
}
LAYOUT = dict(template="simple_white", height=420, margin=dict(l=60, r=20, t=50, b=40),
              legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0.0),
              hovermode="x unified")


def _figure(title: str, x_title: str, y_title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=title, xaxis_title=x_title, yaxis_title=y_title, **LAYOUT)
    return fig


def _line(fig: go.Figure, x, y, name: str, color: str, dash: str | None = None, **kwargs) -> None:
    fig.add_trace(go.Scatter(x=x, y=y, name=name, mode="lines",
                             line=dict(color=color, width=1.6, dash=dash), **kwargs))


def _days(ts: pd.DataFrame) -> pd.Series:
    return ts["time_h"] / 24.0


def temperature(result: SimulationResult) -> go.Figure:
    ts = result.timeseries
    fig = _figure("Air temperature", "Time [days]", "Temperature [°C]")
    _line(fig, _days(ts), ts["outdoor_temp_c"], "Outdoor", COLORS["outdoor"])
    _line(fig, _days(ts), ts["indoor_temp_c"], "Indoor", COLORS["indoor"])
    _line(fig, _days(ts), ts["temp_setpoint_c"], "Cooling setpoint", COLORS["setpoint"], dash="dot")
    return fig


def humidity(result: SimulationResult, ratio: bool = False) -> go.Figure:
    ts = result.timeseries
    if ratio:
        fig = _figure("Indoor humidity ratio", "Time [days]", "Humidity ratio [g water / kg dry air]")
        _line(fig, _days(ts), 1000.0 * ts["indoor_w_kg_kg"], "Indoor", COLORS["indoor"])
        return fig
    fig = _figure("Relative humidity", "Time [days]", "Relative humidity [%]")
    _line(fig, _days(ts), ts["outdoor_rh_percent"], "Outdoor", COLORS["outdoor"])
    _line(fig, _days(ts), ts["indoor_rh_percent"], "Indoor", COLORS["indoor"])
    _line(fig, _days(ts), ts["rh_setpoint_percent"], "Humidity setpoint (upper)", COLORS["setpoint"], dash="dot")
    return fig


def lighting_schedule(result: SimulationResult, days: float = 3.0) -> go.Figure:
    ts = result.timeseries[result.timeseries["time_h"] < days * 24.0]
    fig = _figure(f"Lighting schedule (first {days:g} days)", "Time [h]", "PPFD [µmol/m²/s]")
    _line(fig, ts["time_h"], ts["ppfd_umol_m2_s"], "PPFD on crop", COLORS["lighting"], line_shape="hv")
    return fig


def electrical_power(result: SimulationResult) -> go.Figure:
    ts = result.timeseries
    fig = _figure("Electrical power", "Time [days]", "Electrical power [kW]")
    _line(fig, _days(ts), ts["power_total_w"] / 1000, "Total", COLORS["total"])
    _line(fig, _days(ts), ts["power_lighting_w"] / 1000, "Lighting", COLORS["lighting"])
    _line(fig, _days(ts), (ts["power_hvac_cooling_w"] + ts["power_hvac_heating_w"]) / 1000, "HVAC", COLORS["hvac"])
    return fig


def cooling(result: SimulationResult) -> go.Figure:
    ts = result.timeseries
    fig = _figure("HVAC cooling (thermal, not electrical)", "Time [days]", "Cooling power [kW thermal]")
    _line(fig, _days(ts), ts["cooling_required_w"] / 1000, "Required to hold setpoints", COLORS["outdoor"])
    _line(fig, _days(ts), ts["cooling_total_w"] / 1000, "Delivered (sensible + latent)", COLORS["hvac"])
    _line(fig, _days(ts), ts["cooling_latent_w"] / 1000, "Delivered latent", COLORS["latent"])
    _line(fig, _days(ts), ts["cooling_unmet_w"] / 1000, "Unmet", COLORS["unmet"])
    if ts["cooling_capacity_w"].notna().any():
        _line(fig, _days(ts), ts["cooling_capacity_w"] / 1000, "Capacity", COLORS["setpoint"], dash="dot")
    return fig


def biomass(result: SimulationResult) -> go.Figure:
    ts = result.timeseries
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=_days(ts), y=ts["biomass_dry_g_per_plant"], name="Dry biomass per plant",
                             line=dict(color=COLORS["crop"], width=2)), secondary_y=False)
    fig.add_trace(go.Scatter(x=_days(ts), y=ts["biomass_total_dry_kg"], name="Total dry biomass",
                             line=dict(color=COLORS["setpoint"], width=1.4, dash="dash")), secondary_y=True)
    fig.update_layout(title="Crop dry biomass", xaxis_title="Time [days]", **LAYOUT)
    fig.update_yaxes(title_text="Dry biomass per plant [g]", secondary_y=False)
    fig.update_yaxes(title_text="Total dry biomass [kg]", secondary_y=True)
    return fig


def daily_growth(daily: pd.DataFrame) -> go.Figure:
    fig = _figure("Daily growth", "Day", "Growth [g dry / plant / day]")
    fig.add_trace(go.Bar(x=daily["day"], y=daily["growth_g_dry_per_plant_day"], name="Daily growth",
                         marker_color=COLORS["crop"]))
    return fig


def cumulative_energy(result: SimulationResult) -> go.Figure:
    ts = result.timeseries
    end_days = (ts["time_h"] + result.summary["time_step_s"] / 3600.0) / 24.0
    fig = _figure("Cumulative electrical energy", "Time [days]", "Electrical energy [kWh]")
    _line(fig, end_days, ts["cum_energy_total_kwh"], "Total", COLORS["total"])
    _line(fig, end_days, ts["cum_energy_lighting_kwh"], "Lighting", COLORS["lighting"])
    _line(fig, end_days, ts["cum_energy_hvac_kwh"], "HVAC", COLORS["hvac"])
    return fig


def daily_energy(daily: pd.DataFrame) -> go.Figure:
    fig = _figure("Daily electrical energy", "Day", "Electrical energy [kWh/day]")
    parts = [("Lighting", ["energy_lighting_kwh"], "lighting"),
             ("HVAC", ["energy_hvac_cooling_kwh", "energy_hvac_heating_kwh"], "hvac"),
             ("Fans", ["energy_circulation_fans_kwh", "energy_ventilation_fans_kwh"], "fans"),
             ("Pumps", ["energy_pumps_kwh"], "pumps"), ("Auxiliary", ["energy_auxiliary_kwh"], "auxiliary")]
    for name, cols, color in parts:
        fig.add_trace(go.Bar(x=daily["day"], y=daily[cols].sum(axis=1), name=name, marker_color=COLORS[color]))
    fig.update_layout(barmode="stack", hovermode="x unified")
    return fig


def energy_breakdown(result: SimulationResult) -> go.Figure:
    energy = result.summary["energy_kwh"]
    labels = ["Lighting", "HVAC", "Fans", "Pumps", "Auxiliary"]
    keys = ["lighting", "hvac", "fans", "pumps", "auxiliary"]
    fig = go.Figure(go.Pie(labels=labels, values=[energy[k] for k in keys], sort=False, hole=0.45,
                           marker=dict(colors=[COLORS[k] for k in keys]),
                           texttemplate="%{label}<br>%{percent:.1%}", hovertemplate="%{label}: %{value:.0f} kWh"))
    fig.update_layout(title="Electricity breakdown", showlegend=False,
                      **{k: v for k, v in LAYOUT.items() if k not in ("legend", "hovermode")})
    return fig


def scenario_bars(table: pd.DataFrame, metric: str) -> go.Figure:
    fig = _figure(metric, "", metric)
    fig.add_trace(go.Bar(x=list(table.columns), y=table.loc[metric].values, marker_color=COLORS["hvac"],
                         text=[f"{v:.3g}" for v in table.loc[metric].values], textposition="outside"))
    fig.update_layout(showlegend=False)
    return fig


def scenario_energy_stack(results: dict[str, SimulationResult]) -> go.Figure:
    fig = _figure("Electricity by component", "", "Electrical energy [kWh]")
    for label, key in [("Lighting", "lighting"), ("HVAC", "hvac"), ("Fans", "fans"),
                       ("Pumps", "pumps"), ("Auxiliary", "auxiliary")]:
        fig.add_trace(go.Bar(x=list(results), y=[r.summary["energy_kwh"][key] for r in results.values()],
                             name=label, marker_color=COLORS[key]))
    fig.update_layout(barmode="stack")
    return fig


def scenario_tradeoff(results: dict[str, SimulationResult]) -> go.Figure:
    fig = _figure("Energy versus harvest", "Marketable fresh harvest [kg]", "Total electricity [kWh]")
    fig.add_trace(go.Scatter(
        x=[r.summary["crop"]["marketable_fresh_mass_kg"] for r in results.values()],
        y=[r.summary["energy_kwh"]["total"] for r in results.values()],
        text=list(results), mode="markers+text", textposition="top center",
        marker=dict(size=10, color=COLORS["hvac"])))
    fig.update_layout(showlegend=False, hovermode="closest")
    return fig


def farm_schematic(n_layers: int, footprint_m2: float, height_m: float) -> go.Figure:
    """Conceptual side view of the room (not to scale, not CAD)."""
    fig = go.Figure()
    w, h = 10.0, 6.0
    fig.add_shape(type="rect", x0=0, y0=0, x1=w, y1=h, line=dict(color="#2c3e50", width=3))
    shown = min(int(n_layers), 8)
    gap = (h - 1.0) / shown
    for i in range(shown):
        y = 0.4 + i * gap
        fig.add_shape(type="rect", x0=2.2, y0=y, x1=8.6, y1=y + 0.12 * gap, fillcolor="#8d6e63", line=dict(width=0))
        fig.add_shape(type="rect", x0=2.3, y0=y + 0.12 * gap, x1=8.5, y1=y + 0.34 * gap,
                      fillcolor=COLORS["crop"], opacity=0.75, line=dict(width=0))
        fig.add_shape(type="rect", x0=2.3, y0=y + 0.78 * gap, x1=8.5, y1=y + 0.84 * gap,
                      fillcolor=COLORS["lighting"], line=dict(width=0))
    fig.add_shape(type="rect", x0=0.25, y0=h - 1.5, x1=1.6, y1=h - 0.3, fillcolor=COLORS["hvac"],
                  opacity=0.85, line=dict(width=0))
    notes = [(0.92, h - 0.9, "HVAC", "white"), (0.95, 2.6, "air<br>circulation", "#2c3e50"),
             (9.35, h / 2, "crop<br>layers", COLORS["crop"]), (5.4, h + 0.35, "LED fixtures above each layer",
                                                              "#9a6a00"),
             (5.4, -0.45, f"{footprint_m2:g} m² footprint × {height_m:g} m high; {n_layers} layers = "
                          f"{footprint_m2 * n_layers:g} m² growing area", "#2c3e50")]
    for x, y, text, color in notes:
        fig.add_annotation(x=x, y=y, text=text, showarrow=False, font=dict(color=color, size=12))
    for x0, y0, x1, y1 in [(1.0, h - 1.6, 1.0, 3.3), (1.0, 1.9, 1.0, 0.7), (1.2, 0.5, 2.1, 0.5)]:
        fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y", axref="x", ayref="y",
                           showarrow=True, arrowhead=2, arrowcolor=COLORS["hvac"], arrowwidth=2)
    fig.update_xaxes(visible=False, range=[-0.3, w + 0.3])
    fig.update_yaxes(visible=False, range=[-0.9, h + 0.8], scaleanchor="x")
    fig.update_layout(template="simple_white", height=360, margin=dict(l=10, r=10, t=10, b=10))
    return fig
