"""Widgets shared across more than one tab view."""

import datetime as dt
import json
import math
from collections.abc import Callable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from plotly.subplots import make_subplots

from src.analysis import (
    COMPOSITE_PARAMETER_GROUPS,
    PARAMETER_UNITS,
    TEMPERATURE_COMPOSITE_KEY,
    TEMPERATURE_TREND_PARAMETER_BY_LABEL,
    categorize_parameter,
    compute_parameter_stats,
)
from src.dashboard_context import DashboardContext
from src.data_loader import load_station_metadata
from src.ui_theme import ACCENT_HEX_BY_CATEGORY, chart_card, render_chart, style_fig

# Shared chart/Key-Figures row split across every chart-bearing view.
CHART_ROW_WIDTH_RATIO = [0.72, 0.28]

_PLAIN_MAP_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]}


def pretty_name(parameter: str) -> str:
    """"cloud_cover_total" -> "Cloud Cover Total". Composite keys needing a
    custom label should set one in COMPOSITE_PARAMETER_GROUPS instead."""
    return " ".join(word.capitalize() for word in parameter.split("_"))


def parameter_label_with_unit(parameter: str) -> str:
    """"wind_speed" -> "Wind Speed (m/s)", falling back to the bare name."""
    unit = PARAMETER_UNITS.get(parameter, "")
    return f"{pretty_name(parameter)} ({unit})" if unit else pretty_name(parameter)


def render_cluster_profile(clustered: pd.DataFrame, feature_cols: list[str], value_labels: dict[str, str]) -> None:
    """Per-cluster feature averages plus station counts, shared by Clustering
    and the Map tab's cluster-coloring mode."""
    render_section_label("Cluster profile", style="header")
    # Prefixed with "Mean " since these are cluster averages, not raw readings.
    mean_labels = {f: f"Mean {value_labels[f]}" for f in feature_cols}
    profile = clustered.groupby("cluster")[feature_cols].mean().rename(columns=mean_labels).round(1)
    profile.insert(0, "Stations", clustered.groupby("cluster").size())
    with chart_card():
        st.dataframe(profile, width="stretch")


_K_DIAGNOSTICS_EXPLANATION = (
    "**Inertia** is the sum of squared distances from every station's standardized "
    "feature values to its own cluster's center. Lower means tighter, more compact "
    "clusters.\n\n"
    "**Silhouette score** measures, for each station, how much closer it sits to its "
    "own cluster's average distance than to the nearest other cluster's. It's averaged "
    "across every station and scaled from -1 to 1. Higher means better-separated "
    "clusters.\n\n"
    "**Note:** With a single parameter, this recommendation is only meaningful when that "
    "parameter has a genuine gap in it, like a handful of high-altitude stations sitting "
    "noticeably colder than everywhere else. A parameter with no such gap (humidity, say, "
    "if every station reports a similar value) gives the algorithm nothing to peak on, so "
    "each extra cluster keeps slightly improving the score and the recommendation just "
    "lands on the highest k allowed instead of a real number of groups."
)


def _nice_axis_step(value_range: float, target_ticks: int = 5) -> float:
    """A "1-2-5-times-a-power-of-ten" tick step sized so roughly
    ``target_ticks`` fit across ``value_range``. Plotly's own auto tick
    spacing is tuned for a full-width axis, so it under-labels a narrow
    range like silhouette score's."""
    if value_range <= 0:
        return 1.0
    rough_step = value_range / target_ticks
    magnitude = 10 ** math.floor(math.log10(rough_step))
    residual = rough_step / magnitude
    nice = 1 if residual < 1.5 else 2 if residual < 3 else 5 if residual < 7 else 10
    return nice * magnitude


def render_k_diagnostics_explanation() -> None:
    """Always-visible explanation of how inertia/silhouette score are
    calculated, in its own chart_card() rather than a tooltip. Rendered
    separately from render_k_diagnostics_chart() so callers can place it
    wherever makes sense relative to their own k-slider."""
    with chart_card():
        render_section_label("What is Inertia and Silhouette Score?", style="header")
        st.markdown(_K_DIAGNOSTICS_EXPLANATION)


