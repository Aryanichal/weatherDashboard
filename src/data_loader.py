"""Fetch and locally cache DWD (Deutscher Wetterdienst) station observation data.

Uses the `wetterdienst` library, which wraps the DWD Climate Data Center (CDC)
open data FTP/HTTP archive. No API key is required.

wetterdienst is pre-1.0 and its API changes between versions, so the version
is pinned in requirements.txt. If these calls start failing after an
`pip install -U wetterdienst`, check the "Python API" docs for the installed
version: https://wetterdienst.readthedocs.io/
"""

import datetime as dt
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from zipfile import BadZipFile

import numpy as np
import pandas as pd
import streamlit as st
from wetterdienst import Settings
from wetterdienst.exceptions import ProductFileNotFoundError
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
SETTINGS = Settings(cache_dir=DATA_DIR / ".wetterdienst-cache")

# Raised by wetterdienst when a station's ZIP archive can't be read:
# BadZipFile for a corrupted download, ProductFileNotFoundError when it
# unpacked but lacked the expected "produkt*" file.
_ARCHIVE_ERRORS = (BadZipFile, ProductFileNotFoundError)


class WeatherDataFetchError(Exception):
    """Raised when DWD's observation archive can't be read, even after
    get_station_data()'s retry with the cache bypassed. Callers should show
    a plain-language message instead of the raw zipfile/wetterdienst traceback."""

CLIMATE_SUMMARY = ("daily", "climate_summary")
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

# Clustering needs a real population (hundreds of stations), not the handful
# a user picks by hand. Split at the network's own lat/lon midpoint, not
# federal-state borders, since climate tracks geography more than politics.
REGION_OPTIONS = ["All Germany", "North", "South", "East", "West"]
_GERMANY_LAT_MIDPOINT = 51.2
_GERMANY_LON_MIDPOINT = 10.5
# Capped so a wide date range (or "All Germany") still fetches in a
# reasonable time -- fetch time scales with station count (one ZIP archive
# per station), and 40 stations already takes ~15-50s.
MAX_REGION_STATIONS = 40


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


def get_station_metadata(station_ids: list[str]) -> pd.DataFrame:
    """Return station metadata (station_id, name, start_date, end_date, ...) for the given ids.

    Cheap compared to ``get_station_data``: fetches only station-list metadata,
    not the actual observation time series.
    """
    request = DwdObservationRequest(
        parameters=REQUEST_PARAMETERS,
        settings=SETTINGS,
    ).filter_by_station_id(station_id=station_ids)
    return request.df.to_pandas()


# Courtesy ceiling on concurrent connections to a public government server.
_MAX_FETCH_WORKERS = 8


