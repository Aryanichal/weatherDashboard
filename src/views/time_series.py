"""Time Series tab: raw parameter values over time, per selected station."""

from collections.abc import Callable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analysis import (
    HUMIDITY_COMPOSITE_COMPONENTS,
    HUMIDITY_COMPOSITE_KEY,
    PRECIPITATION_COMPOSITE_KEY,
    PRECIPITATION_FORM_LABELS,
    TEMPERATURE_COMPONENT_PARAMETERS,
    TEMPERATURE_COMPOSITE_KEY,
    TEMPERATURE_GROUND_PARAMETER,
    TEMPERATURE_PRIMARY_PARAMETER,
    TEMPERATURE_TREND_LABELS,
    WIND_COMPOSITE_KEY,
)
from src.dashboard_context import DashboardContext
from src.ui_theme import chart_card, render_chart
from src.views.common import (
    CHART_ROW_WIDTH_RATIO,
    find_stations_missing_data,
    merge_missing_stations,
    pretty_name,
    render_key_figures_box,
    render_missing_stations_indicator,
    render_missing_stations_notice,
    render_parameter_and_subset,
)

_MISSING_ANCHOR = "missing-stations-parameter_series"
_CHART_CARD_KEY = "chart-card-parameter_series"
_TEMPERATURE_FEATURED_CARD_KEY = "chart-card-parameter_series-temperature-featured"
_TEMPERATURE_GROUND_CARD_KEY = "chart-card-parameter_series-temperature-ground"
_PRECIPITATION_HEIGHT_CARD_KEY = "chart-card-parameter_series-precipitation-height"
_WIND_SPEED_CARD_KEY = "chart-card-parameter_series-wind-speed"

_STATION_COLORS = px.colors.qualitative.Plotly
_GRID_CHART_HEIGHT = 340
_FEATURED_CHART_HEIGHT = 480

# Which of the other two 2m series bound the shaded band (low, high) for
# each trend-line choice. min/max always occupy the low/high slot; only
# mean ever moves between being the line and being a band edge.
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


def _render_line_chart(subset: pd.DataFrame, parameter: str) -> go.Figure:
    """Plain line chart for one parameter -- used for any non-composite
    parameter (the default case in render()) and for each component of
    the Humidity/Pressure Vapor composite."""
    fig = px.line(
        subset, x="date", y="value", color="station_name",
        title=f"{pretty_name(parameter)} over time",
        labels={"value": pretty_name(parameter), "station_name": "Station"},
    )
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    return fig


def _render_temperature_band(subset: pd.DataFrame, trend_parameter: str) -> go.Figure:
    """2m air temperature as a shaded band + one highlighted trend line
    per station. ``trend_parameter`` picks which of the three 2m series
    (mean/max/min) is drawn as the solid line; the other two become the
    band's lower and upper edge, via _TEMPERATURE_BAND_BOUNDS. ``subset``
    must already be filtered to just the three 2m parameters."""
    low_parameter, high_parameter = _TEMPERATURE_BAND_BOUNDS[trend_parameter]
    trend_label = TEMPERATURE_TREND_LABELS[trend_parameter]
    low_label = TEMPERATURE_TREND_LABELS[low_parameter]
    high_label = TEMPERATURE_TREND_LABELS[high_parameter]

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
    """Average daily-mean 2m air temperature per calendar month, always
    keyed to the mean series regardless of the band chart's trend toggle."""
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


def _render_snow_depth_chart(subset: pd.DataFrame) -> go.Figure:
    """Daily snow depth per station. Grouped under Precipitation but
    rendered as its own block, since depth is an accumulated stock, not
    the same kind of quantity as a daily rain amount or form code."""
    fig = px.line(
        subset, x="date", y="value", color="station_name",
        title="Snow Depth over time",
        labels={"value": "Snow Depth (cm)", "station_name": "Station"},
    )
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    return fig


def _render_wind_speed_chart(subset: pd.DataFrame) -> go.Figure:
    """Daily mean wind speed. Gust is kept separate (_render_wind_gust_chart)
    since it's a spiky peak reading that doesn't band against a daily mean."""
    speed = subset[subset["parameter"] == "wind_speed"]
    fig = px.line(
        speed, x="date", y="value", color="station_name",
        title="Wind Speed over time",
        labels={"value": "Wind Speed (m/s)", "station_name": "Station"},
    )
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    return fig


def _render_wind_gust_chart(subset: pd.DataFrame) -> go.Figure:
    """Peak wind gust per calendar month -- zooms out from noisy daily data,
    same idea as _render_monthly_average_chart() for temperature."""
    gust = subset[subset["parameter"] == "wind_gust_max"].copy()
    gust["month"] = pd.to_datetime(gust["date"]).dt.to_period("M").dt.to_timestamp()
    monthly = gust.groupby(["station_name", "month"], as_index=False)["value"].max()

    fig = px.bar(
        monthly, x="month", y="value", color="station_name", barmode="group",
        title="Peak Wind Gust by Month",
        labels={"value": "Max Gust (m/s)", "month": "Month", "station_name": "Station"},
    )
    fig.update_xaxes(tickformat="%b %Y", dtick="M1")
    return fig


