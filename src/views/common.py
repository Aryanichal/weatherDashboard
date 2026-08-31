"""Widgets shared across more than one tab view."""

import datetime as dt
from collections.abc import Callable

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
from src.ui_theme import ACCENT_HEX_BY_CATEGORY, chart_card

# Every chart-bearing view (Time Series, Map, Regression, Clustering)
# shares this same chart/Key-Figures row split -- 72% chart, 28% Key
# Figures box -- so the ratio lives here once rather than being repeated
# (and drifting) per view.
CHART_ROW_WIDTH_RATIO = [0.72, 0.28]


def pretty_name(parameter: str) -> str:
    """"cloud_cover_total" -> "Cloud Cover Total". Composite keys that
    don't read cleanly through this generic snake_case split (e.g.
    "humidity_pressure_vapor") should instead set an explicit "label" in
    their COMPOSITE_PARAMETER_GROUPS entry -- see _dropdown_label()."""
    return " ".join(word.capitalize() for word in parameter.split("_"))


def _dropdown_label(value: str) -> str:
    """Display text for one "Parameter" dropdown option. Composite keys
    use their group's explicit "label" when present (see
    COMPOSITE_PARAMETER_GROUPS in src/analysis.py); everything else
    (real DWD parameters, and composites without a custom label) falls
    back to pretty_name()."""
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
    """``style="label"`` (default) is for form-field labels above an input
    ("Location", "Parameter", "Weather stations", ...). ``style="header"``
    is for an actual section heading introducing a chart/card below it
    ("Key Figures:", "10-Day Forecast", "Next 48 hours", ...) -- these are
    two different roles that, now that the top-level nav's own type size
    grew substantially (see app.py), need visibly different weight rather
    than the one size both used before.

    Same token the Live Weather hero's city name uses (see
    _render_current() in src/views/live_weather.py) -- previously this
    read --m3-primary instead, which desaturates to a visibly lighter
    grey than --m3-on-primary-container under the "neutral" theme
    (#8C8C8C vs #444444), so section titles and that text didn't match.
    """
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
    spanning the full row across ``option_count`` equal columns, a shared
    sliding underline indicator (one bar that slides between columns, not
    one per-button), and a lift+color hover affordance on the inactive
    options. Originally built one-off for the top-level Live Weather/
    Weather Analysis switch in app.py; pulled out here so the "Weather
    Analysis" sub-nav (Time Series/Map/Regression/Clustering/Discover
    Global Warming) can share the exact same look instead of keeping its
    default pill-button skin the top-level switch moved away from.

    The two buttons in the original version were siblings inside one
    wrapper <div> (stButtonGroup's own direct children are [label, that
    div] -- confirmed by inspecting the live DOM), so the sliding
    indicator lives on *that* div via ::after, not on stButtonGroup or any
    one button -- one shared bar sliding across on `aria-checked`, not N
    independent per-button underlines. A faint 1px rail runs the full
    width under every option (visible under inactive ones too), with the
    shorter, thicker, colored indicator layered on top of just the active
    column.

    The indicator keeps the original design's proportions (34% of a 50%
    column, i.e. 68% of its own column's width, centered) rather than a
    fixed absolute width, so it scales down sensibly as ``option_count``
    grows and each column gets narrower -- one rule per column overrides
    `left` for whichever button currently carries `aria-checked="true"`.

    The scoped selectors below each add one extra ancestor attribute
    selector versus the global stButtonGroup rules in _BASE_CSS, so they
    out-specificity those rules (three attribute selectors vs. two)
    without needing an "!important + later source order" trick -- this
    one just wins outright.
    """
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
        # The default button rule elsewhere in this file fixes height at
        # 32px with overflow: hidden (sized for its 1rem font) -- at a
        # bigger font-size that clips the text top and bottom. Letting the
        # box size to its own content instead of that fixed height fixes it.
        f"height: auto !important; min-height: 0 !important; overflow: visible !important; "
        f"line-height: 1.25 !important; "
        f"flex: 1 1 {column_pct:.3f}% !important; justify-content: center !important; "
        f"font-size: {font_size} !important; font-weight: 700 !important; letter-spacing: 0.02em; "
        f"padding: 0.5rem 0.5rem 0.9rem !important; "
        f"color: color-mix(in srgb, var(--m3-on-primary-container, #1E4469) 50%, transparent) !important; "
        f"transition: color 0.15s ease, transform 0.15s ease; "
        f"}}"
        # Hover affordance on the unselected options only -- a small lift
        # plus their full active-state color, so they visibly invite a
        # click without touching the already-active option (which doesn't
        # need one).
        f'[class*="{key}"] [data-testid="stButtonGroup"] button:not([aria-checked="true"]):hover {{ '
        f"color: var(--m3-on-primary-container, #1E4469) !important; "
        f"transform: translateY(-3px); "
        f"}}"
        # The button's text sits inside a [data-testid="stMarkdownContainer"]
        # > <p> that carries its own fixed 14px rule elsewhere -- the
        # existing "font-size: inherit" trick on button-p (see _BASE_CSS)
        # inherits from that div, not from the button several levels up, so
        # it never picks up the size above without this.
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
    """Min/mean/max/mode/total for one parameter's filtered data, combined
    into a single vertically-stacked box (one bordered card, one row per
    stat) rather than five separate metric cards spanning the full row --
    sized to sit in the narrow leftover column next to its own chart (see
    CHART_ROW_WIDTH_RATIO above, and the ``render_key_figures`` callable
    render_parameter_and_subset() returns below) instead of stretching
    full-width above it.

    ``chart_height`` should be whatever pixel height the chart sitting
    next to this box was given (``fig.update_layout(height=...)``; 450 is
    Plotly's own default when a caller never sets one, e.g. Map/
    Regression/Clustering's charts) -- this box's own CSS height is set to
    match it (plus chart_card()'s own padding/border) directly, in
    pixels, rather than via a `height: 100%` percentage chain. The
    percentage approach doesn't work here: a percentage height only
    resolves against a parent with a *definite* (non-auto) height, and
    Streamlit's own bordered-container wrapper is itself auto-sized to
    its content, so `height: 100%` on it (or on anything inside it)
    silently collapses back to "auto" per the CSS spec, regardless of how
    tall the column around it has stretched. An explicit pixel height
    sidesteps that chain entirely.

    ``stats``, when provided, is used as-is instead of being computed from
    ``subset``/``parameter`` via compute_parameter_stats() -- this is how
    a composite with its own stats function (e.g. compute_temperature_stats
    in src/analysis.py) supplies numbers that don't all come from one
    series. Unlike the old five-card layout, each row's label no longer
    needs to repeat the parameter's own name (there's already one "Key
    Figures:" header above the whole box), so this no longer takes a
    ``display_label`` override either -- ``parameter`` only ever affects
    the accent color lookup now.
    """
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
    # No per-row background (an alternating accent tint was tried and
    # then explicitly reverted) -- every row reads the same: a muted
    # default-ink label, an accent-colored bold value, both directly on
    # the card's own plain background.
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
    # An explicit pixel height, matched to the chart sitting next to this
    # box (chart_height + chart_card()'s own ~24px top/bottom padding +
    # ~1px border each side, see _BASE_CSS in src/ui_theme.py) -- not
    # `height: 100%`. A percentage height only resolves against a parent
    # with a *definite* (non-auto) height, and Streamlit's own bordered-
    # container wrapper is itself auto-sized to its content, so
    # `height: 100%` here silently collapses back to "auto" per the CSS
    # spec regardless of how tall the column around it has stretched --
    # this sidesteps that chain entirely by not depending on it.
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

    ``render_key_figures`` is a callable taking one optional ``chart_height``
    argument (or ``None`` if ``show_stats=False``, or the composite is
    "stats_parameters"-shaped -- see below) that renders the combined Key
    Figures box (see render_key_figures_box()) when called -- it is *not*
    rendered here. Callers are expected to call it themselves inside
    whichever column should hold it, typically the narrow leftover column
    next to this view's own chart (``chart_col, stats_col = st.columns(CHART_ROW_WIDTH_RATIO)``,
    then ``with stats_col: render_key_figures(chart_height)`` once the chart
    itself is known) rather than a full-width block above the chart --
    this used to render inline, full-width, right here, before Key
    Figures moved next to its chart instead of above it. Pass the same
    pixel height the paired chart was given
    (``fig.update_layout(height=...)``) so the box matches it -- see
    render_key_figures_box()'s own docstring for why that's a plain
    argument instead of something this function could work out on its own.

    ``collapse_composites`` replaces each group's component parameters
    (see COMPOSITE_PARAMETER_GROUPS in src/analysis.py) with one grouped
    dropdown entry. When a composite is selected, ``parameter`` is that
    composite's synthetic key and ``subset`` contains every one of its
    components' rows; what ``render_key_figures`` is set to depends on
    which shape the group uses:

      - "stats_fn": one merged box, via the group's own function
        (currently just "Temperature", via compute_temperature_stats()).
      - "stats_parameters": left ``None`` -- the caller is expected to call
        render_key_figures_box() itself, once per component, since a
        fixed single box doesn't fit every composite's presentation (e.g.
        Humidity and Pressure Vapor wants each component's own box sitting
        next to its own chart, not one merged box for both).
      - neither (just "primary"): the default -- one box off that single
        parameter, labeled with the composite's own name.

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
    Map keeps showing max temperature there too. Every other composite has
    no toggle, so it's always that group's "primary" parameter (falling
    back to its first component for a "stats_parameters"-shaped group like
    Humidity and Pressure Vapor, which has no single obvious "primary" --
    see the effective_parameter assignment below) -- e.g. Precipitation's
    other component, precipitation_form, is a category code, not a
    continuous quantity, so there's no meaningful single number to reduce
    it to outside Time Series' own dedicated monthly-breakdown chart. Only
    Time Series itself needs the full ``parameter``/``subset`` -- its
    composite views render every component at once rather than reducing
    to one.

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
        format_func=_dropdown_label,
    )

    if parameter in COMPOSITE_PARAMETER_GROUPS:
        group_for_canonical = COMPOSITE_PARAMETER_GROUPS[parameter]
        canonical_parameter = group_for_canonical.get("primary", group_for_canonical["components"][0])
    else:
        canonical_parameter = parameter
    st.session_state[_SHARED_PARAMETER_KEY] = canonical_parameter

    # Unconditional, not "only when parameter changed since this view's own
    # last render": app.py only ever runs one view's render() per script
    # pass (see its module docstring), so a change-only update left this
    # stale whenever a *different* view ran in between and overwrote
    # "active_theme_parameter" itself (Live Weather does this every render,
    # via its own current conditions -- see live_weather.py) -- switching
    # back to this view without touching its dropdown then kept whatever
    # theme that other view last set, instead of reasserting this view's
    # own current parameter's theme.
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
            # Not every composite has a "primary" -- a "stats_parameters"
            # group like Humidity and Pressure Vapor has two co-equal
            # components instead of one designated representative, so
            # fall back to the first of them.
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
    exact prefix, same trick render_key_figures_box() uses.

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
