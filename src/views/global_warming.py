"""Discover Global Warming tab: "Global Warming Trend" (user-adjustable
settings) and "Future Prediction" (model forecasts, independent of the
trend tab's settings)."""

import calendar
import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st
from src.ui_theme import chart_card, render_chart
from src.dashboard_context import DashboardContext

from src.data_loader import (
    ANOMALY_BASELINE_END_YEAR,
    ANOMALY_BASELINE_START_YEAR,
    TREND_START_YEAR,
    WeatherDataFetchError,
    load_climate_change_indicators,
    load_hot_days_data,
    load_long_run_data,
    load_station_metadata,
)

from src.forecasting import (
    FORECAST_CACHE_VERSION,
    HOT_DAYS_INDICATOR,
    JULY_TEMPERATURE_INDICATOR,
    PYTORCH_MODEL_NAME,
    RAINY_DAYS_INDICATOR,
    load_forecasts,
)



def _warn_about_missing_coverage(
    city_stations: dict[str, str],
    climate_indicators: pd.DataFrame,
    long_run_data: pd.DataFrame,
    hot_days_data: pd.DataFrame,
) -> None:
    """Warn per city about any chart that will render empty for it.

    Some DWD stations only report a subset of parameters, so a chart can
    otherwise render blank with no explanation.
    """
    for city in city_stations:
        missing: list[str] = []
        city_indicators = climate_indicators.loc[climate_indicators["city"] == city]

        if city_indicators["annual_mean_temp"].notna().sum() == 0:
            missing.append("mean temperature (Global Warming Trend chart)")
        if city_indicators["hot_nights"].notna().sum() == 0:
            missing.append("overnight minimum temperature (Hot Nights chart)")
        if city_indicators["heavy_rain_days"].notna().sum() == 0:
            missing.append("precipitation (Heavy-Rain Days chart)")
        if city not in set(long_run_data["city"]):
            missing.append("a monthly average temperature (Average Temperature chart)")
        city_hot_days = hot_days_data.loc[hot_days_data["city"] == city]
        if city_hot_days["days_above_threshold"].notna().sum() == 0:
            missing.append("daytime maximum temperature (Hot Days chart)")

        if missing:
            st.warning(
                f"**{city}**'s station doesn't report: {', '.join(missing)}. "
                "That's a gap in what this specific DWD station measures "
                "(e.g. a wind-only airfield station) not a bug so its line "
                "will be missing from those charts."
            )


def _render_future_forecast(
    city: str,
    indicator: str,
    y_label: str,
    title: str,
    forecasts: pd.DataFrame,
    metrics: pd.DataFrame,
    history: pd.DataFrame,
) -> None:
    """Render one observed series plus both model forecasts for a city."""
    city_history = history.loc[(history["city"] == city) & (history["indicator"] == indicator)]
    city_forecasts = forecasts.loc[(forecasts["city"] == city) & (forecasts["indicator"] == indicator)]
    city_metrics = metrics.loc[(metrics["city"] == city) & (metrics["indicator"] == indicator)].copy()
    if city_history.empty or city_forecasts.empty or city_metrics.empty:
        st.info(f"No forecast data is currently available for {indicator.lower()} in {city}.")
        return
    forecast_fig = px.line(
        city_history,
        x="year",
        y="observed_value",
        markers=True,
        labels={"year": "Year", "observed_value": y_label},
        title=title,
    )
    forecast_fig.update_traces(name="Observed", line={"color": "#1f77b4"})
    model_colours = {"Linear trend": "#d62728", PYTORCH_MODEL_NAME: "#2ca02c"}
    for model_name, model_data in city_forecasts.groupby("model", sort=False):
        model_data = model_data.sort_values("year")
        colour = model_colours.get(model_name, "#444444")
        rgb = ",".join(str(int(colour[index:index + 2], 16)) for index in (1, 3, 5))
        forecast_fig.add_scatter(
            x=model_data["year"], y=model_data["upper_80"], mode="lines",
            line={"width": 0, "color": colour}, showlegend=False, hoverinfo="skip",
        )
        forecast_fig.add_scatter(
            x=model_data["year"], y=model_data["lower_80"], mode="lines",
            line={"width": 0, "color": colour}, fill="tonexty",
            fillcolor=f"rgba({rgb},0.12)", name=f"{model_name} 80% interval", legendgroup=model_name,
        )
        forecast_fig.add_scatter(
            x=model_data["year"], y=model_data["predicted_value"], mode="lines+markers",
            line={"color": colour, "dash": "dash"}, name=f"{model_name} forecast", legendgroup=model_name,
        )
    with chart_card():
        render_chart(forecast_fig)

    unit = city_metrics["unit"].iloc[0]
    city_metrics[f"MAE ({unit})"] = city_metrics["mae"].map("{:.2f}".format)
    city_metrics[f"RMSE ({unit})"] = city_metrics["rmse"].map("{:.2f}".format)
    with chart_card():
        st.dataframe(
            city_metrics[["model", "test_start_year", "test_end_year", f"MAE ({unit})", f"RMSE ({unit})"]].rename(
                columns={"model": "Model", "test_start_year": "Test start", "test_end_year": "Test end"}
            ),
            hide_index=True,
            width="stretch",
        )


