"""Widgets shared across more than one tab view."""

import pandas as pd
import streamlit as st

# Since each tab keeps its own independent "Parameter" selectbox, this is the
# single shared key that tracks whichever one the user most recently touched
# -- that's what drives the animated background (see src/ui_theme.py).
ACTIVE_PARAMETER_KEY = "active_weather_parameter"


def render_parameter_and_subset(raw: pd.DataFrame, key: str) -> tuple[str, pd.DataFrame]:
    """Render a "Parameter" selectbox scoped to one tab and filter ``raw`` to it."""

    def _update_active_parameter() -> None:
        st.session_state[ACTIVE_PARAMETER_KEY] = st.session_state[key]

    parameter = st.selectbox(
        "Parameter", sorted(raw["parameter"].unique()), key=key, on_change=_update_active_parameter,
    )
    subset = raw[raw["parameter"] == parameter].dropna(subset=["value"])
    return parameter, subset
