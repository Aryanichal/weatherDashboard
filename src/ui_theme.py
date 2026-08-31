import colorsys

import plotly.graph_objects as go
import streamlit as st

from src.analysis import categorize_parameter

SURFACE = {
    "surface": "#EEF2F6",
    "surface_container_lowest": "#F9FAFB",
    "surface_container_low": "#D8E2EC",
    "surface_container": "#D5E2F0",
    "on_surface_variant": "#52657A",
    "outline_variant": "#B7C6D7",
}

PRIMARY = {
    "primary": "#4D77CB",
    "primary_container": "#A9CCF9",
    "on_primary_container": "#1E4469",
}

def _with_hue(hex_color: str, hue_degrees: float | None, saturation: float | None = None) -> str:
    """Return ``hex_color`` with its hue (and optionally saturation)
    replaced, keeping its own lightness -- and, unless overridden, its own
    saturation -- untouched. Used to derive a whole category's palette from
    the app's default blue one token-by-token, so every derived color keeps
    the exact same HSL "recipe" (same S, same L) as its blue counterpart,
    only the hue rotates (or, for "neutral", saturation drops to 0)."""
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = h if hue_degrees is None else hue_degrees / 360
    s = s if saturation is None else saturation
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))


_THEME_TOKENS = {**SURFACE, **PRIMARY}

# "neutral" still derives algorithmically from the blue tokens above
# (desaturating to 0% keeps their exact lightness, which is all a clean
# grey needs -- confirmed to look good). "precipitation" and "temperature"
# are hand-picked instead of hue-rotated: rotating navy's hue to yellow
# while keeping its same (fairly low) lightness/saturation lands on
# olive/khaki, not a vivid yellow -- a "pure"-looking yellow only exists
# at high lightness *and* high saturation, a band navy was nowhere near.
# Hand-picking both categories (rather than just yellow) keeps them a
# matched, equally-vivid "poppy" pair instead of one vivid one and one
# left muted. on_primary_container (used as plain text throughout the
# app) still clears WCAG AA comfortably: blue 8.6:1, yellow 7.1:1 against
# white.
PALETTES_BY_CATEGORY = {
    "precipitation": {
        "surface": "#EDF3FE",
        "surface_container_lowest": "#F9FBFF",
        "surface_container_low": "#D6E4FB",
        "surface_container": "#D2E3FE",
        "on_surface_variant": "#3E5D8A",
        "outline_variant": "#B8CDF0",
        "primary": "#2979FF",
        "primary_container": "#D6E4FF",
        # Desaturated and hue-shifted further toward slate/indigo from a
        # "textbook" fully-saturated royal blue (#0D47A1, HSL 216/85/34) --
        # that much saturation on a pure primary hue is what reads as
        # clip-art/PowerPoint blue. This is the same token used as plain
        # text everywhere in the app (see ACCENT_HEX_BY_CATEGORY below), so
        # only it changes here -- "primary"/"primary_container" above are
        # separate tokens for other UI elements (progress-bar fills etc.)
        # the user wasn't asking to retint.
        "on_primary_container": "#31469B",
    },
    "temperature": {
        "surface": "#FFF8E1",
        "surface_container_lowest": "#FFFDF5",
        "surface_container_low": "#FFECB3",
        "surface_container": "#FFE59A",
        "on_surface_variant": "#8A6D1D",
        "outline_variant": "#F0D68A",
        "primary": "#FFC107",
        "primary_container": "#FFE9A8",
        "on_primary_container": "#7A4F01",
    },
    "neutral": {name: _with_hue(hexval, hue_degrees=None, saturation=0.0) for name, hexval in _THEME_TOKENS.items()},
}

# Key Figures toolbar accent per src.analysis.categorize_parameter() --
# the "on_primary_container" token out of each category's full palette
# above, i.e. the exact same #1E4469 (blue) / #695A1E (gold) / #444444
# (grey) family every other themed element in the app now reads (see
# render_section_label() in src/views/common.py, render_brand() and
# _current_ink_hex() above). This used to read the "primary" token
# instead, which desaturates to a visibly lighter grey (#8C8C8C) under
# the "neutral" theme.
ACCENT_HEX_BY_CATEGORY = {category: palette["on_primary_container"] for category, palette in PALETTES_BY_CATEGORY.items()}


