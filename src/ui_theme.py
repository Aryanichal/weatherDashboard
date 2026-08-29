"""Dynamic background themes that switch based on the selected weather parameter.

Pure CSS/no external assets (no image downloads, no network calls) so it
works offline and keeps the app self-contained. Each theme is a static,
muted mesh gradient -- a soft blend of a couple of low-saturation accent
colors over a neutral zinc/slate base (the current "soft gradient" look
used by modern product UIs).

"""

import plotly.graph_objects as go
import streamlit as st

# Map each climate_summary parameter to the weather "mood" that best matches
# it. Unrecognized/future parameters fall back to the neutral "cloudy" theme.
PARAMETER_THEMES: dict[str, str] = {
    "temperature_air_mean_2m": "sunny",
    "temperature_air_max_2m": "sunny",
    "temperature_air_min_2m": "sunny",
    "temperature_air_min_0_05m": "sunny",
    "sunshine_duration": "sunny",
    "cloud_cover_total": "cloudy",
    "humidity": "cloudy",
    "pressure_air_site": "cloudy",
    "pressure_vapor": "cloudy",
    "precipitation_height": "rainy",
    "precipitation_form": "rainy",
    "snow_depth": "snowy",
    "wind_speed": "windy",
    "wind_gust_max": "windy",
}

DEFAULT_THEME = "cloudy"


def get_theme_for_parameter(parameter: str) -> str:
    return PARAMETER_THEMES.get(parameter, DEFAULT_THEME)


_BASE_CSS = """
<style>
[data-testid="stHeader"] { background: transparent; }

@keyframes weather-fade-out {
    from { opacity: 1; }
    to { opacity: 0; }
}
/* Sits above .stApp's own (new) background and fades away to reveal it --
   see the module docstring for why this is a real element + @keyframes
   animation rather than a transition or a negative-z-index pseudo-element. */
.weather-fade-overlay {
    position: fixed;
    inset: 0;
    z-index: 1;
    pointer-events: none;
    animation: weather-fade-out 1.1s ease forwards;
}

/* Explicit positive z-index (and the "position" needed for it to apply) so
   actual content always paints above the fade overlay, regardless of DOM
   order or whatever stacking context .stApp itself happens to establish. */
[data-testid="stAppViewContainer"] .main .block-container,
[data-testid="stSidebar"] {
    position: relative;
    z-index: 2;
}

/* Frosted-glass content panel so charts/text stay readable over the
   background -- keeps a modern sleek look without sacrificing contrast. */
[data-testid="stAppViewContainer"] .main .block-container {
    background: rgba(255, 255, 255, 0.82);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-radius: 20px;
    padding: 0.5rem 2.5rem 2rem;
    margin-top: 0;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}
/* Streamlit reserves a large top gap (both on .main itself and again on its
   first child) by default to clear the header bar; our own smaller padding
   above already covers that clearance, so this collapses the leftover
   reserved space instead of stacking on top of it. */
[data-testid="stAppViewContainer"] .main,
[data-testid="stAppViewContainer"] .main > div:first-child {
    padding-top: 0 !important;
}
/* The title (st.title -> h1) and the row after it (st.tabs) each carry
   their own default top margin/gap on top of the block-container's own
   padding above -- trim those too so the title sits right at the top of
   the panel and the tab row sits close under it. */
.main .block-container h1:first-of-type {
    margin-top: 0 !important;
    padding-top: 0 !important;
}
[data-testid="stVerticalBlock"] {
    gap: 0.5rem !important;
}
[data-testid="stHeader"] {
    height: 2rem;
}
/* Floating frosted-glass card, matching the main content panel, instead of
   a flush-to-the-edge slab -- the margin is what lets the rounded corners
   and shadow actually read against the background instead of being clipped
   by the viewport edge. */
[data-testid="stSidebar"] {
    background: rgba(255, 255, 255, 0.55);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    margin: 0.25rem 0 0.25rem 1rem;
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.5);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    overflow: hidden;
    height: calc(100vh - 0.5rem);
}
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebarContent"] {
    padding-top: 0.5rem;
}

/* The multiselect's selected-station "tags" default to Streamlit's fixed
   accent color (blue) regardless of theme; tie them to the active theme's
   accent instead, set as a CSS custom property alongside the background in
   render_weather_background() below. Several overlapping selectors because
   BaseWeb nests a couple of elements/states here (base, hovered, focused)
   that can each carry their own background. */
[data-testid="stMultiSelect"] span[data-baseweb="tag"],
[data-testid="stMultiSelect"] span[data-baseweb="tag"]:hover,
[data-testid="stMultiSelect"] span[data-baseweb="tag"][aria-disabled="false"] {
    background-color: var(--theme-accent, #3b82f6) !important;
    border-color: var(--theme-accent, #3b82f6) !important;
}
</style>
"""