def _fetch_station_chunk(station_ids: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch one chunk of stations, retrying once on a corrupted archive
    -- scoped to just this chunk so one bad station doesn't force
    re-fetching every other one too."""
    request = DwdObservationRequest(
        parameters=REQUEST_PARAMETERS,
        start_date=start_date,
        end_date=end_date,
        settings=SETTINGS,
    ).filter_by_station_id(station_id=station_ids)
    try:
        return request.values.all().df.to_pandas()
    except _ARCHIVE_ERRORS:
        retry_settings = SETTINGS.model_copy(update={"cache_disable": True})
        retry_request = DwdObservationRequest(
            parameters=REQUEST_PARAMETERS,
            start_date=start_date,
            end_date=end_date,
            settings=retry_settings,
        ).filter_by_station_id(station_id=station_ids)
        return retry_request.values.all().df.to_pandas()


def get_station_data(
    station_ids: list[str],
    start_date: str,
    end_date: str,
    cache: bool = False,
) -> pd.DataFrame:
    """Return the requested DWD observations for station ids.

    Parameters:
    station_ids: DWD station ids, e.g. ["00433", "01048"] (Berlin-Tempelhof, Dresden-Klotzsche)
    start_date / end_date: "YYYY-MM-DD"
    cache: reuse a local parquet cache under data/ instead of re-downloading

    Raises:
    WeatherDataFetchError
        If DWD's per-station ZIP archive can't be read even after a retry.
        wetterdienst caches the archive with only a 5-minute TTL, so a
        corrupted download would otherwise keep failing identically until
        it expires; retrying once with caching disabled forces a fresh
        download and self-heals a one-off network blip immediately.
    """
    # Include requested datasets in the cache name so a change from, for
    # example, climate summaries to wind data triggers a fresh download.
    dataset_key = "-".join(f"{resolution}-{dataset}" for resolution, dataset, *_ in REQUEST_PARAMETERS)
    cache_key = f"{'-'.join(sorted(station_ids))}_{start_date}_{end_date}_{dataset_key}.parquet"
    cache_path = DATA_DIR / cache_key
    if cache and cache_path.exists():
        return pd.read_parquet(cache_path)

    # Fetching chunks concurrently (network I/O releases the GIL) measured
    # a ~22x speedup on a 40-station fetch (134s -> 6s) over sequential.
    n_workers = min(_MAX_FETCH_WORKERS, len(station_ids))
    chunks = [station_ids[i::n_workers] for i in range(n_workers)] if n_workers > 1 else [station_ids]

    if len(chunks) == 1:
        try:
            frames = [_fetch_station_chunk(chunks[0], start_date, end_date)]
        except _ARCHIVE_ERRORS as exc:
            raise WeatherDataFetchError(
                "DWD's weather data archive is temporarily unreachable or returned a "
                "corrupted file. This is usually transient -- please try again in a "
                "moment, or try again with fewer stations or a narrower date range."
            ) from exc
    else:
        frames = []
        first_error: Exception | None = None
        with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
            futures = [executor.submit(_fetch_station_chunk, chunk, start_date, end_date) for chunk in chunks]
            for future in as_completed(futures):
                try:
                    frames.append(future.result())
                except _ARCHIVE_ERRORS as exc:
                    first_error = first_error or exc
        if first_error is not None:
            # All-or-nothing: a silently-missing station is worse than a loud failure.
            raise WeatherDataFetchError(
                "DWD's weather data archive is temporarily unreachable or returned a "
                "corrupted file. This is usually transient -- please try again in a "
                "moment, or try again with fewer stations or a narrower date range."
            ) from first_error

    if len(frames) > 1:
        # Threads finish in arbitrary order; sort for a deterministic result.
        df = pd.concat(frames, ignore_index=True).sort_values(
            ["station_id", "parameter", "date"], kind="stable"
        ).reset_index(drop=True)
    else:
        df = frames[0]

    if cache:
        df.to_parquet(cache_path)

    return df


def get_long_run_climate_data(
    city_stations: dict[str, str] | None = None,
    start_year: int = TREND_START_YEAR,
    month: int = 7,
) -> pd.DataFrame:
    """Return mean temperatures for one month of the year, for the given cities each year.

    ``city_stations`` maps city name to DWD station id, e.g.
    ``{"Berlin": "00433"}``; defaults to ``LONG_RUN_CITY_STATIONS``.
    ``month`` (1-12) selects which calendar month is averaged; defaults to July.

    The result contains one row per city and year since ``start_year``,
    including the current year. ``full_date`` is the 1st of ``month`` and
    labels the averaged month.
    """
    city_stations = city_stations or LONG_RUN_CITY_STATIONS
    last_completed_year = datetime.now(UTC).year
    first_year = start_year
    observations = get_station_data(
        station_ids=list(city_stations.values()),
        start_date=f"{first_year}-01-01",
        end_date=f"{last_completed_year}-12-31",
        cache=True,
    )

    temperatures = observations.loc[
        observations["parameter"] == "temperature_air_mean_2m",
        ["station_id", "date", "value"],
    ].dropna()
    temperatures = temperatures.assign(date=pd.to_datetime(temperatures["date"], utc=True))
    station_to_city = {station_id: city for city, station_id in city_stations.items()}
    temperatures["city"] = temperatures["station_id"].astype(str).map(station_to_city)
    temperatures = temperatures.dropna(subset=["city"])
    temperatures = temperatures.loc[
        temperatures["date"].dt.year.between(first_year, last_completed_year)
    ]
    month_temperatures = temperatures.loc[temperatures["date"].dt.month == month].copy()
    month_temperatures["year"] = month_temperatures["date"].dt.year

    month_averages = month_temperatures.groupby(["city", "year"], as_index=False)["value"].mean()
    month_averages["full_date"] = pd.to_datetime(
        month_averages["year"].astype(str) + f"-{month:02d}-01", utc=True
    )
    return (
        month_averages.rename(columns={"value": "observed_temp"})
        [["city", "year", "full_date", "observed_temp"]]
        .sort_values(["city", "year"])
        .reset_index(drop=True)
    )


def get_hot_days_data(
    city_stations: dict[str, str] | None = None,
    start_year: int = TREND_START_YEAR,
    hot_day_threshold: float = 30.0,
) -> pd.DataFrame:
    """Return yearly counts of days above ``hot_day_threshold`` for the given cities.

    ``city_stations`` maps city name to DWD station id; defaults to
    ``LONG_RUN_CITY_STATIONS``.

    A hot day is defined as a day with ``temperature_air_max_2m`` strictly
    greater than ``hot_day_threshold`` (°C). ``full_date`` is January 1 and
    labels its year.
    """
    city_stations = city_stations or LONG_RUN_CITY_STATIONS
    last_completed_year = datetime.now(UTC).year
    first_year = start_year
    observations = get_station_data(
        station_ids=list(city_stations.values()),
        start_date=f"{first_year}-01-01",
        end_date=f"{last_completed_year}-12-31",
        cache=True,
    )

    temperatures = observations.loc[
        observations["parameter"] == "temperature_air_max_2m",
        ["station_id", "date", "value"],
    ].dropna()
    temperatures = temperatures.assign(date=pd.to_datetime(temperatures["date"], utc=True))
    station_to_city = {station_id: city for city, station_id in city_stations.items()}
    temperatures["city"] = temperatures["station_id"].astype(str).map(station_to_city)
    hot_days = temperatures.loc[
        temperatures["city"].notna()
        & temperatures["date"].dt.year.between(first_year, last_completed_year)
        & (temperatures["value"] > hot_day_threshold)
    ].copy()
    hot_days["year"] = hot_days["date"].dt.year

    yearly_counts = (
        hot_days.groupby(["city", "year"], as_index=False)
        .size()
        .rename(columns={"size": "days_above_threshold"})
    )
    # A city-year absent from `yearly_counts` is ambiguous: never crossed the
    # threshold (a real 0), or no readings that year (should stay missing).
    # Distinguish using how many valid readings actually exist that year.
    yearly_observation_counts = (
        temperatures.loc[temperatures["city"].notna() & temperatures["date"].dt.year.between(first_year, last_completed_year)]
        .assign(year=lambda df: df["date"].dt.year)
        .groupby(["city", "year"], as_index=False)
        .size()
        .rename(columns={"size": "n_observations"})
    )
    city_years = pd.MultiIndex.from_product(
        [city_stations, range(first_year, last_completed_year + 1)],
        names=["city", "year"],
    ).to_frame(index=False)
    result = (
        city_years.merge(yearly_counts, on=["city", "year"], how="left")
        .merge(yearly_observation_counts, on=["city", "year"], how="left")
    )
    result["days_above_threshold"] = result["days_above_threshold"].fillna(0)
    result.loc[result["n_observations"].isna(), "days_above_threshold"] = pd.NA
    result["days_above_threshold"] = result["days_above_threshold"].astype("Int64")
    result["full_date"] = pd.to_datetime(result["year"].astype(str) + "-01-01", utc=True)
    return result[["city", "year", "full_date", "days_above_threshold"]]


def get_climate_change_indicators_data(
    city_stations: dict[str, str] | None = None,
    start_year: int = TREND_START_YEAR,
    baseline_start_year: int = ANOMALY_BASELINE_START_YEAR,
    baseline_end_year: int = ANOMALY_BASELINE_END_YEAR,
    hot_night_threshold: float = 20.0,
    heavy_rain_threshold: float = 20.0,
) -> pd.DataFrame:
    """Return annual anomaly, heat, and rainfall indicators for each city.

    ``city_stations`` maps city name to DWD station id; defaults to
    ``LONG_RUN_CITY_STATIONS``.

    Temperature anomalies use each city's ``baseline_start_year``-``baseline_end_year``
    mean annual temperature as the baseline. A hot night has minimum
    temperature above ``hot_night_threshold`` (°C); a heavy-rain day has
    precipitation above ``heavy_rain_threshold`` (mm). The current year's
    values are year-to-date.
    """
    city_stations = city_stations or LONG_RUN_CITY_STATIONS
    last_year = datetime.now(UTC).year
    observations = get_station_data(
        station_ids=list(city_stations.values()),
        start_date=f"{min(baseline_start_year, start_year)}-01-01",
        end_date=f"{last_year}-12-31",
        cache=True,
    )
    station_to_city = {station_id: city for city, station_id in city_stations.items()}
    values = observations[["station_id", "date", "parameter", "value"]].dropna()
    values = values.assign(date=pd.to_datetime(values["date"], utc=True))
    values["city"] = values["station_id"].astype(str).map(station_to_city)
    values = values.loc[
        values["city"].notna()
        & values["date"].dt.year.between(min(baseline_start_year, start_year), last_year)
    ].copy()
    values["year"] = values["date"].dt.year

    annual_mean = (
        values.loc[values["parameter"] == "temperature_air_mean_2m"]
        .groupby(["city", "year"], as_index=False)["value"]
        .mean()
        .rename(columns={"value": "annual_mean_temp"})
    )
    baseline = (
        annual_mean.loc[annual_mean["year"].between(baseline_start_year, baseline_end_year)]
        .groupby("city", as_index=False)["annual_mean_temp"]
        .mean()
        .rename(columns={"annual_mean_temp": "baseline_temp"})
    )
    city_years = pd.MultiIndex.from_product(
        [city_stations, range(start_year, last_year + 1)],
        names=["city", "year"],
    ).to_frame(index=False)
    result = city_years.merge(annual_mean, on=["city", "year"], how="left").merge(baseline, on="city", how="left")
    result["temperature_anomaly"] = result["annual_mean_temp"] - result["baseline_temp"]
    result["temperature_anomaly_5y"] = result.groupby("city")["temperature_anomaly"].transform(
        lambda series: series.rolling(window=5, min_periods=1).mean()
    )

    def annual_count(parameter: str, threshold: float, name: str) -> pd.DataFrame:
        parameter_values = values.loc[values["parameter"] == parameter]
        counts = (
            parameter_values.loc[parameter_values["value"] > threshold]
            .groupby(["city", "year"], as_index=False)
            .size()
            .rename(columns={"size": name})
        )
        # Same real-0-vs-missing distinction as get_hot_days_data.
        observation_counts = (
            parameter_values.groupby(["city", "year"], as_index=False)
            .size()
            .rename(columns={"size": "n_observations"})
        )
        merged = (
            city_years.merge(counts, on=["city", "year"], how="left")
            .merge(observation_counts, on=["city", "year"], how="left")
        )
        merged[name] = merged[name].fillna(0)
        merged.loc[merged["n_observations"].isna(), name] = pd.NA
        merged[name] = merged[name].astype("Int64")
        return merged[["city", "year", name]]

    hot_nights = annual_count("temperature_air_min_2m", hot_night_threshold, "hot_nights")
    heavy_rain_days = annual_count("precipitation_height", heavy_rain_threshold, "heavy_rain_days")
    result = result.merge(hot_nights, on=["city", "year"]).merge(heavy_rain_days, on=["city", "year"])
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


## Streamlit-cached wrappers ##################################################
# Thin `st.cache_data` layers over the functions above, so `app.py` and the
# view modules never need to import `streamlit` alongside the plain data
# functions or duplicate cache-key logic.


@st.cache_data(show_spinner="Loading station metadata from DWD...")
def load_stations() -> pd.DataFrame:
    return list_stations()


@st.cache_data(show_spinner="Checking data coverage for selected stations...")
def load_station_metadata(station_ids: list[str]) -> pd.DataFrame:
    return get_station_metadata(station_ids)


def stations_in_region(region: str, start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
    """Station metadata for a real clustering population: every station
    reporting at some point in [start_date, end_date], narrowed to one
    geographic half of Germany if ``region`` isn't "All Germany".

    Deterministically capped at MAX_REGION_STATIONS via an even spread
    across sorted station IDs (``np.linspace``), not a prefix, to stay
    spatially representative."""
    stations = load_stations()
    start_ts = pd.Timestamp(start_date, tz="UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC")
    active = stations[(stations["start_date"] <= end_ts) & (stations["end_date"] >= start_ts)]

    if region == "North":
        active = active[active["latitude"] >= _GERMANY_LAT_MIDPOINT]
    elif region == "South":
        active = active[active["latitude"] < _GERMANY_LAT_MIDPOINT]
    elif region == "East":
        active = active[active["longitude"] >= _GERMANY_LON_MIDPOINT]
    elif region == "West":
        active = active[active["longitude"] < _GERMANY_LON_MIDPOINT]

    active = active.sort_values("station_id").reset_index(drop=True)
    if len(active) > MAX_REGION_STATIONS:
        indices = np.linspace(0, len(active) - 1, MAX_REGION_STATIONS).round().astype(int)
        active = active.iloc[indices]
    return active


@st.cache_data(show_spinner="Fetching observations from DWD...")
def load_data(station_ids: list[str], start: str, end: str) -> pd.DataFrame:
    return get_station_data(station_ids, start, end)


def _region_cache_path(region: str, start_date: str, end_date: str) -> Path:
    dataset_key = "-".join(f"{resolution}-{dataset}" for resolution, dataset, *_ in REQUEST_PARAMETERS)
    safe_region = region.replace(" ", "-")
    return DATA_DIR / f"region-{safe_region}_{start_date}_{end_date}_{dataset_key}.parquet"


def get_region_station_data(region: str, station_ids: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Like get_station_data(), but disk-cached under a key derived from
    the region name instead of every station ID (which can run to 40 and
    make an unreasonably long filename).

    A second, independent cache layer on top of load_region_data()'s
    st.cache_data: this one persists on disk across server restarts, and
    is also what start_background_region_prefetch() writes into ahead of
    time, from outside any Streamlit script run."""
    cache_path = _region_cache_path(region, start_date, end_date)
    if cache_path.exists():
        return pd.read_parquet(cache_path)
    df = get_station_data(station_ids, start_date, end_date, cache=False)
    df.to_parquet(cache_path)
    return df


# Separate wrapper (not load_data()) so it gets its own spinner text --
# st.cache_data's message is fixed per-function.
@st.cache_data(
    show_spinner=(
        "Fetching weather data for this region. DWD serves one file per station, so pulling "
        "up to 40 stations at once can take up to a minute on first load..."
    )
)
def load_region_data(region: str, station_ids: list[str], start: str, end: str) -> pd.DataFrame:
    return get_region_station_data(region, station_ids, start, end)


# Warms get_region_station_data()'s on-disk cache for every region at the
# app's default date range, in a background thread, once per server process
# (the flag below makes repeat calls a no-op). Calls get_region_station_data()
# directly, not load_region_data() -- st.cache_data expects a real Streamlit
# script execution, which a background thread isn't.
_PREFETCH_LOCK = threading.Lock()
_PREFETCH_STARTED = False
DEFAULT_DATE_RANGE = ("2023-01-01", "2023-12-31")


def start_background_region_prefetch() -> None:
    global _PREFETCH_STARTED
    with _PREFETCH_LOCK:
        if _PREFETCH_STARTED:
            return
        _PREFETCH_STARTED = True

    def _run() -> None:
        start, end = DEFAULT_DATE_RANGE
        start_date, end_date = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        for region in REGION_OPTIONS:
            try:
                candidates = stations_in_region(region, start_date, end_date)
                if candidates.empty:
                    continue
                get_region_station_data(region, candidates["station_id"].tolist(), start, end)
            except Exception:
                # Best-effort warmup only; a real UI request surfaces genuine failures.
                pass

    threading.Thread(target=_run, name="region-prefetch", daemon=True).start()


@st.cache_data(show_spinner="Loading long-run city temperatures from DWD...")
def load_long_run_data(city_stations: dict[str, str], start_year: int, month: int) -> pd.DataFrame:
    return get_long_run_climate_data(city_stations, start_year=start_year, month=month)


@st.cache_data(show_spinner="Counting hot days from DWD observations...")
def load_hot_days_data(city_stations: dict[str, str], start_year: int, hot_day_threshold: float) -> pd.DataFrame:
    return get_hot_days_data(city_stations, start_year=start_year, hot_day_threshold=hot_day_threshold)


@st.cache_data(show_spinner="Calculating climate-change indicators from DWD observations...")
def load_climate_change_indicators(
    city_stations: dict[str, str],
    start_year: int,
    baseline_start_year: int,
    baseline_end_year: int,
    hot_night_threshold: float,
    heavy_rain_threshold: float,
) -> pd.DataFrame:
    return get_climate_change_indicators_data(
        city_stations,
        start_year=start_year,
        baseline_start_year=baseline_start_year,
        baseline_end_year=baseline_end_year,
        hot_night_threshold=hot_night_threshold,
        heavy_rain_threshold=heavy_rain_threshold,
    )


if __name__ == "__main__":
    # Quick smoke test: Berlin-Tempelhof, last full year of historical data.
    get_station_data(["00433"], "2023-01-01", "2023-12-31")
    print(get_long_run_climate_data())