_BASE_CSS = """
<style>
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDeployButton"], .stDeployButton, .stDeployButton * {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
}
[data-testid="stStatusWidget"] {
    position: fixed !important;
    left: 1rem;
    bottom: 0.75rem;
    z-index: 1000000;
}

[data-testid="stSpinner"] {
    position: fixed !important;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 1000001;
    background: color-mix(in srgb, var(--m3-surface-container-lowest, #F9FAFB) 94%, transparent) !important;
    border: 1px solid color-mix(in srgb, var(--m3-on-primary-container, #1E4469) 30%, transparent);
    border-radius: 16px;
    box-shadow: 0 12px 40px rgba(28, 42, 59, 0.18);
    padding: 1.5rem 2rem;
    width: max-content;
    max-width: min(90vw, 420px);
}
[data-testid="stSpinner"] p {
    color: var(--m3-on-primary-container, #1E4469) !important;
}
[data-testid="stSpinner"]::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    background: rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    width: 100vw;
    height: 100vh;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
}
[data-testid="stSpinner"] > div {
    justify-content: center;
}

[data-testid="stAppViewContainer"] .main .block-container {
    position: relative;
    z-index: 2;
}

[data-testid="stAppViewContainer"] .main .block-container,
[data-testid="stMainBlockContainer"] {
    padding: 0.5rem 2.5rem 2rem !important;
    margin-top: 0;
}
[data-testid="stAppViewContainer"] .main,
[data-testid="stAppViewContainer"] .main > div:first-child,
[data-testid="stMain"] {
    padding-top: 0 !important;
}
.main .block-container .app-brand,
[data-testid="stMainBlockContainer"] .app-brand {
    margin-top: -0.25rem !important;
    margin-bottom: 2.25rem !important;
    padding-top: 0 !important;
    line-height: 1 !important;
}
.main .block-container [data-testid="stVerticalBlock"] > [data-testid="element-container"]:first-child,
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-child {
    margin-top: 0 !important;
    padding-top: 0 !important;
}
[data-testid="stVerticalBlock"] {
    gap: 0.5rem !important;
}
[data-testid="stHeader"] {
    height: 2rem;
}
/* Every st.segmented_control() in the app -- the main navigation (see
   app.py; standing in for st.tabs() so a shared station/date-range row
   can sit between the nav and whichever view is showing, which a real
   tab bar can't host since its header and content are one atomic widget)
   and the Temperature composite's Mean/Max/Min trend-line toggle (see
   _render_temperature_band()'s caller in src/views/time_series.py) --
   both render through this same [data-testid="stButtonGroup"] widget, so
   one shared rule styles every option as the same rounded-card look
   chart_card() below uses, with the active option picked out by a solid
   fill of the app's current accent color (var(--m3-primary), the same
   one driving the "Key Figures" stat-accent boxes) rather than a second,
   different "selected" treatment. */
[data-testid="stButtonGroup"] {
    gap: 0.75rem !important;
}
[data-testid="stButtonGroup"] button {
    background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.35), rgba(255, 255, 255, 0) 55%),
        color-mix(in srgb, color-mix(in srgb, white 80%, var(--m3-surface-container-low, #D8E2EC) 20%) 80%, transparent) !important;
    -webkit-backdrop-filter: blur(16px) saturate(150%);
    backdrop-filter: blur(16px) saturate(150%);
    border: 1px solid rgba(255, 255, 255, 0.5) !important;
    border-radius: 24px !important;
    box-shadow: 0 12px 32px rgba(28, 42, 59, 0.16) !important;
    color: var(--m3-on-surface-variant, #52657A) !important;
    font-size: 1rem !important;
    font-weight: 500 !important;
    padding: 0.5rem 1.25rem !important;
    transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease, font-weight 0.15s ease;
}
[data-testid="stButtonGroup"] button p {
    font-size: inherit !important;
    font-weight: inherit !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"] {
    background: color-mix(in srgb, var(--m3-on-primary-container, #1E4469) 80%, white) !important;
    border-color: color-mix(in srgb, var(--m3-on-primary-container, #1E4469) 80%, white) !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
}
/* Real st.tabs() styling, still needed for the Global Warming view's own
   "Global Warming Trend"/"Future Prediction" sub-tabs (see
   src/views/global_warming.py) even though the top-level nav above no
   longer uses st.tabs(). */
[data-testid="stTabPanel"] > [data-testid="stVerticalBlock"] {
    gap: 1rem !important;
}
[data-testid="stTab"] p {
    font-weight: 700 !important;
    font-size: 1.1rem !important;
    letter-spacing: 0.01em;
    color: color-mix(in srgb, var(--m3-on-primary-container, #1E4469) 50%, transparent) !important;
    transition: color 0.15s ease;
}
[role="tablist"] {
    display: inline-flex;
    gap: 1.5rem;
}
[data-testid="stTabs"] hr {
    display: none;
}
[role="tablist"]::after {
    height: 1px !important;
    background: color-mix(in srgb, var(--m3-outline-variant, #B7C6D7) 45%, transparent) !important;
}
[role="tablist"] .react-aria-SelectionIndicator {
    height: 3px !important;
    background: var(--m3-on-primary-container, #1E4469) !important;
}
[data-testid="stTab"] {
    background: transparent !important;
    padding: 0.4rem 0.1rem !important;
    transition: transform 0.15s ease;
}
[data-testid="stTab"][aria-selected="true"] p {
    color: var(--m3-on-primary-container, #1E4469) !important;
}
/* Same lift+full-color hover affordance the segmented-control navs use
   (see render_segmented_nav_css() in src/views/common.py) on the
   unselected tab only -- the active one doesn't need an invitation to
   click. Placement/width intentionally untouched here (content-sized,
   left-aligned, not stretched or centered) -- this reskin is typography/
   color/indicator/hover only, same visual language as the other nav
   rows without changing this one's layout. */
[data-testid="stTab"]:not([aria-selected="true"]):hover {
    transform: translateY(-3px);
}
[data-testid="stTab"]:not([aria-selected="true"]):hover p {
    color: var(--m3-on-primary-container, #1E4469) !important;
}
[data-testid="stDateInput"] label {
    font-weight: 600 !important;
}
[data-testid="stMultiSelect"] span[data-tag] {
    background-color: color-mix(in srgb, var(--m3-primary-container, #A9CCF9) 94%, transparent) !important;
    border-color: var(--m3-primary-container, #A9CCF9) !important;
}
[data-testid="stMultiSelect"] span[data-tag],
[data-testid="stMultiSelect"] span[data-tag] * {
    color: var(--m3-on-primary-container, #1E4469) !important;
    -webkit-text-fill-color: var(--m3-on-primary-container, #1E4469) !important;
}

[data-testid="stVerticalBlockBorderWrapper"][data-testid="stVerticalBlockBorderWrapper"]:not([data-testid="stAppViewBlockContainer"] > *),
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {
    background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.35), rgba(255, 255, 255, 0) 55%),
        color-mix(in srgb, color-mix(in srgb, white 80%, var(--m3-surface-container-low, #D8E2EC) 20%) 80%, transparent) !important;
    -webkit-backdrop-filter: blur(16px) saturate(150%);
    backdrop-filter: blur(16px) saturate(150%);
    border: 1px solid rgba(255, 255, 255, 0.5) !important;
    outline: none !important;
    border-radius: 24px !important;
    box-shadow: 0 12px 32px rgba(28, 42, 59, 0.16) !important;
    padding: 1.5rem !important;
    overflow: hidden !important;
}

[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stMultiSelect"] [role="group"][data-rac],
[data-testid="stSelectbox"] [role="group"][data-rac],
[data-testid="stDateInputField"] {
    background: color-mix(in srgb, var(--m3-surface-container-lowest, #F9FAFB) 94%, transparent) !important;
    border: none !important;
    outline: none !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 14px rgba(28, 42, 59, 0.12);
    transition: box-shadow 0.15s ease;
}
[data-testid="stNumberInputContainer"] {
    background: color-mix(in srgb, var(--m3-surface-container-low, #D8E2EC) 60%, transparent) !important;
}
[data-testid="stNumberInputField"],
[data-testid="stNumberInputStepDown"],
[data-testid="stNumberInputStepUp"] {
    color: var(--m3-on-surface-variant, #52657A) !important;
}
[data-testid="stMultiSelect"]:focus-within [data-baseweb="select"],
[data-testid="stSelectbox"]:focus-within [data-baseweb="select"],
[data-testid="stMultiSelect"]:focus-within [role="group"][data-rac],
[data-testid="stSelectbox"]:focus-within [role="group"][data-rac],
[data-testid="stDateInput"]:focus-within [data-testid="stDateInputField"] {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--m3-on-primary-container, #1E4469) 22%, transparent) !important;
}
[data-testid="stExpander"] details {
    background: color-mix(in srgb, var(--m3-surface-container-lowest, #F9FAFB) 94%, transparent) !important;
    border: none !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 14px rgba(28, 42, 59, 0.12) !important;
}
[data-testid="stExpander"] summary {
    background: transparent !important;
}
[data-baseweb="menu"] {
    background: color-mix(in srgb, var(--m3-surface-container-lowest, #F9FAFB) 94%, transparent) !important;
    border-radius: 10px !important;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(28, 42, 59, 0.12) !important;
}
.modebar-btn:hover, .modebar-btn.active {
    background: color-mix(in srgb, var(--m3-on-primary-container, #1E4469) 12%, transparent) !important;
    border-radius: 6px !important;
}
[data-testid="stVerticalBlock"][class*="-stat-accent"] {
    border: none !important;
}
[class*="-stat-accent"] [data-testid="stMetricLabel"] p,
[class*="-stat-accent"] [data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}
[data-testid="stVerticalBlock"][class*="-stat-accent"],
[data-testid="stVerticalBlock"][class*="-stat-plain"] {
    padding: 1rem 1.25rem !important;
}
[class*="-stat-accent"] [data-testid="stMetricLabel"] p,
[class*="-stat-plain"] [data-testid="stMetricLabel"] p {
    font-size: 14px !important;
}
[class*="-stat-accent"] [data-testid="stMetricValue"],
[class*="-stat-plain"] [data-testid="stMetricValue"] {
    font-size: 29px !important;
}
</style>
"""

