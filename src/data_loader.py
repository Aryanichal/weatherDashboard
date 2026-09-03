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

# DWD ships each station's data as a ZIP archive; wetterdienst raises one of
# these two when an archive can't be read -- BadZipFile for a corrupted/
# truncated download, ProductFileNotFoundError when the archive unpacked
# fine but didn't contain the expected "produkt*" file. get_station_data()
# below retries once with caching disabled before giving up (see its
# docstring), so by the time either of these actually surfaces to a caller,
# retrying transparently already didn't help.
_ARCHIVE_ERRORS = (BadZipFile, ProductFileNotFoundError)


class WeatherDataFetchError(Exception):
    """Raised when DWD's observation archive can't be read, even after
    get_station_data()'s own retry with the local cache bypassed. Callers
    (view modules) should catch this and show a plain-language message
    instead of letting the original zipfile/wetterdienst traceback surface,
    since neither means anything to a user picking weather stations."""

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

# Clustering needs a real population (hundreds of stations), not the
# handful a user picks by hand in the station multiselect -- see
# stations_in_region() below. Splits are at the midpoint of the network's
# own lat/lon range, not federal-state borders or the old East/West
# Germany line, since climate tracks latitude/altitude/coastal proximity
# far more than administrative or historical political boundaries.
REGION_OPTIONS = ["All Germany", "North", "South", "East", "West"]
_GERMANY_LAT_MIDPOINT = 51.2
_GERMANY_LON_MIDPOINT = 10.5
# Capped so a wide date range (or "All Germany") still fetches in a
# reasonable time -- climate-zone-style clustering has no need for
# literally every station DWD has ever operated. DWD ships one ZIP
# archive per station (see get_station_data()'s docstring), so fetch
# time scales with station count and is dominated by per-station network
# round-trips rather than data volume -- empirically, 40 stations took
# anywhere from ~15s to ~50s depending on DWD server conditions, and 100+
# occasionally spiked past a minute. 40 is chosen as a balance between a
# real population (order-of-magnitude beyond a hand-picked handful) and
# staying inside what's tolerable for an interactive rerun.
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


# See get_station_data()'s own comment at its call site for the measured
# speedup this buys; 8 is a courtesy ceiling on concurrent connections to
# a public government server, not a value that was observed to fail.
_MAX_FETCH_WORKERS = 8


