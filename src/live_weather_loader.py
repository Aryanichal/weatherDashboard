"""Fetch live/near-term forecast weather data from DWD's MOSMIX product.

Uses the `wetterdienst` library's DwdMosmixRequest, which wraps DWD's MOSMIX
(Model Output Statistics) forecast -- a genuinely different DWD product from
the daily climate_summary observations the rest of this dashboard uses (see
src/data_loader.py): MOSMIX is numerical-model output re-issued ~4x/day,
covering roughly the next 10 days at hourly resolution, and it uses its own
station catalog (WMO-style 5-digit ids, e.g. "10865" for Muenchen-Stadt) --
NOT the DWD climate-observation station ids used elsewhere in this app (e.g.
"01048"), so a station selection made in the other tabs doesn't carry over
here. No API key is required, same as the rest of the app's DWD access.

Reference: DWD's MOSMIX documentation --
https://www.dwd.de/DE/leistungen/opendata/help/modelle/mosmix_erlaeuterung_de.pdf
"""

import math

import pandas as pd
import streamlit as st
from wetterdienst.provider.dwd.mosmix import DwdForecastDate, DwdMosmixRequest

from src.data_loader import SETTINGS

LOCAL_TIMEZONE = "Europe/Berlin"

# Curated MOSMIX station ids for Germany's ~40 largest cities by
# population. MOSMIX's own station catalog has ~5,600 entries (airports,
# small automatic stations, several near-duplicates per city, ...), so
# picking straight from the full list isn't practical for a simple
# dropdown -- these were looked up by name from
# DwdMosmixRequest(...).all().df, picked as each city's main/best-known
# station, and each verified individually to actually return every one of
# PARAMETERS (a handful of MOSMIX stations only carry a subset). Most ids
# are 5-digit numeric (DWD's main synoptic-station catalog, the same
# family the original 12 cities' ids came from); a few larger cities
# (Duisburg, Bochum, Wuppertal, Gelsenkirchen, Krefeld, Oberhausen,
# Rostock, Muenster, Mainz) only have a smaller alphanumeric-id automatic
# station nearby -- confirmed to carry the full parameter set too.
CITY_STATIONS = {
    "Berlin": "10384",  # Berlin-Tempelhof
    "Hamburg": "10147",  # Hamburg-Fuhlsbuettel
    "Munich": "10865",  # Muenchen-Stadt
    "Cologne": "10513",  # Koeln/Bonn
    "Frankfurt": "10637",  # Frankfurt/Main
    "Stuttgart": "10739",  # Stuttgart-Schnarrenberg
    "Duesseldorf": "10400",
    "Leipzig": "10471",
    "Dortmund": "10416",
    "Essen": "10410",
    "Bremen": "10224",
    "Dresden": "10487",  # Dresden-Stadt
    "Hannover": "10338",
    "Nuremberg": "10763",
    "Duisburg": "K1188",
    "Bochum": "H432",
    "Wuppertal": "N8322",  # Wuppertal-Barmen
    "Bielefeld": "10326",
    "Bonn": "10517",  # Bonn-Friesdorf
    "Muenster": "P0036",  # Muenster Zentrum
    "Mannheim": "10729",
    "Karlsruhe": "10727",
    "Augsburg": "10852",
    "Wiesbaden": "10633",
    "Moenchengladbach": "10403",
    "Gelsenkirchen": "K1115",
    "Braunschweig": "10348",
    "Chemnitz": "10577",
    "Kiel": "10046",  # Kiel-Holtenau
    "Aachen": "10501",
    "Halle": "10466",  # Halle (Saale)
    "Magdeburg": "10361",
    "Freiburg": "10803",  # Freiburg im Breisgau
    "Krefeld": "N8527",
    "Luebeck": "10156",
    "Mainz": "K2613",
    "Erfurt": "10554",
    "Oberhausen": "N9079",
    "Rostock": "P0175",  # Rostock-Stadt
    "Kassel": "10438",
}

