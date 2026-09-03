"""Live Weather tab: current conditions and upcoming forecast for one
selected city, from DWD's MOSMIX forecast product (src/live_weather_loader.py).
Doesn't use the shared station-multiselect/date-range row from app.py --
MOSMIX has no date range and its own station catalog."""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analysis import categorize_parameter
from src.live_weather_loader import (
    CITY_COORDINATES,
    CITY_STATIONS,
    LiveWeatherFetchError,
    current_snapshot,
    daily_summary,
    fetch_forecast,
)
from src.ui_theme import ACCENT_HEX_BY_CATEGORY, chart_card, style_fig
from src.views.common import render_section_label

_DEFAULT_CITY = "Munich"


def _format(value: float | None, decimals: int, unit: str) -> str:
    return "—" if value is None else f"{value:.{decimals}f} {unit}".strip()


def _day_label(date, index: int) -> str:
    return "Today" if index == 0 else date.strftime("%a")


def _render_hero(city: str, snapshot: dict) -> None:
    """Current-conditions block -- icon, temperature, city name, description
    -- sits unboxed directly on the page background (no st.container(), so
    it skips the app's global "card" styling)."""
    st.markdown(
        f'<div style="font-size:1.2rem; font-weight:600; '
        f'color:var(--m3-on-primary-container, #1E4469);">{city}</div>'
        f'<div style="display:flex; align-items:center; gap:0.85rem;">'
        f'<span style="font-size:3.4rem; line-height:1;">{snapshot["icon"]}</span>'
        f'<span style="font-size:3.4rem; font-weight:700; line-height:1; '
        f'color:var(--m3-on-primary-container, #1E4469);">'
        f'{_format(snapshot["temperature_c"], 0, "°C")}</span>'
        f'</div>'
        f'<div style="font-size:1.05rem; opacity:0.75; margin-top:0.3rem;">{snapshot["label"]}</div>',
        unsafe_allow_html=True,
    )


_MAP_CARD_KEY = "live-weather-mini-map"


