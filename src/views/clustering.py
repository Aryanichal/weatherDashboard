"""Clustering tab: group stations by chosen weather parameter(s).

Two ways to view the same underlying KMeans grouping, picked via the
"View as" toggle rendered by render_view_selector() below -- app.py calls
that directly above the shared Region/Date-range row (rather than this
module's own render() rendering it inline, like every other per-view
control does) specifically so it reads as one more level of the page's
own navigation, sitting right under the Time Series/Map/Regression/
Clustering/Global Warming row rather than below content that hasn't
rendered yet:

- "Scatter Plot": exactly two chosen parameters plotted directly as X/Y
  axes, so every axis is real and directly readable (no synthetic
  composite axes to interpret).
- "Map View": station position comes from real latitude/longitude instead
  of an abstract feature-space scatter, so clustering is free to use as
  many parameters as picked (default: all of them) without ever needing a
  PCA-style projection -- parameters only ever show up as a color, never
  as a plotting axis. Geography is often exactly what explains why
  stations land in the same cluster (coastal vs. inland, north vs. south,
  altitude, ...), so seeing it directly on a map can be more legible than
  the scatter's own chart. (This used to be a "Cluster" color mode on the
  Map tab itself; moved here so both ways of viewing a cluster live in one
  tab instead of being split across two.)

Both run over a real population of stations (every station reporting in a
region, not the handful a user happens to have picked in the station
multiselect elsewhere in the app) -- see stations_in_region() in
src/data_loader.py for why clustering specifically needs that.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analysis import (
    DEFAULT_CLUSTER_FEATURES,
    MAX_CLUSTER_K,
    PARAMETER_UNITS,
    build_station_features,
    cluster_stations,
    compute_k_diagnostics,
)
from src.dashboard_context import DashboardContext
from src.data_loader import WeatherDataFetchError, load_region_data, load_stations, stations_in_region
from src.ui_theme import chart_card, render_chart
from src.views.common import (
    parameter_label_with_unit,
    pretty_name,
    render_cluster_profile,
    render_full_bleed_map,
    render_k_diagnostics_chart,
    render_k_diagnostics_explanation,
    render_section_label,
    render_segmented_nav_css,
)

_VIEW_MODE_KEY = "clustering_view_mode"
_SCATTER_CHART_CARD_KEY = "chart-card-parameter_clustering"
_MAP_CHART_CARD_KEY = "chart-card-parameter_clustering_map"
_MAP_DIAGNOSTICS_CARD_KEY = "chart-card-parameter_clustering_map_diagnostics"
# Seeds each slider with the recommended k (see compute_k_diagnostics()
# in src/analysis.py) -- st.slider() then owns the key itself from then
# on, so a manual drag sticks *until the recommendation itself changes*
# (a different parameter/region selection recomputes a new best_k), at
# which point the slider re-seeds to follow it rather than being left
# pointing at a now-stale recommendation (see _seed_k_slider() below).
# Scatter and Map View get their own pairs of keys since they cluster on
# different parameter sets (fixed 2 vs. however many are picked) and so
# can land on different recommended k values.
_K_SLIDER_KEY = "cluster_k_slider"
_K_SLIDER_SEED_KEY = "cluster_k_slider_seed"
_MAP_K_SLIDER_KEY = "cluster_map_k_slider"
_MAP_K_SLIDER_SEED_KEY = "cluster_map_k_slider_seed"
_X_FEATURE_KEY = "cluster_x_feature"
_Y_FEATURE_KEY = "cluster_y_feature"
_MAP_FEATURES_KEY = "cluster_map_features"
# Plotly Express's own default discrete-color sequence -- hardcoded (rather
# than imported from plotly.express.colors.qualitative) so the custom
# legend built in _render_cluster_legend() below stays visually identical
# to whatever px.scatter_map() colors the dots with, without needing to
# force a non-default color_discrete_sequence just to know the values.
_CLUSTER_COLORS = [
    "#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A",
    "#19D3F3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52",
]


def _seed_k_slider(slider_key: str, seed_key: str, best_k: int | None) -> None:
    """Point ``slider_key`` at ``best_k`` whenever the recommendation
    itself has changed since the last time this ran (tracked in
    ``seed_key``) -- not just the first time the slider ever renders.
    ``best_k`` only ever changes because the chosen parameters/region
    changed (it doesn't depend on the slider's own value), so re-seeding
    on every *change* rather than only once still leaves a manual drag
    alone for as long as the recommendation it was based on stays valid,
    while keeping the slider from silently pointing at a stale k after
    the recommendation moves out from under it."""
    if best_k is not None and st.session_state.get(seed_key) != best_k:
        st.session_state[slider_key] = best_k
        st.session_state[seed_key] = best_k


def render_view_selector_css() -> None:
    """Just the CSS half of render_view_selector() below, split out so
    app.py can call it unconditionally on *every* rerun -- including runs
    where Live Weather, not Clustering, is showing and the widget itself
    never renders at all. A scoped CSS rule with no matching element in
    the DOM is a harmless no-op, but calling it only while Clustering is
    active (i.e. tied to the same condition as the widget) left a window,
    on the exact rerun that switches away from Clustering, where the old
    widget's DOM node could still be present for one paint while this
    rule had already been removed -- visible as a one-frame flash of
    Streamlit's own default pill-button skin on the "Map View"/"Scatter
    Plot" control right before the page swaps to Live Weather. Keeping
    the rule permanently in the DOM regardless of which view is active
    removes that window instead of trying to win the race."""
    render_segmented_nav_css(_VIEW_MODE_KEY, option_count=2, font_size="1.05rem", margin_top="0.5rem", margin_bottom="1.5rem")


def render_view_selector() -> None:
    """The "Map View"/"Scatter Plot" widget itself, called by app.py
    directly above the shared Region/Date-range row (before render()
    below ever runs) so it sits as one more level of the page's own top
    navigation rather than as a control below it. Its styling (see
    render_view_selector_css() above) is injected separately and
    unconditionally, not here. Stores its choice under _VIEW_MODE_KEY in
    st.session_state; render() below reads it from there instead of
    re-rendering the widget itself."""
    st.segmented_control(
        "View as",
        options=["Map View", "Scatter Plot"],
        default="Map View",
        key=_VIEW_MODE_KEY,
        label_visibility="collapsed",
        width="stretch",
    )


def current_view_mode() -> str:
    """Whichever of "Map View"/"Scatter Plot" render_view_selector() above
    last set, defaulting to "Map View" the same way render() below
    does -- a small accessor so render() doesn't need to reach into this
    module's session-state key directly."""
    return st.session_state.get(_VIEW_MODE_KEY) or "Map View"