def render(ctx: DashboardContext) -> None:
    trend_tab, prediction_tab = st.tabs(["Global Warming Trend", "Future Prediction"])
    with trend_tab:
        _render_trend_tab(ctx)
    with prediction_tab:
        _render_prediction_tab()


def _render_trend_tab(ctx: DashboardContext) -> None:
    city_stations = {name: ctx.id_by_name[name] for name in ctx.selected_names}
    current_year = dt.date.today().year

    # Bound year controls by the latest start date among selected stations;
    # an earlier baseline silently drops that city's anomaly as NaN.
    station_metadata = load_station_metadata(list(city_stations.values()))
    earliest_common_year = pd.to_datetime(station_metadata["start_date"]).dt.year.max()
    min_selectable_year = int(earliest_common_year) if pd.notna(earliest_common_year) else TREND_START_YEAR

    with st.expander("Global warming trend settings"):
        st.caption(
            f"Earliest year with data for every selected station: {min_selectable_year} "
            f"(limited by whichever selected station's records start latest)."
        )
        gw_start_year = st.number_input(
            "Trend start year", min_value=min_selectable_year, max_value=current_year,
            value=max(TREND_START_YEAR, min_selectable_year),
        )
        gw_baseline_start_year, gw_baseline_end_year = st.slider(
            "Anomaly baseline period",
            min_value=min_selectable_year, max_value=current_year,
            value=(
                max(ANOMALY_BASELINE_START_YEAR, min_selectable_year),
                max(ANOMALY_BASELINE_END_YEAR, min_selectable_year),
            ),
            help=(
                "The 'normal' reference period each year is compared against. "
                "Every year's temperature anomaly = that year's average temperature "
                "minus the average temperature over this baseline period. It doesn't "
                "change the underlying data, only where the chart's zero line sits."
                "e.g. an older, cooler baseline makes recent years look more anomalous, "
                "while a recent baseline makes them look closer to normal. "
                "1991–2020 is the current WMO standard 30-year climate normal."
            ),
        )
        gw_month = st.selectbox(
            "Month to average for the 'Average Temperature' chart",
            options=list(range(1, 13)),
            index=6,
            format_func=lambda m: calendar.month_name[m],
        )
        gw_hot_day_threshold = st.number_input("Hot day threshold (°C)", value=30.0, step=1.0)
        gw_hot_night_threshold = st.number_input("Hot night threshold (°C)", value=20.0, step=1.0)
        gw_heavy_rain_threshold = st.number_input("Heavy-rain threshold (mm)", value=20.0, step=1.0)

    try:
        climate_indicators = load_climate_change_indicators(
            city_stations,
            gw_start_year,
            gw_baseline_start_year,
            gw_baseline_end_year,
            gw_hot_night_threshold,
            gw_heavy_rain_threshold,
        )
        long_run_data = load_long_run_data(city_stations, gw_start_year, gw_month)
        hot_days_data = load_hot_days_data(city_stations, gw_start_year, gw_hot_day_threshold)
    except WeatherDataFetchError as exc:
        st.error(f"Couldn't load weather data: {exc}")
        return
    _warn_about_missing_coverage(city_stations, climate_indicators, long_run_data, hot_days_data)

    month_name = calendar.month_name[gw_month]
    temp_missing = climate_indicators["annual_mean_temp"].notna().sum() == 0
    hot_nights_missing = climate_indicators["hot_nights"].notna().sum() == 0
    heavy_rain_missing = climate_indicators["heavy_rain_days"].notna().sum() == 0
    long_run_missing = long_run_data.empty
    hot_days_missing = hot_days_data["days_above_threshold"].notna().sum() == 0

    if temp_missing and hot_nights_missing and heavy_rain_missing and long_run_missing and hot_days_missing:
        st.error("No temperature or precipitation data is available for the selected station.")
        return

    if temp_missing:
        st.info("No mean temperature data is available for the selected station.")
    else:
        anomaly_plot_data = climate_indicators.melt(
            id_vars=["city", "year"],
            value_vars=["temperature_anomaly", "temperature_anomaly_5y"],
            var_name="series",
            value_name="temperature_anomaly_c",
        )
        anomaly_plot_data["series"] = anomaly_plot_data["series"].map(
            {
                "temperature_anomaly": "Annual anomaly",
                "temperature_anomaly_5y": "5-year rolling mean",
            }
        )
        anomaly_fig = px.line(
            anomaly_plot_data,
            x="year",
            y="temperature_anomaly_c",
            color="city",
            line_dash="series",
            labels={
                "year": "Year",
                "temperature_anomaly_c": f"Temperature anomaly (°C, vs. {gw_baseline_start_year}–{gw_baseline_end_year})",
                "city": "City",
                "series": "Series",
            },
            title="Global Warming Trend",
        )
        with chart_card():
            render_chart(anomaly_fig)
            st.caption(
                f"Anomalies are relative to each city's {gw_baseline_start_year}–{gw_baseline_end_year} "
                f"annual-mean-temperature baseline; {current_year} values are year-to-date."
            )

    hot_nights_col, heavy_rain_col = st.columns(2)
    with hot_nights_col:
        if hot_nights_missing:
            st.info("No overnight temperature data is available for any selected station.")
        else:
            hot_nights_fig = px.line(
                climate_indicators,
                x="year",
                y="hot_nights",
                color="city",
                markers=True,
                labels={
                    "year": "Year",
                    "hot_nights": f"Hot nights above {gw_hot_night_threshold:g} °C",
                    "city": "City",
                },
                title="Hot Nights",
                )
            with chart_card():
                render_chart(hot_nights_fig)
    with heavy_rain_col:
        if heavy_rain_missing:
            st.info("No precipitation data is available for any selected station.")
        else:
            heavy_rain_fig = px.line(
                climate_indicators,
                x="year",
                y="heavy_rain_days",
                color="city",
                markers=True,
                labels={
                    "year": "Year",
                    "heavy_rain_days": f"Days above {gw_heavy_rain_threshold:g} mm",
                    "city": "City",
                },
                title="Heavy-Rain Days",
                )
            with chart_card():
                render_chart(heavy_rain_fig)

    if long_run_missing:
        st.info(f"No {month_name} temperature data is available for any selected station.")
    else:
        temperature_fig = px.line(
            long_run_data,
            x="year",
            y="observed_temp",
            color="city",
            markers=True,
            labels={"year": "Year", "observed_temp": f"Average {month_name} temperature (°C)", "city": "City"},
            title=f"Average {month_name} Temperature",
        )
        with chart_card():
            render_chart(temperature_fig)

    if hot_days_missing:
        st.info("No daytime maximum temperature data is available for any selected station.")
    else:
        hot_days_fig = px.line(
            hot_days_data,
            x="year",
            y="days_above_threshold",
            color="city",
            markers=True,
            labels={
                "year": "Year",
                "days_above_threshold": f"Days above {gw_hot_day_threshold:g} °C",
                "city": "City",
            },
            title=f"Hot Days Above {gw_hot_day_threshold:g} °C",
        )
        with chart_card():
            render_chart(hot_days_fig)
            st.caption("The current year's hot-day count is year-to-date.")