def render_k_diagnostics_chart(
    diagnostics: pd.DataFrame, best_k: int, collapsed: bool = True, card_key: str | None = None
) -> None:
    """Elbow (inertia) + silhouette score across k, backing a cluster-count
    slider's recommended-k label. Collapsed into an expander by default;
    pass ``collapsed=False`` to render in place instead (e.g. next to the
    map). ``card_key`` (only used when not collapsed) wraps the chart in a
    zero-padding chart_card()."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=diagnostics["k"], y=diagnostics["inertia"], mode="lines+markers", name="Inertia"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=diagnostics["k"], y=diagnostics["silhouette"], mode="lines+markers", name="Silhouette score"),
        secondary_y=True,
    )
    fig.update_xaxes(title_text="Number of clusters (k)")
    fig.update_yaxes(title_text="Inertia", secondary_y=False)
    silhouette_span = diagnostics["silhouette"].max() - diagnostics["silhouette"].min()
    fig.update_yaxes(
        title_text="Silhouette score", dtick=_nice_axis_step(silhouette_span), secondary_y=True
    )
    # Explicit empty title: style_fig() sets title_font_color unconditionally,
    # and Plotly renders a literal "undefined" placeholder with no title set.
    fig.update_layout(title="", height=280, margin=dict(t=20, b=10))

    def _render_caption() -> None:
        st.caption(f"Silhouette score peaks at k={best_k}, which is why the slider above starts there.")
        st.caption('Inertia keeps falling as k grows, but flattens out around the same point (the classic "elbow").')

    if collapsed:
        with st.expander("How was the recommended k chosen?"):
            render_section_label("Inertia and silhouette score by k", style="header")
            _render_caption()
            render_chart(fig)
            render_k_diagnostics_explanation()
    else:
        render_section_label("Inertia and silhouette score by k", style="header")
        _render_caption()
        if card_key:
            st.markdown(
                f'<style>div[data-testid="stVerticalBlock"][class*="{card_key}"] {{ '
                f"padding: 0 !important; "
                f"}}</style>",
                unsafe_allow_html=True,
            )
            with chart_card(key=card_key):
                render_chart(fig)
        else:
            render_chart(fig)


def _dropdown_label(value: str) -> str:
    """Display text for one "Parameter" dropdown option. Composite keys use
    their group's explicit "label" when present, else pretty_name()."""
    group = COMPOSITE_PARAMETER_GROUPS.get(value)
    if group and "label" in group:
        return group["label"]
    return pretty_name(value)


