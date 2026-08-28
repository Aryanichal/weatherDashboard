"""Static theming/CSS for the dashboard.

Pure CSS/no external assets (no image downloads, no network calls) so it
works offline and keeps the app self-contained. The page is a single flat
neutral gray, deliberately off the brand palette below, and the sidebar is a
subtle light gray of its own -- the actual color/contrast lives in
individual "cards" (see chart_card()): borderless white containers with a
soft drop shadow, echoing the card-based dashboard look (white canvas, white
content tiles that pop off it) rather than a colored panel-on-panel look.

Fixed brand palette (https://colorhunt.co/palette/e3f2fd90caf92196f30d47a1),
still used for chart cards and selected-station tags via PALETTE["blue"] /
PALETTE["navy"] -- just not for the page background or sidebar anymore.
"""

import plotly.graph_objects as go
import streamlit as st

PALETTE = {
    "blue": "#2196F3",
    "navy": "#0D47A1",
}


_BASE_CSS = """
<style>
[data-testid="stHeader"] { background: transparent; }
/* The "Deploy" button is Streamlit's own dev-facing chrome, not something
   end users of this dashboard need. Both the data-testid attribute
   selector and the plain class selector, since Streamlit's toolbar renders
   both on the same element and a class selector wins any specificity
   tie-break a future version might introduce; also collapse width/height
   so a hidden-but-still-flex-sized element can't still occupy toolbar
   space. (The hamburger menu -- #MainMenu / stMainMenu -- used to be
   hidden here too; that's been reverted, it's back.) */
[data-testid="stDeployButton"], .stDeployButton, .stDeployButton * {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
}
/* The "Running..." status spinner doesn't have to be hidden to get it out
   of that corner -- it's just a normally-flowed toolbar element, so pulling
   it out with fixed positioning (the same trick used for .app-brand below)
   relocates it to a bottom corner instead. z-index is set well above
   Streamlit's own header chrome (it uses very large z-index values for its
   header/toolbar) so nothing from that toolbar can render on top of and
   collide with either this or .app-brand. */
[data-testid="stStatusWidget"] {
    position: fixed !important;
    left: 1rem;
    bottom: 0.75rem;
    z-index: 1000000;
}

/* st.cache_data's show_spinner (e.g. "Fetching observations from DWD...")
   renders in-flow whereever the triggering call happens to sit on the page,
   which is why it used to show up as a small, easy-to-miss line of text
   halfway down the app. Pull it out of that flow and pin it front-and-center
   as a proper card instead, styled like the rest of the dashboard's white
   cards (see stVerticalBlockBorderWrapper below) plus a dimming backdrop so
   it reads as a modal-style loading state rather than a page detail. */
[data-testid="stSpinner"] {
    position: fixed !important;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 1000001;
    background: #FFFFFF !important;
    border: 1px solid color-mix(in srgb, var(--theme-accent, #2196F3) 30%, transparent);
    border-radius: 16px;
    box-shadow: 0 12px 40px rgba(15, 23, 42, 0.18);
    padding: 1.5rem 2rem;
    width: max-content;
    max-width: min(90vw, 420px);
}
[data-testid="stSpinner"] p {
    color: #0D47A1 !important;
}
[data-testid="stSpinner"]::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    background: rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    /* Extend the backdrop from the card's own centered box back out to
       cover the full viewport -- undoes the parent's translate/centering
       for this pseudo-element only. */
    width: 100vw;
    height: 100vh;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
}
[data-testid="stSpinner"] > div {
    justify-content: center;
}

/* Explicit positive z-index so actual content always paints above the page
   background, regardless of DOM order or whatever stacking context .stApp
   itself happens to establish. */
[data-testid="stAppViewContainer"] .main .block-container,
[data-testid="stSidebar"] {
    position: relative;
    z-index: 2;
}

/* The page background is now a faint wash rather than a busy panel-on-panel
   look, so the main canvas itself just needs padding -- no background/blur/
   shadow of its own, since the individual chart_card() tiles below are what
   carry color now.
   [data-testid="stMainBlockContainer"] is the current (~1.62) testid for
   this element -- confirmed via DevTools that Streamlit renamed/dropped the
   `.main` class this file's selectors were originally written against
   somewhere between 1.37 and 1.62 (same story as stVerticalBlockBorderWrapper
   elsewhere in this file), which is why "flush to the top" silently stopped
   working: `.main .block-container` no longer matches anything, so none of
   these rules were actually applying. `.block-container` on its own still
   exists as a class, so only the `.main`-rooted selectors needed the
   testid added alongside them, kept together for the same wide-version-range
   reason as elsewhere in this file. */
[data-testid="stAppViewContainer"] .main .block-container,
[data-testid="stMainBlockContainer"] {
    padding: 0.5rem 2.5rem 2rem !important;
    margin-top: 0;
}
/* Streamlit reserves a large top gap (confirmed via DevTools: 96px, on
   stMainBlockContainer specifically in the current version) to clear the
   header bar; our own smaller padding above already covers that clearance,
   so this collapses the leftover reserved space instead of stacking on top
   of it. */
[data-testid="stAppViewContainer"] .main,
[data-testid="stAppViewContainer"] .main > div:first-child,
[data-testid="stMain"] {
    padding-top: 0 !important;
}
/* The brand wordmark (render_brand()) carries a default top margin/gap on
   top of the block-container's own padding above -- trim it, and then pull
   it up most (not all) of the way back with a negative margin, leaving a
   small deliberate gap so it reads as "near the top" rather than stuck
   flush against the very edge of the viewport. line-height: 1 removes the
   font's own default leading, which otherwise adds a bit more apparent
   space above the glyphs on top of the padding/margin math. */
.main .block-container .app-brand,
[data-testid="stMainBlockContainer"] .app-brand {
    margin-top: -0.25rem !important;
    /* Breathing room below the title: keeps WeatheRe pinned flush at the
       top (the negative margin-top above is what does that) while pushing
       the tabs row and everything under it down, instead of the two
       sitting almost flush against each other. */
    margin-bottom: 1.5rem !important;
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
/* Standardized vertical rhythm for the main content area specifically:
   confirmed via precise measurement (not eyeballing) that title-to-tabs
   and tabs-to-"Parameter" were already a consistent 16px apart, but
   "Parameter"-to-chart-card was only 8px (the global gap above, since
   those two are siblings inside the tab panel's own vertical block) --
   this brings that last gap in line with the other two instead of it
   reading as tighter/different for no visible reason. Scoped to just the
   tab panel's own content block so it doesn't also loosen up unrelated
   spacing elsewhere (sidebar, expander internals, side-by-side columns)
   that wasn't part of this alignment pass. */
[data-testid="stTabPanel"] > [data-testid="stVerticalBlock"] {
    gap: 1rem !important;
}
[data-testid="stHeader"] {
    height: 2rem;
}
/* Tab labels ("Time Series", "Map", "Regression", "Clustering", "Global
   Warming Trend") default to font-weight 400 for both the active and
   inactive tabs -- semi-bolded so the row reads as proper section
   navigation without being as heavy as full bold. */
[data-testid="stTab"] p {
    font-weight: 600 !important;
}
/* Segmented-control look: the active tab sits in its own white rounded
   capsule (shadow to match the "popped" look used elsewhere) instead of
   Streamlit's default underline-only indicator. Confirmed via DevTools
   that the sliding underline bar is a separate element,
   `.react-aria-SelectionIndicator` (not a border/box-shadow on the tab
   itself, which is why it needed hiding rather than overriding one
   property) -- the white capsule below replaces it as the selection cue
   instead of stacking both. No track background and no divider line under
   the row -- there's a bare, already-hidden <hr> in here too (unrelated,
   left alone), but the actual visible 2px divider turned out to be a
   `::after` pseudo-element on the tablist itself (content:"", height:2px,
   a light-grey background) -- confirmed by walking pixel-by-pixel with
   elementFromPoint since it doesn't show up as a border/box-shadow on any
   element's own computed style, only on its generated ::after. */
[role="tablist"] {
    display: inline-flex;
    gap: 0.25rem;
}
[data-testid="stTabs"] hr {
    display: none;
}
[role="tablist"]::after {
    display: none !important;
}
[role="tablist"] .react-aria-SelectionIndicator {
    display: none;
}
/* Every tab is always a white capsule; the active one swaps to the brand
   navy (same as "WeatheRe") with white text instead of just gaining a
   shadow, so the row reads as a proper on/off toggle rather than
   "selected = slightly raised". */
[data-testid="stTab"] {
    background: #FFFFFF !important;
    border-radius: 999px !important;
    padding: 0.4rem 1rem !important;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.12);
    transition: background-color 0.15s ease, box-shadow 0.15s ease;
}
[data-testid="stTab"][aria-selected="true"] {
    background: #0D47A1 !important;
}
[data-testid="stTab"][aria-selected="true"] p {
    color: #FFFFFF !important;
}
/* Subtle light-gray panel (deliberately off the app's blue accent palette,
   per instruction) so it still reads as its own "colored panel" without
   competing with the page -- the margin is what lets the rounded corners
   and shadow actually read against the page instead of being clipped by
   the viewport edge. Being a light fill (not a dark one, unlike the
   previous vivid-blue version), widget text/labels below are flipped to a
   dark neutral instead of white for contrast. */
[data-testid="stSidebar"] {
    background: #E9ECEF;
    margin: 0.25rem 0 0.25rem 1rem;
    border-radius: 20px;
    border: 1px solid rgba(0, 0, 0, 0.06);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
    overflow: hidden;
    height: calc(100vh - 0.5rem);
    transition: min-width 0.15s ease, max-width 0.15s ease, width 0.15s ease;
}
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebarContent"] {
    padding-top: 0.5rem;
}
/* Flip default widget text to a dark neutral so it stays legible against
   the light-gray fill above -- covers the "Selection" header, the
   "Weather stations" multiselect label, and the "Date range" label.
   Anything inside the date-input box itself is excluded so that box stays
   fully native -- confirmed via a real DevTools inspection that this
   Streamlit build renders the picked day/month/year as React Aria
   "spinbutton" spans (`data-rac`), not the older plain BaseWeb <input>
   this file originally assumed; this blanket text-color rule was still
   catching those spans. `[data-rac]` is React Aria's own marker attribute
   on every element it manages, so excluding by that -- rather than by a
   specific DOM shape -- covers this version and isn't tied to assumptions
   about internal structure the way the old `[data-baseweb="input"] *`
   exclusion was. The "Date range" label itself sits outside the React
   Aria date field, so it's untouched by the exclusion and still gets
   recolored as intended. */
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p:not([data-testid="stDateInput"] *),
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] span:not([data-baseweb="tag"] *):not([data-testid="stDateInput"] [data-baseweb="input"] *):not([data-rac]) {
    color: #212529 !important;
}
/* "Date range" label specifically called out heavier than the rest. */
[data-testid="stDateInput"] label {
    font-weight: 600 !important;
}
/* The multiselect's selected-station "tags" default to Streamlit's own
   blue (rgb(31,119,180)), not the brand's -- pinned to the same navy as
   "WeatheRe" instead, matching the active-tab capsule elsewhere in this
   file. [data-baseweb="tag"] was this rule's original selector, written
   against an older Streamlit's BaseWeb-based multiselect; confirmed via
   DevTools that the current build's tags carry a `data-tag` attribute
   instead (no `data-baseweb` anywhere on them), which is why this was
   silently never applying -- same story as the several other
   [data-baseweb=...]/[data-testid=...] selectors elsewhere in this file
   that turned out to be stale against the newer React Aria-based DOM. */
[data-testid="stMultiSelect"] span[data-tag] {
    background-color: #0D47A1 !important;
    border-color: #0D47A1 !important;
}
/* Tag text (and its remove "x" icon) defaults to dark grey, confirmed via
   DevTools as rgb(33,37,41) -- invisible-ish on the navy fill above, so
   forced to white. Scoped to inside the tag specifically so the dropdown
   list's own option text (a separate popover element, not a descendant of
   the tag) stays whatever color it already is, unaffected.
   -webkit-text-fill-color is required alongside color, not optional
   belt-and-suspenders -- confirmed by testing color alone first: it took
   in getComputedStyle(...).color but the glyphs kept rendering in the old
   dark grey regardless, because Chromium paints text using
   -webkit-text-fill-color when present and this component sets it
   explicitly (same root cause as the date-input fix elsewhere in this
   file). */
[data-testid="stMultiSelect"] span[data-tag],
[data-testid="stMultiSelect"] span[data-tag] * {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

/* Card look for chart_card()'s st.container(border=True) wrapper: solid
   white, no border, and a soft shadow instead of Streamlit's default flat
   grey-bordered box -- the shadow alone is what separates it from the page
   now that there's no border or background tint to do that job.

   This needs TWO selectors because Streamlit restructured how border=True
   containers reach the DOM somewhere between 1.37 and 1.62 (confirmed by
   actually running this app under both versions -- this file's fixes kept
   silently no-op'ing on a newer Streamlit than whatever this was last
   tested against, which is exactly the gap requirements.txt's wide
   `streamlit>=1.38,<2.0` leaves open):

   - Old (~1.37): every bordered container got its own dedicated
     [data-testid="stVerticalBlockBorderWrapper"] element. That testid was
     NOT exclusive to border=True containers, though -- Streamlit wraps its
     own page-level main content area in one too (border=False, so
     Streamlit itself leaves it with no visible border/padding). Both used
     to get force-styled identically by this rule, producing a big white
     rounded "card" behind the whole page with a real chart_card() nested
     inside it. The :not() exclusion is what told them apart: a real
     chart_card() is always nested at least one level deep, while
     Streamlit's own page-level wrapper is always a direct child of
     stAppViewBlockContainer.
   - New (~1.62): stVerticalBlockBorderWrapper doesn't exist in the DOM at
     all anymore -- border=True now applies directly to the
     [data-testid="stVerticalBlock"] div itself, and Streamlit wraps just
     that one in a new [data-testid="stLayoutWrapper"] (confirmed this
     wrapper does NOT appear around plain, unconfigured vertical blocks --
     only around ones with real layout props like border/height set, which
     is what makes `stLayoutWrapper > stVerticalBlock` a safe, precise
     selector without needing an exclusion this time).

   Streamlit's own border/radius for these elements ships as
   emotion-injected CSS that also carries !important, and that <style> tag
   isn't guaranteed to land in the document before this one -- so a plain
   single-attribute selector can lose the cascade purely on source order
   even though it's !important on both sides. Repeating the attribute
   selector in the old-version half doesn't change what it matches, only
   its specificity (0,2,0 instead of 0,1,0), which wins regardless of
   order -- that's the actual fix there, not the !important alone. */
[data-testid="stVerticalBlockBorderWrapper"][data-testid="stVerticalBlockBorderWrapper"]:not([data-testid="stAppViewBlockContainer"] > *),
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {
    background: #FFFFFF !important;
    border: none !important;
    outline: none !important;
    border-radius: 24px !important;
    box-shadow: 0 12px 32px rgba(15, 23, 42, 0.16) !important;
    padding: 1.5rem !important;
    /* Confirmed via a real headless render (on the old-DOM version) that
       this padding correctly insets the plotly element by an even 24px on
       all four sides (measured precisely, not just eyeballed) -- overflow:
       hidden isn't covering for a layout bug, it's just what stops the
       chart's own square corners (or a future wider element) from poking
       past the card's rounded ones. */
    overflow: hidden !important;
}

/* Select/multiselect boxes: solid white, no visible border, matching the
   date-input box's own native look (confirmed via DevTools that Streamlit's
   date box is already borderless white by default -- these two just
   weren't, so this brings them in line with it rather than the other way
   around). Two selectors because Streamlit rebuilt these widgets on React
   Aria at some point, dropping [data-baseweb="select"] (BaseWeb's old
   "Root"/"ControlContainer" element) entirely -- confirmed via DevTools
   that on the current build neither testid nor attribute exists anymore,
   so that half of this rule was silent dead weight until the
   [role="group"][data-rac] half was added (React Aria's own generic
   wrapper role, confirmed to be the actual box in this build: its
   computed background before this rule was Streamlit's default input
   grey, `rgb(240, 242, 246)`, distinct from the pure white this asks for).
   Kept both selectors together (rather than replacing the old one) since
   requirements.txt allows a wide `streamlit>=1.38,<2.0` range and there's
   no guarantee which internal version is actually installed. */
[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stMultiSelect"] [role="group"][data-rac],
[data-testid="stSelectbox"] [role="group"][data-rac] {
    background: #FFFFFF !important;
    border: none !important;
    outline: none !important;
    border-radius: 10px !important;
    /* The "popped off the page" shadow -- e.g. the "Parameter" dropdown,
       which isn't wrapped in a full chart_card() anymore, still needed
       something to read as raised rather than flat-printed on the page. */
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.12);
    transition: box-shadow 0.15s ease;
}
/* ...except inside the sidebar: its boxes (station tags, and the date box
   left untouched elsewhere) are deliberately flat against the sidebar's
   own panel, not popped -- this undoes the shadow above for that context
   specifically rather than scoping the rule with a `:not()`, since a
   plain override reads clearer than a negated compound selector here. */
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [role="group"][data-rac],
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"][data-rac] {
    box-shadow: none;
}
/* Focus falls on an element nested inside the box, not the box itself, so
   :focus-within on the wrapper is what catches "this control is active"
   and lets us draw a focus ring -- there's no resting border to move away
   from anymore, so this is purely additive on focus. */
[data-testid="stMultiSelect"]:focus-within [data-baseweb="select"],
[data-testid="stSelectbox"]:focus-within [data-baseweb="select"],
[data-testid="stMultiSelect"]:focus-within [role="group"][data-rac],
[data-testid="stSelectbox"]:focus-within [role="group"][data-rac] {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--theme-accent, #2196F3) 22%, transparent) !important;
}
/* The "Global warming trend settings" expander is no longer wrapped in a
   chart_card() -- its own <details> box now carries that same white/
   shadow/radius treatment directly, matching the "Parameter" selectbox
   above pixel-for-pixel (same radius, same shadow values) rather than
   sitting inside a separate outer card. Its native thin grey border
   (confirmed via DevTools: 1px solid rgba(38,39,48,0.2), 8px radius) is
   stripped first so it doesn't show through/double up with this one.
   The <summary> header row also gets its own light-grey background, but
   only once the expander is open (confirmed via DevTools: collapsed and
   expanded states use two different emotion classes, `rgba(0,0,0,0)` vs
   `rgb(248,249,251)`, as a native "this section is active" highlight) --
   testing only the collapsed state missed this the first time around. */
[data-testid="stExpander"] details {
    background: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.12) !important;
}
[data-testid="stExpander"] summary {
    background: transparent !important;
}
/* The popover menu (select options list) -- give it the same rounded,
   soft-shadow treatment as everything else instead of BaseWeb's default
   hard-edged white box. The date-input's calendar popover is left alone
   (native), same as the date box itself. */
[data-baseweb="menu"] {
    border-radius: 10px !important;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12) !important;
}
/* Plotly chart toolbar (zoom/pan/download): color comes from style_fig()'s
   modebar config, this is just the hover/active affordance -- a soft
   rounded highlight instead of Plotly's default hard-edged grey square,
   so it reads as a modern icon button rather than a stock widget. */
.modebar-btn:hover, .modebar-btn.active {
    background: color-mix(in srgb, #2196F3 12%, transparent) !important;
    border-radius: 6px !important;
}
</style>
"""

