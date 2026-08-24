"""Widgets shared across more than one tab view."""

import pandas as pd
import streamlit as st


def render_parameter_and_subset(raw: pd.DataFrame, key: str) -> tuple[str, pd.DataFrame]:
    """Render a "Parameter" selectbox scoped to one tab and filter ``raw`` to it."""
    parameter = st.selectbox("Parameter", sorted(raw["parameter"].unique()), key=key)
    subset = raw[raw["parameter"] == parameter].dropna(subset=["value"])
    return parameter, subset
