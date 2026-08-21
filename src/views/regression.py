"""Regression tab: linear trend line for one station's parameter over time."""

import plotly.express as px
import streamlit as st

from src.analysis import fit_trend
from src.dashboard_context import DashboardContext
from src.views.common import render_parameter_and_subset


def render(ctx: DashboardContext) -> None:
    parameter, subset = render_parameter_and_subset(ctx.raw, key="parameter_regression")
    station_for_trend = st.selectbox("Station", ctx.selected_names, key="trend_station")
    station_id = ctx.id_by_name[station_for_trend]
    trend_input = subset[subset["station_id"] == station_id]

    if len(trend_input) < 2:
        st.info("Not enough data points for a trend line.")
        return

    result = fit_trend(trend_input)
    st.write(f"Slope: {result['slope_per_day'] * 365:.4f} units/year")
    fig = px.line(result["data"], x="date", y=["value", "trend"])
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    st.plotly_chart(fig, width="stretch")