# Flat, single-color page background -- deliberately off the app's blue
# palette per instruction: no gradient, no wash, just one faded
# grayish-white behind everything.
_BACKGROUND_COLOR = "#F5F5F7"

# Fixed accent (PALETTE["blue"]) for anything that needs a solid color tied
# to the brand -- chart cards, the multiselect "tag" background -- rather
# than Streamlit's default blue. Not part of the background/sidebar change
# above; still drawn from the palette since it wasn't called out.
_ACCENT = PALETTE["blue"]


def render_app_background() -> None:
    """Inject the base CSS and the static page background."""
    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<style>.stApp {{ background: {_BACKGROUND_COLOR}; }}'
        f' :root {{ --theme-accent: {_ACCENT}; }}</style>',
        unsafe_allow_html=True,
    )


def render_brand() -> None:
    """Render the "WeatheRe" wordmark in the brand navy, at the top-left of
    the main content area, immediately next to the sidebar -- this replaces
    the old st.title("Weather Dashboard"). Deliberately normal document
    flow rather than position: fixed to a hardcoded coordinate: an in-flow
    element at the top of .block-container sits right at the sidebar's edge
    and automatically shifts left with .main when the sidebar is collapsed,
    which a fixed position could not do without JS to track sidebar state."""
    st.markdown(
        f'<div class="app-brand" style="text-align: left; font-weight: 700; '
        f'font-size: 1.6rem; letter-spacing: 0.02em; '
        f'color: {PALETTE["navy"]};">WeatheRe</div>',
        unsafe_allow_html=True,
    )


