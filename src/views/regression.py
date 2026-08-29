"""Regression tab: linear trend line for one station's parameter over time."""

import plotly.express as px
import streamlit as st

from src.analysis import fit_trend
from src.dashboard_context import DashboardContext
from src.ui_theme import chart_card, render_chart
from src.views.common import pretty_name, render_parameter_and_subset


def render(ctx: DashboardContext) -> None:
    parameter, subset = render_parameter_and_subset(ctx.raw, key="parameter_regression")
    station_for_trend = st.selectbox("Station", ctx.selected_names, key="trend_station")
    station_id = ctx.id_by_name[station_for_trend]
    trend_input = subset[subset["station_id"] == station_id]

    if len(trend_input) < 2:
        st.info("Not enough data points for a trend line.")
        return

    result = fit_trend(trend_input)
    value_label = pretty_name(parameter)
    st.write(f"Slope: {result['slope_per_day'] * 365:.4f} units/year")
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
