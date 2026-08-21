"""Fetch and locally cache DWD (Deutscher Wetterdienst) station observation data.

Uses the `wetterdienst` library, which wraps the DWD Climate Data Center (CDC)
open data FTP/HTTP archive. No API key is required.

wetterdienst is pre-1.0 and its API changes between versions, so the version
is pinned in requirements.txt. If these calls start failing after an
`pip install -U wetterdienst`, check the "Python API" docs for the installed
version: https://wetterdienst.readthedocs.io/
"""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
SETTINGS = Settings(cache_dir=DATA_DIR / ".wetterdienst-cache")

CLIMATE_SUMMARY = ("daily", "climate_summary")
#WIND = ("hourly", "wind")
#PRESSURE = ("hourly", "pressure")
REQUEST_PARAMETERS = [CLIMATE_SUMMARY]
LONG_RUN_CITY_STATIONS = {
    "Berlin": "00433",       # Berlin-Tempelhof
    "Munich": "03379",       # München-Stadt
    "Dresden": "01048",      # Dresden-Klotzsche
    "Frankfurt": "01420",    # Frankfurt/Main-Flughafen
}
TREND_START_YEAR = 2007
ANOMALY_BASELINE_START_YEAR = 1991
ANOMALY_BASELINE_END_YEAR = 2020


def list_stations() -> pd.DataFrame:
    """Return metadata (station_id, name, latitude, longitude, height, ...)
    for every DWD station that reports the daily climate_summary dataset.

    Climate summaries are a daily dataset, so the station selector is limited
    to stations that report daily climate-summary observations.
    """
    request = DwdObservationRequest(
        parameters=REQUEST_PARAMETERS,
        settings=SETTINGS,
    )
    return request.all().df.to_pandas()


def get_station_data(
    station_ids: list[str],
    start_date: str,
    end_date: str,
    cache: bool = False,
) -> pd.DataFrame:
    """Return the requested DWD observations for station ids.

    Parameters
    ----------
    station_ids: DWD station ids, e.g. ["00433", "01048"] (Berlin-Tempelhof, Dresden-Klotzsche)
    start_date / end_date: "YYYY-MM-DD"
    cache: reuse a local parquet cache under data/ instead of re-downloading
    """
    # Include requested datasets in the cache name so a change from, for
    # example, climate summaries to wind data triggers a fresh download.
    dataset_key = "-".join(f"{resolution}-{dataset}" for resolution, dataset, *_ in REQUEST_PARAMETERS)
    cache_key = f"{'-'.join(sorted(station_ids))}_{start_date}_{end_date}_{dataset_key}.parquet"
    cache_path = DATA_DIR / cache_key
    if cache and cache_path.exists():
        return pd.read_parquet(cache_path)

    request = DwdObservationRequest(
        parameters=REQUEST_PARAMETERS,
        start_date=start_date,
        end_date=end_date,
        settings=SETTINGS,
    ).filter_by_station_id(station_id=station_ids)

    df = request.values.all().df.to_pandas()

    if cache:
        df.to_parquet(cache_path)

    return df


def export_sample_csv(
    df: pd.DataFrame,
    path: Path | None = None,
    parameter: str | None = None,
) -> Path:
    """Export the first 200 rows, optionally limited to one parameter."""
    export_path = path or DATA_DIR / "dwd_sample_first_200_rows.csv"
    sample = df if parameter is None else df[df["parameter"] == parameter]
    sample.head(200).to_csv(export_path, index=False)
    return export_path


def get_long_run_climate_data() -> pd.DataFrame:
    """Return July mean temperatures for four German cities each year.

    The result contains one row per city and year since 2007, including the
    current year. ``full_date`` is July 1 and labels the averaged month.
    """
    last_completed_year = datetime.now(UTC).year
    first_year = TREND_START_YEAR
    observations = get_station_data(
        station_ids=list(LONG_RUN_CITY_STATIONS.values()),
        start_date=f"{first_year}-01-01",
        end_date=f"{last_completed_year}-12-31",
        cache=True,
    )

    temperatures = observations.loc[
        observations["parameter"] == "temperature_air_mean_2m",
        ["station_id", "date", "value"],
    ].dropna()
    temperatures = temperatures.assign(date=pd.to_datetime(temperatures["date"], utc=True))
    station_to_city = {station_id: city for city, station_id in LONG_RUN_CITY_STATIONS.items()}
    temperatures["city"] = temperatures["station_id"].astype(str).map(station_to_city)
    temperatures = temperatures.dropna(subset=["city"])
    temperatures = temperatures.loc[
        temperatures["date"].dt.year.between(first_year, last_completed_year)
    ]
    july_temperatures = temperatures.loc[temperatures["date"].dt.month == 7].copy()
    july_temperatures["year"] = july_temperatures["date"].dt.year

    july_averages = july_temperatures.groupby(["city", "year"], as_index=False)["value"].mean()
    july_averages["full_date"] = pd.to_datetime(
        july_averages["year"].astype(str) + "-07-01", utc=True
    )
    return (
        july_averages.rename(columns={"value": "observed_temp"})
        [["city", "year", "full_date", "observed_temp"]]
        .sort_values(["city", "year"])
        .reset_index(drop=True)
    )


