"""Widgets shared across more than one tab view."""

import pandas as pd
import streamlit as st


def render_parameter_and_subset(raw: pd.DataFrame, key: str) -> tuple[str, pd.DataFrame]:
    """Render a "Parameter" selectbox scoped to one tab and filter ``raw`` to it.

    The label is drawn manually (font-weight 600, semi-bold) rather than
    left as the selectbox's own native label -- CSS alone can't target just
    this widget's label by text content, and this app has other selectboxes
    (e.g. "Forecast city") that shouldn't also turn semi-bold as a side
    effect. The other inline style values (14px/#212529, 4px gap) are
    copied from Streamlit's own computed label style, not guessed, so it
    reads identically to a native widget label apart from the weight.
    label_visibility="collapsed" removes the selectbox's own label and its
    reserved space entirely so it isn't duplicated underneath. """
    st.markdown(
        '<p style="font-size:14px;font-weight:600;color:#212529;'
        'margin-bottom:4px;">Parameter</p>',
        unsafe_allow_html=True,
    )
    parameter = st.selectbox(
        "Parameter",
        sorted(raw["parameter"].unique()),
        key=key,
        label_visibility="collapsed",
    )
    subset = raw[raw["parameter"] == parameter].dropna(subset=["value"])
    return parameter, subset
