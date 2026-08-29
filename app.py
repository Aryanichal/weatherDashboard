"""Streamlit dashboard for exploring DWD (German weather service) station data.

Run with:
    streamlit run app.py
"""

import datetime as dt

import streamlit as st

from src.dashboard_context import DashboardContext
from src.data_loader import load_data, load_stations
from src.ui_theme import apply_dynamic_theme, render_app_background, render_brand
from src.views import clustering, global_warming, map_view, regression, time_series

st.set_page_config(page_title="Weather Dashboard", layout="wide")

render_app_background()
render_brand()

# A couple of well-known stations preselected so the app is usable
# immediately, without the user having to search the full list first. Only
# the IDs are hardcoded -- display names are always looked up from the
# loaded station list below, so they match DWD's actual official spelling
# instead of a hand-typed label going stale/wrong.
DEFAULT_STATION_IDS = ["00433", "01048"]

with st.sidebar:
    st.header("Selection")

    stations_df = load_stations()
    name_by_id = dict(zip(stations_df["station_id"], stations_df["name"]))
    id_by_name = {v: k for k, v in name_by_id.items()}

    selected_names = st.multiselect(
        "Weather stations",
        options=list(name_by_id.values()),
        default=[name_by_id[s] for s in DEFAULT_STATION_IDS if s in name_by_id],
    )
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

raw["station_name"] = raw["station_id"].map(name_by_id)

ctx = DashboardContext(
    raw=raw,
    selected_names=selected_names,
    id_by_name=id_by_name,
    id_to_name=name_by_id,
)

tab_series, tab_map, tab_regression, tab_clustering, tab_global_warming = st.tabs(
    ["Time Series", "Map", "Regression", "Clustering", "Discover Global Warming"]
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

# Re-themes the whole page (background, sidebar, brand, tabs, ...) to
# whichever tab's "Parameter" dropdown the user most recently changed --
# see apply_dynamic_theme()'s docstring for why this has to run after
# every tab above rather than once at the top.
apply_dynamic_theme(st.session_state.get("active_theme_parameter"))