def _fetch_station_chunk(station_ids: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch one chunk of stations, with the same corrupted-archive retry
    get_station_data() has always done -- scoped to just this chunk now
    rather than the whole request, so one bad station's download doesn't
    force re-fetching every other station too."""
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

    Parameters
    ----------
    station_ids: DWD station ids, e.g. ["00433", "01048"] (Berlin-Tempelhof, Dresden-Klotzsche)
    start_date / end_date: "YYYY-MM-DD"
    cache: reuse a local parquet cache under data/ instead of re-downloading

    Raises
    ------
    WeatherDataFetchError
        If DWD's per-station ZIP archive can't be read even after a retry
        (see below) -- e.g. an interrupted download left a truncated file,
        or DWD's own server briefly served a bad copy. wetterdienst caches
        the downloaded archive under SETTINGS.cache_dir with only a 5-minute
        TTL (see download_climate_observations_data() in wetterdienst's own
        download.py), so a corrupted download would otherwise keep failing
        identically for up to 5 minutes -- every retry would just re-read
        the same corrupted bytes back off disk. Retrying once with a
        cache-disabled copy of the settings instead forces an immediate
        fresh download, which self-heals the common case (a one-off
        network blip) without the caller needing to wait out the TTL or
        clear the cache directory by hand.
    """
    # Include requested datasets in the cache name so a change from, for
    # example, climate summaries to wind data triggers a fresh download.
    dataset_key = "-".join(f"{resolution}-{dataset}" for resolution, dataset, *_ in REQUEST_PARAMETERS)
    cache_key = f"{'-'.join(sorted(station_ids))}_{start_date}_{end_date}_{dataset_key}.parquet"
    cache_path = DATA_DIR / cache_key
    if cache and cache_path.exists():
        return pd.read_parquet(cache_path)

    # wetterdienst fetches each station's ZIP archive one at a time inside
    # a single request.values.all() call -- measured empirically at ~3.4s
    # per station sequentially. Splitting station_ids into chunks and
    # fetching them concurrently (network I/O releases the GIL, so threads
    # work fine here) measured a ~22x speedup on a 40-station fetch (134s
    # -> 6s) with zero errors and identical row counts, so it's the single
    # biggest lever for this app's slowest operation. _MAX_FETCH_WORKERS
    # caps concurrency well short of what was tested clean, out of
    # courtesy to a public government server rather than because higher
    # was observed to fail.
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
            # All-or-nothing, matching the single-chunk behavior above --
            # a station silently missing from a clustering population
            # because its one chunk failed is a worse outcome than the
            # whole fetch failing loudly and being retried.
            raise WeatherDataFetchError(
                "DWD's weather data archive is temporarily unreachable or returned a "
                "corrupted file. This is usually transient -- please try again in a "
                "moment, or try again with fewer stations or a narrower date range."
            ) from first_error

    if len(frames) > 1:
        # Threads finish in whatever order the network happens to respond,
        # so a naive concat would leave row order (and anything downstream
        # that infers a station's plotted color from first-appearance
        # order, e.g. Time Series' legend) shuffled differently on every
        # rerun. Sorting restores the same deterministic order the old
        # single sequential request always produced.
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
    # A city-year absent from `yearly_counts` is ambiguous: it means either
    # "the station reported all year and never crossed the threshold" (a
    # real 0) or "the station reported nothing that year" (closed, not yet
    # installed, data gap -- should be missing, not a false 0). Distinguish
    # them using how many valid daily readings actually exist for that
    # city-year, from before the threshold filter was applied.
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
        # Distinguish "reported all year, never crossed the threshold" (a
        # real 0) from "no readings for this parameter that year" (station
        # closed / not yet installed / data gap -- must stay missing, not
        # a false 0), the same way get_hot_days_data does.
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
    """Station metadata (station_id, name, latitude, longitude, ...) for a
    real clustering population: every station that was actually reporting
    at some point in [start_date, end_date] (excludes ones that closed
    decades earlier or hadn't opened yet, which would just fetch as empty),
    narrowed to one geographic half of Germany if ``region`` isn't
    "All Germany" (see REGION_OPTIONS/the lat/lon midpoints above).

    Deterministically capped at MAX_REGION_STATIONS by taking an even
    spread across station IDs sorted ascending (via ``np.linspace``
    indices) rather than the first N -- a plain prefix would arbitrarily
    favor however DWD happened to assign IDs instead of staying spatially
    representative of the requested region.
    """
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
    """Like get_station_data(), but disk-cached under a short key derived
    from the region name (e.g. "region-North_2023-01-01_2023-12-31_....parquet")
    instead of every station ID joined together -- a region's station list
    can run to 40 IDs, which would make an unreasonably long filename via
    get_station_data()'s own cache= keying, and the region name is already
    a perfectly good cache key on its own, since stations_in_region() is
    itself deterministic for a given (region, date range).

    This is a second, independent cache layer on top of load_region_data()'s
    st.cache_data one below: that one only lives as long as the current
    server process, this one persists on disk across restarts -- so a
    region/date-range combination already fetched once stays instant even
    after redeploying or restarting the app, not just within one running
    session. Also what start_background_region_prefetch() below writes
    into ahead of time, from outside any Streamlit script run.
    """
    cache_path = _region_cache_path(region, start_date, end_date)
    if cache_path.exists():
        return pd.read_parquet(cache_path)
    df = get_station_data(station_ids, start_date, end_date, cache=False)
    df.to_parquet(cache_path)
    return df


# A separate cached wrapper around the exact same fetch, purely so
# clustering's region-sized requests (see stations_in_region() above) get
# their own explanatory spinner text instead of load_data()'s generic one
# -- st.cache_data's show_spinner message is fixed per-function, not
# overridable per call, and "up to a minute" with no reason reads as the
# app hanging. Keeping this as a distinct function also means its cache
# entries don't collide with load_data()'s if both happen to request an
# identical station list, which is harmless (Streamlit just caches twice).
@st.cache_data(
    show_spinner=(
        "Fetching weather data for this region. DWD serves one file per station, so pulling "
        "up to 40 stations at once can take up to a minute on first load..."
    )
)
def load_region_data(region: str, station_ids: list[str], start: str, end: str) -> pd.DataFrame:
    return get_region_station_data(region, station_ids, start, end)


# Warms get_region_station_data()'s on-disk cache for every region, at the
# app's own default date range, in a background thread -- once per server
# process (the module-level flag below is what makes repeat calls, e.g.
# every Streamlit rerun, a no-op instead of spawning a new thread each
# time). Means a user who opens Clustering or Map's cluster mode after the
# app has been running a while finds the default date range already
# cached, instead of paying the up-to-a-minute DWD fetch right when
# they're waiting on it -- even if nobody has visited those tabs yet this
# session, since st.cache_data's own cache (and this disk cache) are both
# shared across every session on this server process, not per-user.
#
# Deliberately calls get_region_station_data() directly rather than
# load_region_data() -- st.cache_data's machinery expects to run inside a
# real Streamlit script execution (for its spinner, mainly), which a
# background thread started at import time isn't; the plain function only
# touches the disk cache, which is exactly what needs pre-warming here.
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
                # Best-effort warmup only -- a real request from the UI
                # later will surface any genuine fetch problem properly
                # (as a WeatherDataFetchError shown to the user), so a
                # background failure here should stay silent rather than
                # crash a thread nothing is watching.
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