def get_hot_days_data() -> pd.DataFrame:
    """Return yearly counts of days above 30 °C for the long-run cities.

    A hot day is defined as a day with ``temperature_air_max_2m`` strictly
    greater than 30 °C. ``full_date`` is January 1 and labels its year.
    """
    last_completed_year = datetime.now(UTC).year
    first_year = TREND_START_YEAR
    observations = get_station_data(
        station_ids=list(LONG_RUN_CITY_STATIONS.values()),
        start_date=f"{first_year}-01-01",
        end_date=f"{last_completed_year}-12-31",
        cache=True,
    )

    temperatures = observations.loc[
        observations["parameter"] == "temperature_air_max_2m",
        ["station_id", "date", "value"],
    ].dropna()
    temperatures = temperatures.assign(date=pd.to_datetime(temperatures["date"], utc=True))
    station_to_city = {station_id: city for city, station_id in LONG_RUN_CITY_STATIONS.items()}
    temperatures["city"] = temperatures["station_id"].astype(str).map(station_to_city)
    hot_days = temperatures.loc[
        temperatures["city"].notna()
        & temperatures["date"].dt.year.between(first_year, last_completed_year)
        & (temperatures["value"] > 30)
    ].copy()
    hot_days["year"] = hot_days["date"].dt.year

    yearly_counts = (
        hot_days.groupby(["city", "year"], as_index=False)
        .size()
        .rename(columns={"size": "days_above_30c"})
    )
    city_years = pd.MultiIndex.from_product(
        [LONG_RUN_CITY_STATIONS, range(first_year, last_completed_year + 1)],
        names=["city", "year"],
    ).to_frame(index=False)
    result = city_years.merge(yearly_counts, on=["city", "year"], how="left")
    result["days_above_30c"] = result["days_above_30c"].fillna(0).astype(int)
    result["full_date"] = pd.to_datetime(result["year"].astype(str) + "-01-01", utc=True)
    return result[["city", "year", "full_date", "days_above_30c"]]


def get_climate_change_indicators_data() -> pd.DataFrame:
    """Return annual anomaly, heat, and rainfall indicators for each city.

    Temperature anomalies use each city's 1991–2020 mean annual temperature as
    the baseline. A hot night has minimum temperature above 20 °C; a heavy-rain
    day has precipitation above 20 mm. The current year's values are year-to-date.
    """
    last_year = datetime.now(UTC).year
    observations = get_station_data(
        station_ids=list(LONG_RUN_CITY_STATIONS.values()),
        start_date=f"{ANOMALY_BASELINE_START_YEAR}-01-01",
        end_date=f"{last_year}-12-31",
        cache=True,
    )
    station_to_city = {station_id: city for city, station_id in LONG_RUN_CITY_STATIONS.items()}
    values = observations[["station_id", "date", "parameter", "value"]].dropna()
    values = values.assign(date=pd.to_datetime(values["date"], utc=True))
    values["city"] = values["station_id"].astype(str).map(station_to_city)
    values = values.loc[
        values["city"].notna()
        & values["date"].dt.year.between(ANOMALY_BASELINE_START_YEAR, last_year)
    ].copy()
    values["year"] = values["date"].dt.year

    annual_mean = (
        values.loc[values["parameter"] == "temperature_air_mean_2m"]
        .groupby(["city", "year"], as_index=False)["value"]
        .mean()
        .rename(columns={"value": "annual_mean_temp"})
    )
    baseline = (
        annual_mean.loc[annual_mean["year"].between(ANOMALY_BASELINE_START_YEAR, ANOMALY_BASELINE_END_YEAR)]
        .groupby("city", as_index=False)["annual_mean_temp"]
        .mean()
        .rename(columns={"annual_mean_temp": "baseline_temp"})
    )
    city_years = pd.MultiIndex.from_product(
        [LONG_RUN_CITY_STATIONS, range(TREND_START_YEAR, last_year + 1)],
        names=["city", "year"],
    ).to_frame(index=False)
    result = city_years.merge(annual_mean, on=["city", "year"], how="left").merge(baseline, on="city", how="left")
    result["temperature_anomaly"] = result["annual_mean_temp"] - result["baseline_temp"]
    result["temperature_anomaly_5y"] = result.groupby("city")["temperature_anomaly"].transform(
        lambda series: series.rolling(window=5, min_periods=1).mean()
    )

    def annual_count(parameter: str, threshold: float, name: str) -> pd.DataFrame:
        counts = (
            values.loc[(values["parameter"] == parameter) & (values["value"] > threshold)]
            .groupby(["city", "year"], as_index=False)
            .size()
            .rename(columns={"size": name})
        )
        return city_years.merge(counts, on=["city", "year"], how="left").fillna({name: 0})

    hot_nights = annual_count("temperature_air_min_2m", 20, "hot_nights")
    heavy_rain_days = annual_count("precipitation_height", 20, "heavy_rain_days")
    result = result.merge(hot_nights, on=["city", "year"]).merge(heavy_rain_days, on=["city", "year"])
    result[["hot_nights", "heavy_rain_days"]] = result[["hot_nights", "heavy_rain_days"]].astype(int)
    result["full_date"] = pd.to_datetime(result["year"].astype(str) + "-01-01", utc=True)
    return result[
        [
            "city",
            "year",
            "full_date",
            "annual_mean_temp",
            "temperature_anomaly",
            "temperature_anomaly_5y",
            "hot_nights",
            "heavy_rain_days",
        ]
    ]


if __name__ == "__main__":
    # Quick smoke test: Berlin-Tempelhof, last full year of historical data.
    df = get_station_data(["00433"], "2023-01-01", "2023-12-31")
    #print(df.head())
    #print(df["parameter"].unique())
    ##print(f"Exported first 200 climate-summary rows to {export_sample_csv(df)}")
    print(get_long_run_climate_data())
