"""Simple on-demand analysis tools applied to a selection of weather data.

Kept intentionally minimal: a linear trend fit and a KMeans clustering of
stations. Extend with more sklearn models as needed.
"""

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler


def fit_trend(df: pd.DataFrame, date_col: str = "date", value_col: str = "value") -> dict:
    """Fit value ~ time (ordinal days) and return slope/intercept/predictions.

    Returns a dict with the fitted line added as a "trend" column so it can
    be overlaid on a time series plot.
    """
    data = df.dropna(subset=[value_col]).copy()
    data["_t"] = pd.to_datetime(data[date_col]).map(pd.Timestamp.toordinal)

    model = LinearRegression()
    model.fit(data[["_t"]], data[value_col])
    data["trend"] = model.predict(data[["_t"]])

    return {
        "slope_per_day": float(model.coef_[0]),
        "intercept": float(model.intercept_),
        "data": data.drop(columns="_t"),
    }


def cluster_stations(
    station_summary: pd.DataFrame,
    feature_cols: list[str],
    n_clusters: int = 3,
) -> pd.DataFrame:
    """KMeans-cluster stations on aggregated feature columns (e.g. mean
    temperature, total precipitation). Returns the input df with a `cluster`
    column added.
    """
    features = station_summary[feature_cols].dropna()
    scaled = StandardScaler().fit_transform(features)

    model = KMeans(n_clusters=n_clusters, random_state=0, n_init="auto")
    labels = model.fit_predict(scaled)

    result = station_summary.loc[features.index].copy()
    result["cluster"] = labels.astype(str)
    return result


PARAMETER_UNITS = {
    "temperature_air_max_2m": "°C",
    "temperature_air_mean_2m": "°C",
    "temperature_air_min_2m": "°C",
    "temperature_air_min_0_05m": "°C",
    "precipitation_height": "mm",
    "wind_gust_max": "m/s",
    "wind_speed": "m/s",
    "humidity": "%",
    "pressure_air_site": "hPa",
    "pressure_vapor": "hPa",
    "snow_depth": "cm",
    "sunshine_duration": "s",
}

HOT_DAY_TEMPERATURE_PARAMETER = "temperature_air_max_2m"
HOT_DAY_THRESHOLD_C = 30.0


def compute_parameter_stats(subset: pd.DataFrame, parameter: str) -> dict[str, float | int | str | None]:
    """Return min/mean/max/mode plus one parameter-aware "total" figure for
    whatever parameter is currently selected in a tab's "Parameter" dropdown.

    ``subset`` is expected to already be filtered to that one parameter
    (e.g. the second element render_parameter_and_subset() returns) --
    this recomputes nothing about *which* rows to use, only aggregates
    the "value" column it's given.

    The "total" figure's meaning depends on the parameter, since a single
    fixed definition (e.g. always summing) isn't meaningful for most of
    DWD's climate_summary parameters:
      - precipitation_height: summing rainfall over a period is the
        standard "how much rain fell in total" figure.
      - temperature_air_max_2m: DWD's own definition of a "hot day" is a
        day whose *maximum* temperature exceeds 30°C (mean/min temperature
        crossing 30°C isn't the standard definition, which is why this is
        gated to specifically the max-temperature parameter, not every
        temperature_air_* one) -- reuses the same threshold/parameter
        get_hot_days_data() in data_loader.py already uses, so this
        headline number and the Global Warming tab's own hot-day charts
        agree with each other.
      - everything else (cloud cover, wind, pressure, snow depth, the
        other temperature variants, ...): there's no obviously "correct"
        single total for these, so this falls back to a plain count of
        valid observations -- always meaningful regardless of parameter,
        and it doubles as a sample-size figure for the other four stats.
    """
    values = subset["value"].dropna()
    unit = PARAMETER_UNITS.get(parameter, "")

    if values.empty:
        return {
            "min": None,
            "mean": None,
            "max": None,
            "mode": None,
            "unit": unit,
            "total_label": "Observations",
            "total": 0,
            "total_unit": "",
        }

    mode_values = values.mode()
    mode = float(mode_values.iloc[0]) if not mode_values.empty else None

    if parameter == "precipitation_height":
        total_label, total, total_unit = "Total precipitation", float(values.sum()), "mm"
    elif parameter == HOT_DAY_TEMPERATURE_PARAMETER:
        total_label = f"Hot days (>{HOT_DAY_THRESHOLD_C:g}°C)"
        total, total_unit = int((values > HOT_DAY_THRESHOLD_C).sum()), "days"
    else:
        total_label, total, total_unit = "Observations", int(values.count()), ""

    return {
        "min": float(values.min()),
        "mean": float(values.mean()),
        "max": float(values.max()),
        "mode": mode,
        "unit": unit,
        "total_label": total_label,
        "total": total,
        "total_unit": total_unit,
    }