def _format_stat(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    return f"{value:.2f} {unit}".strip()


def _format_total(value: int | float, unit: str) -> str:
    return f"{value:,.0f} {unit}".strip()


def render_section_label(text: str, style: str = "label") -> None:
    font_size = "20px" if style == "header" else "15px"
    letter_spacing = "0.1px" if style == "header" else "0.2px"
    st.markdown(
        f'<p style="font-size:{font_size};font-weight:600;letter-spacing:{letter_spacing};'
        f'color:var(--m3-on-primary-container, #1E4469);'
        f'margin:0 0 0.5rem 0;">{text}</p>',
        unsafe_allow_html=True,
    )


def render_segmented_nav_css(
    key: str,
    option_count: int,
    font_size: str,
    margin_top: str = "0",
    margin_bottom: str = "1.5rem",
) -> None:
    """Bare, no-pill skin for one ``st.segmented_control()``: big bold text
    spanning the full row, a shared sliding underline indicator (one bar
    that slides between columns on `aria-checked`, not per-button), and a
    lift+color hover affordance on inactive options. Indicator width is
    68% of its own column, so it scales as ``option_count`` grows. Scoped
    selectors here out-specificity the global stButtonGroup rules in
    _BASE_CSS by one extra ancestor selector."""
    column_pct = 100 / option_count
    indicator_width_pct = 0.68 * column_pct
    offset_pct = (column_pct - indicator_width_pct) / 2

    indicator_position_rules = "".join(
        f'[class*="{key}"] [data-testid="stButtonGroup"] > div:has(button:nth-child({i})[aria-checked="true"])::after {{ '
        f"left: {(i - 1) * column_pct + offset_pct:.3f}%; "
        f"}}"
        for i in range(1, option_count + 1)
    )

    st.markdown(
        f'<style>'
        f'[class*="{key}"] [data-testid="stButtonGroup"] {{ '
        f"gap: 0 !important; margin: {margin_top} 0 {margin_bottom} 0; "
        f"}}"
        f'[class*="{key}"] [data-testid="stButtonGroup"] > div:has(button) {{ '
        f"position: relative; "
        f"border-bottom: 1px solid color-mix(in srgb, var(--m3-outline-variant, #B7C6D7) 70%, transparent); "
        f"}}"
        f'[class*="{key}"] [data-testid="stButtonGroup"] > div:has(button)::after {{ '
        f'content: ""; position: absolute; bottom: 0; height: 2px; '
        f"width: {indicator_width_pct:.3f}%; left: {offset_pct:.3f}%; "
        f"background: var(--m3-on-primary-container, #1E4469); "
        f"transition: left 0.28s cubic-bezier(.4, 0, .2, 1); "
        f"}}"
        f"{indicator_position_rules}"
        f'[class*="{key}"] [data-testid="stButtonGroup"] button {{ '
        f"background: none !important; border: none !important; box-shadow: none !important; "
        f"backdrop-filter: none !important; -webkit-backdrop-filter: none !important; "
        f"border-radius: 0 !important; "
        # Overrides the fixed 32px button height, which clips text at bigger font-sizes.
        f"height: auto !important; min-height: 0 !important; overflow: visible !important; "
        f"line-height: 1.25 !important; "
        f"flex: 1 1 {column_pct:.3f}% !important; justify-content: center !important; "
        f"font-size: {font_size} !important; font-weight: 700 !important; letter-spacing: 0.02em; "
        f"padding: 0.5rem 0.5rem 0.9rem !important; "
        f"color: color-mix(in srgb, var(--m3-on-primary-container, #1E4469) 50%, transparent) !important; "
        f"transition: color 0.15s ease, transform 0.15s ease; "
        f"}}"
        # Hover affordance on unselected options only.
        f'[class*="{key}"] [data-testid="stButtonGroup"] button:not([aria-checked="true"]):hover {{ '
        f"color: var(--m3-on-primary-container, #1E4469) !important; "
        f"transform: translateY(-3px); "
        f"}}"
        # Overrides the fixed 14px rule on the button's inner <p>.
        f'[class*="{key}"] [data-testid="stButtonGroup"] button p {{ '
        f"font-size: {font_size} !important; font-weight: 700 !important; line-height: 1.25 !important; "
        f"}}"
        f'[class*="{key}"] [data-testid="stButtonGroup"] button[aria-checked="true"] {{ '
        f"color: var(--m3-on-primary-container, #1E4469) !important; "
        f"}}"
        f"</style>",
        unsafe_allow_html=True,
    )


def render_key_figures_box(
    subset: pd.DataFrame,
    parameter: str,
    key_prefix: str,
    stats: dict[str, float | int | str | None] | None = None,
    chart_height: int = 450,
) -> None:
    """Min/mean/max/mode/total for one parameter's filtered data, as a single
    vertically-stacked box sized to sit beside its chart.

    ``chart_height`` should match the chart's own height, this box's CSS
    height is set to it directly in pixels rather than `height: 100%`,
    since that collapses to "auto" against Streamlit's auto-sized wrapper.

    ``stats``, when provided, is used as-is instead of computed from
    ``subset``/``parameter``, lets a composite with its own stats function
    (e.g. compute_temperature_stats) supply numbers from more than one series."""
    stats = stats if stats is not None else compute_parameter_stats(subset, parameter)
    unit = stats["unit"]
    active_parameter = st.session_state.get("active_theme_parameter", parameter)
    accent_hex = ACCENT_HEX_BY_CATEGORY[categorize_parameter(active_parameter)]

    stat_defs = [
        ("Min", _format_stat(stats["min"], unit)),
        ("Mean", _format_stat(stats["mean"], unit)),
        ("Max", _format_stat(stats["max"], unit)),
        ("Mode", _format_stat(stats["mode"], unit)),
        (stats["total_label"], _format_total(stats["total"], stats["total_unit"])),
    ]

    render_section_label("Key Figures:", style="header")

    card_key = f"{key_prefix}-key-figures"
    rows = "".join(
        f'<div style="display:flex; justify-content:space-between; align-items:center; '
        f'gap:0.75rem; padding:0.7rem 0.15rem;'
        f'{"" if i == len(stat_defs) - 1 else "border-bottom:1px solid color-mix(in srgb, var(--m3-outline-variant, #B7C6D7) 45%, transparent);"}">'
        f'<span style="font-size:0.85rem; font-weight:600; text-transform:uppercase; '
        f'letter-spacing:0.04em; opacity:0.65; white-space:nowrap;">{stat_label}</span>'
        f'<span style="font-size:1.3rem; font-weight:700; white-space:nowrap; '
        f'color:{accent_hex};">{value}</span>'
        f'</div>'
        for i, (stat_label, value) in enumerate(stat_defs)
    )
    # chart_height plus chart_card()'s own top/bottom padding+border.
    box_height = chart_height + 2 * 25
    st.markdown(
        f'<style>div[data-testid="stVerticalBlock"][class*="{card_key}"] {{ '
        f"height: {box_height}px !important; padding: 0.85rem 1rem !important; "
        f"}}</style>",
        unsafe_allow_html=True,
    )
    with chart_card(key=card_key):
        st.markdown(
            f'<div style="height:100%; display:flex; flex-direction:column; justify-content:space-between;">'
            f'{rows}</div>',
            unsafe_allow_html=True,
        )


_SHARED_PARAMETER_KEY = "shared_selected_parameter"
TEMPERATURE_TREND_TOGGLE_KEY = "temperature_trend_line"
_SHARED_TEMPERATURE_TREND_KEY = "shared_temperature_trend_label"


def _composite_key_for_parameter(parameter: str) -> str | None:
    """Return the COMPOSITE_PARAMETER_GROUPS key whose components include
    ``parameter``, or None if it isn't part of any composite."""
    for composite_key, group in COMPOSITE_PARAMETER_GROUPS.items():
        if parameter in group["components"]:
            return composite_key
    return None


def _render_temperature_trend_toggle() -> str:
    """Mean/Max/Min toggle for the "Temperature" composite, shared (same
    widget key, same GC-safe re-seed trick) across every view exactly like
    _SHARED_PARAMETER_KEY above -- picking "Max" in Regression and
    switching to Map keeps showing max temperature there too, rather than
    resetting to Mean. _SHARED_TEMPERATURE_TREND_KEY is the durable plain-
    dict backup (see render_parameter_and_subset()'s docstring for why
    that's needed) that survives to reseed TEMPERATURE_TREND_TOGGLE_KEY
    whenever Streamlit has dropped it after a run where the toggle wasn't
    rendered at all (i.e. Temperature wasn't the active parameter, in any
    view). Returns the current trend label ("Mean", "Max", or "Min")."""
    shared_label = st.session_state.get(_SHARED_TEMPERATURE_TREND_KEY)
    if shared_label is not None and TEMPERATURE_TREND_TOGGLE_KEY not in st.session_state:
        st.session_state[TEMPERATURE_TREND_TOGGLE_KEY] = shared_label

    trend_label = st.segmented_control(
        "Trend line",
        options=list(TEMPERATURE_TREND_PARAMETER_BY_LABEL),
        default="Mean",
        key=TEMPERATURE_TREND_TOGGLE_KEY,
    )
    # segmented_control returns None if the user clicks the selected
    # option again to deselect it -- fall back to Mean rather than
    # breaking whatever reads this next.
    trend_label = trend_label or "Mean"
    st.session_state[_SHARED_TEMPERATURE_TREND_KEY] = trend_label
    return trend_label


def render_parameter_and_subset(
    raw: pd.DataFrame, key: str, show_stats: bool = True, collapse_composites: bool = False
) -> tuple[str, pd.DataFrame, str, pd.DataFrame, Callable[..., None] | None]:
    """Render a "Parameter" selectbox scoped to one view and filter ``raw`` to it.
    Returns ``(parameter, subset, effective_parameter, effective_subset, render_key_figures)``.

    ``render_key_figures`` takes an optional ``chart_height`` and renders
    the Key Figures box (render_key_figures_box()) -- not rendered here,
    since callers place it next to their own chart once its height is known.

    ``collapse_composites`` replaces each group's component parameters (see
    COMPOSITE_PARAMETER_GROUPS) with one grouped dropdown entry. When a
    composite is selected, what ``render_key_figures`` does depends on the
    group's shape: "stats_fn" renders one merged box via the group's own
    stats function; "stats_parameters" is left ``None`` since the caller
    must render one box per component itself; otherwise it's one box off
    the group's "primary" parameter.

    ``effective_parameter``/``effective_subset`` reduce a composite down to
    one real DWD parameter, for callers needing a single series (Regression's
    trend fit, Map/Clustering's per-station mean). For "Temperature" that's
    whichever of mean/max/min the shared Mean/Max/Min toggle has selected;
    other composites use their "primary" (or first component, if none).

    Every view calling this shares one selection via
    st.session_state[_SHARED_PARAMETER_KEY], always a real DWD parameter
    (never a composite key). Composite-aware callers translate it to
    whichever composite currently contains it before offering it as this
    dropdown's value, and translate back when writing a new selection.

    The re-seed below only fires when this widget's own persisted value is
    missing, not merely stale -- Streamlit drops a `key=`-bound value after
    a few reruns where its widget doesn't execute (e.g. switching through
    every other view and back). _SHARED_PARAMETER_KEY is a plain dict entry
    that survives that, so it can re-seed the widget when needed, without
    clobbering a value the user just picked this run (in which case
    Streamlit already wrote it, so the key isn't "missing")."""
    render_section_label("Parameter")

    available_parameters = set(raw["parameter"].unique())
    options = available_parameters
    if collapse_composites:
        for composite_key, group in COMPOSITE_PARAMETER_GROUPS.items():
            components = set(group["components"])
            if available_parameters & components:
                options = (options - components) | {composite_key}
    options = sorted(options)

    shared_parameter = st.session_state.get(_SHARED_PARAMETER_KEY)
    if shared_parameter is not None and key not in st.session_state:
        desired = _composite_key_for_parameter(shared_parameter) if collapse_composites else shared_parameter
        if collapse_composites and desired is None:
            desired = shared_parameter
        if desired in options:
            st.session_state[key] = desired

    parameter = st.selectbox(
        "Parameter",
        options,
        key=key,
        label_visibility="collapsed",
        format_func=_dropdown_label,
    )

    if parameter in COMPOSITE_PARAMETER_GROUPS:
        group_for_canonical = COMPOSITE_PARAMETER_GROUPS[parameter]
        canonical_parameter = group_for_canonical.get("primary", group_for_canonical["components"][0])
    else:
        canonical_parameter = parameter
    st.session_state[_SHARED_PARAMETER_KEY] = canonical_parameter

    st.session_state["active_theme_parameter"] = parameter

    render_key_figures = None
    if parameter in COMPOSITE_PARAMETER_GROUPS:
        group = COMPOSITE_PARAMETER_GROUPS[parameter]
        subset = raw[raw["parameter"].isin(group["components"])].dropna(subset=["value"])
        if show_stats and "stats_parameters" not in group:
            if "stats_fn" in group:
                stats = group["stats_fn"](subset)
                render_key_figures = lambda chart_height=450: render_key_figures_box(
                    subset, group["primary"], key_prefix=key, stats=stats, chart_height=chart_height
                )
            else:
                stats_subset = raw[raw["parameter"] == group["primary"]].dropna(subset=["value"])
                render_key_figures = lambda chart_height=450: render_key_figures_box(
                    stats_subset, group["primary"], key_prefix=key, chart_height=chart_height
                )
        if parameter == TEMPERATURE_COMPOSITE_KEY:
            trend_label = _render_temperature_trend_toggle()
            effective_parameter = TEMPERATURE_TREND_PARAMETER_BY_LABEL[trend_label]
        else:
            # No "primary" for a "stats_parameters" group -- fall back to its first component.
            effective_parameter = group.get("primary", group["components"][0])
    else:
        subset = raw[raw["parameter"] == parameter].dropna(subset=["value"])
        if show_stats:
            render_key_figures = lambda chart_height=450: render_key_figures_box(
                subset, parameter, key_prefix=key, chart_height=chart_height
            )
        effective_parameter = parameter

    effective_subset = raw[raw["parameter"] == effective_parameter].dropna(subset=["value"])
    return parameter, subset, effective_parameter, effective_subset, render_key_figures


def _station_missing_reason(
    raw: pd.DataFrame,
    metadata: pd.DataFrame,
    parameter: str,
    station_id: str,
    start_date: dt.date,
    end_date: dt.date,
    component_parameters: list[str] | None = None,
) -> str:
    """Explain why ``station_id`` has zero valid rows for ``parameter`` in
    ``raw`` over [start_date, end_date]. Three causes, checked in order:
    (1) the station's reporting window doesn't overlap the date range at
    all, (2) it overlaps but ``raw`` has no rows for this parameter (the
    station doesn't measure it), (3) rows exist but every ``value`` is NaN
    (a genuine data gap).

    ``parameter`` may be a composite key -- causes 2/3 then check across
    all of that composite's components. ``component_parameters`` overrides
    that with an exact list instead, for a caller whose chart only draws
    from *some* of a composite's components (see find_stations_missing_data())."""
    if station_id in metadata.index:
        station_start = metadata.loc[station_id, "start_date"]
        station_end = metadata.loc[station_id, "end_date"]
        if pd.notna(station_start) and pd.notna(station_end):
            station_start, station_end = station_start.date(), station_end.date()
            if station_end < start_date or station_start > end_date:
                return (
                    f"not operational in the selected date range "
                    f"(reports {station_start:%d/%m/%Y}–{station_end:%d/%m/%Y})"
                )

    if component_parameters is None:
        component_parameters = (
            COMPOSITE_PARAMETER_GROUPS[parameter]["components"] if parameter in COMPOSITE_PARAMETER_GROUPS else [parameter]
        )
    station_rows = raw[(raw["station_id"] == station_id) & (raw["parameter"].isin(component_parameters))]
    if station_rows.empty:
        return f"does not report {pretty_name(parameter)}"
    return f"has no {pretty_name(parameter)} readings in the selected date range (data gap)"


def missing_station_reason(
    ctx: DashboardContext, parameter: str, station_id: str, start_date: dt.date, end_date: dt.date
) -> str:
    """Single-station version of find_stations_missing_data(), for tabs
    (e.g. regression) that operate on one station at a time rather than
    plotting all selected stations together."""
    metadata = load_station_metadata([station_id]).set_index("station_id")
    return _station_missing_reason(ctx.raw, metadata, parameter, station_id, start_date, end_date)


def find_stations_missing_data(
    ctx: DashboardContext,
    parameter: str,
    subset: pd.DataFrame,
    start_date: dt.date,
    end_date: dt.date,
    component_parameters: list[str] | None = None,
) -> list[dict[str, str]]:
    """Diff the stations selected in the station-picker row against the ones
    actually present in ``subset``, and explain each gap -- charts silently
    drop a station with zero rows, so this is the shared notice each view
    renders before its chart.

    ``subset`` must already be filtered to exactly what the caller's chart
    draws from, and ``component_parameters`` must match whenever it differs
    from ``parameter``'s full-composite default -- a wider ``subset`` makes
    a station read as "present" via some other component it actually has
    no rows for."""
    selected_ids = [ctx.id_by_name[name] for name in ctx.selected_names]
    present_ids = set(subset["station_id"].unique())
    missing_ids = [sid for sid in selected_ids if sid not in present_ids]
    if not missing_ids:
        return []

    metadata = load_station_metadata(missing_ids).set_index("station_id")
    return [
        {
            "station_id": station_id,
            "station_name": ctx.id_to_name.get(station_id, station_id),
            "reason": _station_missing_reason(
                ctx.raw, metadata, parameter, station_id, start_date, end_date, component_parameters
            ),
        }
        for station_id in missing_ids
    ]


def merge_missing_stations(*missing_lists: list[dict[str, str]]) -> list[dict[str, str]]:
    """Combine several find_stations_missing_data() results into one list
    for a single banner, deduping exact ``(station_id, reason)`` repeats
    (a station can legitimately appear twice with different reasons)."""
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, str]] = []
    for missing in missing_lists:
        for entry in missing:
            dedupe_key = (entry["station_id"], entry["reason"])
            if dedupe_key not in seen:
                seen.add(dedupe_key)
                merged.append(entry)
    return merged


