"""Time Series tab: raw parameter values over time, per selected station."""

import plotly.express as px
import streamlit as st

from src.dashboard_context import DashboardContext
from src.views.common import render_parameter_and_subset


def render(ctx: DashboardContext) -> None:
    parameter, subset = render_parameter_and_subset(ctx.raw, key="parameter_series")
    fig = px.line(
        subset, x="date", y="value", color="station_name",
        title=f"{parameter} over time",
    )
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    st.plotly_chart(fig, width="stretch")
