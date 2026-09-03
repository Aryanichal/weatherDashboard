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


# A KMeans run on a single feature is just sorting stations and cutting the
# sorted list into k chunks -- the useful version clusters on several
# parameters together, so stations end up grouped by overall climate profile
# rather than by one number. These are the base (non-composite, continuous)
# parameters offered as the default feature set wherever that's needed
# (Clustering tab, Map tab's cluster-coloring mode)  any station missing
# one isn't dropped from the *offering*, only from the fit itself (see
# cluster_stations() below), so a station without sunshine data still shows
# up if it's later deselected from the feature list.
DEFAULT_CLUSTER_FEATURES = [
    "temperature_air_mean_2m",
    "precipitation_height",
    "wind_speed",
    "humidity",
    "sunshine_duration",
]


def build_station_features(raw: pd.DataFrame, feature_params: list[str]) -> pd.DataFrame:
    """Pivot long-format station observations into one row per station and
    one column per parameter in ``feature_params``, each holding that
    station's mean value over whatever date range/stations ``raw`` already
    covers. A station that never reports one of ``feature_params`` at all
    gets NaN in that column rather than being silently dropped here --
    cluster_stations() below is what actually excludes incomplete rows,
    so callers can still report *which* stations were excluded and why.

    Columns come back in exactly ``feature_params``' order, not the
    alphabetical order ``unstack()`` would otherwise produce -- keeps
    column order predictable for callers regardless of what order
    ``feature_params`` (typically a user's own selection) happened to list
    them in.
    """
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


# Shared across every clustering view (Clustering tab, Map tab's cluster
# mode) rather than duplicated per view -- both need the exact same
# "recommend a k before the slider renders" behavior, and drift between
# two copies of this logic would be an easy, silent bug to introduce later.
MAX_CLUSTER_K = 10


def compute_k_diagnostics(feature_matrix: pd.DataFrame, complete: pd.DataFrame) -> tuple[pd.DataFrame | None, int | None]:
    """Inertia and silhouette score across k=2..MAX_CLUSTER_K, meant to be
    computed *before* a cluster-count slider renders so its initial value
    can be seeded with a recommended k instead of an arbitrary fixed
    default. The recommendation comes from silhouette score (the k with
    the most clearly separated groups) -- unlike inertia, which always
    keeps falling as k grows, silhouette has an actual peak to recommend
    from. Returns ``(None, None)`` when there aren't enough complete rows
    to compare more than one k.
    """
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
# Some DWD parameters are more useful to users grouped together under one
# dropdown entry than picked between individually. Each composite maps a
# synthetic key (never an actual DWD `parameter` value) to the raw
# parameters it bundles ("components") and how its Key Figures cards are
# computed -- see COMPOSITE_PARAMETER_GROUPS at the bottom of this file for
# the three supported shapes, and render_parameter_and_subset() in
# src/views/common.py, which offers/expands these in the dropdown.

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

# Mean/Max/Min trend-line toggle for the "Temperature" composite -- shared
# by every view that offers it (see render_parameter_and_subset() in
# src/views/common.py), not just Time Series' own band chart, so this
# lives here rather than in time_series.py alongside the other
# composite-wide constants above.
TEMPERATURE_TREND_LABELS = {
    "temperature_air_mean_2m": "Mean",
    "temperature_air_max_2m": "Max",
    "temperature_air_min_2m": "Min",
}
TEMPERATURE_TREND_PARAMETER_BY_LABEL = {label: param for param, label in TEMPERATURE_TREND_LABELS.items()}

PRECIPITATION_COMPOSITE_KEY = "precipitation"
# snow_depth is grouped in here since snow is a direct consequence of
# precipitation falling in that form (see PRECIPITATION_FORM_LABELS below)
# -- but it's a different kind of quantity (an accumulated depth, not a
# daily amount or a category), so it gets its own cards + chart appended
# after the main precipitation_height/precipitation_form ones rather than
# being merged into either. See time_series.py's PRECIPITATION_COMPOSITE_KEY
# branch.
PRECIPITATION_COMPONENT_PARAMETERS = ["precipitation_height", "precipitation_form", "snow_depth"]
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
    one series (min/max off the daily *mean* series would understate how
    cold/hot it actually got).

      - min: the coldest single reading -- the minimum of the *daily
        minimum* (temperature_air_min_2m) series.
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
    frost reading) are simply ignored here, the same way they're
    excluded from the band chart.
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
# Each entry supports one of three shapes, all handled by
# render_parameter_and_subset() in src/views/common.py:
#   - "stats_fn": one merged 5-card block, computed by the group's own
#     function (Temperature -- min/max need sourcing from different
#     series than mean/mode).
#   - "stats_parameters": one complete, independently-labeled 5-card
#     block per parameter listed, with rendering order left to the
#     calling view (Humidity and Pressure Vapor -- collapsing to a
#     single block would lose one of the two readings).
#   - neither (just "primary"): the default -- one 5-card block off that
#     single parameter, labeled with the composite's own name
#     (Precipitation, Wind).
# "label" overrides the dropdown's display text for composites that
# don't read cleanly through pretty_name()'s generic snake_case split.
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