def _render_theme_vars(palette: dict[str, str]) -> None:
    css_vars = " ".join(f'--m3-{role.replace("_", "-")}: {hex_value};' for role, hex_value in palette.items())
    st.markdown(
        f'<style>.stApp {{ background: {palette["surface"]}; }}'
        f' :root {{ {css_vars} }}</style>',
        unsafe_allow_html=True,
    )


def render_app_background() -> None:
    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    # Paint whichever theme this session last landed on (falling back to
    # "neutral" -- the same default apply_dynamic_theme() itself falls back
    # to) right away, instead of always starting from a hardcoded
    # "precipitation" (blue) palette and letting apply_dynamic_theme() correct
    # it at the very end of the script. Streamlit streams each st.markdown()
    # to the browser as soon as it executes rather than batching the whole
    # script's output, so that hardcoded starting palette was visibly
    # painted for a moment before apply_dynamic_theme()'s correction arrived
    # -- a blue flash on every load/rerun whenever the actual theme wasn't
    # blue (confirmed empirically). Reading the same "active_theme_parameter"
    # apply_dynamic_theme() reads lets this first paint already match in the
    # common case (nothing this run changes it); apply_dynamic_theme() still
    # runs at the end to correct it for the now-rare case where this run's
    # own view/selection actually changes the category.
    parameter = st.session_state.get("active_theme_parameter")
    category = categorize_parameter(parameter) if parameter else "neutral"
    _render_theme_vars(PALETTES_BY_CATEGORY[category])