# Static mesh gradients: a couple of soft, low-saturation radial blobs over a
# neutral zinc/slate base. Kept light across every theme (including "rainy",
# which used to go near-black) so the frosted panel and the chart ink color
# in style_fig() stay legible no matter which theme is active.
_THEME_GRADIENTS = {
    "sunny": """
        radial-gradient(at 15% 15%, rgba(255, 200, 130, 0.55) 0, transparent 55%),
        radial-gradient(at 85% 10%, rgba(255, 150, 130, 0.35) 0, transparent 55%),
        radial-gradient(at 50% 95%, rgba(255, 224, 160, 0.5) 0, transparent 60%),
        linear-gradient(180deg, #fafafa 0%, #f4f4f5 100%)""",
    "cloudy": """
        radial-gradient(at 20% 20%, rgba(148, 163, 184, 0.35) 0, transparent 55%),
        radial-gradient(at 80% 80%, rgba(203, 213, 225, 0.45) 0, transparent 60%),
        radial-gradient(at 50% 40%, rgba(226, 232, 240, 0.3) 0, transparent 60%),
        linear-gradient(180deg, #f8fafc 0%, #eef1f5 100%)""",
    "rainy": """
        radial-gradient(at 15% 20%, rgba(129, 156, 216, 0.35) 0, transparent 55%),
        radial-gradient(at 85% 15%, rgba(165, 180, 224, 0.3) 0, transparent 55%),
        radial-gradient(at 50% 100%, rgba(199, 210, 240, 0.5) 0, transparent 60%),
        linear-gradient(180deg, #f5f7fb 0%, #e9edf6 100%)""",
    "snowy": """
        radial-gradient(at 20% 10%, rgba(186, 222, 245, 0.5) 0, transparent 55%),
        radial-gradient(at 80% 90%, rgba(224, 242, 254, 0.6) 0, transparent 60%),
        radial-gradient(at 50% 40%, rgba(240, 249, 255, 0.3) 0, transparent 60%),
        linear-gradient(180deg, #fbfdff 0%, #eef6fb 100%)""",
    "windy": """
        radial-gradient(at 15% 85%, rgba(148, 210, 189, 0.35) 0, transparent 55%),
        radial-gradient(at 85% 20%, rgba(180, 220, 205, 0.35) 0, transparent 55%),
        radial-gradient(at 50% 40%, rgba(230, 245, 240, 0.3) 0, transparent 60%),
        linear-gradient(180deg, #f7fbfa 0%, #eaf4f0 100%)""",
}

# A more saturated pick from each theme's own accent hue, used for anything
# that needs a solid (non-gradient) color tied to the current theme -- e.g.
# the multiselect "tag" background below -- rather than Streamlit's fixed
# default accent color.
_THEME_ACCENTS = {
    "sunny": "#f2a340",
    "cloudy": "#64748b",
    "rainy": "#5b7bd1",
    "snowy": "#4fb3d9",
    "windy": "#4aa585",
}

_LAST_THEME_KEY = "_weather_bg_last_theme"


def render_weather_background(parameter: str) -> None:
    """Inject the background CSS matching ``parameter``'s weather theme,
    fading in from whichever theme was showing before."""
    theme = get_theme_for_parameter(parameter)
    previous_theme = st.session_state.get(_LAST_THEME_KEY, theme)
    st.session_state[_LAST_THEME_KEY] = theme

    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<style>.stApp {{ background: {_THEME_GRADIENTS[theme]}; }}'
        f' :root {{ --theme-accent: {_THEME_ACCENTS[theme]}; }}</style>',
        unsafe_allow_html=True,
    )
    if previous_theme != theme:
        st.markdown(
            f'<style>.weather-fade-overlay {{ background: {_THEME_GRADIENTS[previous_theme]}; }}</style>'
            '<div class="weather-fade-overlay"></div>',
            unsafe_allow_html=True,
        )


# Muted, low-contrast ink that reads fine over the frosted-glass panel
# (rgba(255,255,255,0.82), see _BASE_CSS) regardless of which theme is active
# behind it, so charts don't need to know/care which theme is showing.
_CHART_INK = "#2f3947"
_CHART_GRID = "rgba(47, 57, 71, 0.12)"


def style_fig(fig: go.Figure) -> go.Figure:
    """Strip a Plotly figure's opaque white chrome so it blends into the
    frosted-glass content panel instead of sitting on it as a stark white box."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=_CHART_INK,
        title_font_color=_CHART_INK,
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=60, b=40, l=40, r=20),
    )
    fig.update_xaxes(gridcolor=_CHART_GRID, zerolinecolor=_CHART_GRID, linecolor=_CHART_GRID)
    fig.update_yaxes(gridcolor=_CHART_GRID, zerolinecolor=_CHART_GRID, linecolor=_CHART_GRID)
    return fig
