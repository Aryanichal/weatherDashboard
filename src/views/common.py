"""Widgets shared across more than one tab view."""

import pandas as pd
import streamlit as st

from src.analysis import categorize_parameter, compute_parameter_stats
from src.ui_theme import ACCENT_HEX_BY_CATEGORY


def pretty_name(parameter: str) -> str:
    """Turn a raw snake_case parameter/column name (e.g. "cloud_cover_total",
    as it comes straight from wetterdienst's DWD data) into a display string
    with spaces and each word capitalized ("Cloud Cover Total").

    str.capitalize() rather than str.title() per word: title() would also
    force a unit suffix like the "2m" in "temperature_air_mean_2m" to
    "2M", which reads as a typo -- capitalize() only touches the first
    character, and a leading digit is left as-is, so "2m" stays "2m"."""
    return " ".join(word.capitalize() for word in parameter.split("_"))


def _format_stat(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    return f"{value:.2f} {unit}".strip()


def _format_total(value: int | float, unit: str) -> str:
    return f"{value:,.0f} {unit}".strip()


def render_section_label(text: str) -> None:
    """Render a small section-heading label in the M3 "Title Medium" scale
    (16px/600 weight/0.15px tracking) and this app's accent-blue.

    Used above every dropdown/data callout in a tab -- "Parameter",
    "Key Figures:", "Station", "Slope" -- so they all read as one type
    scale and spacing rhythm instead of each widget/st.write() drifting to
    its own default size and color."""
    st.markdown(
        f'<p style="font-size:16px;font-weight:600;letter-spacing:0.15px;'
        f'color:color-mix(in srgb, var(--m3-primary, #4D77CB) 85%, transparent);'
        f'margin:0 0 0.5rem 0;">{text}</p>',
        unsafe_allow_html=True,
    )


def render_stats_toolbar(subset: pd.DataFrame, parameter: str, key_prefix: str) -> None:
    """Render a min/mean/max/mode/total "toolbar" row for one parameter's
    already-filtered data, as five separate chart_card()-style boxes rather
    than one box holding five metrics.

    Dynamic by construction: it's driven entirely by whatever ``subset``/
    ``parameter`` the caller's own "Parameter" dropdown currently has
    selected, so switching that dropdown recomputes and re-renders this on
    the very next Streamlit rerun -- there's no separate state to keep in
    sync, because there's nothing fixed to go stale. See
    compute_parameter_stats() in src/analysis.py for what "total" means
    for a given parameter (it isn't always a sum).

    The 1st/3rd/5th boxes (Min, Max, Total) get the "stat-accent" marker
    class -- solid background, white text -- while the 2nd/4th (Mean, Mode)
    get "stat-plain" and keep the white chart-card look with tinted text;
    see the "[class*=...]" rules in ui_theme.py for the category-independent
    structure (padding, font size, white text on accent) each class
    triggers. The *color* itself follows the same app-wide "active theme"
    parameter as apply_dynamic_theme() in src/ui_theme.py (whichever tab's
    "Parameter" dropdown was most recently changed) rather than this call's
    own ``parameter`` -- otherwise switching to a tab whose own dropdown
    still sits on its old value would show a stale color that visibly
    disagreed with the now-recolored background/sidebar/etc. The values
    (min/mean/max/...) still come from ``parameter``/``subset`` as always;
    only the box *color* is shared app-wide. It's injected below as a
    <style> block scoped to this call's own ``key_prefix``, since all tabs'
    bodies run in the same Streamlit script pass (st.tabs only hides the
    other panels in the DOM, it doesn't skip rendering them) and a global
    `:root` color variable would leak whichever tab rendered last into
    every other tab. ``key_prefix`` must be unique per calling tab
    (Streamlit requires unique widget/container keys app-wide) -- callers
    pass their own selectbox key, which is already unique per tab."""
    stats = compute_parameter_stats(subset, parameter)
    unit = stats["unit"]
    label = pretty_name(parameter)
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


def render_parameter_and_subset(raw: pd.DataFrame, key: str, show_stats: bool = True) -> tuple[str, pd.DataFrame]:
    """Render a "Parameter" selectbox scoped to one tab and filter ``raw`` to it.

    The label is drawn manually (M3 "Title Medium" scale -- same 16px/600/
    0.15px-tracking/0.5rem-margin treatment as "Key Figures:" in
    render_stats_toolbar(), so the two section labels in this column read
    as one consistent scale rather than two different sizes) rather than
    left as the selectbox's own native label -- CSS alone can't target just
    this widget's label by text content, and this app has other selectboxes
    (e.g. "Forecast city") that shouldn't also pick up this styling as a
    side effect. The color matches the app's accent-blue used everywhere
    else (WeatheRe brand text, "Key Figures:", tab-selected color).
    label_visibility="collapsed" removes the selectbox's own label and its
    reserved space entirely so it isn't duplicated underneath.

    ``show_stats`` renders render_stats_toolbar() directly below the
    dropdown, above whatever chart the caller builds from the returned
    subset -- on by default, since every current caller wants it; the
    escape hatch exists for a future tab that doesn't.

    This is also the single place that feeds app.py's app-wide dynamic
    theme (see apply_dynamic_theme() in src/ui_theme.py): every tab has
    its own independent "Parameter" dropdown, so there's no one "current"
    parameter to theme the whole page on -- instead, whichever dropdown's
    value actually *changed* since its own last render is recorded as
    st.session_state["active_theme_parameter"], so the background/sidebar/
    etc. follow whichever one the user most recently touched, regardless
    of which tab it's in."""
    render_section_label("Parameter")
    parameter = st.selectbox(
        "Parameter",
        sorted(raw["parameter"].unique()),
        key=key,
        label_visibility="collapsed",
        # format_func only changes what's *displayed* for each option --
        # the value this function returns (and everything downstream that
        # filters `raw` on it) is still the raw snake_case parameter name,
        # so callers don't need their own pretty_name() lookup just to
        # re-derive which rows to filter.
        format_func=pretty_name,
    )
    prev_value_key = f"_theme_prev_{key}"
    if st.session_state.get(prev_value_key) != parameter:
        st.session_state["active_theme_parameter"] = parameter
    st.session_state[prev_value_key] = parameter

    subset = raw[raw["parameter"] == parameter].dropna(subset=["value"])
    if show_stats:
        render_stats_toolbar(subset, parameter, key_prefix=key)
    return parameter, subset