def chart_card():
    """A borderless white card with a soft shadow (see the
    stVerticalBlockBorderWrapper rule in _BASE_CSS) for a chart to live in.
    Use as ``with chart_card(): st.plotly_chart(style_fig(fig), ...)`` --
    style_fig() already makes the figure's own background transparent, so it
    blends straight into the card underneath it instead of showing as a
    separate white box inside it."""
    return st.container(border=True)


# PALETTE["navy"] for text/gridlines -- reads fine over the tinted
# chart_card() background regardless of which weather mood is active, since
# only the page background (not the accent/ink) changes with the mood.
_CHART_INK = PALETTE["navy"]
_CHART_GRID = "rgba(13, 71, 161, 0.12)"


def style_fig(fig: go.Figure) -> go.Figure:
    """Strip a Plotly figure's opaque white chrome so it blends into the
    chart_card() it's rendered in instead of sitting on it as a stark white box."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=_CHART_INK,
        title_font_color=_CHART_INK,
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=60, b=50, l=40, r=40),
        # Plotly's modebar (the zoom/pan/download toolbar) defaults to
        # its own grey-on-white palette regardless of the figure's own
        # theming -- pinned to the brand accent instead so it doesn't look
        # like a leftover default widget bolted onto a themed chart.
        modebar=dict(bgcolor="rgba(0,0,0,0)", color="#90A4AE", activecolor=PALETTE["blue"]),
    )
    fig.update_xaxes(gridcolor=_CHART_GRID, zerolinecolor=_CHART_GRID, linecolor=_CHART_GRID)
    fig.update_yaxes(gridcolor=_CHART_GRID, zerolinecolor=_CHART_GRID, linecolor=_CHART_GRID)
    return fig


# Plotly's default modebar includes select2d/lasso2d (rectangle/freeform
# selection) which are for scatter-plot brushing, not the line/bar charts
# every chart in this app actually uses -- trimmed along with the little
# Plotly logo button for a cleaner, more modern-looking toolbar rather than
# every chart carrying the full stock button set regardless of relevance.
_CHART_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]}


def render_chart(fig: go.Figure) -> None:
    """Render a Plotly figure with this app's shared styling and modebar config.

    Use as ``with chart_card(): render_chart(fig)`` -- the one place that
    wires together style_fig() and the trimmed/recolored modebar config, so
    every chart in the app gets both consistently instead of each call site
    repeating the same st.plotly_chart(style_fig(fig), ...) boilerplate."""
    st.plotly_chart(style_fig(fig), width="stretch", config=_CHART_CONFIG)
