"""Widgets shared across more than one tab view."""

import pandas as pd
import streamlit as st

from src.analysis import (
    COMPOSITE_PARAMETER_GROUPS,
    categorize_parameter,
    compute_parameter_stats,
)
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


def render_parameter_and_subset(
    raw: pd.DataFrame, key: str, show_stats: bool = True, collapse_composites: bool = False
) -> tuple[str, pd.DataFrame]:
    """Render a "Parameter" selectbox scoped to one tab and filter ``raw`` to it.

    ``collapse_composites`` replaces each group's component parameters
    (see COMPOSITE_PARAMETER_GROUPS in src/analysis.py) with one grouped
    dropdown entry. When a composite is selected, the returned ``subset``
    contains every one of its components' rows; the Key Figures toolbar
    underneath uses that composite's own ``stats_fn`` if it has one
    (currently just "Temperature"), otherwise falls back to the default:
    compute_parameter_stats() on just the composite's "primary" parameter.
    """
    render_section_label("Parameter")

    available_parameters = set(raw["parameter"].unique())
    options = available_parameters
    if collapse_composites:
        for composite_key, group in COMPOSITE_PARAMETER_GROUPS.items():
            components = set(group["components"])
            if available_parameters & components:
                options = (options - components) | {composite_key}

    parameter = st.selectbox(
        "Parameter",
        sorted(options),
        key=key,
        label_visibility="collapsed",
        format_func=pretty_name,
    )
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
    else:
        subset = raw[raw["parameter"] == parameter].dropna(subset=["value"])
        if show_stats:
            render_stats_toolbar(subset, parameter, key_prefix=key)

    return parameter, subset