def render(ctx: DashboardContext) -> None:
    # The "Region" selectbox itself lives in app.py, in the slot the other
    # four views use for the station multiselect -- Clustering runs over
    # every station in a region rather than a hand-picked list, so that
    # multiselect doesn't apply to it (see DashboardContext.region's
    # docstring in src/dashboard_context.py).
    region = ctx.region

    view_mode = current_view_mode()

    candidate_stations = stations_in_region(region, ctx.start_date, ctx.end_date)
    if candidate_stations.empty:
        st.info("No stations report in this region for the selected date range.")
        return

    if view_mode == "Map View":
        _render_map_view(ctx, region, candidate_stations)
    else:
        _render_scatter_view(ctx, region, candidate_stations)


def _render_scatter_view(ctx: DashboardContext, region: str, candidate_stations: pd.DataFrame) -> None:
    st.caption("Clusters across every station reporting in this region.")

    available_features = sorted(PARAMETER_UNITS)
    default_x = DEFAULT_CLUSTER_FEATURES[0] if DEFAULT_CLUSTER_FEATURES[0] in available_features else available_features[0]
    default_y = next(
        (p for p in DEFAULT_CLUSTER_FEATURES[1:] if p in available_features and p != default_x),
        next(p for p in available_features if p != default_x),
    )
    # The actual selectbox widgets render *below* the chart (see
    # _render_axis_selectors(), called at the bottom of this function) --
    # reading the current choice straight from session_state here, before
    # those widgets are even instantiated this run, is what makes that
    # possible: a keyed widget's session_state entry already reflects a
    # just-made choice by the time the script reruns from the top, so the
    # chart above can use it immediately despite being built first.
    x_feature = st.session_state.get(_X_FEATURE_KEY, default_x)
    y_feature = st.session_state.get(_Y_FEATURE_KEY, default_y)

    if x_feature == y_feature:
        st.info("Pick two different parameters for X and Y below.")
        _render_axis_selectors(available_features, x_feature, y_feature)
        return
    chosen_features = [x_feature, y_feature]

    try:
        raw = load_region_data(region, candidate_stations["station_id"].tolist(), str(ctx.start_date), str(ctx.end_date))
    except WeatherDataFetchError as exc:
        st.error(f"Couldn't load weather data: {exc}")
        _render_axis_selectors(available_features, x_feature, y_feature)
        return

    feature_matrix = build_station_features(raw, chosen_features)
    complete = feature_matrix.dropna()

    diagnostics, best_k = compute_k_diagnostics(feature_matrix, complete)
    _seed_k_slider(_K_SLIDER_KEY, _K_SLIDER_SEED_KEY, best_k)
    slider_label = f"Number of clusters (k). Recommended: k={best_k}" if best_k is not None else "Number of clusters (k)"
    n_clusters = st.slider(slider_label, 2, MAX_CLUSTER_K, key=_K_SLIDER_KEY)
    if len(complete) < n_clusters:
        station_word = "station" if len(complete) == 1 else "stations"
        st.info(
            f"Only {len(complete)} {station_word} in {region} report both chosen parameters -- "
            f"pick different parameters below, a different region, or a lower cluster count to run "
            f"KMeans with {n_clusters} clusters."
        )
        _render_axis_selectors(available_features, x_feature, y_feature)
        return

    clustered = cluster_stations(feature_matrix, n_clusters=n_clusters)
    clustered["station_name"] = clustered.index.map(ctx.id_to_name)
    value_labels = {f: parameter_label_with_unit(f) for f in chosen_features}

    st.caption(
        f"Clustering {len(complete)} of {len(candidate_stations)} stations in {region} "
        f"({len(candidate_stations) - len(complete)} excluded for missing one of the chosen parameters)."
    )

    if diagnostics is not None:
        render_k_diagnostics_chart(diagnostics, best_k)

    fig = _scatter_chart(clustered, chosen_features, value_labels)
    render_cluster_profile(clustered, chosen_features, value_labels)
    with chart_card(key=_SCATTER_CHART_CARD_KEY):
        render_chart(fig)

    _render_axis_selectors(available_features, x_feature, y_feature)

    with chart_card():
        table = clustered.reset_index().rename(
            columns={"station_id": "Station ID", "station_name": "Station", "cluster": "Cluster", **value_labels}
        )
        st.dataframe(
            table[["Station ID", "Station", *value_labels.values(), "Cluster"]],
            width="stretch",
        )


