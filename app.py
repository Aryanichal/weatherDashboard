"""Streamlit dashboard for exploring DWD (German weather service) station data.

Run with:
    streamlit run app.py
"""

import datetime as dt

import pandas as pd
import streamlit as st

from src.dashboard_context import DashboardContext
from src.data_loader import (
    REGION_OPTIONS,
    WeatherDataFetchError,
    load_data,
    load_stations,
    start_background_region_prefetch,
)
from src.ui_theme import apply_dynamic_theme, render_app_background, render_brand
from src.views import clustering, global_warming, live_weather, map_view, regression, time_series
from src.views.common import render_section_label, render_segmented_nav_css

st.set_page_config(page_title="Weather Dashboard", layout="wide")

render_app_background()
render_brand()

# Warms Clustering/Map's default region/date range in the background so
# opening those tabs doesn't always pay the full DWD fetch cost live.
start_background_region_prefetch()

# Geographically spread-out stations preselected so the app is usable
# immediately. Only IDs are hardcoded; display names are looked up below.
DEFAULT_STATION_IDS = [
    "00433",  # Berlin-Tempelhof
    "03379",  # München-Stadt
    "01420",  # Frankfurt/Main
    "01975",  # Hamburg-Fuhlsbüttel
    "04928",  # Stuttgart (Schnarrenberg)
]
# Compact city list shown before "Browse all DWD stations" is checked.
# Unioned with DEFAULT_STATION_IDS so the preselected defaults stay pickable.
RECOMMENDED_CITY_STATION_IDS = ["00433", "01048", "03379", "01420", "02014", "01443"]

HISTORICAL_VIEWS = {
    "Time Series": time_series,
    "Map": map_view,
    "Regression": regression,
    "Clustering": clustering,
    "Global Warming": global_warming,
}
_HISTORICAL_VIEW_KEY = "active_historical_view"
_SHARED_HISTORICAL_VIEW_KEY = "shared_active_historical_view"
_TOP_LEVEL_NAV_KEY = "top_level_nav"
render_segmented_nav_css(_TOP_LEVEL_NAV_KEY, option_count=2, font_size="2.5rem", margin_bottom="1rem")

# Must run every rerun (not just while Clustering shows) to avoid a
# one-frame flash of the default pill-button skin when switching tabs.
clustering.render_view_selector_css()

top_level = st.segmented_control(
    "Section",
    options=["Live Weather", "Weather Analysis"],
    default="Live Weather",
    label_visibility="collapsed",
    key=_TOP_LEVEL_NAV_KEY,
    width="stretch",
)
if not top_level:
    # None if the option was clicked again to deselect it.
    top_level = "Live Weather"

if top_level == "Live Weather":
    live_weather.render()
