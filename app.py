"""Streamlit dashboard for exploring DWD (German weather service) station data.

Run with:
    streamlit run app.py
"""

import datetime as dt

import streamlit as st

from src.dashboard_context import DashboardContext
from src.data_loader import WeatherDataFetchError, load_data, load_stations
from src.ui_theme import apply_dynamic_theme, render_app_background, render_brand
from src.views import clustering, global_warming, map_view, regression, time_series
from src.views.common import render_section_label

st.set_page_config(page_title="Weather Dashboard", layout="wide")

render_app_background()
render_brand()

# A couple of well-known stations preselected so the app is usable
# immediately, without the user having to search the full list first. Only
# the IDs are hardcoded -- display names are always looked up from the
# loaded station list below, so they match DWD's actual official spelling
# instead of a hand-typed label going stale/wrong.
DEFAULT_STATION_IDS = ["00433", "01048"]

VIEWS = {
    "Time Series": time_series,
    "Map": map_view,
    "Regression": regression,
    "Clustering": clustering,
    "Discover Global Warming": global_warming,
}

# st.segmented_control() stands in for st.tabs() specifically so the
# station/date-range row below can sit between the nav and whichever view
# is showing. st.tabs() can't host that: its header and content are one
# atomic widget, and anything placed after st.tabs() but before its `with
# tab:` blocks renders below the active tab's full content, not between
# the header and it (confirmed empirically, not just from docs). One
# side effect: unlike st.tabs() -- which runs every tab's body every
# script pass, only hiding the inactive ones in the DOM -- only the
# selected view's own render() call actually executes here. That's a bit
# more efficient and doesn't change apply_dynamic_theme()'s behavior
# (see its docstring), since each view's own widget state still persists
# in st.session_state across runs regardless of whether it rendered.
active_view = st.segmented_control(
    "Navigation", options=list(VIEWS), default="Time Series", label_visibility="collapsed",
)
if not active_view:
    # Returns None if the selected option is clicked again to deselect it
    # -- fall back to the default view rather than showing nothing.
    active_view = "Time Series"

selection_cols = st.columns([3, 1])
with selection_cols[0]:
    stations_df = load_stations()
    name_by_id = dict(zip(stations_df["station_id"], stations_df["name"]))
    id_by_name = {v: k for k, v in name_by_id.items()}

    render_section_label("Weather stations")
    selected_names = st.multiselect(
        "Weather stations",
        options=list(name_by_id.values()),
        default=[name_by_id[s] for s in DEFAULT_STATION_IDS if s in name_by_id],
        label_visibility="collapsed",
    )
    selected_ids = [id_by_name[n] for n in selected_names]

with selection_cols[1]:
    render_section_label("Date range")
    start_date, end_date = st.date_input(
        "Date range",
        value=(dt.date(2023, 1, 1), dt.date(2023, 12, 31)),
        min_value=dt.date(1950, 1, 1),
        max_value=dt.date.today(),
        format="DD/MM/YYYY",
        label_visibility="collapsed",
    )

if not selected_ids:
    st.info("Select at least one station above to load data.")
    st.stop()

try:
    raw = load_data(selected_ids, str(start_date), str(end_date))
except WeatherDataFetchError as exc:
    st.error(f"Couldn't load weather data: {exc}")
    st.stop()

if raw.empty:
    st.warning("No data returned for this selection.")
    st.stop()

raw["station_name"] = raw["station_id"].map(name_by_id)

ctx = DashboardContext(
    raw=raw,
    selected_names=selected_names,
    id_by_name=id_by_name,
    id_to_name=name_by_id,
    start_date=start_date,
    end_date=end_date,
)

VIEWS[active_view].render(ctx)

# Re-themes the whole page (background, brand, nav row, ...) to whichever
# view's "Parameter" dropdown the user most recently changed -- see
# apply_dynamic_theme()'s docstring for why this has to run after the
# view renders rather than once at the top.
apply_dynamic_theme(st.session_state.get("active_theme_parameter"))
