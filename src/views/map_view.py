"""Map tab: mean parameter value per station, plotted geographically."""

import plotly.express as px
import streamlit as st

from src.dashboard_context import DashboardContext
from src.data_loader import load_stations
from src.ui_theme import chart_card, render_chart
from src.views.common import pretty_name, render_parameter_and_subset


def render(ctx: DashboardContext) -> None:
    parameter, subset = render_parameter_and_subset(ctx.raw, key="parameter_map")
    stations_meta = load_stations()
    if stations_meta.empty:
        st.caption("Station coordinate metadata is unavailable right now.")
        return

    avg_value = subset.groupby("station_id", as_index=False)["value"].mean()
    merged = stations_meta.merge(avg_value, on="station_id")
    fig = px.scatter_map(
        merged, lat="latitude", lon="longitude", size="value", color="value",
        hover_name="name", zoom=4.5, map_style="open-street-map",
        title=f"Mean {pretty_name(parameter)} by station",
        labels={"value": pretty_name(parameter)},
    )
    with chart_card():
        render_chart(fig)