def render_missing_stations_indicator(missing: list[dict[str, str]], anchor_id: str, card_key: str) -> None:
    """Warning icon overlaid right next to wherever the word "Station"
    renders inside a tab's chart_card() (the legend title in Time Series,
    the x-axis title in Clustering -- px.bar's own `labels={"station_name":
    "Station", ...}` makes that literally the same word) when
    find_stations_missing_data() found selected stations that aren't
    plotted. Renders nothing if ``missing`` is empty (but still removes a
    previous run's icon, since nothing else will).

    Must be called from *inside* the same ``with chart_card(key=card_key):``
    block it's meant to overlay -- ``card_key`` locates that container via
    the "st-key-{key}" class Streamlit adds to it."""
    icon_id = f"missing-station-icon-{card_key}"
    if not missing:
        components.html(
            f'<script>'
            f'var el = window.parent.document.getElementById({icon_id!r}); '
            f'if (el) {{ el.remove(); }}'
            f'</script>',
            height=0,
        )
        return

    station_word = "station" if len(missing) == 1 else "stations"
    tooltip = f"Data points not available for {len(missing)} selected {station_word} -- click for details"
    config = json.dumps({"cardKey": card_key, "iconId": icon_id, "anchorId": anchor_id, "tooltip": tooltip})
    components.html(
        f"""
        <script>
        (function() {{
            var cfg = {config};
            var doc = window.parent.document;

            function place() {{
                var card = doc.querySelector('[class*="' + cfg.cardKey + '"]');
                if (!card) return false;
                var texts = card.querySelectorAll('svg text');
                var titleEl = null;
                for (var i = 0; i < texts.length; i++) {{
                    if (texts[i].textContent.trim() === 'Station') {{ titleEl = texts[i]; break; }}
                }}
                if (!titleEl) return false;

                card.style.position = 'relative';
                var cardRect = card.getBoundingClientRect();
                var titleRect = titleEl.getBoundingClientRect();

                var icon = doc.getElementById(cfg.iconId);
                if (!icon) {{
                    icon = doc.createElement('a');
                    icon.id = cfg.iconId;
                    icon.setAttribute('aria-label', 'warning');
                    icon.textContent = '\\u26A0\\uFE0F';
                    icon.style.cssText = (
                        'position:absolute; z-index:5; text-decoration:none; '
                        + 'font-size:12px; line-height:1;'
                    );
                    card.appendChild(icon);
                }}
                icon.href = '#' + cfg.anchorId;
                icon.title = cfg.tooltip;
                // Measured live -- position isn't fixed across chart types/station counts.
                icon.style.top = (titleRect.top - cardRect.top) + 'px';
                icon.style.left = (titleRect.right - cardRect.left + 6) + 'px';
                return true;
            }}

            // Plotly's own SVG can take a moment to finish rendering
            // after this script first runs -- retry briefly rather than
            // giving up after a single failed lookup.
            var attempts = 0;
            var timer = setInterval(function() {{
                attempts += 1;
                if (place() || attempts > 30) clearInterval(timer);
            }}, 100);
        }})();
        </script>
        """,
        height=0,
    )


