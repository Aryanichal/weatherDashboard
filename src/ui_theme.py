import plotly.graph_objects as go
import streamlit as st

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

[data-testid="stAppViewContainer"] .main .block-container,
[data-testid="stSidebar"] {
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
[data-testid="stTabPanel"] > [data-testid="stVerticalBlock"] {
    gap: 1rem !important;
}
[data-testid="stHeader"] {
    height: 2rem;
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
[data-testid="stSidebar"] {
    background: var(--m3-surface-container, #D5E2F0);
    margin: 0.25rem 0 0.25rem 1rem;
    border-radius: 20px;
    border: 1px solid color-mix(in srgb, var(--m3-outline-variant, #B7C6D7) 40%, transparent);
    box-shadow: 0 8px 24px rgba(28, 42, 59, 0.08);
    overflow: hidden;
    height: calc(100vh - 0.5rem);
    transition: min-width 0.15s ease, max-width 0.15s ease, width 0.15s ease;
}
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebarContent"] {
    padding-top: 0.5rem;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p:not([data-testid="stDateInput"] *),
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] span:not([data-baseweb="tag"] *):not([data-testid="stDateInput"] [data-baseweb="input"] *):not([data-rac]) {
    color: var(--m3-on-surface-variant, #52657A) !important;
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
[data-testid="stSelectbox"] [role="group"][data-rac] {
    background: color-mix(in srgb, var(--m3-surface-container-lowest, #F9FAFB) 94%, transparent) !important;
    border: none !important;
    outline: none !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 14px rgba(28, 42, 59, 0.12);
    transition: box-shadow 0.15s ease;
}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [role="group"][data-rac],
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"][data-rac] {
    box-shadow: none;
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
[data-testid="stSelectbox"]:focus-within [role="group"][data-rac] {
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
</style>
"""

_BACKGROUND_COLOR = SURFACE["surface"]


def render_app_background() -> None:
    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    tokens = {**SURFACE, **PRIMARY}
    css_vars = " ".join(f'--m3-{role.replace("_", "-")}: {hex_value};' for role, hex_value in tokens.items())
    st.markdown(
        f'<style>.stApp {{ background: {_BACKGROUND_COLOR}; }}'
        f' :root {{ {css_vars} }}</style>',
        unsafe_allow_html=True,
    )


def render_brand() -> None:
    st.markdown(
        f'<div class="app-brand" style="text-align: left; font-weight: 700; '
        f'font-size: 1.6rem; letter-spacing: 0.02em; '
        f'color: color-mix(in srgb, {PRIMARY["primary"]} 85%, transparent);">WeatheRe</div>',
        unsafe_allow_html=True,
    )


def chart_card():
    return st.container(border=True)


_CHART_INK = PRIMARY["on_primary_container"]
_CHART_GRID = "rgba(30, 68, 105, 0.12)"

_CHART_TITLE_COLOR = "rgba(77, 119, 203, 0.85)"


def style_fig(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=_CHART_INK,
        title_font_color=_CHART_TITLE_COLOR,
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
