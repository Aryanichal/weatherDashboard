"""Widgets shared across more than one tab view."""

import pandas as pd
import streamlit as st


def pretty_name(parameter: str) -> str:
    """Turn a raw snake_case parameter/column name (e.g. "cloud_cover_total",
    as it comes straight from wetterdienst's DWD data) into a display string
    with spaces and each word capitalized ("Cloud Cover Total").

    str.capitalize() rather than str.title() per word: title() would also
    force a unit suffix like the "2m" in "temperature_air_mean_2m" to
    "2M", which reads as a typo -- capitalize() only touches the first
    character, and a leading digit is left as-is, so "2m" stays "2m"."""
    return " ".join(word.capitalize() for word in parameter.split("_"))


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
        # format_func only changes what's *displayed* for each option --
        # the value this function returns (and everything downstream that
        # filters `raw` on it) is still the raw snake_case parameter name,
        # so callers don't need their own pretty_name() lookup just to
        # re-derive which rows to filter.
        format_func=pretty_name,
    )
    subset = raw[raw["parameter"] == parameter].dropna(subset=["value"])
    return parameter, subset