def apply_dynamic_theme(parameter: str | None) -> None:
    """Re-assert every --m3-* custom property (and .stApp's background)
    using the color category of ``parameter`` (see categorize_parameter()
    in src/analysis.py), overriding the best-guess palette
    render_app_background() already painted at the top of the script (see
    its own docstring) with this run's actual, final category -- the two
    only ever disagree when this run's own view/selection changed it.

    CSS custom properties on :root apply document-wide regardless of where
    in the page's source their defining <style> tag sits, and the later of
    two equal-specificity :root rules wins -- so calling this once, after
    the current view (and so its own "Parameter" dropdown, if it has one)
    has rendered, is enough to re-theme the page background, brand text,
    nav row, and every other var()-driven color in one shot. It
    intentionally doesn't touch Plotly chart colors (style_fig() in this
    module) -- those are baked into each figure as literal RGB values at
    build time, not read from CSS, and were deliberately kept on a fixed
    colorblind-friendly palette per earlier feedback on this dashboard.

    ``parameter`` is whichever of the several independent per-view
    "Parameter" dropdowns the user most recently changed (tracked in
    st.session_state by render_parameter_and_subset() in
    src/views/common.py) -- there's no single "current" parameter since
    every view keeps its own selection, so this app-wide theme follows
    whichever one was touched last, defaulting to "neutral" (this app's
    every dropdown defaults to the alphabetically-first parameter, which
    is "Cloud Cover Total") before the user has touched any of them."""
    category = categorize_parameter(parameter) if parameter else "neutral"
    _render_theme_vars(PALETTES_BY_CATEGORY[category])


