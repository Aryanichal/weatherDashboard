"""Simple on-demand analysis tools applied to a selection of weather data.

Kept intentionally minimal: a linear trend fit and a KMeans clustering of
stations. Extend with more sklearn models as needed.
"""

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler


def fit_trend(df: pd.DataFrame, date_col: str = "date", value_col: str = "value") -> dict:
    """Fit value ~ time (ordinal days) and return slope/intercept/predictions."""
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
    """KMeans-cluster stations on aggregated feature columns."""
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

# --- Composite "Parameter" dropdown entries -------------------------------
# Some DWD parameters are more useful to users grouped together under one
# dropdown entry than picked between individually. Each composite maps a
# synthetic key (never an actual DWD `parameter` value) to the raw
# parameters it bundles ("components") and which single one of those backs
# the Key Figures cards by default ("primary") -- see
# render_parameter_and_subset() in src/views/common.py, which offers/
# expands these, and COMPOSITE_PARAMETER_GROUPS at the bottom of this file,
# which also wires in a composite's custom stats function when one exists.

TEMPERATURE_COMPOSITE_KEY = "temperature"
TEMPERATURE_COMPONENT_PARAMETERS = [
    "temperature_air_max_2m",
    "temperature_air_mean_2m",
    "temperature_air_min_2m",
]
# temperature_air_min_0_05m is a 5cm-above-ground reading (frost risk), not
# the same metric as the three 2m air-temperature variants -- it rides
# along under "Temperature" but as its own chart (see time_series.py) and
# is excluded from compute_temperature_stats() below, same as it's
# excluded from the 2m band chart.
TEMPERATURE_GROUND_PARAMETER = "temperature_air_min_0_05m"
TEMPERATURE_ALL_PARAMETERS = TEMPERATURE_COMPONENT_PARAMETERS + [TEMPERATURE_GROUND_PARAMETER]
TEMPERATURE_PRIMARY_PARAMETER = "temperature_air_mean_2m"

PRECIPITATION_COMPOSITE_KEY = "precipitation"
PRECIPITATION_COMPONENT_PARAMETERS = ["precipitation_height", "precipitation_form"]
PRECIPITATION_PRIMARY_PARAMETER = "precipitation_height"

# DWD's numeric codes for precipitation_form (RSKF), per DWD's own dataset
# description (cdc.dwd.de, "Tägliche Stationsbeobachtungen der
# Niederschlagsform"). Codes 2/3/5 are not defined there -- any code not
# in this dict falls back to a generic "Code {n}" label at display time.
PRECIPITATION_FORM_LABELS = {
    0.0: "No precipitation",
    1.0: "Rain (historical, pre-1979)",
    4.0: "Unknown form (precipitation reported)",
    6.0: "Rain (automatic)",
    7.0: "Snow (automatic)",
    8.0: "Rain and snow / sleet (automatic)",
    9.0: "Missing / undetermined (automatic)",
}

PARAMETER_COLOR_CATEGORY = {
    "temperature_air_max_2m": "temperature",
    "temperature_air_mean_2m": "temperature",
    "temperature_air_min_2m": "temperature",
    "temperature_air_min_0_05m": "temperature",
    "sunshine_duration": "temperature",
    TEMPERATURE_COMPOSITE_KEY: "temperature",
    "precipitation_height": "precipitation",
    "precipitation_form": "precipitation",
    "humidity": "precipitation",
    "pressure_vapor": "precipitation",
    PRECIPITATION_COMPOSITE_KEY: "precipitation",
    "cloud_cover_total": "neutral",
    "snow_depth": "neutral",
    "wind_gust_max": "neutral",
    "wind_speed": "neutral",
    "pressure_air_site": "neutral",
}


def categorize_parameter(parameter: str) -> str:
    """Map a DWD parameter (or composite key) to a Key Figures color
    category. Unrecognized parameters default to "neutral" rather than
    raising."""
    return PARAMETER_COLOR_CATEGORY.get(parameter, "neutral")


def compute_parameter_stats(subset: pd.DataFrame, parameter: str) -> dict[str, float | int | str | None]:
    """Return min/mean/max/mode plus one parameter-aware "total" figure,
    all read off ``subset``'s single "value" column.

    ``subset`` is expected to already be filtered to one real parameter.
    This is the right function for any parameter whose min/mean/max/mode
    all meaningfully come from *the same* series -- for composites where
    that's not true (see compute_temperature_stats() below), a dedicated
    stats function is used instead.
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


def compute_temperature_stats(subset: pd.DataFrame) -> dict[str, float | int | str | None]:
    """Key Figures for the "Temperature" composite, with each stat read
    from its own correct source rather than all five being derived off
    one series (a bug flagged in review: computing min/max off the daily
    *mean* series understates how cold/hot it actually got, since it's
    reporting the min of an already-averaged series).

      - min: the coldest single reading in the period -- the minimum of
        the *daily minimum* (temperature_air_min_2m) series.
      - max: the hottest single reading -- the maximum of the *daily
        maximum* (temperature_air_max_2m) series.
      - mean: the average of the *daily mean* (temperature_air_mean_2m)
        series -- this one genuinely is a mean-of-means, so it's
        unchanged.
      - mode: the single most frequently occurring reading across all
        three 2m series pooled together, since there's no one series a
        composite's mode should read off.

    ``subset`` is long-format rows for (at least) the three 2m
    temperature parameters -- any other rows present (e.g. the ground
    frost reading, if the caller passed the full composite subset) are
    simply ignored here, the same way they're excluded from the band
    chart.
    """
    min_values = subset.loc[subset["parameter"] == "temperature_air_min_2m", "value"].dropna()
    mean_values = subset.loc[subset["parameter"] == "temperature_air_mean_2m", "value"].dropna()
    max_values = subset.loc[subset["parameter"] == "temperature_air_max_2m", "value"].dropna()
    pooled_values = pd.concat([min_values, mean_values, max_values])

    if pooled_values.empty:
        return {
            "min": None,
            "mean": None,
            "max": None,
            "mode": None,
            "unit": "°C",
            "total_label": "Observations",
            "total": 0,
            "total_unit": "",
        }

    mode_values = pooled_values.mode()
    mode = float(mode_values.iloc[0]) if not mode_values.empty else None

    return {
        "min": float(min_values.min()) if not min_values.empty else None,
        "mean": float(mean_values.mean()) if not mean_values.empty else None,
        "max": float(max_values.max()) if not max_values.empty else None,
        "mode": mode,
        "unit": "°C",
        "total_label": "Observations",
        "total": int(mean_values.count()),
        "total_unit": "",
    }


# Defined last so it can reference the compute_*_stats functions above.
# "stats_fn", when present, overrides the default primary-parameter-based
# stats computation for that composite -- see render_parameter_and_subset()
# in src/views/common.py.
COMPOSITE_PARAMETER_GROUPS = {
    TEMPERATURE_COMPOSITE_KEY: {
        "components": TEMPERATURE_ALL_PARAMETERS,
        "primary": TEMPERATURE_PRIMARY_PARAMETER,
        "stats_fn": compute_temperature_stats,
    },
    PRECIPITATION_COMPOSITE_KEY: {
        "components": PRECIPITATION_COMPONENT_PARAMETERS,
        "primary": PRECIPITATION_PRIMARY_PARAMETER,
    },
}