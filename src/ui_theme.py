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


# Every SURFACE/PRIMARY token shares one blue hue (~210-220 deg) at its own
# individual saturation/lightness -- confirmed via colorsys.rgb_to_hls on
# each hex above. That means a whole alternate-hue theme can be derived
# token-by-token from this one, rather than hand-picking new colors per
# token: "temperature" rotates every token to the same warm gold hue (48),
# "neutral" desaturates every token to 0% (same lightness, no hue), and
# "precipitation" is just the existing blue set, unmodified. Every derived
# color therefore sits at the *same* saturation/lightness as its blue
# counterpart -- never more, never less, per this feature's own ask.
_THEME_TOKENS = {**SURFACE, **PRIMARY}

PALETTES_BY_CATEGORY = {
    "precipitation": dict(_THEME_TOKENS),
    "temperature": {name: _with_hue(hexval, hue_degrees=48) for name, hexval in _THEME_TOKENS.items()},
    "neutral": {name: _with_hue(hexval, hue_degrees=None, saturation=0.0) for name, hexval in _THEME_TOKENS.items()},
}

# Key Figures toolbar accent per src.analysis.categorize_parameter() --
# just the "primary" token out of each category's full palette above.
ACCENT_HEX_BY_CATEGORY = {category: palette["primary"] for category, palette in PALETTES_BY_CATEGORY.items()}


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
    background: color-mix(in srgb, var(--m3-primary, #4D77CB) 80%, white) !important;
    border-color: color-mix(in srgb, var(--m3-primary, #4D77CB) 80%, white) !important;
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
    font-weight: 500 !important;
    font-size: 1rem !important;
    color: var(--m3-on-surface-variant, #52657A) !important;
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
    background: color-mix(in srgb, var(--m3-primary, #4D77CB) 85%, transparent) !important;
}
[data-testid="stTab"] {
    background: transparent !important;
    padding: 0.4rem 0.1rem !important;
    transition: color 0.15s ease;
}
[data-testid="stTab"][aria-selected="true"] p {
    color: color-mix(in srgb, var(--m3-primary, #4D77CB) 85%, transparent) !important;
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
    _render_theme_vars(PALETTES_BY_CATEGORY["precipitation"])


def apply_dynamic_theme(parameter: str | None) -> None:
    """Re-assert every --m3-* custom property (and .stApp's background)
    using the color category of ``parameter`` (see categorize_parameter()
    in src/analysis.py), overriding the default blue palette
    render_app_background() painted at the top of the script.

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
    st.markdown(
        f'<div class="app-brand" style="text-align: left; font-weight: 700; '
        f'font-size: 1.6rem; letter-spacing: 0.02em; '
        f'color: color-mix(in srgb, var(--m3-primary, {PRIMARY["primary"]}) 85%, transparent);">WeatheRe</div>',
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


_CHART_INK = PRIMARY["on_primary_container"]
_CHART_GRID = "rgba(30, 68, 105, 0.12)"


def _current_chart_title_color() -> str:
    """The chart title ("heading") color for whatever category the app-wide
    dynamic theme (see apply_dynamic_theme()) is currently on -- read from
    the same st.session_state["active_theme_parameter"] that theme uses, so
    a chart's own heading always matches the background/nav row/Key Figures
    color it's currently sitting in. Only the *title* follows the theme;
    axis ticks/gridlines/legend text and the data lines themselves
    (_CHART_INK/_CHART_GRID, and each view's own px.line/... colors) stay
    fixed, per this dashboard's earlier colorblind-accessibility feedback
    on those specific elements."""
    parameter = st.session_state.get("active_theme_parameter")
    category = categorize_parameter(parameter) if parameter else "neutral"
    hex_color = ACCENT_HEX_BY_CATEGORY[category]
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},0.85)"


def style_fig(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=_CHART_INK,
        title_font_color=_current_chart_title_color(),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_color=_CHART_INK),
        margin=dict(t=60, b=50, l=40, r=40),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color="#90A4AE", activecolor=PRIMARY["on_primary_container"]),
    )
    fig.update_xaxes(
        gridcolor=_CHART_GRID,
        zerolinecolor=_CHART_GRID,
        linecolor=_CHART_GRID,
        tickfont_color=_CHART_INK,
        title_font_color=_CHART_INK,
    )
    fig.update_yaxes(
        gridcolor=_CHART_GRID,
        zerolinecolor=_CHART_GRID,
        linecolor=_CHART_GRID,
        tickfont_color=_CHART_INK,
        title_font_color=_CHART_INK,
    )
    return fig


_CHART_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]}


def render_chart(fig: go.Figure) -> None:
    st.plotly_chart(style_fig(fig), width="stretch", config=_CHART_CONFIG)
