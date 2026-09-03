"""Map tab: mean parameter value per station, plotted geographically.

(Cluster-coloring used to live here as an alternate mode; it's moved to
the Clustering tab's own "Map View" option instead -- see
src/views/clustering.py -- so cluster-by-map and cluster-by-scatter sit
together in one place rather than being split across two tabs.)
"""

import plotly.express as px
import streamlit as st

from src.dashboard_context import DashboardContext
from src.data_loader import load_stations
from src.views.common import (
    CHART_ROW_WIDTH_RATIO,
    find_stations_missing_data,
    pretty_name,
    render_full_bleed_map,
    render_missing_stations_notice,
    render_parameter_and_subset,
    render_section_label,
)

_MISSING_ANCHOR = "missing-stations-parameter_map"
_CHART_CARD_KEY = "chart-card-parameter_map"


def render(ctx: DashboardContext) -> None:
    _parameter, _subset, parameter, subset, render_key_figures = render_parameter_and_subset(
        ctx.raw, key="parameter_map", collapse_composites=True
    )
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

    render_section_label(f"Mean {pretty_name(parameter)} by station", style="header")
    fig = px.scatter_map(
        merged, lat="latitude", lon="longitude", size="value", color="value",
        hover_name="name", zoom=4.5, map_style="open-street-map",
        labels={"value": pretty_name(parameter)},
    )
    # CHART_ROW_WIDTH_RATIO's share of the row, same as every other
    # chart-bearing tab (Time Series, Regression, Clustering) -- see
    # common.py for where this convention started. Key Figures goes in
    # the remaining column, right next to the map.
    row_columns = st.columns(CHART_ROW_WIDTH_RATIO)
    with row_columns[0]:
        render_full_bleed_map(fig, _CHART_CARD_KEY, missing, _MISSING_ANCHOR)
    if render_key_figures:
        with row_columns[1]:
            render_key_figures()
    render_missing_stations_notice(missing, _MISSING_ANCHOR)