def _render_axis_selectors(available_features: list[str], x_feature: str, y_feature: str) -> None:
    """The X/Y parameter pickers, deliberately rendered after the chart
    they control (see _render_scatter_view()'s docstring comment on
    reading them from session_state early) rather than above it."""
    axis_cols = st.columns(2)
    with axis_cols[0]:
        render_section_label("X-axis parameter")
        st.selectbox(
            "X-axis parameter", available_features, index=available_features.index(x_feature),
            format_func=pretty_name, label_visibility="collapsed", key=_X_FEATURE_KEY,
        )
    with axis_cols[1]:
        render_section_label("Y-axis parameter")
        st.selectbox(
            "Y-axis parameter", available_features, index=available_features.index(y_feature),
            format_func=pretty_name, label_visibility="collapsed", key=_Y_FEATURE_KEY,
        )


def _scatter_chart(clustered, chosen_features: list[str], value_labels: dict[str, str]):
    x_feature, y_feature = chosen_features
    fig = px.scatter(
        clustered, x=x_feature, y=y_feature, color="cluster", hover_name="station_name",
        title=f"Stations clustered by {pretty_name(x_feature)} and {pretty_name(y_feature)}",
        labels={x_feature: value_labels[x_feature], y_feature: value_labels[y_feature], "cluster": "Cluster"},
    )
    return fig