# (latitude, longitude) per curated city, for the small "where is this on
# the map" widget on the Live Weather view -- read off the same MOSMIX
# station list CITY_STATIONS' ids were picked from, not re-derived from
# CITY_STATIONS itself, since a station's coordinates aren't otherwise
# available without a network call.
CITY_COORDINATES = {
    "Berlin": (52.47, 13.40),
    "Hamburg": (53.63, 10.00),
    "Munich": (48.17, 11.53),
    "Cologne": (50.87, 7.17),
    "Frankfurt": (50.05, 8.60),
    "Stuttgart": (48.83, 9.20),
    "Duesseldorf": (51.30, 6.77),
    "Leipzig": (51.32, 12.42),
    "Dortmund": (51.52, 7.62),
    "Essen": (51.40, 6.97),
    "Bremen": (53.05, 8.80),
    "Dresden": (51.05, 13.73),
    "Hannover": (52.47, 9.68),
    "Nuremberg": (49.50, 11.05),
    "Duisburg": (51.47, 6.73),
    "Bochum": (51.48, 7.27),
    "Wuppertal": (51.27, 7.18),
    "Bielefeld": (51.97, 8.55),
    "Bonn": (50.70, 7.15),
    "Muenster": (51.97, 7.63),
    "Mannheim": (49.52, 8.55),
    "Karlsruhe": (49.03, 8.37),
    "Augsburg": (48.43, 10.93),
    "Wiesbaden": (50.05, 8.33),
    "Moenchengladbach": (51.23, 6.50),
    "Gelsenkirchen": (51.50, 7.10),
    "Braunschweig": (52.28, 10.45),
    "Chemnitz": (50.78, 12.87),
    "Kiel": (54.38, 10.15),
    "Aachen": (50.78, 6.10),
    "Halle": (51.52, 11.95),
    "Magdeburg": (52.12, 11.58),
    "Freiburg": (48.02, 7.83),
    "Krefeld": (51.30, 6.53),
    "Luebeck": (53.82, 10.70),
    "Mainz": (49.98, 8.27),
    "Erfurt": (50.98, 10.97),
    "Oberhausen": (51.52, 6.82),
    "Rostock": (54.08, 12.13),
    "Kassel": (51.30, 9.45),
}

# The subset of MOSMIX's ~120 available parameters this view actually
# shows -- a normal weather-app front page, not another analysis tab, so
# this is deliberately narrow. See DwdMosmixMetadata's "large" dataset
# (MOSMIX_L) for the full parameter list.
PARAMETERS = [
    "temperature_air_mean_2m",
    "temperature_dew_point_mean_2m",
    "wind_speed",
    "wind_direction",
    "wind_gust_max_last_1h",
    "precipitation_height_significant_weather_last_1h",
    "pressure_air_site_reduced",
    "cloud_cover_total",
    "weather_significant",
]

UNITS = {
    "temperature_air_mean_2m": "°C",
    "temperature_dew_point_mean_2m": "°C",
    "wind_speed": "m/s",
    "wind_gust_max_last_1h": "m/s",
    "precipitation_height_significant_weather_last_1h": "mm",
    "pressure_air_site_reduced": "hPa",
    "cloud_cover_total": "%",
}

# weather_significant is DWD's forecast rendering of the WMO "present
# weather" code table (WMO code table 4677/4680) -- 0-3 are cloud-cover-only
# categories (no precipitation), then increasing code ranges for fog,
# drizzle, rain, snow, showers, and thunderstorms. DWD's forecast only ever
# emits a subset of the full 0-99 table (codes describing *past* weather
# evolution, e.g. "clouds dissolving", don't apply to a forecast), so this
# buckets by range rather than listing every individual code.
#
# The 5th column is a real DWD parameter name whose existing color category
# (see PARAMETER_COLOR_CATEGORY in src/analysis.py) matches that bucket's
# weather -- clear reuses "temperature"'s warm gold, cloudy/foggy reuses
# "neutral"'s grey, anything wet reuses "precipitation"'s blue. Passing one
# of these through st.session_state["active_theme_parameter"] is how this
# view re-themes the whole page (background, nav row, ...) via the same
# apply_dynamic_theme() mechanism every other tab's "Parameter" dropdown
# already drives, rather than adding a second theming path.
_TEMPERATURE_THEME_PARAMETER = "temperature_air_mean_2m"
_NEUTRAL_THEME_PARAMETER = "cloud_cover_total"
_PRECIPITATION_THEME_PARAMETER = "precipitation_height"

