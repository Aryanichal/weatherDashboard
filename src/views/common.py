"""Widgets shared across more than one tab view."""

import datetime as dt

import pandas as pd
import streamlit as st

from src.analysis import (
    COMPOSITE_PARAMETER_GROUPS,
    TEMPERATURE_COMPOSITE_KEY,
    TEMPERATURE_TREND_PARAMETER_BY_LABEL,
    categorize_parameter,
    compute_parameter_stats,
)
from src.dashboard_context import DashboardContext
from src.data_loader import load_station_metadata
from src.ui_theme import ACCENT_HEX_BY_CATEGORY


def pretty_name(parameter: str) -> str:
    """"cloud_cover_total" -> "Cloud Cover Total". Also handles composite
    keys like "temperature" -> "Temperature" with no special-casing."""
    return " ".join(word.capitalize() for word in parameter.split("_"))


def _format_stat(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    return f"{value:.2f} {unit}".strip()


def _format_total(value: int | float, unit: str) -> str:
    return f"{value:,.0f} {unit}".strip()


def render_section_label(text: str) -> None:
    st.markdown(
        f'<p style="font-size:16px;font-weight:600;letter-spacing:0.15px;'
        f'color:color-mix(in srgb, var(--m3-primary, #4D77CB) 85%, transparent);'
        f'margin:0 0 0.5rem 0;">{text}</p>',
        unsafe_allow_html=True,
    )


def render_stats_toolbar(
    subset: pd.DataFrame,
    parameter: str,
    key_prefix: str,
    display_label: str | None = None,
    stats: dict[str, float | int | str | None] | None = None,
) -> None:
    """Min/mean/max/mode/total cards for one parameter's filtered data.

    ``stats``, when provided, is used as-is instead of being computed from
    ``subset``/``parameter`` via compute_parameter_stats() -- this is how
    a composite with its own stats function (e.g. compute_temperature_stats
    in src/analysis.py) supplies numbers that don't all come from one
    series. ``parameter``/``subset`` are still required in that case (for
    the active-theme accent color and as harmless bookkeeping), just not
    used to compute the numbers themselves.

    ``display_label`` overrides the card titles (used when the cards
    should read a composite's own name, e.g. "Temperature", rather than
    ``parameter``'s name).
    """
    stats = stats if stats is not None else compute_parameter_stats(subset, parameter)
    unit = stats["unit"]
    label = display_label or pretty_name(parameter)
    active_parameter = st.session_state.get("active_theme_parameter", parameter)
    accent_hex = ACCENT_HEX_BY_CATEGORY[categorize_parameter(active_parameter)]

    stat_defs = [
        ("min", f"Min {label}", _format_stat(stats["min"], unit), True),
        ("mean", f"Mean {label}", _format_stat(stats["mean"], unit), False),
        ("max", f"Max {label}", _format_stat(stats["max"], unit), True),
        ("mode", f"Mode {label}", _format_stat(stats["mode"], unit), False),
        ("total", stats["total_label"], _format_total(stats["total"], stats["total_unit"]), True),
    ]

    render_section_label("Key Figures:")

    st.markdown(
        f'<style>'
        f'[class*="{key_prefix}-"][class*="-stat-accent"] {{'
        f'background: color-mix(in srgb, {accent_hex} 80%, white) !important;'
        f'}}'
        f'[class*="{key_prefix}-"][class*="-stat-plain"] [data-testid="stMetricLabel"] p,'
        f'[class*="{key_prefix}-"][class*="-stat-plain"] [data-testid="stMetricValue"] {{'
        f'color: color-mix(in srgb, {accent_hex} 85%, transparent) !important;'
        f'}}'
        f'</style>',
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    for col, (slug, title, value, accent) in zip(cols, stat_defs):
        marker = "stat-accent" if accent else "stat-plain"
        with col, st.container(border=True, key=f"{key_prefix}-{slug}-{marker}"):
            st.metric(title, value)


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
) -> tuple[str, pd.DataFrame, str, pd.DataFrame]:
    """Render a "Parameter" selectbox scoped to one view and filter ``raw`` to it.
    Returns ``(parameter, subset, effective_parameter, effective_subset)``.

    ``collapse_composites`` replaces each group's component parameters
    (see COMPOSITE_PARAMETER_GROUPS in src/analysis.py) with one grouped
    dropdown entry. When a composite is selected, ``parameter`` is that
    composite's synthetic key and ``subset`` contains every one of its
    components' rows; the Key Figures toolbar underneath uses that
    composite's own ``stats_fn`` if it has one (currently just
    "Temperature"), otherwise falls back to the default:
    compute_parameter_stats() on just the composite's "primary" parameter.

    ``effective_parameter``/``effective_subset`` are what every caller
    that needs to reduce a selection down to *one real DWD parameter* for
    its own single-series computation (Regression's trend fit, Map's
    per-station mean, Clustering's per-station mean) should use instead of
    ``parameter``/``subset``: for a non-composite selection they're
    identical to ``parameter``/``subset``; for the "Temperature" composite,
    ``effective_parameter`` is whichever of mean/max/min 2m air temperature
    the Mean/Max/Min toggle this function renders (see
    _render_temperature_trend_toggle() above) currently has selected --
    that toggle is shared across every view the same way the "Parameter"
    dropdown itself is, so picking "Max" in Regression and switching to
    Map keeps showing max temperature there too; for "Precipitation",
    which has no toggle, it's always PRECIPITATION_PRIMARY_PARAMETER
    (precipitation_height) -- its other component, precipitation_form, is
    a category code, not a continuous quantity, so there's no meaningful
    single number to reduce it to outside Time Series' own dedicated
    monthly-breakdown chart. Only Time Series itself needs the full
    ``parameter``/``subset`` -- its composite views render every component
    at once rather than reducing to one.

    Every view calling this shares one selection: picking "Temperature" in
    Time Series and switching to Map, Regression, or Clustering shows that
    same choice there too, and vice versa. This works by keeping one
    canonical value in st.session_state[_SHARED_PARAMETER_KEY] that's
    always a real DWD parameter (never a composite key, since only Time
    Series' own dropdown ever offers composites -- app.py only ever runs
    one view's render() per script pass, see its own module docstring, so
    there's no risk of two of these calls fighting over it in the same
    run). Composite-aware callers translate the canonical value to
    whichever composite currently contains it (via
    _composite_key_for_parameter()) before offering it as this dropdown's
    current value; non-composite callers use it directly, since their
    options are always real parameters and so is the canonical value.
    Whichever direction a change came from, this dropdown's own resulting
    ``parameter`` is translated back the same way (a composite's own
    "primary" component standing in for the composite itself) and written
    back to the canonical value, so the next view to render picks it up.

    The re-seeding below (``if key not in st.session_state``) only fires
    when THIS widget's own persisted value is missing -- never when it's
    merely stale, which matters because Streamlit quietly drops a widget's
    session_state entry once it goes unrendered for a few reruns (verified
    empirically: a plain, non-widget session_state entry survives any
    number of reruns without being touched, but a `key=`-bound one gets
    wiped back to its default after ~4-5 reruns where its own
    st.selectbox() call never executes -- exactly what happens to every
    OTHER view's "parameter_*" key while the user sits on one view for a
    while). That's what _SHARED_PARAMETER_KEY is *for*: unlike the widget
    keys, it's a plain dict entry Streamlit never garbage-collects, so it
    survives to re-seed whichever widget key got wiped meanwhile -- e.g.
    switching Time Series -> Map -> Regression -> Clustering -> Global
    Warming -> back to Time Series used to reset Time Series' own dropdown
    to its default, because by then Streamlit had already dropped
    "parameter_series" from session_state; re-seeding only when the key is
    truly absent (rather than whenever it merely differs from the last
    value this call saw, which the previous version of this function did)
    fixes that without also clobbering a value the user just picked in
    THIS dropdown this run -- when that happens, Streamlit has already
    written the new value into st.session_state[key] before this function
    is even called, so the key is never "missing" in that case.
    """
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
        format_func=pretty_name,
    )

    canonical_parameter = (
        COMPOSITE_PARAMETER_GROUPS[parameter]["primary"] if parameter in COMPOSITE_PARAMETER_GROUPS else parameter
    )
    st.session_state[_SHARED_PARAMETER_KEY] = canonical_parameter

    prev_value_key = f"_theme_prev_{key}"
    if st.session_state.get(prev_value_key) != parameter:
        st.session_state["active_theme_parameter"] = parameter
    st.session_state[prev_value_key] = parameter

    if parameter in COMPOSITE_PARAMETER_GROUPS:
        group = COMPOSITE_PARAMETER_GROUPS[parameter]
        subset = raw[raw["parameter"].isin(group["components"])].dropna(subset=["value"])
        if show_stats:
            stats_fn = group.get("stats_fn")
            if stats_fn is not None:
                render_stats_toolbar(
                    subset, group["primary"], key_prefix=key,
                    display_label=pretty_name(parameter), stats=stats_fn(subset),
                )
            else:
                stats_subset = raw[raw["parameter"] == group["primary"]].dropna(subset=["value"])
                render_stats_toolbar(
                    stats_subset, group["primary"], key_prefix=key, display_label=pretty_name(parameter)
                )
        if parameter == TEMPERATURE_COMPOSITE_KEY:
            trend_label = _render_temperature_trend_toggle()
            effective_parameter = TEMPERATURE_TREND_PARAMETER_BY_LABEL[trend_label]
        else:
            effective_parameter = group["primary"]
    else:
        subset = raw[raw["parameter"] == parameter].dropna(subset=["value"])
        if show_stats:
            render_stats_toolbar(subset, parameter, key_prefix=key)
        effective_parameter = parameter

    effective_subset = raw[raw["parameter"] == effective_parameter].dropna(subset=["value"])
    return parameter, subset, effective_parameter, effective_subset