def _render_cluster_legend(cluster_labels: list[str]) -> None:
    """A plain-page legend for the map's discrete cluster colors, standing
    in for Plotly's own in-chart legend (disabled inside
    render_full_bleed_map()) -- keeps the chart_card() holding nothing but
    the map itself, per the same "title/legend live outside the card"
    treatment as the rest of this view."""
    swatches = "".join(
        f'<span style="display:inline-flex; align-items:center; gap:0.4rem; margin:0 1.2rem 0.5rem 0;">'
        f'<span style="width:10px; height:10px; border-radius:50%; '
        f'background:{_CLUSTER_COLORS[i % len(_CLUSTER_COLORS)]}; display:inline-block;"></span>'
        f'<span style="font-size:0.85rem; opacity:0.85;">Cluster {label}</span>'
        f"</span>"
        for i, label in enumerate(cluster_labels)
    )
    st.markdown(f'<div style="display:flex; flex-wrap:wrap;">{swatches}</div>', unsafe_allow_html=True)


def _render_region_caption(ctx: DashboardContext, text: str) -> None:
    """Writes ``text`` into the Region column itself (see
    DashboardContext.region_column's own docstring) instead of the full
    page width below the shared row -- keeps it anchored directly under
    the Region dropdown even while the "Cluster stations by" multiselect
    next to it grows to 2-3 rows of chips, rather than being pushed down
    to match whichever column in that row ends up tallest. A Streamlit
    column reference stays writable after its own `with` block has
    already closed, which is what makes appending to it from here, well
    after app.py rendered it, possible at all. Falls back to a plain,
    full-width caption if no column was captured (ctx.region_column is
    None outside Clustering)."""
    if ctx.region_column is not None:
        with ctx.region_column:
            st.caption(text)
    else:
        st.caption(text)


