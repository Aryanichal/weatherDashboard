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
    series.

    ``display_label`` overrides the card titles (used when the cards
    should read a composite's own name rather than ``parameter``'s name).
    Left as ``None``, the cards read ``parameter``'s own pretty name --
    which is what render_parameter_and_subset() below wants for the
    "stats_parameters" case, where each block should stay labeled with
    its own real parameter, not the composite it's grouped under.
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
    contains every one of its components' rows; how Key Figures renders
    underneath depends on which of three shapes the group uses:

      - "stats_fn": one merged 5-card block, computed by the group's own
        function (e.g. Temperature, which needs min/max sourced from
        different series than mean/mode -- see compute_temperature_stats).
      - "stats_parameters": one complete, independently-labeled 5-card
        block per parameter listed (e.g. Humidity and Pressure Vapor,
        where collapsing to a single block would lose one of the two
        readings rather than clarify anything).
      - neither (just "primary"): the default -- one 5-card block off
        that single parameter, labeled with the composite's own name
        (e.g. Precipitation, Wind).
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
        format_func=_dropdown_label,
    )
    prev_value_key = f"_theme_prev_{key}"
    if st.session_state.get(prev_value_key) != parameter:
        st.session_state["active_theme_parameter"] = parameter
    st.session_state[prev_value_key] = parameter

    if parameter in COMPOSITE_PARAMETER_GROUPS:
        group = COMPOSITE_PARAMETER_GROUPS[parameter]
        subset = raw[raw["parameter"].isin(group["components"])].dropna(subset=["value"])
        # Composites with "stats_parameters" (e.g. Humidity and Pressure
        # Vapor) render nothing here -- the caller is expected to call
        # render_stats_toolbar() itself, once per component, interleaved
        # with that component's own chart, since a fixed "all cards then
        # all charts" order doesn't fit every composite's presentation.
        if show_stats and "stats_parameters" not in group:
            if "stats_fn" in group:
                render_stats_toolbar(
                    subset, group["primary"], key_prefix=key,
                    display_label=_dropdown_label(parameter), stats=group["stats_fn"](subset),
                )
            else:
                stats_subset = raw[raw["parameter"] == group["primary"]].dropna(subset=["value"])
                render_stats_toolbar(
                    stats_subset, group["primary"], key_prefix=key, display_label=_dropdown_label(parameter)
                )
    else:
        subset = raw[raw["parameter"] == parameter].dropna(subset=["value"])
        if show_stats:
            render_stats_toolbar(subset, parameter, key_prefix=key)

    return parameter, subset