def _render_featured_chart(
    fig: go.Figure,
    missing: list[dict[str, str]] | None = None,
    card_key: str | None = None,
    render_key_figures: Callable[..., None] | None = None,
) -> None:
    """Render one chart at the taller "featured" height, above whatever
    grid of smaller charts follows it. ``render_key_figures``, when given,
    renders that composite's Key Figures box into the row's remaining
    column. ``missing``/``card_key``, when given, overlay the
    missing-station warning icon; ``card_key`` must be unique app-wide."""
    fig.update_layout(height=_FEATURED_CHART_HEIGHT)
    row_columns = st.columns(CHART_ROW_WIDTH_RATIO)
    with row_columns[0], chart_card(key=card_key):
        if missing and card_key:
            render_missing_stations_indicator(missing, _MISSING_ANCHOR, card_key=card_key)
        render_chart(fig)
    if render_key_figures:
        with row_columns[1]:
            render_key_figures(_FEATURED_CHART_HEIGHT)


def _render_chart_grid(
    figs: list[go.Figure],
    missing: list[dict[str, str]] | None = None,
    icon_card_key: str | None = None,
    render_key_figures: Callable[..., None] | None = None,
) -> None:
    """Lay out ``figs`` one per row instead of pairing two to a row.
    ``missing``/``icon_card_key``, when given, overlay the missing-station
    warning icon on just the *first* chart's card (the composite's
    "primary" component) -- ``icon_card_key`` must be unique app-wide.
    ``render_key_figures``, when given, renders into that same first row;
    every later row's remaining column stays empty."""
    for fig in figs:
        fig.update_layout(height=_GRID_CHART_HEIGHT, title_font_size=16)
    is_first = True
    for fig in figs:
        row_columns = st.columns(CHART_ROW_WIDTH_RATIO)
        card_key = icon_card_key if is_first else None
        with row_columns[0], chart_card(key=card_key):
            if is_first and missing and icon_card_key:
                render_missing_stations_indicator(missing, _MISSING_ANCHOR, card_key=icon_card_key)
            render_chart(fig)
        if is_first and render_key_figures:
            with row_columns[1]:
                render_key_figures(_GRID_CHART_HEIGHT)
        is_first = False


def _render_chart_row(fig: go.Figure, render_key_figures: Callable[..., None] | None = None) -> None:
    """Render one chart at CHART_ROW_WIDTH_RATIO's share of its row, for a
    chart meant to sit under a specific chart above it rather than stretch
    full width. ``render_key_figures``, when given, renders into the row's
    remaining column."""
    fig.update_layout(height=_GRID_CHART_HEIGHT, title_font_size=16)
    row_columns = st.columns(CHART_ROW_WIDTH_RATIO)
    with row_columns[0], chart_card():
        render_chart(fig)
    if render_key_figures:
        with row_columns[1]:
            render_key_figures(_GRID_CHART_HEIGHT)


def _render_humidity_composite(ctx: DashboardContext, subset: pd.DataFrame) -> list[dict[str, str]]:
    """Humidity and Pressure Vapor: each component's own chart, with its own
    Key Figures box beside it. Marked "stats_parameters" in
    COMPOSITE_PARAMETER_GROUPS so render_parameter_and_subset() leaves
    ``render_key_figures`` as ``None``, leaving layout up to this function.

    Each component gets its own missing-station check scoped to just that
    component, not the composite as a whole -- a station present via
    humidity alone shouldn't suppress the warning on the Pressure Vapor
    chart it's missing from. Returns the merged list for render()."""
    missing_lists = []
    for component in HUMIDITY_COMPOSITE_COMPONENTS:
        component_subset = subset[subset["parameter"] == component]
        component_missing = find_stations_missing_data(ctx, component, component_subset, ctx.start_date, ctx.end_date)
        missing_lists.append(component_missing)
        card_key = f"chart-card-parameter_series-{component}"
        row_columns = st.columns(CHART_ROW_WIDTH_RATIO)
        with row_columns[0], chart_card(key=card_key):
            if component_missing:
                render_missing_stations_indicator(component_missing, _MISSING_ANCHOR, card_key=card_key)
            render_chart(_render_line_chart(component_subset, component))
        with row_columns[1]:
            render_key_figures_box(component_subset, component, key_prefix=f"parameter_series-{component}")
    return merge_missing_stations(*missing_lists)