def _station_missing_reason(
    raw: pd.DataFrame,
    metadata: pd.DataFrame,
    parameter: str,
    station_id: str,
    start_date: dt.date,
    end_date: dt.date,
) -> str:
    """Explain why ``station_id`` has zero valid rows for ``parameter`` in
    ``raw`` over [start_date, end_date].

    Three distinguishable causes, checked in order of how conclusive the
    evidence is:

    1. The station's own reporting window (from DWD's per-station metadata,
       independent of ``parameter``) doesn't overlap the selected date
       range at all -- it was installed after / decommissioned before the
       range, so no dataset for it could have anything here regardless of
       parameter.
    2. The station's window does overlap, but ``raw`` has no rows at all
       for this station+parameter combination -- wetterdienst never
       returned any, which for climate_summary means the station's
       equipment doesn't measure this parameter.
    3. Rows exist for this station+parameter, but ``value`` was NaN for
       every one of them in this range -- a genuine data gap rather than
       an unsupported parameter.

    ``parameter`` may be a composite key (e.g. "temperature") rather than
    a real DWD parameter -- COMPOSITE_PARAMETER_GROUPS[parameter] never
    appears as a value in ``raw["parameter"]`` itself (see
    render_parameter_and_subset()'s docstring), so cause 2/3 above are
    checked against every one of that composite's *components* instead:
    a station only "does not report" the composite if it has zero rows
    for every one of them, and only has a "data gap" if it has rows for
    at least one component but none with a valid value.
    """
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
    ctx: DashboardContext, parameter: str, subset: pd.DataFrame, start_date: dt.date, end_date: dt.date
) -> list[dict[str, str]]:
    """Diff the stations selected in the station-picker row against the
    ones actually present in ``subset`` (already filtered to ``parameter``
    and non-null ``value`` by render_parameter_and_subset()), and explain
    each gap.

    Every chart-producing view (time series, map, clustering; regression
    via missing_station_reason() above) aggregates ``subset`` in a way that
    just silently omits a station with zero rows -- a px.line color group,
    a groupby, an inner merge -- with nothing to tell the user that station
    was ever selected. This is the shared "what got dropped and why" check
    each view renders as a notice before its chart.
    """
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
            "reason": _station_missing_reason(ctx.raw, metadata, parameter, station_id, start_date, end_date),
        }
        for station_id in missing_ids
    ]


