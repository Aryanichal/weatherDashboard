"""Time Series tab: raw parameter values over time, per selected station."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analysis import (
    PRECIPITATION_COMPOSITE_KEY,
    PRECIPITATION_FORM_LABELS,
    TEMPERATURE_COMPONENT_PARAMETERS,
    TEMPERATURE_COMPOSITE_KEY,
    TEMPERATURE_GROUND_PARAMETER,
    TEMPERATURE_PRIMARY_PARAMETER,
)
from src.dashboard_context import DashboardContext
from src.ui_theme import chart_card, render_chart
from src.views.common import pretty_name, render_parameter_and_subset

_STATION_COLORS = px.colors.qualitative.Plotly
_GRID_CHART_HEIGHT = 340
_GRID_COLUMNS = 2


def _station_color(station_name: str, station_order: list[str]) -> str:
    return _STATION_COLORS[station_order.index(station_name) % len(_STATION_COLORS)]


def _rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _render_temperature_band(subset: pd.DataFrame) -> go.Figure:
    """2m air temperature (max/mean/min) as a shaded band + mean line per
    station. ``subset`` must already be filtered to just the three 2m
    parameters."""
    wide = subset.pivot_table(index=["station_name", "date"], columns="parameter", values="value").reset_index()
    wide = wide.sort_values(["station_name", "date"])
    station_order = sorted(wide["station_name"].unique())

    fig = go.Figure()
    for station_name in station_order:
        station_data = wide[wide["station_name"] == station_name]
        color = _station_color(station_name, station_order)

        fig.add_trace(
            go.Scatter(
                x=station_data["date"],
                y=station_data["temperature_air_max_2m"],
                mode="lines",
                line=dict(width=0),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=station_data["date"],
                y=station_data["temperature_air_min_2m"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor=_rgba(color, 0.18),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=station_data["date"],
                y=station_data["temperature_air_mean_2m"],
                mode="lines",
                name=station_name,
                line=dict(color=color),
                customdata=station_data[["temperature_air_min_2m", "temperature_air_max_2m"]],
                hovertemplate=(
                    f"<b>{station_name}</b><br>"
                    "%{x|%d-%m-%Y}<br>"
                    "Mean: %{y:.1f} °C<br>"
                    "Min: %{customdata[0]:.1f} °C · Max: %{customdata[1]:.1f} °C"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(title="Temperature over time", legend_title_text="Station")
    fig.update_yaxes(title="Temperature (°C)")
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    return fig


def _render_ground_frost_chart(subset: pd.DataFrame) -> go.Figure:
    """Second temperature visual: the 5cm ground-level minimum, kept on
    its own axis since it's a frost-risk reading rather than an
    air-temperature variant."""
    ground = subset[subset["parameter"] == TEMPERATURE_GROUND_PARAMETER]
    fig = px.line(
        ground, x="date", y="value", color="station_name",
        title="Ground Frost Temperature (5cm) over time",
        labels={"value": "Temperature (°C)", "station_name": "Station"},
    )
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    return fig


def _render_monthly_average_chart(subset: pd.DataFrame) -> go.Figure:
    """Third temperature visual: average daily-mean 2m air temperature per
    calendar month, per station -- the season-at-a-glance summary of the
    noisy daily band chart above."""
    mean_temp = subset[subset["parameter"] == TEMPERATURE_PRIMARY_PARAMETER].copy()
    mean_temp["month"] = pd.to_datetime(mean_temp["date"]).dt.to_period("M").dt.to_timestamp()
    monthly = mean_temp.groupby(["station_name", "month"], as_index=False)["value"].mean()

    fig = px.bar(
        monthly, x="month", y="value", color="station_name", barmode="group",
        title="Average Monthly Temperature",
        labels={"value": "Mean Temperature (°C)", "month": "Month", "station_name": "Station"},
    )
    fig.update_xaxes(tickformat="%b %Y", dtick="M1")
    return fig


def _render_precipitation_height_chart(subset: pd.DataFrame) -> go.Figure:
    """First precipitation visual: daily rainfall amount per station, as
    a bar chart -- rainfall totals are conventionally shown as bars
    (one per day), unlike temperature which reads better as a continuous
    line."""
    height = subset[subset["parameter"] == "precipitation_height"]
    fig = px.bar(
        height, x="date", y="value", color="station_name", barmode="group",
        title="Precipitation over time",
        labels={"value": "Precipitation (mm)", "station_name": "Station"},
    )
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    return fig


def _render_precipitation_form_chart(subset: pd.DataFrame) -> go.Figure:
    """Second precipitation visual: what form the precipitation took,
    as a monthly stacked bar of day counts per DWD precipitation-form
    code (see PRECIPITATION_FORM_LABELS in src/analysis.py) -- one
    faceted panel per station, since form and station both need their
    own visual dimension and color is already spent on form."""
    form = subset[subset["parameter"] == "precipitation_form"].dropna(subset=["value"]).copy()
    form["form_label"] = form["value"].map(PRECIPITATION_FORM_LABELS)
    form["form_label"] = form["form_label"].fillna(form["value"].apply(lambda code: f"Code {code:g}"))
    form["month"] = pd.to_datetime(form["date"]).dt.to_period("M").dt.to_timestamp()
    monthly_counts = (
        form.groupby(["station_name", "month", "form_label"], as_index=False)
        .size()
        .rename(columns={"size": "days"})
    )

    fig = px.bar(
        monthly_counts, x="month", y="days", color="form_label", barmode="stack",
        facet_col="station_name",
        title="Precipitation Form by Month",
        labels={"days": "Days", "month": "Month", "form_label": "Form"},
    )
    fig.update_xaxes(tickformat="%b %Y", dtick="M2")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return fig


def _render_chart_grid(figs: list[go.Figure], columns: int = _GRID_COLUMNS) -> None:
    """Lay out ``figs`` in a fixed-column grid instead of stacking each one
    full-width, so a typical desktop viewport shows multiple charts at
    once without scrolling."""
    for fig in figs:
        fig.update_layout(height=_GRID_CHART_HEIGHT, title_font_size=16)
    for start in range(0, len(figs), columns):
        row_figs = figs[start : start + columns]
        row_columns = st.columns(len(row_figs))
        for col, fig in zip(row_columns, row_figs):
            with col, chart_card():
                render_chart(fig)


def render(ctx: DashboardContext) -> None:
    parameter, subset = render_parameter_and_subset(ctx.raw, key="parameter_series", collapse_composites=True)

    if parameter == TEMPERATURE_COMPOSITE_KEY:
        band_subset = subset[subset["parameter"].isin(TEMPERATURE_COMPONENT_PARAMETERS)]
        _render_chart_grid(
            [
                _render_temperature_band(band_subset),
                _render_ground_frost_chart(subset),
                _render_monthly_average_chart(subset),
            ]
        )
    elif parameter == PRECIPITATION_COMPOSITE_KEY:
        _render_chart_grid(
            [
                _render_precipitation_height_chart(subset),
                _render_precipitation_form_chart(subset),
            ]
        )
    else:
        fig = px.line(
            subset, x="date", y="value", color="station_name",
            title=f"{pretty_name(parameter)} over time",
            labels={"value": pretty_name(parameter), "station_name": "Station"},
        )
        fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
        with chart_card():
            render_chart(fig)