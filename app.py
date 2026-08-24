"""Streamlit dashboard for exploring DWD (German weather service) station data.

Run with:
    streamlit run app.py
"""

import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analysis import cluster_stations, fit_trend
from src.data_loader import get_station_data, list_stations

st.set_page_config(page_title="DWD Weather Dashboard", layout="wide")
st.title("DWD Weather Dashboard")

# A handful of well-known stations as a sensible default so the app is
# usable immediately, without forcing a full station list download+scroll.
DEFAULT_STATIONS = {
    "00433": "Berlin-Tempelhof",
    "01048": "Dresden-Klotzsche",
    "04177": "Muenchen-Stadt",
    "02014": "Hamburg-Fuhlsbuettel",
    "01443": "Freiburg",
}


@st.cache_data(show_spinner="Loading station metadata from DWD...")
def load_stations():
    return list_stations()


@st.cache_data(show_spinner="Fetching observations from DWD...")
def load_data(station_ids: list[str], start: str, end: str) -> pd.DataFrame:
    return get_station_data(station_ids, start, end)


with st.sidebar:
    st.header("Selection")

    use_full_list = st.checkbox("Browse full DWD station list", value=False)
    if use_full_list:
        stations_df = load_stations()
        name_by_id = dict(zip(stations_df["station_id"], stations_df["name"]))
    else:
        name_by_id = DEFAULT_STATIONS

    selected_names = st.multiselect(
        "Weather stations",
        options=list(name_by_id.values()),
        default=list(DEFAULT_STATIONS.values())[:2],
    )
    id_by_name = {v: k for k, v in name_by_id.items()}
    selected_ids = [id_by_name[n] for n in selected_names]

    start_date, end_date = st.date_input(
        "Date range",
        value=(dt.date(2023, 1, 1), dt.date(2023, 12, 31)),
        min_value=dt.date(1950, 1, 1),
        max_value=dt.date.today(),
    )

if not selected_ids:
    st.info("Select at least one station in the sidebar to load data.")
    st.stop()

raw = load_data(selected_ids, str(start_date), str(end_date))

if raw.empty:
    st.warning("No data returned for this selection.")
    st.stop()

id_to_name = {v: k for k, v in id_by_name.items()}
raw["station_name"] = raw["station_id"].map(id_to_name)

parameter = st.selectbox("Parameter", sorted(raw["parameter"].unique()))
subset = raw[raw["parameter"] == parameter].dropna(subset=["value"])

tab_series, tab_map, tab_regression, tab_clustering = st.tabs(
    ["Time Series", "Map", "Regression", "Clustering"]
)

with tab_series:
    fig = px.line(
        subset, x="date", y="value", color="station_name",
        title=f"{parameter} over time",
    )
    st.plotly_chart(fig, width="stretch")

with tab_map:
    stations_meta = load_stations() if use_full_list else pd.DataFrame()
    if stations_meta.empty:
        st.caption("Enable 'Browse full DWD station list' in the sidebar to see station coordinates.")
    else:
        avg_value = subset.groupby("station_id", as_index=False)["value"].mean()
        merged = stations_meta.merge(avg_value, on="station_id")
        fig = px.scatter_map(
            merged, lat="latitude", lon="longitude", size="value", color="value",
            hover_name="name", zoom=4.5, map_style="open-street-map",
            title=f"Mean {parameter} by station",
        )
        st.plotly_chart(fig, width="stretch")

with tab_regression:
    station_for_trend = st.selectbox("Station", selected_names, key="trend_station")
    station_id = id_by_name[station_for_trend]
    trend_input = subset[subset["station_id"] == station_id]

    if len(trend_input) < 2:
        st.info("Not enough data points for a trend line.")
    else:
        result = fit_trend(trend_input)
        st.write(f"Slope: {result['slope_per_day'] * 365:.4f} units/year")
        fig = px.line(result["data"], x="date", y=["value", "trend"])
        st.plotly_chart(fig, width="stretch")

with tab_clustering:
    n_clusters = st.slider("Number of clusters", 2, 6, 3)
    per_station = subset.groupby("station_id", as_index=False)["value"].mean()
    per_station["station_name"] = per_station["station_id"].map(id_to_name)

    if len(per_station) < n_clusters:
        st.info("Select more stations than clusters to run KMeans.")
    else:
        clustered = cluster_stations(per_station, feature_cols=["value"], n_clusters=n_clusters)
        fig = px.bar(
            clustered.sort_values("value"), x="station_name", y="value", color="cluster",
            title=f"Stations clustered by mean {parameter}",
        )
        st.plotly_chart(fig, width="stretch")
        st.dataframe(clustered)