def _render_prediction_tab() -> None:
    st.caption(
        "The models forecast annual hot-day counts, average July temperatures, and rainy-day counts rather than the weather in a specific year. "
        "The partial current year is excluded from model fitting."
    )
    try:
        forecasts, forecast_metrics, forecast_history = load_forecasts(FORECAST_CACHE_VERSION)
    except (ValueError, KeyError, WeatherDataFetchError) as error:
        st.error(f"Unable to prepare the future-trend forecast: {error}")
        return

    forecast_city = st.selectbox(
        "Forecast city",
        options=sorted(forecasts["city"].unique()),
        key="future_trend_city",
    )
    _render_future_forecast(
        forecast_city, HOT_DAYS_INDICATOR, "Days above 30 °C",
        f"{forecast_city}: Hot Days Above 30 °C Forecast", forecasts, forecast_metrics, forecast_history,
    )
    st.subheader("Average July Temperature Future Prediction")
    _render_future_forecast(
        forecast_city, JULY_TEMPERATURE_INDICATOR, "Average July temperature (°C)",
        f"{forecast_city}: Average July Temperature Forecast", forecasts, forecast_metrics, forecast_history,
    )
    st.subheader("Rainy Days Future Prediction")
    _render_future_forecast(
        forecast_city, RAINY_DAYS_INDICATOR, "Rainy days above 1 mm",
        f"{forecast_city}: Rainy Days Above 1 mm Forecast", forecasts, forecast_metrics, forecast_history,
    )
