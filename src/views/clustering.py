"""Clustering tab: KMeans-cluster selected stations by mean parameter value."""

import plotly.express as px
import streamlit as st

from src.analysis import cluster_stations
from src.dashboard_context import DashboardContext
from src.ui_theme import chart_card, render_chart
from src.views.common import pretty_name, render_parameter_and_subset


def render(ctx: DashboardContext) -> None:
    parameter, subset = render_parameter_and_subset(ctx.raw, key="parameter_clustering")
    n_clusters = st.slider("Number of clusters", 2, 6, 3)
    per_station = subset.groupby("station_id", as_index=False)["value"].mean()
    per_station["station_name"] = per_station["station_id"].map(ctx.id_to_name)

    if len(per_station) < n_clusters:
        st.info("Select more stations than clusters to run KMeans.")
        return

    clustered = cluster_stations(per_station, feature_cols=["value"], n_clusters=n_clusters)
    value_label = pretty_name(parameter)
    fig = px.bar(
        clustered.sort_values("value"), x="station_name", y="value", color="cluster",
        title=f"Stations clustered by mean {value_label}",
        labels={"value": value_label, "station_name": "Station", "cluster": "Cluster"},
    )
    with chart_card():
        render_chart(fig)
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
