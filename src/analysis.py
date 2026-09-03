"""Simple on-demand analysis tools applied to a selection of weather data.

A linear trend fit and a KMeans clustering of stations across however many
weather parameters are chosen at once. Extend with more sklearn models as
needed.
"""

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from sklearn.metrics import silhouette_score
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


# Default feature set for Clustering/Map's cluster mode -- clustering on
# several parameters together groups stations by overall climate profile,
# not just one number.
DEFAULT_CLUSTER_FEATURES = [
    "temperature_air_mean_2m",
    "precipitation_height",
    "wind_speed",
    "humidity",
    "sunshine_duration",
]


def build_station_features(raw: pd.DataFrame, feature_params: list[str]) -> pd.DataFrame:
    """Pivot long-format station observations into one row per station, one
    column per parameter in ``feature_params``, holding each station's mean
    value. A station missing a parameter gets NaN rather than being dropped
    here -- cluster_stations() excludes incomplete rows, so callers can
    still report which stations were excluded and why.

    Columns come back in ``feature_params``' own order, not ``unstack()``'s
    alphabetical one."""
    subset = raw[raw["parameter"].isin(feature_params)].dropna(subset=["value"])
    pivoted = subset.groupby(["station_id", "parameter"])["value"].mean().unstack("parameter")
    return pivoted.reindex(columns=feature_params)


def cluster_stations(features: pd.DataFrame, n_clusters: int = 3) -> pd.DataFrame:
    """KMeans-cluster stations on however many columns ``features`` has
    (typically from build_station_features()). Rows with a missing value in
    any column are dropped before fitting -- KMeans can't handle NaN, and
    imputing a station's *only* reading for a parameter it doesn't actually
    report would fabricate data rather than describe it.

    Returns the clustered rows, original index preserved, with one
    "cluster" column appended.
    """
    complete = features.dropna()
    scaled = StandardScaler().fit_transform(complete)

    model = KMeans(n_clusters=n_clusters, random_state=0, n_init="auto")
    model.fit(scaled)

    result = complete.copy()
    result["cluster"] = model.labels_.astype(str)
    return result


def cluster_diagnostics(features: pd.DataFrame, k_values: range) -> pd.DataFrame:
    """Inertia and silhouette score for each k in ``k_values`` -- the two
    standard diagnostics for picking how many KMeans clusters to use.
    Inertia (within-cluster sum of squared distances) always keeps falling
    as k grows, so it's read for where the drop-off flattens out (the
    "elbow"); silhouette score (-1 to 1, higher is better-separated
    clusters) has an actual peak to read off directly instead.
    """
    complete = features.dropna()
    scaled = StandardScaler().fit_transform(complete)

    rows = []
    for k in k_values:
        if k < 2 or k >= len(complete):
            continue
        model = KMeans(n_clusters=k, random_state=0, n_init="auto").fit(scaled)
        rows.append(
            {
                "k": k,
                "inertia": float(model.inertia_),
                "silhouette": float(silhouette_score(scaled, model.labels_)),
            }
        )
    return pd.DataFrame(rows)


# Shared across every clustering view so both use the exact same "recommend
# a k before the slider renders" behavior.
MAX_CLUSTER_K = 10


def compute_k_diagnostics(feature_matrix: pd.DataFrame, complete: pd.DataFrame) -> tuple[pd.DataFrame | None, int | None]:
    """Inertia and silhouette score across k=2..MAX_CLUSTER_K, computed
    *before* a cluster-count slider renders so its default can be seeded
    with a recommended k -- the one with peak silhouette score. Returns
    ``(None, None)`` when there aren't enough complete rows to compare."""
    max_k = min(MAX_CLUSTER_K, len(complete) - 1)
    if max_k < 2:
        return None, None
    diagnostics = cluster_diagnostics(feature_matrix, range(2, max_k + 1))
    if diagnostics.empty:
        return None, None
    best_k = int(diagnostics.loc[diagnostics["silhouette"].idxmax(), "k"])
    return diagnostics, best_k


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
# Each composite maps a synthetic key to the raw parameters it bundles
# ("components") and how its Key Figures cards are computed -- see
# COMPOSITE_PARAMETER_GROUPS at the bottom of this file.

