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
    """Return ``hex_color`` with its hue (and optionally saturation) replaced,
    keeping its lightness untouched."""
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = h if hue_degrees is None else hue_degrees / 360
    s = s if saturation is None else saturation
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))


_THEME_TOKENS = {**SURFACE, **PRIMARY}

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

# Key Figures toolbar accent, keyed by categorize_parameter()'s category.
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
/* Styles every st.segmented_control() (main nav + Temperature trend toggle)
   as a rounded-card look, active option filled with the accent color. */
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
/* Real st.tabs() styling, used by Global Warming's sub-tabs. */
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
/* Same lift+color hover as the segmented-control navs, unselected tab only. */
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

/* backdrop-filter lives on a ::before, not this box directly: applied here,
   it'd make position:fixed fullscreen charts resolve against this card
   instead of the viewport and get clipped by overflow:hidden below. No
   z-index either -- that would trap the fullscreen frame's stacking too. */
[data-testid="stVerticalBlockBorderWrapper"][data-testid="stVerticalBlockBorderWrapper"]:not([data-testid="stAppViewBlockContainer"] > *),
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {
    position: relative;
    border: 1px solid rgba(255, 255, 255, 0.5) !important;
    outline: none !important;
    border-radius: 24px !important;
    box-shadow: 0 12px 32px rgba(28, 42, 59, 0.16) !important;
    padding: 1.5rem !important;
    overflow: hidden !important;
}
[data-testid="stVerticalBlockBorderWrapper"][data-testid="stVerticalBlockBorderWrapper"]:not([data-testid="stAppViewBlockContainer"] > *)::before,
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    border-radius: inherit;
    background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.35), rgba(255, 255, 255, 0) 55%),
        color-mix(in srgb, color-mix(in srgb, white 80%, var(--m3-surface-container-low, #D8E2EC) 20%) 80%, transparent) !important;
    -webkit-backdrop-filter: blur(16px) saturate(150%);
    backdrop-filter: blur(16px) saturate(150%);
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
/* Animates st.slider()'s thumb gliding between steps instead of jumping.
   Targeted by inline transform since BaseWeb's class hash isn't stable. */
[data-testid="stSlider"] div[style*="translate(-50%, -50%)"] {
    transition: left 0.1s ease-out;
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
    parameter = st.session_state.get("active_theme_parameter")
    category = categorize_parameter(parameter) if parameter else "neutral"
    _render_theme_vars(PALETTES_BY_CATEGORY[category])


def apply_dynamic_theme(parameter: str | None) -> None:
    """Re-assert every --m3-* CSS var using ``parameter``'s color category,
    overriding render_app_background()'s best-guess palette with this run's
    actual one. Doesn't touch Plotly chart colors -- those stay on a fixed
    colorblind-friendly palette (see style_fig())."""
    category = categorize_parameter(parameter) if parameter else "neutral"
    _render_theme_vars(PALETTES_BY_CATEGORY[category])


def render_brand() -> None:
    st.markdown(
        f'<div class="app-brand" style="text-align: left; font-weight: 700; '
        f'font-size: 1.85rem; letter-spacing: 0.02em; '
        f'color: var(--m3-on-primary-container, {PRIMARY["on_primary_container"]});">WeatheRe</div>',
        unsafe_allow_html=True,
    )


def chart_card(key: str | None = None):
    """``key`` lets callers target this specific card with scoped CSS
    afterwards (Streamlit adds an "st-key-{key}" class to the wrapper)."""
    return st.container(border=True, key=key)


def _current_ink_hex() -> str:
    """Text-color hex for the current theme category, so chart chrome (axis
    ticks, gridlines, legend, title) matches the page text around it. Only
    chrome follows the theme -- data-series colors stay fixed for a11y."""
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
