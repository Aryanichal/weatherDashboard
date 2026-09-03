"""Clustering tab: group stations by chosen weather parameter(s).

Two ways to view the same underlying KMeans grouping, picked via the
"View as" toggle (render_view_selector() below):
- "Scatter Plot": exactly two chosen parameters plotted as X/Y axes.
- "Map View": station position is real lat/long, so clustering can use
  any number of parameters (default: all).

Both cluster over every station reporting in the region, not just the
ones picked in the station multiselect elsewhere in the app.
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
# Scatter and Map View get separate slider keys since they cluster on
# different parameter sets and can recommend different k values.
_K_SLIDER_KEY = "cluster_k_slider"
_K_SLIDER_SEED_KEY = "cluster_k_slider_seed"
_MAP_K_SLIDER_KEY = "cluster_map_k_slider"
_MAP_K_SLIDER_SEED_KEY = "cluster_map_k_slider_seed"
_X_FEATURE_KEY = "cluster_x_feature"
_Y_FEATURE_KEY = "cluster_y_feature"
_MAP_FEATURES_KEY = "cluster_map_features"

_CLUSTER_COLORS = [
    "#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A",
    "#19D3F3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52",
]


def _seed_k_slider(slider_key: str, seed_key: str, best_k: int | None) -> None:
    """Re-seed ``slider_key`` to ``best_k`` only when the recommendation
    changes (tracked via ``seed_key``), so a manual drag sticks until then."""
    if best_k is not None and st.session_state.get(seed_key) != best_k:
        st.session_state[slider_key] = best_k
        st.session_state[seed_key] = best_k


def render_view_selector_css() -> None:
    """CSS half of render_view_selector(), split out so app.py can call it
    unconditionally on every rerun -- calling it only while Clustering is
    active caused a one-frame flash of unstyled pill buttons when leaving
    the tab."""
    render_segmented_nav_css(_VIEW_MODE_KEY, option_count=2, font_size="1.05rem", margin_top="0.5rem", margin_bottom="1.5rem")


def render_view_selector() -> None:
    """The "Map View"/"Scatter Plot" widget, called by app.py above the
    shared Region/Date-range row so it reads as top-level page navigation.
    Stores its choice under _VIEW_MODE_KEY; render() below reads it from
    session_state rather than re-rendering the widget."""
    st.segmented_control(
        "View as",
        options=["Map View", "Scatter Plot"],
        default="Map View",
        key=_VIEW_MODE_KEY,
        label_visibility="collapsed",
        width="stretch",
    )


def current_view_mode() -> str:
    """Current "Map View"/"Scatter Plot" choice, defaulting to "Map View"."""
    return st.session_state.get(_VIEW_MODE_KEY) or "Map View"


def render(ctx: DashboardContext) -> None:
    # Clustering runs over every station in the region, not the hand-picked
    # multiselect the other views use.
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
    # Read from session_state directly since the selectbox widgets that own
    # these keys render below the chart (_render_axis_selectors()).
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
    they control rather than above it."""
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
    """Plain-page legend for the map's cluster colors, standing in for
    Plotly's own in-chart legend (disabled in render_full_bleed_map())."""
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
    """Writes ``text`` into the Region column (kept writable after app.py's
    own `with` block closed) instead of full page width, so it stays
    anchored under the Region dropdown. Falls back to a full-width caption
    if no column was captured."""
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

    cluster_order = sorted(merged["cluster"].unique(), key=int)
    render_section_label("Station clusters", style="header")
    _render_cluster_legend(cluster_order)

    fig = px.scatter_map(
        merged, lat="latitude", lon="longitude", color="cluster", hover_name="name",
        hover_data=chosen_features, zoom=5.3, center={"lat": 51.2, "lon": 10.3}, map_style="open-street-map",
        category_orders={"cluster": cluster_order},
        color_discrete_sequence=_CLUSTER_COLORS,
    )

    fig.update_layout(height=820)
    map_columns = st.columns([2, 2])
    with map_columns[0]:
        render_full_bleed_map(fig, _MAP_CHART_CARD_KEY)
    if diagnostics is not None:
        with map_columns[1]:
            render_k_diagnostics_chart(diagnostics, best_k, collapsed=False, card_key=_MAP_DIAGNOSTICS_CARD_KEY)
            render_k_diagnostics_explanation()

    render_cluster_profile(clustered, chosen_features, value_labels)
