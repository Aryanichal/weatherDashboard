"""Regression tab: linear trend line for one station's parameter over time."""

import plotly.express as px
import streamlit as st

from src.analysis import fit_trend
from src.dashboard_context import DashboardContext
from src.ui_theme import chart_card, render_chart
from src.views.common import (
    missing_station_reason,
    pretty_name,
    render_parameter_and_subset,
    render_section_label,
)


def render(ctx: DashboardContext) -> None:
    parameter, subset = render_parameter_and_subset(ctx.raw, key="parameter_regression")
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
    render_section_label(f"Slope: {result['slope_per_day'] * 365:.4f} units/year")
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
    with chart_card():
        render_chart(fig)
