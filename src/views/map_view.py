"""Map tab: mean parameter value per station, plotted geographically."""

import plotly.express as px
import streamlit as st

from src.dashboard_context import DashboardContext
from src.data_loader import load_stations
from src.ui_theme import chart_card, render_chart
from src.views.common import (
    find_stations_missing_data,
    pretty_name,
    render_missing_stations_indicator,
    render_missing_stations_notice,
    render_parameter_and_subset,
)

_MISSING_ANCHOR = "missing-stations-parameter_map"
_CHART_CARD_KEY = "chart-card-parameter_map"


def render(ctx: DashboardContext) -> None:
    parameter, subset = render_parameter_and_subset(ctx.raw, key="parameter_map")
    missing = find_stations_missing_data(ctx, parameter, subset, ctx.start_date, ctx.end_date)

    stations_meta = load_stations()
    if stations_meta.empty:
        st.caption("Station coordinate metadata is unavailable right now.")
        render_missing_stations_notice(missing, _MISSING_ANCHOR)
        return

    avg_value = subset.groupby("station_id", as_index=False)["value"].mean()
    merged = stations_meta.merge(avg_value, on="station_id")
    if merged.empty:
        st.caption(f"No {pretty_name(parameter)} data for any selected station in this date range.")
        render_missing_stations_notice(missing, _MISSING_ANCHOR)
        return

    fig = px.scatter_map(
        merged, lat="latitude", lon="longitude", size="value", color="value",
        hover_name="name", zoom=4.5, map_style="open-street-map",
        title=f"Mean {pretty_name(parameter)} by station",
        labels={"value": pretty_name(parameter)},
    )
    with chart_card(key=_CHART_CARD_KEY):
        render_missing_stations_indicator(missing, _MISSING_ANCHOR, card_key=_CHART_CARD_KEY)
        render_chart(fig)
    render_missing_stations_notice(missing, _MISSING_ANCHOR)