_WEATHER_CODE_ICONS: list[tuple[int, int, str, str, str]] = [
    (0, 0, "☀️", "Clear sky", _TEMPERATURE_THEME_PARAMETER),
    (1, 1, "🌤️", "Mostly clear", _TEMPERATURE_THEME_PARAMETER),
    (2, 2, "⛅", "Partly cloudy", _NEUTRAL_THEME_PARAMETER),
    (3, 3, "☁️", "Overcast", _NEUTRAL_THEME_PARAMETER),
    (4, 39, "🌫️", "Haze", _NEUTRAL_THEME_PARAMETER),
    (40, 49, "🌫️", "Fog", _NEUTRAL_THEME_PARAMETER),
    (50, 59, "🌦️", "Drizzle", _PRECIPITATION_THEME_PARAMETER),
    (60, 65, "🌧️", "Rain", _PRECIPITATION_THEME_PARAMETER),
    (66, 69, "🌧️", "Freezing rain", _PRECIPITATION_THEME_PARAMETER),
    (70, 79, "🌨️", "Snow", _PRECIPITATION_THEME_PARAMETER),
    (80, 84, "🌦️", "Rain showers", _PRECIPITATION_THEME_PARAMETER),
    (85, 89, "🌨️", "Snow showers", _PRECIPITATION_THEME_PARAMETER),
    (90, 99, "⛈️", "Thunderstorm", _PRECIPITATION_THEME_PARAMETER),
]


class LiveWeatherFetchError(Exception):
    """Raised when DWD's MOSMIX forecast can't be fetched or parsed.
    Callers (the Live Weather view) should catch this and show a
    plain-language message instead of letting wetterdienst's/an XML
    parser's traceback surface -- mirrors WeatherDataFetchError in
    src/data_loader.py."""


def weather_icon_label_and_theme(code: float | None) -> tuple[str, str, str]:
    """(emoji, description, theme_parameter) for one weather_significant
    code -- see _WEATHER_CODE_ICONS above for the source table.
    ``theme_parameter`` is a real DWD parameter name to feed into
    apply_dynamic_theme()/st.session_state["active_theme_parameter"]."""
    if code is None or pd.isna(code):
        return "❓", "Unknown", _NEUTRAL_THEME_PARAMETER
    code_int = int(round(code))
    for low, high, icon, label, theme_parameter in _WEATHER_CODE_ICONS:
        if low <= code_int <= high:
            return icon, label, theme_parameter
    return "❓", "Unknown", _NEUTRAL_THEME_PARAMETER


def relative_humidity_percent(temperature_c: float | None, dewpoint_c: float | None) -> float | None:
    """Relative humidity (%) via the Magnus formula -- MOSMIX reports dew
    point rather than relative humidity directly. a/b are the Alduchov &
    Eskridge (1996) Magnus-formula coefficients (a=17.625, b=243.04 degC),
    a standard, widely-cited approximation for this conversion."""
    if temperature_c is None or dewpoint_c is None or pd.isna(temperature_c) or pd.isna(dewpoint_c):
        return None
    a, b = 17.625, 243.04
    gamma_dew = (a * dewpoint_c) / (b + dewpoint_c)
    gamma_air = (a * temperature_c) / (b + temperature_c)
    return 100 * math.exp(gamma_dew - gamma_air)


