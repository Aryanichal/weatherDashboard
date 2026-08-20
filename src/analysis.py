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
