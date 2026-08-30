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
_FEATURED_CHART_HEIGHT = 480

# Short labels for the band-chart trend-line toggle, and which of the
# other two 2m series bound the shaded band (low, high) for each choice.
# temperature_air_min_2m/_max_2m always occupy the low/high slot no
# matter what -- min <= mean <= max always holds in DWD's climate_summary
# -- only temperature_air_mean_2m ever moves between being the line and
# being a band edge.
_TEMPERATURE_TREND_LABELS = {
    "temperature_air_mean_2m": "Mean",
    "temperature_air_max_2m": "Max",
    "temperature_air_min_2m": "Min",
}
_TEMPERATURE_TREND_PARAMETER_BY_LABEL = {label: param for param, label in _TEMPERATURE_TREND_LABELS.items()}
_TEMPERATURE_BAND_BOUNDS = {
    "temperature_air_mean_2m": ("temperature_air_min_2m", "temperature_air_max_2m"),
    "temperature_air_max_2m": ("temperature_air_min_2m", "temperature_air_mean_2m"),
    "temperature_air_min_2m": ("temperature_air_mean_2m", "temperature_air_max_2m"),
}


def _station_color(station_name: str, station_order: list[str]) -> str:
    return _STATION_COLORS[station_order.index(station_name) % len(_STATION_COLORS)]


def _rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _render_temperature_band(subset: pd.DataFrame, trend_parameter: str) -> go.Figure:
    """2m air temperature as a shaded band + one highlighted trend line
    per station. ``trend_parameter`` picks which of the three 2m series
    (mean/max/min) is drawn as the solid line; the other two become the
    band's lower and upper edge, via _TEMPERATURE_BAND_BOUNDS. ``subset``
    must already be filtered to just the three 2m parameters."""
    low_parameter, high_parameter = _TEMPERATURE_BAND_BOUNDS[trend_parameter]
    trend_label = _TEMPERATURE_TREND_LABELS[trend_parameter]
    low_label = _TEMPERATURE_TREND_LABELS[low_parameter]
    high_label = _TEMPERATURE_TREND_LABELS[high_parameter]

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
                y=station_data[high_parameter],
                mode="lines",
                line=dict(width=0),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=station_data["date"],
                y=station_data[low_parameter],
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
                y=station_data[trend_parameter],
                mode="lines",
                name=station_name,
                line=dict(color=color),
                customdata=station_data[[low_parameter, high_parameter]],
                hovertemplate=(
                    f"<b>{station_name}</b><br>"
                    "%{x|%d-%m-%Y}<br>"
                    f"{trend_label}: " "%{y:.1f} °C<br>"
                    f"{low_label}: " "%{customdata[0]:.1f} °C · "
                    f"{high_label}: " "%{customdata[1]:.1f} °C"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(title=f"Temperature over time ({trend_label} trend)", legend_title_text="Station")
    fig.update_yaxes(title="Temperature (°C)")
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    return fig


def _render_ground_frost_chart(subset: pd.DataFrame) -> go.Figure:
    """Ground-level (5cm) minimum -- kept on its own axis since it's a
    frost-risk reading rather than an air-temperature variant."""
    ground = subset[subset["parameter"] == TEMPERATURE_GROUND_PARAMETER]
    fig = px.line(
        ground, x="date", y="value", color="station_name",
        title="Ground Frost Temperature (5cm) over time",
        labels={"value": "Temperature (°C)", "station_name": "Station"},
    )
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    return fig


def _render_monthly_average_chart(subset: pd.DataFrame) -> go.Figure:
    """Average daily-mean 2m air temperature per calendar month, per
    station -- always keyed to the mean series regardless of the band
    chart's trend-line toggle, since this is meant as a stable seasonal
    reference rather than something that should shift with it."""
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
    """Daily rainfall amount per station, as a bar chart -- rainfall
    totals are conventionally shown as bars, unlike temperature."""
    height = subset[subset["parameter"] == "precipitation_height"]
    fig = px.bar(
        height, x="date", y="value", color="station_name", barmode="group",
        title="Precipitation over time",
        labels={"value": "Precipitation (mm)", "station_name": "Station"},
    )
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    return fig


def _render_precipitation_form_chart(subset: pd.DataFrame) -> go.Figure:
    """What form the precipitation took, as a monthly stacked bar of day
    counts per DWD precipitation-form code (see PRECIPITATION_FORM_LABELS
    in src/analysis.py), faceted one panel per station."""
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


def _render_featured_chart(fig: go.Figure) -> None:
    """Render one chart full-width at the taller "featured" height, above
    whatever grid of smaller charts follows it."""
    fig.update_layout(height=_FEATURED_CHART_HEIGHT)
    with chart_card():
        render_chart(fig)


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

        trend_label = st.segmented_control(
            "Trend line",
            options=list(_TEMPERATURE_TREND_PARAMETER_BY_LABEL),
            default="Mean",
            key="temperature_trend_line",
        )
        # segmented_control returns None if the user clicks the selected
        # option again to deselect it -- fall back to Mean rather than
        # letting the chart below break.
        trend_parameter = _TEMPERATURE_TREND_PARAMETER_BY_LABEL[trend_label or "Mean"]

        _render_featured_chart(_render_temperature_band(band_subset, trend_parameter))
        _render_chart_grid(
            [
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