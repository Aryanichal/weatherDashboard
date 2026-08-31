"""Regression tab: linear trend line for one station's parameter over time."""

import plotly.express as px
import streamlit as st

from src.analysis import fit_trend
from src.dashboard_context import DashboardContext
from src.ui_theme import chart_card, render_chart
from src.views.common import (
    CHART_ROW_WIDTH_RATIO,
    missing_station_reason,
    pretty_name,
    render_parameter_and_subset,
    render_section_label,
)


def render(ctx: DashboardContext) -> None:
    _parameter, _subset, parameter, subset, render_key_figures = render_parameter_and_subset(
        ctx.raw, key="parameter_regression", collapse_composites=True
    )
    render_section_label("Station")
    station_for_trend = st.selectbox(
        "Station", ctx.selected_names, key="trend_station", label_visibility="collapsed"
    )
    station_id = ctx.id_by_name[station_for_trend]
    trend_input = subset[subset["station_id"] == station_id]

    if len(trend_input) < 2:
        if trend_input.empty:
            reason = missing_station_reason(ctx, parameter, station_id, ctx.start_date, ctx.end_date)
            st.info(f"No trend for {station_for_trend} -- {reason}.")
        else:
            st.info(
                f"Only one {pretty_name(parameter)} reading for {station_for_trend} in the "
                f"selected date range -- at least two are needed to fit a trend."
            )
        return

    result = fit_trend(trend_input)
    value_label = pretty_name(parameter)
    render_section_label(f"Slope: {result['slope_per_day'] * 365:.4f} units/year", style="header")
    fig = px.line(
        result["data"], x="date", y=["value", "trend"],
        title=f"{value_label} trend for {station_for_trend}",
        # Plotly Express melts y=[...] into synthetic "variable"/"value"
        # columns for wide-form data, but the input here already has a real
        # column literally named "value" -- to avoid the collision, Plotly
        # silently renames its own synthetic one to "_value" (confirmed via
        # DevTools: the rendered y-axis title was "_value", not "value",
        # before this was added), so that's the key the y-axis label
        # actually needs.
        labels={"_value": value_label, "variable": "Series"},
    )
    fig.for_each_trace(lambda t: t.update(name={"value": value_label, "trend": "Trend"}.get(t.name, t.name)))
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    # CHART_ROW_WIDTH_RATIO's share of the row, same as every other
    # chart-bearing tab (Time Series, Map, Clustering) -- see common.py for
    # where this convention started. Key Figures goes in the remaining
    # column, right next to the chart.
    row_columns = st.columns(CHART_ROW_WIDTH_RATIO)
    with row_columns[0], chart_card():
        render_chart(fig)
    if render_key_figures:
        with row_columns[1]:
            render_key_figures()