else:
    # Re-seed the sub-nav's widget state: Streamlit drops it whenever "Live
    # Weather" is picked instead, so without this it'd reset every time.
    shared_view = st.session_state.get(_SHARED_HISTORICAL_VIEW_KEY)
    if shared_view in HISTORICAL_VIEWS and _HISTORICAL_VIEW_KEY not in st.session_state:
        st.session_state[_HISTORICAL_VIEW_KEY] = shared_view

    # Clustering renders its own nav tier right below this one, so it needs
    # tighter spacing than the other views.
    is_clustering = st.session_state.get(_HISTORICAL_VIEW_KEY) == "Clustering"
    render_segmented_nav_css(
        _HISTORICAL_VIEW_KEY, option_count=len(HISTORICAL_VIEWS), font_size="1.05rem",
        margin_top="0.5rem", margin_bottom=("1rem" if is_clustering else "2rem"),
    )
    active_view = st.segmented_control(
        "Navigation",
        options=list(HISTORICAL_VIEWS),
        default="Time Series",
        key=_HISTORICAL_VIEW_KEY,
        label_visibility="collapsed",
        width="stretch",
    )
    if not active_view:
        active_view = "Time Series"
    st.session_state[_SHARED_HISTORICAL_VIEW_KEY] = active_view

    # Covers every DWD station, not just what's selected below -- Clustering
    # looks up names for stations outside the multiselect entirely.
    stations_df = load_stations()
    name_by_id = dict(zip(stations_df["station_id"], stations_df["name"]))
    id_by_name = {v: k for k, v in name_by_id.items()}

    # Rendered here (above Region/Date-range) so it reads as another level
    # of top nav, not a control below content that hasn't rendered yet.
    if active_view == "Clustering":
        clustering.render_view_selector()

    selection_cols = st.columns([3, 1])

    # Renders first: "Weather stations" below needs start_date/end_date
    # already chosen to filter to date-compatible stations.
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

    with selection_cols[0]:
        if active_view == "Clustering":
            render_section_label("Region")
            region = st.selectbox("Region", REGION_OPTIONS, label_visibility="collapsed")
            selected_names: list[str] = []
            selected_ids: list[str] = []
        else:
            region = None
            stations_df = load_stations().copy()
            stations_df["start_date"] = pd.to_datetime(stations_df["start_date"], utc=True, errors="coerce")
            stations_df["end_date"] = pd.to_datetime(stations_df["end_date"], utc=True, errors="coerce")
            selected_start = pd.Timestamp(start_date, tz="UTC")
            selected_end = pd.Timestamp(end_date, tz="UTC")
            # Restrict to stations whose reporting window overlaps the chosen dates.
            date_compatible_stations = stations_df.loc[
                (stations_df["start_date"] <= selected_end)
                & (stations_df["end_date"].isna() | (stations_df["end_date"] >= selected_start))
            ]
      
            show_all_stations = st.session_state.get("browse_all_historical_stations", False)
            available_stations = (
                date_compatible_stations
                if show_all_stations
                else date_compatible_stations.loc[
                    date_compatible_stations["station_id"].isin(
                        set(RECOMMENDED_CITY_STATION_IDS) | set(DEFAULT_STATION_IDS)
                    )
                ]
            )
            name_by_id = dict(zip(available_stations["station_id"], available_stations["name"]))
            id_by_name = {v: k for k, v in name_by_id.items()}
            available_names = list(name_by_id.values())

            # A date-range change can make an existing selection invalid. Remove
            # it before rendering the widget rather than leaving a stale option.
            station_selector_key = "historical_station_selector"
            if station_selector_key in st.session_state:
                st.session_state[station_selector_key] = [
                    name for name in st.session_state[station_selector_key] if name in available_names
                ]

            render_section_label("Weather stations")
            selected_names = st.multiselect(
                "Weather stations",
                options=available_names,
                default=[name_by_id[s] for s in DEFAULT_STATION_IDS if s in name_by_id],
                key=station_selector_key,
                label_visibility="collapsed",
                help="Only stations with climate-summary data overlapping the selected date range are listed.",
            )
            show_all_stations = st.checkbox(
                "Browse all DWD stations for this date range",
                value=False,
                key="browse_all_historical_stations",
                help=(
                    "By default, a compact list of verified city stations is shown. Since not every DWD "
                    "station reports on all the parameters for a given time range, some stations here may "
                    "still be missing the specific parameter you pick above."
                ),
            )
            if show_all_stations:
                st.caption(f"{len(available_names):,} stations are available for this date range.")
            else:
                st.caption("Showing six recommended city stations. Enable browsing to search all compatible stations.")
            selected_ids = [id_by_name[n] for n in selected_names]

    if active_view == "Clustering":
        # Clustering fetches its own region-scoped data independently (see
        # src/views/clustering.py) 
        raw = pd.DataFrame()
    else:
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

        returned_ids = set(raw["station_id"].astype(str))
        unavailable_names = [name for name in selected_names if str(id_by_name[name]) not in returned_ids]
        if unavailable_names:
            st.warning(
                "No observations were returned for: " + ", ".join(unavailable_names) + ". They were excluded."
            )
            selected_names = [name for name in selected_names if name not in unavailable_names]

        raw["station_name"] = raw["station_id"].map(name_by_id)

    ctx = DashboardContext(
        raw=raw,
        selected_names=selected_names,
        id_by_name=id_by_name,
        id_to_name=name_by_id,
        start_date=start_date,
        end_date=end_date,
        region=region,
        region_column=selection_cols[0] if active_view == "Clustering" else None,
    )

    HISTORICAL_VIEWS[active_view].render(ctx)

# Re-themes the page to whichever "Parameter" dropdown was last changed;
# must run after the view renders (see apply_dynamic_theme()).
apply_dynamic_theme(st.session_state.get("active_theme_parameter"))
