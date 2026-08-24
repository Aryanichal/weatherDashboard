"""Streamlit dashboard for exploring DWD (German weather service) station data.

Run with:
    streamlit run app.py
"""

import datetime as dt

import streamlit as st

from src.dashboard_context import DashboardContext
from src.data_loader import load_data, load_stations
from src.views import clustering, global_warming, map_view, regression, time_series

st.set_page_config(page_title="Weather Dashboard", layout="wide")
st.title("Weather Dashboard")

# A handful of well-known stations as a sensible default so the app is
# usable immediately, without forcing a full station list download+scroll.
DEFAULT_STATIONS = {
    "00433": "Berlin-Tempelhof",
    "01048": "Dresden-Klotzsche",
    "03379": "Muenchen-Stadt",
    "02014": "Hamburg-Fuhlsbuettel",
    "01443": "Freiburg",
}

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
        format="DD/MM/YYYY",
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

ctx = DashboardContext(
    raw=raw,
    selected_ids=selected_ids,
    selected_names=selected_names,
    id_by_name=id_by_name,
    id_to_name=id_to_name,
    use_full_list=use_full_list,
)

tab_series, tab_map, tab_regression, tab_clustering, tab_global_warming = st.tabs(
    ["Time Series", "Map", "Regression", "Clustering", "Global Warming Trend"]
)

with tab_series:
    time_series.render(ctx)

with tab_map:
    map_view.render(ctx)

with tab_regression:
    regression.render(ctx)

with tab_clustering:
    clustering.render(ctx)

with tab_global_warming:
    global_warming.render(ctx)
