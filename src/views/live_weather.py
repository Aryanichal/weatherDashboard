"""Live Weather tab: current conditions and the upcoming days' forecast for
one selected city, from DWD's MOSMIX forecast product (see
src/live_weather_loader.py). This is the dashboard's homepage/default view.

Unlike the other five tabs, this one does *not* use the shared station-
multiselect/historical-date-range row app.py renders above them: MOSMIX has
no "date range" (it's always "now plus the next ~10 days") and uses a
different station catalog than the historical climate-observation data those
tabs analyze, so that row wouldn't mean anything here. app.py special-cases
this view for exactly that reason -- see its own comments.
"""

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
    """The current-conditions block -- icon, temperature, city name,
    description -- sits unboxed directly on the page background (no
    st.container(), so it never picks up this app's global "every
    top-level block gets a white rounded card" rule; see the
    `[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]`
    selector in src/ui_theme.py's _BASE_CSS for that rule). Called from
    inside the left-hand column of render()'s top row, beside the
    Location dropdown."""
    # Icon and temperature sit on the same line (not in separate
    # st.columns(), which left too wide a gap between them). Left-aligned,
    # flush with the row's left edge, since this sits in the left column.
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
    """A small "where is this" map -- just a dot at the selected city, no
    text on the map itself -- built the same way src/views/map_view.py's
    historical Map tab builds its own (px.scatter_map() on a free,
    tokenless OpenStreetMap base), just zoomed into a single point instead
    of plotting every selected station. Marker color follows the same
    category the rest of the page is themed to (see
    weather_icon_label_and_theme() in src/live_weather_loader.py), so it's
    gold on a clear day, blue when it's wet, grey when it's overcast --
    never a fixed color regardless of theme.
    """
    lat, lon = CITY_COORDINATES[city]
    accent_hex = ACCENT_HEX_BY_CATEGORY[categorize_parameter(snapshot["theme_parameter"])]

    # Zoomed out from street-level (10) to a "which part of the country"
    # view -- the city name and temperature no longer render on the map
    # itself (see below), so this is purely how much surrounding geography
    # the dot sits in.
    fig = px.scatter_map(
        {"lat": [lat], "lon": [lon]}, lat="lat", lon="lon",
        zoom=8.5, map_style="open-street-map",
    )
    fig.update_traces(mode="markers", marker=dict(size=13, color=accent_hex), hoverinfo="skip")
    # Shorter than the space technically available (parameters + "Next
    # days" together run to roughly this height) so the card's bottom edge
    # clears "Next 48 hours" below it with real breathing room, rather than
    # stretching to fill the same height and ending up right up against it.
    fig.update_layout(height=300, showlegend=False)
    # render_chart() would apply style_fig()'s fixed t=60/b=50/l=40/r=40
    # margins unconditionally -- fine for a normal axed chart, but on a map
    # that reserves a wide band of plain card-background on every side,
    # which read as a second, inner box nested inside chart_card()'s own.
    # Calling style_fig() directly (it returns the same fig it mutates) and
    # zeroing every margin afterwards keeps its theme colors/modebar
    # styling while letting the map fill the card completely.
    style_fig(fig)
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
    # chart_card()'s own default padding (see _BASE_CSS in src/ui_theme.py)
    # left a visible gap of card-background between the card's edge and the
    # map itself. The "st-key-{key}" class Streamlit adds lands on the
    # inner stVerticalBlock, not the outer stVerticalBlockBorderWrapper
    # (confirmed via the live DOM: `[class*=key]` matches exactly one node,
    # data-testid="stVerticalBlock") -- a bare `[class*=key]` selector is
    # specificity 1, so it lost to the global card rule's own specificity-2
    # `[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]`
    # padding, leaving 24px unremoved despite the `!important`. Matching
    # that same element+attribute shape (same fix as _TOP_ROW_KEY above)
    # ties the specificity and wins on source order instead.
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
    """Humidity/wind/gusts/precipitation/pressure/cloud cover, condensed
    into one small card as a single horizontal row (not a 2-column grid).
    Its own row below the temperature/Location row, sized to its own
    content (`width: fit-content`, same "st-key-{key}" scoping trick as
    "Next days"'s card -- see render_missing_stations_indicator() in
    src/views/common.py) rather than stretched full-width, so it reads as
    one compact strip."""
    stat_defs = [
        ("Humidity", _format(snapshot["humidity_pct"], 0, "%")),
        ("Wind", _format(snapshot["wind_speed_ms"], 1, "m/s")),
        ("Gusts", _format(snapshot["wind_gust_ms"], 1, "m/s")),
        ("Precipitation", _format(snapshot["precipitation_mm"], 1, "mm")),
        ("Pressure", _format(snapshot["pressure_hpa"], 0, "hPa")),
        ("Cloud cover", _format(snapshot["cloud_cover_pct"], 0, "%")),
    ]
    # Label reads as a small caption -- uppercase, letter-spaced, muted --
    # with clear room (margin-top) before the bold value below it, rather
    # than the two lines sitting flush against each other.
    items = "".join(
        f'<div style="flex:0 0 auto; min-width:0; padding:0 1.6rem 0 0;">'
        f'<div style="font-size:0.72rem; font-weight:600; text-transform:uppercase; '
        f'letter-spacing:0.06em; opacity:0.6; white-space:nowrap;">{label}</div>'
        f'<div style="font-size:1.35rem; font-weight:700; white-space:nowrap; margin-top:0.4rem; '
        f'color:var(--m3-on-primary-container, #1E4469);">{value}</div></div>'
        for label, value in stat_defs
    )
    # align-items:flex-end bottom-aligns every item's value on one shared
    # baseline (rather than each item just top-aligning independently).
    # Padding bumped past chart_card()'s own default 1.5rem (see _BASE_CSS)
    # for extra room around the text, and the card no longer needs to
    # compete with the hero/Location columns for space now that it has
    # its own row, hence the wider gap between items too.
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
    """One compact, unified horizontal strip -- all days as columns inside
    a single chart_card(), not st.container(border=True) per day (which
    read as a row of separate chunky boxes rather than one cohesive
    widget), and no divider between days. The card itself is sized to its
    content (`width: fit-content`, scoped to this card's own key -- see
    render_missing_stations_indicator() in src/views/common.py for the
    same "st-key-{key}" substring-match trick) rather than stretching to
    the full row width like every other chart_card() in this app, since a
    handful of day columns look lost inside a full-width box. Scrolls
    horizontally if it still doesn't fit."""
    # Without this, "Next days" landed right under the hero's own
    # description line with barely any gap -- close enough to read as
    # part of the hero block instead of its own, separate row.
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
    position and width are ``day``'s [low, high] scaled against the whole
    forecast's overall min/max, so a cold day's bar sits left/blue and a
    hot day's sits right/gold, same idea as a typical weather app's 10-day
    list. Built from per-row st.columns() (not one big HTML table) so it's
    plain Streamlit layout throughout, just like the rest of this view --
    only the bar itself needs raw HTML, since Streamlit has no built-in
    "colored range on a track" widget.
    """
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

    # Same accent the hero icon, mini-map marker, and page background all
    # follow (see weather_icon_label_and_theme() in
    # src/live_weather_loader.py) -- this line/fill was hardcoded to the
    # "clear" theme's gold regardless of current conditions, so it stayed
    # yellow even once the rest of the page had already switched to grey
    # (cloudy) or blue (wet).
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
    # Height tuned so this card's total height (chart + its own tighter
    # padding, see the CSS injected from render() rather than here -- an
    # st.markdown() call placed here would insert its own zero-height
    # element between the section label and the card, an 8px flex-gap
    # that threw the two cards' top edges out of alignment with each
    # other) lands on the same total height as the 10-day forecast card
    # next to it (confirmed by comparing both cards' rendered heights).
    fig.update_layout(title="Hourly temperature", yaxis_title="°C", height=324)
    # render_chart() would apply style_fig()'s fixed t=60/b=50/l=40/r=40
    # margins -- generous enough on a full-width chart, but this one now
    # shares a row with the 10-day forecast card (see render()), so it's
    # noticeably narrower; tightening the margins (still enough room for
    # the title/axis ticks/"°C" label, just not padded past what they
    # need) keeps the actual plotted line from looking squeezed in what's
    # left. Same style_fig()-then-override trick as _render_mini_map().
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
    # Extra top margin here, on top of the top-level nav's own
    # margin-bottom (see app.py) -- that alone read as too tight once the
    # nav's own text grew to 2.5rem.
    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)

    # The current-conditions hero and Location share one row -- a plain
    # st.columns(), not wrapped in an extra st.container(), so it never
    # picks up this app's global "every top-level block gets a card" rule
    # (that rule only matches an explicit st.container()'s own wrapper,
    # not a bare st.columns() row -- confirmed empirically while building
    # the previous version of this layout).
    #
    # st.columns() stretches its columns to fill the row by ratio
    # regardless of actual content width (confirmed empirically while
    # building the previous version of this layout), which left a big gap
    # after the temperature before Location. Wrapping in a keyed
    # st.container() and forcing `flex: 0 0 auto; width: auto` on the
    # hero's own column (same trick as elsewhere in this file) makes it
    # shrink-wrap instead. The wrapping container itself is made invisible
    # (no background/border/shadow/padding) so it doesn't pick up this
    # app's global "every top-level block gets a card" rule -- see the
    # neutralization block below for why that needs a doubled-up attribute
    # selector to actually win. Location keeps a fixed, comfortably-sized
    # width and gets `margin-left: auto`, the standard flexbox trick for
    # "push this item to the far end of the row": it eats all the row's
    # left-over space as its own left margin, so the row still spans the
    # full page width instead of everything bunching up on the left with
    # empty space stranded on the right.
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
        # render_section_label("Location") plus a small info icon after it,
        # for the same "label" typography -- explaining the one thing
        # that isn't obvious from the dropdown alone: this list is a
        # fixed 12 preset cities, not every DWD station.
        #
        # A plain `title` attribute (native browser tooltip) only shows on
        # hover, not on click/tap -- no help on touch devices, and no way
        # to open it deliberately with the mouse either. This is a pure
        # CSS tooltip instead: the icon is a focusable <span> (tabindex),
        # and the tooltip text is a sibling shown via `:hover` *or*
        # `:focus` -- clicking a focusable element gives it focus, so a
        # click opens the tooltip and keeps it open (no JS needed) until
        # something else is clicked, exactly like hover does but
        # click-triggered too.
        city_list = ", ".join(CITY_STATIONS)
        st.markdown(
            f'<style>'
            # The *wrapper* (the whole "Location [i]" row), not just the
            # icon, is the positioned anchor -- anchoring to the icon alone
            # opened the tooltip directly over the "Location" text sitting
            # right next to it (same row, immediately to its left), since
            # "left of the icon" and "under the label text" are the same
            # place. `isolation: isolate` also forces this wrapper to
            # establish its own stacking context, so the tooltip's z-index
            # is guaranteed to be compared against the map card's
            # (z-index: 1, see _MAP_WRAPPER_KEY below) rather than possibly
            # losing to it through some unrelated ancestor stacking
            # context -- it was rendering visually underneath the map
            # without this, even though `display: block` was applied.
            f'.live-weather-info-wrap {{ position: relative; isolation: isolate; }}'
            # Opens sideways, clear to the left of the *entire* wrapper,
            # vertically centered on it -- both above (bottom: 130%) and
            # below (top: 130%) put it right on top of solid-background
            # content directly there (the dropdown right below "Location",
            # or -- above -- not enough clear room before the top nav).
            # The open blank page background further left (nothing else
            # sits at this same height, this far right on the page) has no
            # such collision.
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
            f'<span class="live-weather-info-tooltip">Forecasts are only available for these '
            f'{len(CITY_STATIONS)} preset cities: {city_list}.</span>'
            f'</span>'
            f'</p>',
            unsafe_allow_html=True,
        )
        # Re-skins this one dropdown (box + its option list) with the same
        # frosted-glass gradient/blur/color chart_card() gives "Next days"
        # etc. (see the `[data-testid="stVerticalBlockBorderWrapper"]`
        # rule in src/ui_theme.py's _BASE_CSS) instead of the plain
        # near-white every other input on this page uses.
        #
        # The box itself is a normal in-tree descendant, so it's scoped
        # precisely via this widget's own key. The option list is a
        # different story -- opening it and inspecting the live DOM shows
        # Streamlit portals it straight onto <body> (inside a
        # [data-testid="stSelectboxVirtualDropdown"]), completely outside
        # this widget's own subtree, so no ancestor selector can reach it.
        # The rule below is therefore unscoped at the CSS level -- but
        # since it's injected from inside this module, it only ever
        # enters the page's CSS while Live Weather is the active view
        # (only the active view's render() call executes each rerun, see
        # app.py), and this is the only selectbox Live Weather has -- so
        # in practice it only ever restyles this one dropdown's list.
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
        # Absolutely positioned (anchored to top_row's own `position:
        # relative` above), not a normal flow element -- st.columns()
        # always shares one row height across *every* column, even empty
        # ones (confirmed empirically: putting the map in its own
        # st.columns() row pushed the parameters/"Next days" rows below it
        # down by the map's full height, even on their own, unrelated left
        # side). Taking it out of flow entirely is the only way for it to
        # occupy the empty space to the right of those rows without
        # affecting their position at all.
        # This wrapper is a bare st.container(key=...) purely to give the
        # deferred-write/absolute-positioning trick below a stable target --
        # it holds nothing of its own but the inner chart_card(), so it must
        # be neutralized (same doubled-attribute-selector trick as
        # _TOP_ROW_KEY above) or it silently picks up this app's global
        # "every top-level block gets a card" rule too, showing as a second,
        # outer box around the map's own card.
        #
        # Anchored by `left`/`right` instead of a fixed width, so it
        # stretches to fill whatever horizontal room is actually free.
        # `left: 65%` lines up with the same max-width the hourly chart and
        # 10-day forecast cards below use (see _HOURLY_CHART_CARD_KEY /
        # _TEN_DAY_CARD_KEY) -- both of those, and the narrower
        # fit-content parameters/"Next days" cards, stay within that left
        # 65% of the page, so the map can safely claim everything right of
        # it (up to location_col's own right edge) without ever overlapping
        # them, at any point along the map's height.
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

    # Themes the whole page (background, nav row, ...) to match current
    # conditions -- clear reuses the "Temperature" category's warm gold,
    # cloudy/foggy reuses "neutral"'s grey, anything wet reuses
    # "precipitation"'s blue. See weather_icon_label_and_theme() in
    # src/live_weather_loader.py for the code->category mapping, and
    # apply_dynamic_theme() in src/ui_theme.py (called once at the bottom
    # of app.py) for how this session_state key drives the page theme.
    st.session_state["active_theme_parameter"] = snapshot["theme_parameter"]

    # hero_col was created above (so it lands in its own column), but
    # rendered into here, now that snapshot/theme are known -- Streamlit
    # columns accept writes out of call order, so this is fine.
    with hero_col:
        _render_hero(city, snapshot)

    # map_wrapper was created above, inside location_col, right after the
    # dropdown -- rendered into here, now that snapshot/theme are known.
    # Being absolutely positioned (see its own style block above), it
    # doesn't affect top_row's height at all, so this can't reintroduce
    # either of the two layout bugs the previous approaches hit: hero
    # being pulled down by vertical_alignment, or every later row
    # (parameters, "Next days") getting pushed down by however tall the
    # map is.
    with map_wrapper:
        _render_mini_map(city, snapshot)

    # Own row below the temperature/Location row (not sharing it anymore)
    # -- margin-top separates it from that row above, same idea as the
    # spacer _render_daily_strip() adds above "Next days".
    st.markdown('<div style="margin-top: 1.75rem;"></div>', unsafe_allow_html=True)
    _render_parameters(snapshot)

    _render_daily_strip(daily)

    # Side by side instead of stacked -- each card is narrower as a result
    # (roughly half the page width each, versus the 65% each used full-width
    # before), which is also why the hourly chart's own internal
    # padding/margins were tightened (see _render_hourly_chart()'s own
    # comments). Injected here, before either column, rather than from
    # inside _render_hourly_chart() itself -- an st.markdown() call made
    # *inside* hourly_col would add its own (zero-height, but still
    # flex-gapped) element between that column's section label and its
    # card, throwing the two cards' top edges out of alignment with the
    # 10-day forecast column next to it. A <style> tag works globally
    # regardless of where in the page it's injected from, so hoisting it
    # here avoids adding anything to hourly_col's own content at all.
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
        f"{snapshot['as_of'].strftime('%d %b %Y, %H:%M')} local time -- refreshes automatically every 15 minutes."
    )