def render_missing_stations_indicator(
    missing: list[dict[str, str]], anchor_id: str, card_key: str, top: str = "73px", right: str = "98px"
) -> None:
    """Warning icon overlaid right next to the "Station" text px already
    renders inside a tab's chart_card() (the legend title in Time Series,
    the x-axis title in Clustering) when find_stations_missing_data() found
    selected stations that aren't plotted. Renders nothing if ``missing``
    is empty.

    Must be called from *inside* the same ``with chart_card(key=card_key):``
    block it's meant to overlay: the icon is positioned absolute, and
    ``card_key`` is the key that same chart_card() call was given, used
    here only to scope the CSS that makes that one bordered container
    ``position: relative`` (Streamlit's own containers are static, so
    without this the icon would position against the page instead of the
    card). st.container's own `key=` becomes an "st-key-{key}" class on its
    wrapper div; [class*=...] substring-matches that regardless of the
    exact prefix, same trick render_stats_toolbar() uses.

    ``top``/``right`` default to the Time Series legend title's measured
    position (via getBoundingClientRect() against its chart_card, at
    Plotly's default chart height with a 2-station legend -- Plotly's own
    legend title has no DOM id to anchor to more precisely, and it isn't
    responsive to card width since Plotly's own margins are fixed pixels,
    but it *does* drift vertically as more stations are added and the
    legend grows taller, or if a caller's own "Station" text sits
    somewhere else entirely (e.g. clustering's x-axis title) -- callers
    with a different chart shape should pass their own measured offsets.

    Purely a pointer, not the explanation itself: hovering shows a one-line
    summary (native browser tooltip via the `title` attribute), and
    clicking jumps to the full per-station breakdown that
    render_missing_stations_notice() renders below the chart -- the two
    share ``anchor_id`` so the link lands exactly on that notice."""
    if not missing:
        return
    station_word = "station" if len(missing) == 1 else "stations"
    tooltip = f"Data points not available for {len(missing)} selected {station_word} -- click for details"
    st.markdown(
        f'<style>[class*="{card_key}"] {{ position: relative; }}</style>'
        f'<a href="#{anchor_id}" title="{tooltip}" '
        f'style="position:absolute; top:{top}; right:{right}; z-index:5; '
        f'text-decoration:none; font-size:12px; line-height:1;" '
        f'aria-label="warning">⚠️</a>',
        unsafe_allow_html=True,
    )


def render_missing_stations_notice(missing: list[dict[str, str]], anchor_id: str | None = None) -> None:
    """Render the per-station explanations from find_stations_missing_data()
    as a single warning banner, or nothing if every selected station has
    data. One banner listing every excluded station rather than one banner
    each, so N missing stations don't stack N warnings.

    ``anchor_id`` (shared with the render_missing_stations_indicator() call
    inside the chart above) drops an empty anchor element right before the
    banner, with a little scroll-margin so it doesn't land flush under
    Streamlit's fixed top toolbar, purely so that indicator's "click for
    details" link has somewhere to land."""
    if not missing:
        return
    if anchor_id:
        st.markdown(f'<div id="{anchor_id}" style="scroll-margin-top:80px;"></div>', unsafe_allow_html=True)
    lines = "\n".join(f"- **{station['station_name']}**: {station['reason']}" for station in missing)
    station_word = "station" if len(missing) == 1 else "stations"
    st.warning(f"Not shown -- no data for {len(missing)} selected {station_word}:\n{lines}")