def render_brand() -> None:
    # Same --m3-on-primary-container token every other piece of themed
    # text in the app reads (render_section_label() in
    # src/views/common.py, the Live Weather hero's city name, the nav
    # capsule/tab styling above) -- this used to read --m3-primary
    # instead, which desaturates to a visibly different grey under the
    # "neutral" theme (#8C8C8C vs #444444).
    st.markdown(
        f'<div class="app-brand" style="text-align: left; font-weight: 700; '
        f'font-size: 1.85rem; letter-spacing: 0.02em; '
        f'color: var(--m3-on-primary-container, {PRIMARY["on_primary_container"]});">WeatheRe</div>',
        unsafe_allow_html=True,
    )


def chart_card(key: str | None = None):
    """``key`` is only needed by callers that must target this specific
    card with scoped CSS afterwards (e.g. positioning an overlay icon over
    one particular chart) -- see render_missing_stations_indicator() in
    src/views/common.py. Streamlit adds an "st-key-{key}" class to the
    container's wrapper div, so passing one doesn't change anything
    visually by itself."""
    return st.container(border=True, key=key)


def _current_ink_hex() -> str:
    """Solid on_primary_container-family hex for whatever theme category
    the app-wide dynamic theme (see apply_dynamic_theme()) is currently
    on -- the exact same token render_section_label() and the Live
    Weather hero's city name use (src/views/common.py,
    src/views/live_weather.py), so a chart's chrome (axis ticks,
    gridlines, legend, title, modebar) always matches the page text
    sitting around it: #1E4469 (blue) / #695A1E (gold) / #444444 (grey).
    Only chart *chrome* follows the theme this way -- each view's own
    data-series colors (px.line/... colors, station colors, trend-line
    colors) stay on their fixed, colorblind-friendly palette per this
    dashboard's earlier accessibility feedback, since those encode data
    and must stay distinguishable regardless of theme."""
    parameter = st.session_state.get("active_theme_parameter")
    category = categorize_parameter(parameter) if parameter else "neutral"
    return PALETTES_BY_CATEGORY[category]["on_primary_container"]


def _current_grid_rgba(opacity: float = 0.12) -> str:
    hex_color = _current_ink_hex()
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{opacity})"


def style_fig(fig: go.Figure) -> go.Figure:
    ink = _current_ink_hex()
    grid = _current_grid_rgba()
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=ink,
        title_font_color=ink,
        legend=dict(bgcolor="rgba(0,0,0,0)", font_color=ink),
        # Tightened from t=60/b=50/l=40/r=40 -- every chart in the app goes
        # through this one function, so this is the actual plotted area's
        # own share of its card shrinking regardless of the card's own CSS
        # padding (see the chart_card() rule in _BASE_CSS below, left
        # untouched here since it's shared by every bordered card in the
        # app, not just charts -- shrinking it would also cramp Key
        # Figures stat cards etc.). Still enough room for the title and
        # axis ticks/labels, just not padded past what they need.
        margin=dict(t=42, b=36, l=30, r=20),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color="#90A4AE", activecolor=ink),
    )
    fig.update_xaxes(
        gridcolor=grid,
        zerolinecolor=grid,
        linecolor=grid,
        tickfont_color=ink,
        title_font_color=ink,
    )
    fig.update_yaxes(
        gridcolor=grid,
        zerolinecolor=grid,
        linecolor=grid,
        tickfont_color=ink,
        title_font_color=ink,
    )
    return fig


_CHART_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]}


def render_chart(fig: go.Figure) -> None:
    st.plotly_chart(style_fig(fig), width="stretch", config=_CHART_CONFIG)