TEMPERATURE_COMPOSITE_KEY = "temperature"
TEMPERATURE_COMPONENT_PARAMETERS = [
    "temperature_air_max_2m",
    "temperature_air_mean_2m",
    "temperature_air_min_2m",
]
# 5cm-above-ground reading (frost risk), not the same metric as the three
# 2m variants -- rides along under "Temperature" as its own chart, excluded
# from compute_temperature_stats() and the 2m band chart.
TEMPERATURE_GROUND_PARAMETER = "temperature_air_min_0_05m"
TEMPERATURE_ALL_PARAMETERS = TEMPERATURE_COMPONENT_PARAMETERS + [TEMPERATURE_GROUND_PARAMETER]
TEMPERATURE_PRIMARY_PARAMETER = "temperature_air_mean_2m"

# Shared by every view offering the Temperature composite, not just Time Series.
TEMPERATURE_TREND_LABELS = {
    "temperature_air_mean_2m": "Mean",
    "temperature_air_max_2m": "Max",
    "temperature_air_min_2m": "Min",
}
TEMPERATURE_TREND_PARAMETER_BY_LABEL = {label: param for param, label in TEMPERATURE_TREND_LABELS.items()}

PRECIPITATION_COMPOSITE_KEY = "precipitation"
# snow_depth rides along here (consequence of precipitation) but is an
# accumulated depth, not a daily amount/category, so it gets its own
# cards+chart appended after height/form rather than merged into either.
PRECIPITATION_COMPONENT_PARAMETERS = ["precipitation_height", "precipitation_form", "snow_depth"]
PRECIPITATION_PRIMARY_PARAMETER = "precipitation_height"

# DWD's numeric codes for precipitation_form (RSKF). Codes 2/3/5 are
# undefined; any code not in this dict falls back to "Code {n}".
PRECIPITATION_FORM_LABELS = {
    0.0: "No precipitation",
    1.0: "Rain (historical, pre-1979)",
    4.0: "Unknown form (precipitation reported)",
    6.0: "Rain (automatic)",
    7.0: "Snow (automatic)",
    8.0: "Rain and snow / sleet (automatic)",
    9.0: "Missing / undetermined (automatic)",
}

WIND_COMPOSITE_KEY = "wind"
WIND_COMPONENT_PARAMETERS = ["wind_speed", "wind_gust_max"]
WIND_PRIMARY_PARAMETER = "wind_speed"

HUMIDITY_COMPOSITE_KEY = "humidity_pressure_vapor"
HUMIDITY_COMPOSITE_COMPONENTS = ["humidity", "pressure_vapor"]

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
    HUMIDITY_COMPOSITE_KEY: "precipitation",
    "cloud_cover_total": "neutral",
    "snow_depth": "neutral",
    "wind_gust_max": "neutral",
    "wind_speed": "neutral",
    "pressure_air_site": "neutral",
    WIND_COMPOSITE_KEY: "neutral",
}


def categorize_parameter(parameter: str) -> str:
    """Map a DWD parameter (or composite key) to a Key Figures color
    category. Unrecognized parameters default to "neutral" rather than
    raising."""
    return PARAMETER_COLOR_CATEGORY.get(parameter, "neutral")


def compute_parameter_stats(subset: pd.DataFrame, parameter: str) -> dict[str, float | int | str | None]:
    """Return min/mean/max/mode plus one parameter-aware "total" figure, all
    read off ``subset``'s single "value" column (already filtered to one
    real parameter). For composites where that's not true, see
    compute_temperature_stats() instead."""
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
    """Key Figures for the "Temperature" composite, with each stat read from
    its own correct source rather than all derived off one series (min/max
    off the daily mean would understate how cold/hot it actually got): min
    from the daily-min series, max from daily-max, mean from daily-mean,
    mode from all three pooled together.

    ``subset`` is long-format rows for the three 2m parameters; any other
    rows (e.g. ground frost) are ignored, same as the band chart."""
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


# Each entry supports one of three shapes (see render_parameter_and_subset()
# in src/views/common.py): "stats_fn" (one merged block via a custom
# function), "stats_parameters" (one block per listed parameter), or
# neither (one block off "primary"). "label" overrides the dropdown text
# for composites that don't read cleanly through pretty_name().
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
    WIND_COMPOSITE_KEY: {
        "components": WIND_COMPONENT_PARAMETERS,
        "primary": WIND_PRIMARY_PARAMETER,
    },
    HUMIDITY_COMPOSITE_KEY: {
        "components": HUMIDITY_COMPOSITE_COMPONENTS,
        "stats_parameters": HUMIDITY_COMPOSITE_COMPONENTS,
        "label": "Humidity and Pressure Vapor",
    },
}