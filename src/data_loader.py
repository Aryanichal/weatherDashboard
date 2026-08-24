"""Fetch and locally cache DWD (Deutscher Wetterdienst) station observation data.

Uses the `wetterdienst` library, which wraps the DWD Climate Data Center (CDC)
open data FTP/HTTP archive. No API key is required.

wetterdienst is pre-1.0 and its API changes between versions, so the version
is pinned in requirements.txt. If these calls start failing after an
`pip install -U wetterdienst`, check the "Python API" docs for the installed
version: https://wetterdienst.readthedocs.io/
"""

from pathlib import Path

import pandas as pd
from wetterdienst.provider.dwd.observation import DwdObservationRequest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

RESOLUTION = "daily"
DATASET = "climate_summary"


def list_stations() -> pd.DataFrame:
    """Return metadata (station_id, name, latitude, longitude, height, ...)
    for every DWD station that reports the daily climate_summary dataset.
    """
    request = DwdObservationRequest(
        parameters=[(RESOLUTION, DATASET)],
    )
    return request.all().df.to_pandas()


def get_station_data(
    station_ids: list[str],
    start_date: str,
    end_date: str,
    cache: bool = True,
) -> pd.DataFrame:
    """Return daily climate_summary observations for the given station ids.

    Parameters
    ----------
    station_ids: DWD station ids, e.g. ["00433", "01048"] (Berlin-Tempelhof, Dresden-Klotzsche)
    start_date / end_date: "YYYY-MM-DD"
    cache: reuse a local parquet cache under data/ instead of re-downloading
    """
    cache_key = f"{'-'.join(sorted(station_ids))}_{start_date}_{end_date}.parquet"
    cache_path = DATA_DIR / cache_key
    if cache and cache_path.exists():
        return pd.read_parquet(cache_path)

    request = DwdObservationRequest(
        parameters=[(RESOLUTION, DATASET)],
        start_date=start_date,
        end_date=end_date,
    ).filter_by_station_id(station_id=station_ids)

    df = request.values.all().df.to_pandas()

    if cache:
        df.to_parquet(cache_path)

    return df


if __name__ == "__main__":
    # Quick smoke test: Berlin-Tempelhof, last full year of historical data.
    df = get_station_data(["00433"], "2023-01-01", "2023-12-31")
    print(df.head())
    print(df["parameter"].unique())