def render(ctx: DashboardContext) -> None:
    parameter, subset, effective_parameter, _effective_subset, render_key_figures = render_parameter_and_subset(
        ctx.raw, key="parameter_series", collapse_composites=True
    )
    missing = find_stations_missing_data(ctx, parameter, subset, ctx.start_date, ctx.end_date)

    if subset.empty:
        st.caption(f"No {pretty_name(parameter)} data for any selected station in this date range.")
        render_missing_stations_notice(missing, _MISSING_ANCHOR)
        return

    if parameter == TEMPERATURE_COMPOSITE_KEY:
        band_subset = subset[subset["parameter"].isin(TEMPERATURE_COMPONENT_PARAMETERS)]
        ground_subset = subset[subset["parameter"] == TEMPERATURE_GROUND_PARAMETER]
        monthly_subset = subset[subset["parameter"] == TEMPERATURE_PRIMARY_PARAMETER]

        # Each chart is checked against exactly the parameter(s) it draws
        # from, not the whole composite's union, so a station present only
        # via ground-frost data doesn't wrongly read as "present" for the
        # 2m band chart it has zero rows for.
        band_missing = find_stations_missing_data(
            ctx, TEMPERATURE_COMPOSITE_KEY, band_subset, ctx.start_date, ctx.end_date,
            component_parameters=TEMPERATURE_COMPONENT_PARAMETERS,
        )
        ground_missing = find_stations_missing_data(
            ctx, TEMPERATURE_GROUND_PARAMETER, ground_subset, ctx.start_date, ctx.end_date
        )
        monthly_missing = find_stations_missing_data(
            ctx, TEMPERATURE_PRIMARY_PARAMETER, monthly_subset, ctx.start_date, ctx.end_date
        )

        # effective_parameter is whichever 2m series the shared Mean/Max/Min
        # toggle (rendered by render_parameter_and_subset()) has selected.
        _render_featured_chart(
            _render_temperature_band(band_subset, effective_parameter),
            missing=band_missing, card_key=_TEMPERATURE_FEATURED_CARD_KEY, render_key_figures=render_key_figures,
        )
        _render_chart_grid(
            [
                _render_ground_frost_chart(subset),
                _render_monthly_average_chart(subset),
            ],
            missing=ground_missing, icon_card_key=_TEMPERATURE_GROUND_CARD_KEY,
        )
        render_missing_stations_notice(
            merge_missing_stations(band_missing, ground_missing, monthly_missing), _MISSING_ANCHOR
        )
    elif parameter == PRECIPITATION_COMPOSITE_KEY:
        height_subset = subset[subset["parameter"] == "precipitation_height"]
        form_subset = subset[subset["parameter"] == "precipitation_form"]
        snow_subset = subset[subset["parameter"] == "snow_depth"]

        height_missing = find_stations_missing_data(
            ctx, "precipitation_height", height_subset, ctx.start_date, ctx.end_date
        )
        form_missing = find_stations_missing_data(ctx, "precipitation_form", form_subset, ctx.start_date, ctx.end_date)
        snow_missing = find_stations_missing_data(ctx, "snow_depth", snow_subset, ctx.start_date, ctx.end_date)

        _render_chart_grid(
            [
                _render_precipitation_height_chart(subset),
                _render_precipitation_form_chart(subset),
            ],
            missing=height_missing, icon_card_key=_PRECIPITATION_HEIGHT_CARD_KEY, render_key_figures=render_key_figures,
        )
        _render_chart_row(
            _render_snow_depth_chart(snow_subset),
            render_key_figures=lambda chart_height=_GRID_CHART_HEIGHT: render_key_figures_box(
                snow_subset, "snow_depth", key_prefix="parameter_series-snow_depth", chart_height=chart_height
            ),
        )
        render_missing_stations_notice(
            merge_missing_stations(height_missing, form_missing, snow_missing), _MISSING_ANCHOR
        )
    elif parameter == WIND_COMPOSITE_KEY:
        speed_subset = subset[subset["parameter"] == "wind_speed"]
        gust_subset = subset[subset["parameter"] == "wind_gust_max"]
        
        speed_missing = find_stations_missing_data(ctx, "wind_speed", speed_subset, ctx.start_date, ctx.end_date)
        gust_missing = find_stations_missing_data(ctx, "wind_gust_max", gust_subset, ctx.start_date, ctx.end_date)

        _render_chart_grid(
            [
                _render_wind_speed_chart(subset),
                _render_wind_gust_chart(subset),
            ],
            missing=speed_missing, icon_card_key=_WIND_SPEED_CARD_KEY, render_key_figures=render_key_figures,
        )
        render_missing_stations_notice(merge_missing_stations(speed_missing, gust_missing), _MISSING_ANCHOR)
    elif parameter == HUMIDITY_COMPOSITE_KEY:
        humidity_missing = _render_humidity_composite(ctx, subset)
        render_missing_stations_notice(humidity_missing, _MISSING_ANCHOR)
    else:
        row_columns = st.columns(CHART_ROW_WIDTH_RATIO)
        with row_columns[0], chart_card(key=_CHART_CARD_KEY):
            render_missing_stations_indicator(missing, _MISSING_ANCHOR, card_key=_CHART_CARD_KEY)
            render_chart(_render_line_chart(subset, parameter))
        if render_key_figures:
            with row_columns[1]:
                render_key_figures()
        render_missing_stations_notice(missing, _MISSING_ANCHOR)