@st.cache_data(ttl=900, show_spinner="Fetching live weather from DWD...")
def fetch_forecast(station_id: str) -> pd.DataFrame:
    """Return the latest MOSMIX forecast for one station as a tidy
    (station_id, parameter, date, value) frame -- the same long/tidy shape
    src/data_loader.py's load_data() returns -- with `date` already
    converted from DWD's UTC timestamps to Europe/Berlin local time.

    Cached for 15 minutes (`ttl=900`). Unlike the rest of this app's
    @st.cache_data uses, which cache historical data indefinitely (it never
    changes), MOSMIX is genuinely live and DWD re-issues it ~4x/day, so an
    indefinite cache would silently go stale.
    """
    request = DwdMosmixRequest(
        parameters=[("hourly", "large", parameter) for parameter in PARAMETERS],
        issue=DwdForecastDate.LATEST,
        settings=SETTINGS,
    ).filter_by_station_id(station_id=[station_id])

    try:
        df = request.values.all().df.to_pandas()
    except Exception as exc:
        raise LiveWeatherFetchError(
            "DWD's live forecast (MOSMIX) is temporarily unreachable, or returned data "
            "that couldn't be read. Please try again in a moment."
        ) from exc

    if df.empty:
        raise LiveWeatherFetchError(f"DWD returned no forecast data for station {station_id}.")

    df["date"] = df["date"].dt.tz_convert(LOCAL_TIMEZONE)
    return df


def current_snapshot(df: pd.DataFrame) -> dict[str, object]:
    """The forecast row nearest to right now, reshaped into one flat dict
    for the "current conditions" hero card."""
    pivot = df.pivot(index="date", columns="parameter", values="value").sort_index()
    now = pd.Timestamp.now(tz=LOCAL_TIMEZONE)
    nearest_pos = pivot.index.get_indexer([now], method="nearest")[0]
    row = pivot.iloc[nearest_pos]
    as_of = pivot.index[nearest_pos]

    temperature = row.get("temperature_air_mean_2m")
    dewpoint = row.get("temperature_dew_point_mean_2m")
    cloud_cover = row.get("cloud_cover_total")
    icon, label, theme_parameter = weather_icon_label_and_theme(row.get("weather_significant"))

    return {
        "as_of": as_of,
        "temperature_c": temperature,
        "humidity_pct": relative_humidity_percent(temperature, dewpoint),
        "wind_speed_ms": row.get("wind_speed"),
        "wind_gust_ms": row.get("wind_gust_max_last_1h"),
        "precipitation_mm": row.get("precipitation_height_significant_weather_last_1h"),
        "pressure_hpa": row.get("pressure_air_site_reduced"),
        "cloud_cover_pct": None if cloud_cover is None or pd.isna(cloud_cover) else cloud_cover * 100,
        "icon": icon,
        "label": label,
        "theme_parameter": theme_parameter,
    }


def daily_summary(df: pd.DataFrame, days: int = 7) -> pd.DataFrame:
    """One row per upcoming local calendar day: high/low temperature,
    total precipitation, max wind gust, and a representative weather
    icon/label (the forecast nearest to local noon that day).

    Note for the report's limitations section: MOSMIX only forecasts
    forward from its issue time (~now), so "today" only ever covers the
    remaining hours of the day, not the full 24h -- its high/low can
    understate the day's actual range if run later in the afternoon.
    """
    pivot = df.pivot(index="date", columns="parameter", values="value").sort_index()
    local_dates = pivot.index.date
    unique_dates = sorted(set(local_dates))[:days]

    rows = []
    for date in unique_dates:
        day_df = pivot.loc[local_dates == date]
        noon = pd.Timestamp(date, tz=LOCAL_TIMEZONE) + pd.Timedelta(hours=12)
        nearest_pos = day_df.index.get_indexer([noon], method="nearest")[0]
        representative = day_df.iloc[nearest_pos]
        icon, label, _theme_parameter = weather_icon_label_and_theme(representative.get("weather_significant"))

        rows.append(
            {
                "date": date,
                "high_c": day_df["temperature_air_mean_2m"].max(),
                "low_c": day_df["temperature_air_mean_2m"].min(),
                "precipitation_mm": day_df["precipitation_height_significant_weather_last_1h"].sum(),
                "wind_gust_max_ms": day_df["wind_gust_max_last_1h"].max(),
                "icon": icon,
                "label": label,
            }
        )
    return pd.DataFrame(rows)