def render_full_bleed_map(
    fig, card_key: str, missing: list[dict[str, str]] | None = None, anchor_id: str | None = None
) -> None:
    """Render a scatter_map figure edge-to-edge inside its own chart_card(),
    zeroing every margin so the map fills the card instead of leaving a
    band of card-background around it. Shared by Map's value-mode map and
    Clustering's map-view mode.

    ``missing``/``anchor_id``, when given, render the missing-stations
    warning icon, threaded through here since it must be called from
    inside this card's own ``with chart_card():`` block to position correctly."""
    style_fig(fig)
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
    st.markdown(
        f'<style>div[data-testid="stVerticalBlock"][class*="{card_key}"] {{ '
        f"padding: 0 !important; "
        f"}}</style>",
        unsafe_allow_html=True,
    )
    with chart_card(key=card_key):
        if missing and anchor_id:
            render_missing_stations_indicator(missing, anchor_id, card_key=card_key)
        st.plotly_chart(fig, width="stretch", config=_PLAIN_MAP_CONFIG)


def render_missing_stations_notice(missing: list[dict[str, str]], anchor_id: str | None = None) -> None:
    """Render the per-station explanations from find_stations_missing_data()
    as a single warning banner, or nothing if every selected station has
    data. One banner listing every excluded station rather than one banner
    each, so N missing stations don't stack N warnings."""
    
    if not missing:
        return
    if anchor_id:
        st.markdown(f'<div id="{anchor_id}" style="scroll-margin-top:80px;"></div>', unsafe_allow_html=True)
    lines = "\n".join(f"- **{station['station_name']}**: {station['reason']}" for station in missing)
    station_word = "station" if len(missing) == 1 else "stations"
    st.warning(f"Not shown: No data for {len(missing)} selected {station_word}:\n{lines}")