def _render_mini_map(city: str, snapshot: dict) -> None:
    """A small "where is this" map: a single dot at the selected city, marker
    color following the page's current weather theme."""
    lat, lon = CITY_COORDINATES[city]
    accent_hex = ACCENT_HEX_BY_CATEGORY[categorize_parameter(snapshot["theme_parameter"])]

    fig = px.scatter_map(
        {"lat": [lat], "lon": [lon]}, lat="lat", lon="lon",
        zoom=8.5, map_style="open-street-map",
    )
    fig.update_traces(mode="markers", marker=dict(size=13, color=accent_hex), hoverinfo="skip")
    fig.update_layout(height=300, showlegend=False)
    style_fig(fig)
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
    st.markdown(
        f'<style>div[data-testid="stVerticalBlock"][class*="{_MAP_CARD_KEY}"] {{ '
        f"padding: 0 !important; "
        f"}}</style>",
        unsafe_allow_html=True,
    )
    with chart_card(key=_MAP_CARD_KEY):
        st.plotly_chart(
            fig, width="stretch",
            config={"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]},
        )


_STATS_CARD_KEY = "live-weather-stats"


def _render_parameters(snapshot: dict) -> None:
    """Humidity/wind/gusts/precipitation/pressure/cloud cover as one compact,
    fit-content horizontal strip."""
    stat_defs = [
        ("Humidity", _format(snapshot["humidity_pct"], 0, "%")),
        ("Wind", _format(snapshot["wind_speed_ms"], 1, "m/s")),
        ("Gusts", _format(snapshot["wind_gust_ms"], 1, "m/s")),
        ("Precipitation", _format(snapshot["precipitation_mm"], 1, "mm")),
        ("Pressure", _format(snapshot["pressure_hpa"], 0, "hPa")),
        ("Cloud cover", _format(snapshot["cloud_cover_pct"], 0, "%")),
    ]
    items = "".join(
        f'<div style="flex:0 0 auto; min-width:0; padding:0 1.6rem 0 0;">'
        f'<div style="font-size:0.72rem; font-weight:600; text-transform:uppercase; '
        f'letter-spacing:0.06em; opacity:0.6; white-space:nowrap;">{label}</div>'
        f'<div style="font-size:1.35rem; font-weight:700; white-space:nowrap; margin-top:0.4rem; '
        f'color:var(--m3-on-primary-container, #1E4469);">{value}</div></div>'
        for label, value in stat_defs
    )

    st.markdown(
        f'<style>[class*="{_STATS_CARD_KEY}"] {{ '
        f"width: fit-content !important; padding: 1.6rem 2.2rem !important; "
        f"}}</style>",
        unsafe_allow_html=True,
    )
    with chart_card(key=_STATS_CARD_KEY):
        st.markdown(
            f'<div style="display:flex; flex-direction:row; align-items:flex-end;">{items}</div>',
            unsafe_allow_html=True,
        )


_DAILY_STRIP_CARD_KEY = "live-weather-daily-strip"


def _render_daily_strip(daily) -> None:
    """One compact, fit-content horizontal strip -- all days as columns
    inside a single chart_card(), scrolling horizontally if needed."""
    st.markdown('<div style="margin-top: 2rem;"></div>', unsafe_allow_html=True)
    render_section_label("Next days", style="header")
    items = "".join(
        f'<div style="flex:0 0 auto; min-width:58px; text-align:center; padding:0 0.72rem;">'
        f'<div style="font-size:0.85rem; font-weight:600; opacity:0.85;">{_day_label(day["date"], i)}</div>'
        f'<div style="font-size:1.35rem; margin:0.3rem 0;">{day["icon"]}</div>'
        f'<div style="font-size:0.85rem; white-space:nowrap;">'
        f'<span style="font-weight:700;">{_format(day["high_c"], 0, "°")}</span> '
        f'<span style="opacity:0.55;">{_format(day["low_c"], 0, "°")}</span></div>'
        "</div>"
        for i, (_, day) in enumerate(daily.iterrows())
    )
    st.markdown(
        f'<style>[class*="{_DAILY_STRIP_CARD_KEY}"] {{ '
        f"width: fit-content !important; "
        f"padding-left: 1rem !important; padding-right: 1rem !important; "
        f"}}</style>",
        unsafe_allow_html=True,
    )
    with chart_card(key=_DAILY_STRIP_CARD_KEY):
        st.markdown(
            f'<div style="display:flex; overflow-x:auto; align-items:flex-start;">{items}</div>',
            unsafe_allow_html=True,
        )


_TEN_DAY_CARD_KEY = "live-weather-ten-day"


def _render_ten_day_forecast(daily) -> None:
    """One row per day: label, icon, low, a range bar, high -- the bar's
    position/width are [low, high] scaled against the forecast's overall
    min/max, like a typical weather app's 10-day list."""
    render_section_label("10-Day Forecast", style="header")

    global_low = daily["low_c"].min()
    global_high = daily["high_c"].max()
    span = max(global_high - global_low, 1e-6)

    with chart_card(key=_TEN_DAY_CARD_KEY):
        n = len(daily)
        for i, (_, day) in enumerate(daily.iterrows()):
            left_pct = (day["low_c"] - global_low) / span * 100
            width_pct = max((day["high_c"] - day["low_c"]) / span * 100, 6)

            label_col, icon_col, low_col, bar_col, high_col = st.columns([1.3, 0.7, 0.7, 3.6, 0.7])
            with label_col:
                st.markdown(
                    f'<div style="padding-top:0.35rem; font-weight:600;">{_day_label(day["date"], i)}</div>',
                    unsafe_allow_html=True,
                )
            with icon_col:
                st.markdown(
                    f'<div style="text-align:center; font-size:1.25rem;">{day["icon"]}</div>',
                    unsafe_allow_html=True,
                )
            with low_col:
                st.markdown(
                    f'<div style="text-align:right; padding-top:0.35rem; opacity:0.6;">'
                    f'{_format(day["low_c"], 0, "°")}</div>',
                    unsafe_allow_html=True,
                )
            with bar_col:
                st.markdown(
                    f'<div style="position:relative; height:6px; margin-top:1rem; '
                    f'background:var(--m3-outline-variant, #B7C6D7); border-radius:3px;">'
                    f'<div style="position:absolute; left:{left_pct:.1f}%; width:{width_pct:.1f}%; '
                    f'height:6px; border-radius:3px; '
                    f'background:linear-gradient(90deg, #4FA8E0, #E0A030);"></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with high_col:
                st.markdown(
                    f'<div style="padding-top:0.35rem; font-weight:700;">{_format(day["high_c"], 0, "°")}</div>',
                    unsafe_allow_html=True,
                )
            if i < n - 1:
                st.markdown(
                    '<hr style="margin:0.25rem 0; border:none; '
                    'border-top:1px solid var(--m3-outline-variant, #B7C6D7); opacity:0.5;">',
                    unsafe_allow_html=True,
                )


_HOURLY_CHART_CARD_KEY = "live-weather-hourly-chart"


def _render_hourly_chart(df, snapshot: dict) -> None:
    render_section_label("Next 48 hours", style="header")
    pivot = df.pivot(index="date", columns="parameter", values="value").sort_index()
    horizon = pivot.iloc[:48]

    # Same accent as the hero icon, mini-map marker, and page background.
    accent_hex = ACCENT_HEX_BY_CATEGORY[categorize_parameter(snapshot["theme_parameter"])]
    accent_r, accent_g, accent_b = (int(accent_hex.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=horizon.index,
            y=horizon["temperature_air_mean_2m"],
            mode="lines",
            name="Temperature",
            line=dict(width=2, color=accent_hex),
            fill="tozeroy",
            fillcolor=f"rgba({accent_r}, {accent_g}, {accent_b}, 0.12)",
        )
    )
    # Height tuned to match the 10-day forecast card's total height.
    fig.update_layout(title="Hourly temperature", yaxis_title="°C", height=324)
    style_fig(fig)
    fig.update_layout(margin=dict(t=40, b=32, l=40, r=16))

    with chart_card(key=_HOURLY_CHART_CARD_KEY):
        st.plotly_chart(
            fig, width="stretch",
            config={"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]},
        )


_TOP_ROW_KEY = "live-weather-top-row"
_MAP_WRAPPER_KEY = "live-weather-map-wrapper"


def render() -> None:
    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)

    st.markdown(
        f'<style>'
        f'div[data-testid="stVerticalBlock"][class*="{_TOP_ROW_KEY}"] {{ '
        f"background: none !important; border: none !important; box-shadow: none !important; "
        f"backdrop-filter: none !important; -webkit-backdrop-filter: none !important; "
        f"padding: 0 !important; overflow: visible !important; position: relative !important; "
        f"}} "
        f'[class*="{_TOP_ROW_KEY}"] div[data-testid="stHorizontalBlock"] {{ gap: 2.5rem; }} '
        f'[class*="{_TOP_ROW_KEY}"] div[data-testid="stColumn"]:nth-child(1) {{ '
        f"flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; "
        f"}}"
        f'[class*="{_TOP_ROW_KEY}"] div[data-testid="stColumn"]:nth-child(2) {{ '
        f"flex: 0 0 300px !important; width: 300px !important; margin-left: auto !important; "
        f"}}"
        f"</style>",
        unsafe_allow_html=True,
    )
    top_row = st.container(key=_TOP_ROW_KEY)
    hero_col, location_col = top_row.columns(2, vertical_alignment="bottom")
    with location_col:
        st.markdown(
            f'<style>'
            f'.live-weather-info-wrap {{ position: relative; isolation: isolate; }}'
            f'.live-weather-info-wrap .live-weather-info-tooltip {{ '
            f"display: none; position: absolute; top: 50%; right: calc(100% + 10px); left: auto; "
            f"transform: translateY(-50%); z-index: 9999; "
            f"width: 260px; padding: 0.55rem 0.7rem; border-radius: 10px; "
            f"font-size: 12.5px; font-weight: 400; line-height: 1.4; letter-spacing: normal; "
            f"color: var(--m3-on-primary-container, #1E4469); "
            f"background: color-mix(in srgb, white 92%, var(--m3-surface-container-low, #D8E2EC) 8%); "
            f"border: 1px solid rgba(255, 255, 255, 0.6); box-shadow: 0 8px 20px rgba(28, 42, 59, 0.18); "
            f"}}"
            f'.live-weather-info-wrap:hover .live-weather-info-tooltip, '
            f'.live-weather-info-icon:focus .live-weather-info-tooltip, '
            f'.live-weather-info-wrap:focus-within .live-weather-info-tooltip {{ display: block; }}'
            f"</style>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="live-weather-info-wrap" style="font-size:15px;font-weight:600;'
            f'letter-spacing:0.2px;color:var(--m3-on-primary-container, #1E4469);'
            f'margin:0 0 0.5rem 0; display:flex; align-items:center; gap:0.35rem;">Location'
            f'<span class="live-weather-info-icon" tabindex="0" style="'
            f'display:inline-flex; align-items:center; justify-content:center; width:15px; height:15px; '
            f'border-radius:50%; font-size:11px; font-weight:700; line-height:1; '
            f'cursor:pointer; opacity:0.55; outline:none; '
            f'border:1.3px solid var(--m3-on-primary-container, #1E4469);">i'
            f'<span class="live-weather-info-tooltip">We forecast live weather for only '
            f'{len(CITY_STATIONS)} major cities in Germany.</span>'
            f'</span>'
            f'</p>',
            unsafe_allow_html=True,
        )

        _card_background = (
            "linear-gradient(135deg, rgba(255, 255, 255, 0.35), rgba(255, 255, 255, 0) 55%), "
            "color-mix(in srgb, color-mix(in srgb, white 80%, "
            "var(--m3-surface-container-low, #D8E2EC) 20%) 80%, transparent)"
        )
        st.markdown(
            f'<style>'
            f'[class*="live_weather_city"] [data-baseweb="select"] > div {{ '
            f"background: {_card_background} !important; "
            f"backdrop-filter: blur(16px) saturate(150%); -webkit-backdrop-filter: blur(16px) saturate(150%); "
            f"border: 1px solid rgba(255, 255, 255, 0.5) !important; "
            f"box-shadow: 0 4px 14px rgba(28, 42, 59, 0.12) !important; "
            f"}}"
            f'[data-testid="stSelectboxVirtualDropdown"] [role="listbox"] {{ '
            f"background: {_card_background} !important; "
            f"backdrop-filter: blur(16px) saturate(150%); -webkit-backdrop-filter: blur(16px) saturate(150%); "
            f"border: 1px solid rgba(255, 255, 255, 0.5) !important; "
            f"box-shadow: 0 12px 32px rgba(28, 42, 59, 0.16) !important; "
            f"}}"
            f'[data-testid="stSelectboxVirtualDropdown"] [role="option"] {{ background: transparent !important; }}'
            f"</style>",
            unsafe_allow_html=True,
        )
        city = st.selectbox(
            "Location",
            options=list(CITY_STATIONS),
            index=list(CITY_STATIONS).index(_DEFAULT_CITY),
            label_visibility="collapsed",
            key="live_weather_city",
        )

        st.markdown(
            f'<style>'
            f'div[data-testid="stVerticalBlock"][class*="{_MAP_WRAPPER_KEY}"] {{ '
            f"background: none !important; border: none !important; box-shadow: none !important; "
            f"backdrop-filter: none !important; -webkit-backdrop-filter: none !important; "
            f"padding: 0 !important; "
            f"position: absolute !important; top: 100% !important; right: 0 !important; "
            f"left: calc(65% + 2rem) !important; width: auto !important; "
            f"margin-top: 1rem !important; z-index: 1 !important; "
            f"}}</style>",
            unsafe_allow_html=True,
        )
        map_wrapper = st.container(key=_MAP_WRAPPER_KEY)
    station_id = CITY_STATIONS[city]

    try:
        df = fetch_forecast(station_id)
    except LiveWeatherFetchError as exc:
        st.error(f"Couldn't load live weather: {exc}")
        return

    snapshot = current_snapshot(df)
    daily = daily_summary(df, days=10)

    # Themes the whole page to match current conditions.
    st.session_state["active_theme_parameter"] = snapshot["theme_parameter"]

    with hero_col:
        _render_hero(city, snapshot)

    with map_wrapper:
        _render_mini_map(city, snapshot)
        
    st.markdown('<div style="margin-top: 1.75rem;"></div>', unsafe_allow_html=True)
    _render_parameters(snapshot)

    _render_daily_strip(daily)

    st.markdown(
        f'<style>div[data-testid="stVerticalBlock"][class*="{_HOURLY_CHART_CARD_KEY}"] {{ '
        f"padding: 0.9rem 1rem !important; "
        f"}}</style>",
        unsafe_allow_html=True,
    )
    hourly_col, ten_day_col = st.columns(2, gap="large")
    with hourly_col:
        _render_hourly_chart(df, snapshot)
    with ten_day_col:
        _render_ten_day_forecast(daily)

    st.caption(
        f"Source: DWD MOSMIX forecast (station {station_id}). Data as of "
        f"{snapshot['as_of'].strftime('%d %b %Y, %H:%M')} local time. Refreshes automatically every 15 minutes."
    )
