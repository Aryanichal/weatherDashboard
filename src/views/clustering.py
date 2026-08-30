"""Clustering tab: KMeans-cluster selected stations by mean parameter value."""

import plotly.express as px
import streamlit as st

from src.analysis import cluster_stations
from src.dashboard_context import DashboardContext
from src.ui_theme import chart_card, render_chart
from src.views.common import (
    find_stations_missing_data,
    pretty_name,
    render_missing_stations_indicator,
    render_missing_stations_notice,
    render_parameter_and_subset,
)

_MISSING_ANCHOR = "missing-stations-parameter_clustering"
_CHART_CARD_KEY = "chart-card-parameter_clustering"


def render(ctx: DashboardContext) -> None:
    _parameter, _subset, parameter, subset = render_parameter_and_subset(
        ctx.raw, key="parameter_clustering", collapse_composites=True
    )
    missing = find_stations_missing_data(ctx, parameter, subset, ctx.start_date, ctx.end_date)

    n_clusters = st.slider("Number of clusters", 2, 6, 3)
    per_station = subset.groupby("station_id", as_index=False)["value"].mean()
    per_station["station_name"] = per_station["station_id"].map(ctx.id_to_name)

    if len(per_station) < n_clusters:
        station_word = "station" if len(per_station) == 1 else "stations"
        st.info(
            f"Only {len(per_station)} selected {station_word} have {pretty_name(parameter)} data "
            f"in this date range -- select more stations, a smaller cluster count, or a different "
            f"date range to run KMeans with {n_clusters} clusters."
        )
        render_missing_stations_notice(missing, _MISSING_ANCHOR)
        return

    clustered = cluster_stations(per_station, feature_cols=["value"], n_clusters=n_clusters)
    value_label = pretty_name(parameter)
    fig = px.bar(
        clustered.sort_values("value"), x="station_name", y="value", color="cluster",
        title=f"Stations clustered by mean {value_label}",
        labels={"value": value_label, "station_name": "Station", "cluster": "Cluster"},
    )
    with chart_card(key=_CHART_CARD_KEY):
        render_missing_stations_indicator(missing, _MISSING_ANCHOR, card_key=_CHART_CARD_KEY)
        render_chart(fig)
    render_missing_stations_notice(missing, _MISSING_ANCHOR)
    with chart_card():
        st.dataframe(
            clustered.rename(
                columns={
                    "station_id": "Station ID",
                    "station_name": "Station",
                    "value": value_label,
                    "cluster": "Cluster",
                }
            ),
            width="stretch",
        )
