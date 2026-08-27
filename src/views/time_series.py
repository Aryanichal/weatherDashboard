"""Time series view: a small set of fixed trend charts, no parameter dropdown."""

import altair as alt
import pandas as pd
import streamlit as st

from src.analysis import fit_trend
from src.dashboard_context import DashboardContext


def render(ctx: DashboardContext) -> None:
    top_left, top_right = st.columns(2)

    with top_left:
        st.subheader("Temperature trend")
        _render_temperature_trend(ctx.raw)

    with top_right:
        st.subheader("Daily precipitation")
        _render_daily_precipitation(ctx.raw)

    st.subheader("Temperature range (min/max)")
    _render_temperature_range(ctx.raw)

    st.subheader("Daily temperature calendar")
    _render_temperature_calendar(ctx.raw)


def _render_temperature_trend(raw: pd.DataFrame) -> None:
    mean_temp = raw.loc[raw["parameter"] == "temperature_air_mean_2m"].copy()
    mean_temp["date"] = pd.to_datetime(mean_temp["date"])
    if mean_temp.empty:
        st.info("No mean-temperature data for this selection.")
        return

    fitted_frames = []
    for _, station_data in mean_temp.groupby("station_name"):
        fitted = fit_trend(station_data, date_col="date", value_col="value")["data"].sort_values("date")
        fitted["rolling_7d"] = fitted["value"].rolling(7, min_periods=1).mean()
        fitted_frames.append(fitted)
    fitted = pd.concat(fitted_frames, ignore_index=True)

    raw_line = alt.Chart(fitted).mark_line(opacity=0.25).encode(
        x=alt.X("date:T", title="date"),
        y=alt.Y("value:Q", title="mean temperature (°C)"),
        color=alt.Color("station_name:N", title="station"),
    )
    rolling_line = alt.Chart(fitted).mark_line(strokeWidth=2.5).encode(
        x="date:T", y="rolling_7d:Q", color="station_name:N",
    )
    trend_line = alt.Chart(fitted).mark_line(strokeDash=[6, 4]).encode(
        x="date:T", y="trend:Q", color="station_name:N",
    )
    st.altair_chart(raw_line + rolling_line + trend_line, use_container_width=True)


def _render_daily_precipitation(raw: pd.DataFrame) -> None:
    precip = raw.loc[raw["parameter"] == "precipitation_height"].copy()
    precip["date"] = pd.to_datetime(precip["date"])
    if precip.empty:
        st.info("No precipitation data for this selection.")
        return

    monthly = (
        precip.set_index("date")
        .groupby("station_name")
        .resample("MS")["value"]
        .sum()
        .reset_index()
    )

    chart = alt.Chart(monthly).mark_bar().encode(
        x=alt.X("date:T", title="month"),
        xOffset="station_name:N",
        y=alt.Y("value:Q", title="precipitation (mm)"),
        color=alt.Color("station_name:N", title="station"),
        tooltip=["station_name", "date:T", "value:Q"],
    )
    st.altair_chart(chart, use_container_width=True)


def _render_temperature_range(raw: pd.DataFrame) -> None:
    daily_min = raw.loc[raw["parameter"] == "temperature_air_min_2m", ["station_name", "date", "value"]].rename(columns={"value": "temp_min"})
    daily_max = raw.loc[raw["parameter"] == "temperature_air_max_2m", ["station_name", "date", "value"]].rename(columns={"value": "temp_max"})
    temp_range = daily_min.merge(daily_max, on=["station_name", "date"])
    temp_range["date"] = pd.to_datetime(temp_range["date"])
    if temp_range.empty:
        st.info("No min/max temperature data for this selection.")
        return

    band = alt.Chart(temp_range).mark_area(opacity=0.7).encode(
        x=alt.X("date:T", title="date"),
        y=alt.Y("temp_min:Q", title="temperature (°C)"),
        y2="temp_max:Q",
        color=alt.Color("station_name:N", legend=None),
    ).properties(width=650, height=180)

    st.altair_chart(band.facet(row=alt.Row("station_name:N", title=None)))


def _render_temperature_calendar(raw: pd.DataFrame) -> None:
    mean_temp = raw.loc[raw["parameter"] == "temperature_air_mean_2m", ["station_name", "date", "value"]].dropna().copy()
    mean_temp["date"] = pd.to_datetime(mean_temp["date"])
    if mean_temp.empty:
        st.info("No mean-temperature data for this selection.")
        return

    mean_temp["week"] = mean_temp["date"].dt.isocalendar().week.astype(int)
    mean_temp["weekday"] = mean_temp["date"].dt.day_name()
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    calendar = alt.Chart(mean_temp).mark_rect().encode(
        x=alt.X("week:O", title="week of year"),
        y=alt.Y("weekday:O", title=None, sort=weekday_order),
        color=alt.Color(
            "value:Q",
            title="mean temp (°C)",
            scale=alt.Scale(scheme="redyellowblue", reverse=True),
        ),
        tooltip=["station_name", "date:T", "value:Q"],
    ).properties(width=650, height=140)

    st.altair_chart(calendar.facet(row=alt.Row("station_name:N", title=None)))