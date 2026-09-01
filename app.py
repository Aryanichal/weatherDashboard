"""Streamlit dashboard for exploring DWD (German weather service) station data.

Run with:
    streamlit run app.py
"""

import datetime as dt

import streamlit as st

from src.dashboard_context import DashboardContext
from src.data_loader import WeatherDataFetchError, load_data, load_stations
from src.ui_theme import apply_dynamic_theme, render_app_background, render_brand
from src.views import clustering, global_warming, live_weather, map_view, regression, time_series
from src.views.common import render_section_label, render_segmented_nav_css

st.set_page_config(page_title="Weather Dashboard", layout="wide")

render_app_background()
render_brand()

# A couple of well-known stations preselected so the app is usable
# immediately, without the user having to search the full list first. Only
# the IDs are hardcoded -- display names are always looked up from the
# loaded station list below, so they match DWD's actual official spelling
# instead of a hand-typed label going stale/wrong.
DEFAULT_STATION_IDS = ["00433", "01048"]

HISTORICAL_VIEWS = {
    "Time Series": time_series,
    "Map": map_view,
    "Regression": regression,
    "Clustering": clustering,
    "Global Warming": global_warming,
}
_HISTORICAL_VIEW_KEY = "active_historical_view"
_SHARED_HISTORICAL_VIEW_KEY = "shared_active_historical_view"

# Two-tier navigation: the top-level choice is "what kind of weather info
# do I want" -- live, right-now conditions vs. digging into historical
# data -- not a flat row of six tabs. Only after picking "Analyse
# Historical Data" does its own five-way sub-nav (and the shared station/
# date-range row below it, which only means something for those five
# views) appear. Live Weather is a single, self-contained view with its
# own location picker and no "date range" concept at all (see
# src/views/live_weather.py's module docstring), so it never needs
# either -- hence it being its own top-level branch rather than a sixth
# option alongside the historical ones.
#
# st.segmented_control() stands in for st.tabs() at both levels
# specifically so the station/date-range row can sit between the sub-nav
# and whichever historical view is showing. st.tabs() can't host that:
# its header and content are one atomic widget, and anything placed after
# st.tabs() but before its `with tab:` blocks renders below the active
# tab's full content, not between the header and it (confirmed
# empirically, not just from docs). One side effect: unlike st.tabs() --
# which runs every tab's body every script pass, only hiding the inactive
# ones in the DOM -- only the selected option's own render() call
# actually executes here. That's a bit more efficient and doesn't change
# apply_dynamic_theme()'s behavior (see its docstring), since each view's
# own widget state still persists in st.session_state across runs
# regardless of whether it rendered.
# Bare text, no capsule/pill skin at all -- large and bold enough to read as
# a section header (matching render_brand()'s own weight/letter-spacing in
# src/ui_theme.py) rather than a button. See render_segmented_nav_css() in
# src/views/common.py for the shared implementation -- the "Weather
# Analysis" sub-nav just below reuses the exact same look, at a smaller
# font size (5 columns instead of 2 need to share the row).
_TOP_LEVEL_NAV_KEY = "top_level_nav"
# Tightened from 1.5rem: the sub-nav sits directly below this as the
# second tier of one navigation hierarchy (not a new content section), so
# the two rows read as a connected pair rather than two independently-
# spaced blocks -- the looser gap now lives between the sub-nav and the
# station/date-range controls below it instead (see the
# render_segmented_nav_css() call for _HISTORICAL_VIEW_KEY below).
render_segmented_nav_css(_TOP_LEVEL_NAV_KEY, option_count=2, font_size="2.5rem", margin_bottom="1rem")
top_level = st.segmented_control(
    "Section",
    options=["Live Weather", "Weather Analysis"],
    default="Live Weather",
    label_visibility="collapsed",
    key=_TOP_LEVEL_NAV_KEY,
    width="stretch",
)
if not top_level:
    # Returns None if the selected option is clicked again to deselect it
    # -- fall back to the default rather than showing nothing.
    top_level = "Live Weather"

if top_level == "Live Weather":
    live_weather.render()
else:
    # Same durable-shared-key re-seed trick as _SHARED_PARAMETER_KEY in
    # src/views/common.py: this sub-nav's own widget state gets dropped by
    # Streamlit the moment "Live Weather" is picked at the top level (it
    # stops rendering entirely for that rerun), so without this, coming
    # back to "Weather Analysis" would always reset to "Time
    # Series" instead of wherever the user actually was.
    shared_view = st.session_state.get(_SHARED_HISTORICAL_VIEW_KEY)
    if shared_view in HISTORICAL_VIEWS and _HISTORICAL_VIEW_KEY not in st.session_state:
        st.session_state[_HISTORICAL_VIEW_KEY] = shared_view

    # Same bare-text, sliding-underline skin as the top-level Live Weather/
    # Weather Analysis switch above (see render_segmented_nav_css() in
    # src/views/common.py) instead of this row's previous default pill-
    # button look -- smaller font than the top-level nav's 2.5rem since 5
    # columns, not 2, have to share the row without wrapping ("Discover
    # Global Warming" is the long pole). A small margin-top keeps this
    # visually paired with the top-level nav right above it as one
    # two-tier hierarchy; the much larger margin-bottom is what actually
    # separates it from the station/date-range controls below, which are
    # a distinct content section, not another nav tier.
    render_segmented_nav_css(
        _HISTORICAL_VIEW_KEY, option_count=len(HISTORICAL_VIEWS), font_size="1.05rem",
        margin_top="0.5rem", margin_bottom="2rem",
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

    HISTORICAL_VIEWS[active_view].render(ctx)

# Re-themes the whole page (background, brand, nav row, ...) to whichever
# view's "Parameter" dropdown the user most recently changed -- see
# apply_dynamic_theme()'s docstring for why this has to run after the
# view renders rather than once at the top.
apply_dynamic_theme(st.session_state.get("active_theme_parameter"))