def _render_map_view(ctx: DashboardContext, region: str, candidate_stations: pd.DataFrame) -> None:
    stations_meta = load_stations()
    if stations_meta.empty:
        st.caption("Station coordinate metadata is unavailable right now.")
        return

    _render_region_caption(ctx, "Clusters across every reporting station in this region, plotted by location.")

    # Full-width, directly above the slider -- both stay in this simple
    # top-to-bottom order in the code too, since nothing about the
    # multiselect depends on data fetched later, while the slider's own
    # label needs best_k, which does.
    render_section_label("Cluster stations by")
    chosen_features = st.multiselect(
        "Cluster stations by",
        options=sorted(PARAMETER_UNITS),
        default=sorted(PARAMETER_UNITS),
        format_func=pretty_name,
        label_visibility="collapsed",
        key=_MAP_FEATURES_KEY,
    )

    if not chosen_features:
        st.info("Pick at least one parameter above to cluster stations by.")
        return

    try:
        raw = load_region_data(region, candidate_stations["station_id"].tolist(), str(ctx.start_date), str(ctx.end_date))
    except WeatherDataFetchError as exc:
        st.error(f"Couldn't load weather data: {exc}")
        return

    feature_matrix = build_station_features(raw, chosen_features)
    complete = feature_matrix.dropna()

    diagnostics, best_k = compute_k_diagnostics(feature_matrix, complete)
    _seed_k_slider(_MAP_K_SLIDER_KEY, _MAP_K_SLIDER_SEED_KEY, best_k)
    slider_label = f"Number of clusters (k). Recommended: k={best_k}" if best_k is not None else "Number of clusters (k)"
    n_clusters = st.slider(slider_label, 2, MAX_CLUSTER_K, key=_MAP_K_SLIDER_KEY)

    if len(complete) < n_clusters:
        station_word = "station" if len(complete) == 1 else "stations"
        st.info(
            f"Only {len(complete)} {station_word} in {region} report every chosen parameter -- "
            f"pick fewer parameters, a different region, or a lower cluster count to run KMeans "
            f"with {n_clusters} clusters."
        )
        return

    clustered = cluster_stations(feature_matrix, n_clusters=n_clusters)
    merged = stations_meta.merge(clustered.reset_index(), on="station_id")
    if merged.empty:
        st.caption("No stations in this region have complete data for the chosen parameters.")
        return

    _render_region_caption(
        ctx,
        f"Clustering {len(complete)} of {len(candidate_stations)} stations in {region} "
        f"({len(candidate_stations) - len(complete)} excluded for missing at least one chosen parameter).",
    )

    value_labels = {f: parameter_label_with_unit(f) for f in chosen_features}

    # A fixed, generic title rather than spelling out every chosen
    # parameter (that list can run to a dozen names and dwarf the map
    # below it) -- which parameters are in play is already legible from
    # the multiselect above and each station's own hover tooltip, so this
    # only needs to say what the map itself shows.
    cluster_order = sorted(merged["cluster"].unique(), key=int)
    render_section_label("Station clusters", style="header")
    _render_cluster_legend(cluster_order)
    # An explicit center (roughly Germany's own geographic middle) rather
    # than px.scatter_map()'s own default of centering on the mean of
    # whichever stations happen to be plotted -- that drifts off-center
    # whenever a chosen parameter excludes a lopsided chunk of the country
    # (see the humidity example discussed above, which left mostly
    # northern/eastern stations plotted). Zoom nudged up from 4.9 now that
    # the map's own height has grown tall enough to otherwise pull in a
    # visibly wider vertical slice of neighboring countries at the old
    # zoom level.
    fig = px.scatter_map(
        merged, lat="latitude", lon="longitude", color="cluster", hover_name="name",
        hover_data=chosen_features, zoom=5.3, center={"lat": 51.2, "lon": 10.3}, map_style="open-street-map",
        category_orders={"cluster": cluster_order},
        color_discrete_sequence=_CLUSTER_COLORS,
    )
    # Germany is a north-south-elongated country, so a full-page-width map
    # spends most of its horizontal space on neighboring countries rather
    # than Germany itself. Narrowing the column the map sits in -- rather
    # than shrinking the figure inside a still-full-width card -- keeps
    # chart_card() sized exactly to the map with no border/background
    # revealed around empty space, since a Streamlit container always
    # sizes itself to its column, not the page.
    #
    # Tall enough to reach the bottom of its neighboring column -- the
    # diagnostics chart plus its own title/captions and the explanation
    # box below it (see map_columns[1] below) run noticeably taller than
    # a bare map would on its own, and Streamlit's own column flexbox
    # already stretches this column to match that height regardless, so
    # a short map otherwise just leaves blank space under itself instead
    # of using it. Not something this can size itself to exactly (a fixed
    # pixel height, same tradeoff render_key_figures_box() in
    # src/views/common.py makes for the same reason), but 820 tracks the
    # neighboring column's typical height closely.
    fig.update_layout(height=820)
    map_columns = st.columns([2, 2])
    with map_columns[0]:
        render_full_bleed_map(fig, _MAP_CHART_CARD_KEY)
    # Experimental placement: the elbow/silhouette diagnostics chart sits
    # directly beside the map instead of tucked behind the "How was the
    # recommended k chosen?" expander (see collapsed=False in
    # render_k_diagnostics_chart()'s docstring in src/views/common.py) --
    # only in this Map View mode, to see how it reads before deciding
    # whether to keep it. Scatter Plot's own call further down keeps the
    # collapsed default.
    if diagnostics is not None:
        with map_columns[1]:
            render_k_diagnostics_chart(diagnostics, best_k, collapsed=False, card_key=_MAP_DIAGNOSTICS_CARD_KEY)
            render_k_diagnostics_explanation()

    render_cluster_profile(clustered, chosen_features, value_labels)
