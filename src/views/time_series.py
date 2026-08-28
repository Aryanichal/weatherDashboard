"""Time Series tab: raw parameter values over time, per selected station."""

import plotly.express as px

from src.dashboard_context import DashboardContext
from src.ui_theme import chart_card, render_chart
from src.views.common import render_parameter_and_subset


def render(ctx: DashboardContext) -> None:
    parameter, subset = render_parameter_and_subset(ctx.raw, key="parameter_series")
    fig = px.line(
        subset, x="date", y="value", color="station_name",
        title=f"{parameter} over time",
    )
    fig.update_xaxes(tickformat="%d-%m-%Y", hoverformat="%d-%m-%Y")
    with chart_card():
        render_chart(fig)
