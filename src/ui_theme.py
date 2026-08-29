"""Static theming/CSS for the dashboard.

Pure CSS/no external assets (no image downloads, no network calls) so it
works offline and keeps the app self-contained. The page background,
sidebar panel, cards, and every filled accent element (active tab,
selected-station tags, chart ink) now come from a Material Design 3
tone-based color system -- a blue-tinted SURFACE ladder plus a PRIMARY
accent pair, both below -- rather than one-off grays and a hand-picked
brand hex.

Both were originally seeded from this app's brand blue, #2196F3
(originally from https://colorhunt.co/palette/e3f2fd90caf92196f30d47a1);
see the comments on SURFACE and PRIMARY below for how each is actually
derived from it now.
"""

import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Tone-based surfaces (Material Design 3)
#
#   https://m3.material.io/blog/tone-based-surface-color-m3
#   https://m3.material.io/styles/color/system/overview
#
# M3's surface system is a small ladder of tones cut from one palette --
# surface_dim/surface/surface_bright at the extremes, plus five "container"
# steps in between -- so page background, panels, and cards all read as one
# coherent material instead of mismatched grays. Where a role sits on the
# ladder signals how "raised" that piece of UI is, the same role elevation/
# shadow already play elsewhere in this file; the two are combined below
# rather than one replacing the other.
#
# An earlier version of this ladder used Material Color Utilities' own
# TonalSpot algorithm at standard contrast, seeded from this app's brand
# blue (#2196F3) -- technically correct M3, but that algorithm caps a
# *neutral* palette's chroma extremely low (~4-8) by design, so page
# background, sidebar, and card all landed within a couple of luminance
# points of each other: correct on paper, but it read as "just white"
# rather than an actual toned surface. This version keeps the same ladder
# *shape* (same role names, same relative ordering from dim to
# container-lowest) but hand-tunes each tone at a much higher,
# clearly-visible saturation (~40-48%) and the same hue as the PRIMARY
# accent below (H=212, matching #A9CCF9), so every step -- including the
# cards -- reads as unmistakably blue rather than a hint of one.
#
# surface_container_lowest (inactive tab capsules, select/dropdown boxes,
# expander, popovers, and the chart/graph cards) has gone through a few
# tunings chasing a "blends into the page" complaint, then a "make the
# charts more readable, whiter, glassier" one. First at ~98% lightness,
# matching real M3's tone-100 "brightest step", which looked like plain
# white and got brought down to 94% -- but at 94% it was too close to
# `surface` itself for these elements to read as popped rather than
# blended. 97.5% lightness / 30% saturation was the next step, used for a
# while. Settled here at 98% lightness / 20% saturation -- whiter and
# less blue than that, both for the chart cards specifically (more
# separation between plotted data/text and the card behind it) and for
# every other small floating element sharing this token, while the 20%
# saturation still keeps a last whisper of the same blue tint rather than
# opting out of the tonal system into flat white.
#
# surface_container_low (now just the number-input boxes in the Global
# Warming settings expander, since the sidebar moved to surface_container
# and the chart cards moved to surface_container_lowest above -- see each
# one's own comment) was originally the same ~47% saturation as the rest
# of the ladder, which read as too strongly, distractingly blue for a
# fill this large. Cut to 35% (same lightness/hue) for a calmer, more
# neutral input fill that's still recognizably part of the same blue-tinted
# system, just toned down enough to stop fighting for attention with
# whatever's plotted on top of it.
#
# surface_container (sidebar only) is deliberately a *different*, poppier
# tone from surface_container_low even though both sit at similar
# lightness -- if the sidebar reused surface_container_low, it would land
# so close to primary_container (the station-tag capsule fill) in
# lightness/saturation that the tags would stop visually popping off the
# panel behind them. Kept at the ladder's original ~47% saturation
# instead (before the chart-card cut above) specifically so the panel
# reads as its own confidently-blue surface rather than blending toward
# either the calmer chart cards or the muted page canvas.
# surface (page canvas) lightened/desaturated from its original
# 93%-lightness/44%-saturation to 95%/30% -- reads noticeably closer to
# white while keeping a visible blue tint, rather than the stronger wash
# it started as. This is the outermost layer (.stApp's own background,
# nothing rendered behind it), so literal alpha transparency wouldn't
# have anything but the browser's default white canvas to blend against
# anyway -- lightening/desaturating the flat color directly gets the same
# "more white, still a little blue" result without the redundant blend.
SURFACE = {
    "surface_dim": "#A8C0DC",
    "surface": "#EEF2F6",
    "surface_bright": "#EEF3F9",
    "surface_container_lowest": "#F9FAFB",
    "surface_container_low": "#D8E2EC",
    "surface_container": "#D5E2F0",
    "surface_container_high": "#BFD2E8",
    "surface_container_highest": "#B4CAE4",
    "on_surface": "#1C2A3B",
    "on_surface_variant": "#52657A",
    "outline": "#788BA1",
    "outline_variant": "#B7C6D7",
}

# The app's accent color(s): primary_container is the light, saturated
# blue fill used for the station-tag capsules below, and
# on_primary_container is the dark navy M3's HCT algorithm targets to sit
# at standard contrast (6.08:1, comfortably above AA 4.5:1) *on top of
# that specific fill* -- station tags, mainly, since the tabs no longer
# have a filled background of their own to sit on.
#
# `primary` is a separate, hand-picked blue for text that sits directly on
# a light SURFACE tone rather than on a filled capsule -- currently the
# "WeatheRe" wordmark and the active tab (both label and sliding
# indicator). A previous version pointed these at on_primary_container
# too, for one single "the accent is this exact color everywhere" pair --
# but on_primary_container is tuned dark specifically so text stays
# legible sitting on the *light* primary_container fill; used instead as
# freestanding text against this app's much lighter surface tones, it
# read as too dark/near-black, clashing with the airier blue everywhere
# else rather than feeling like the same accent.
#
# Went through two vivid, WCAG-AA-floor picks first (#1565C0, then
# #166ACA at exactly 4.50:1 against the page -- the normal-text minimum)
# that still read as too saturated/contrasty against how light
# primary_container (the capsule fill, #A9CCF9) looks. Rather than push
# lightness alone (which desaturates and looks washed-out/gray at the
# extreme, the same issue SURFACE ran into earlier), this cuts saturation
# roughly in half (80%->50%) *and* renders at 85% opacity wherever it's
# used (color-mix against transparent, same technique the capsule
# backgrounds use) so the page's own tint shows through slightly --
# together those read as noticeably softer/lighter, closer to the
# capsule's airiness, at the deliberate cost of dropping below AA's 4.5:1
# floor (~3.7:1 against the page) -- acceptable here since this is
# decorative brand/nav text, not body copy, and bold+large weight keeps
# it legible in practice despite the lower contrast ratio.
#
# Hue nudged from 212° to 220° (same 55% saturation/55% lightness) for a
# more "poppy," modern-M3-blue feel -- 212° leans toward cyan/steel, while
# 220° reads as a richer, truer blue at the exact same saturation/
# lightness numbers (this is a perceptual-vividness thing HSL doesn't
# capture in the S value alone: how saturated a color *looks* at a given
# S/L varies by hue). 240° is pure blue on this wheel, so nudging further
# toward it (224°, 228°...) pushes further in the same "poppier" direction
# if this still isn't vivid enough; back toward 200-205° goes the other
# way, toward the steel/muted end.
PRIMARY = {
    "primary": "#4D77CB",
    "primary_container": "#A9CCF9",
    "on_primary_container": "#1E4469",
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
   inactive tabs -- weight 500 (M3's own "titleSmall" tab-label weight,
   medium rather than semibold/600) reads as more refined/modern than a
   heavier weight, and is intentionally the *same* for active and
   inactive: M3 relies on color plus the indicator bar to show what's
   selected, not extra boldness on top, so weight doesn't need to (and
   per that same principle, shouldn't) change between the two states.
   Also bumped up from Streamlit's default 14px to read a bit more
   prominent as primary page navigation rather than blending in at
   body-text size. Color: standard M3 tab convention is active = the
   accent color, inactive = the muted on_surface_variant tone (not
   Streamlit's own near-black default, rgb(38,39,48), which read as
   borderline-black and didn't match this app's blue-tinted palette at
   all) -- so inactive tabs still recede properly relative to the active
   one (see [aria-selected="true"] below, further down, for that
   override) while staying blue-tinted like everything else. */
[data-testid="stTab"] p {
    font-weight: 500 !important;
    font-size: 1rem !important;
    color: var(--m3-on-surface-variant, #52657A) !important;
}
/* M3-style text tab row: a faint rule under the *whole* row (a track,
   like an unfilled progress bar) plus a per-tab sliding indicator bar
   that only actually renders under the active tab and moves to the newly
   active one (confirmed via DevTools this is a real, single DOM element,
   `.react-aria-SelectionIndicator`, that React Aria itself
   mounts/animates -- not something this file needs to position or
   transition by hand, only recolor). This replaces the segmented-control/
   capsule look this used to have (each tab in its own filled pill), which
   read as too heavy/button-like for page navigation.

   `[role="tablist"]`'s own `::after` pseudo-element (content:"",
   height:2px by default) is the row-wide track; it used to be hidden
   entirely (`display: none`) to make room for the capsule look, and the
   indicator was hidden alongside it since two separate moving/colored
   cues would have doubled up with the capsule. Un-hiding both now that
   the capsules are gone: the track at low opacity (a subtle line the
   active indicator sits on top of, not a strong divider competing with
   it), the indicator at full accent color as the actual "this one is
   selected" cue.

   Thickness follows M3's own Primary Tabs spec (divider ~1dp, active
   indicator ~3dp) rather than the 2px both defaulted to -- the active
   indicator being visibly heavier than the row's own baseline track is
   what reinforces "this one is heavier/more emphasized" on top of the
   color difference already doing that job; same height on both would've
   left color as the only cue. */
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
/* A visibly blue-tinted panel (see SURFACE above), not a neutral gray
   one, so it reads as its own "colored panel" without competing with the
   cards in the main content area. Uses surface_container specifically --
   not surface_container_low, which the chart cards use -- kept at a
   higher, poppier saturation (~47% vs the cards' 35%) so the sidebar
   reads as a confidently blue panel of its own rather than echoing the
   calmer card tone; also keeps it visually distinct from
   primary_container (the station-tag capsule fill) so those tags still
   pop forward off the panel instead of blending into it. The margin is
   what lets the rounded corners and shadow actually read against the
   page instead of being clipped by the viewport edge. Being a light
   fill, widget text/labels below are flipped to a dark neutral instead
   of white for contrast. */
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
/* Flip default widget text to a dark neutral so it stays legible against
   the tinted fill above -- covers the "Selection" header, the
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
    /* on_surface (#1C2A3B) was near-black -- same complaint as the old
       inactive-tab color -- so this uses on_surface_variant instead, the
       same muted blue-gray tone inactive tabs now use, for the same
       "still legible, but blue-tinted rather than borderline-black" reason. */
    color: var(--m3-on-surface-variant, #52657A) !important;
}
/* "Date range" label specifically called out heavier than the rest. */
[data-testid="stDateInput"] label {
    font-weight: 600 !important;
}
/* The multiselect's selected-station "tags" default to Streamlit's own
   blue (rgb(31,119,180)), not the brand's -- pinned to the M3
   primary-container role instead (same standard-contrast pair as the
   active-tab capsule elsewhere in this file). [data-baseweb="tag"] was
   this rule's original selector, written against an older Streamlit's
   BaseWeb-based multiselect; confirmed via DevTools that the current
   build's tags carry a `data-tag` attribute instead (no `data-baseweb`
   anywhere on them), which is why this was silently never applying --
   same story as the several other [data-baseweb=...]/[data-testid=...]
   selectors elsewhere in this file that turned out to be stale against
   the newer React Aria-based DOM. */
[data-testid="stMultiSelect"] span[data-tag] {
    background-color: color-mix(in srgb, var(--m3-primary-container, #A9CCF9) 94%, transparent) !important;
    border-color: var(--m3-primary-container, #A9CCF9) !important;
}
/* Tag text (and its remove "x" icon) defaults to dark grey, confirmed via
   DevTools as rgb(33,37,41) -- close enough to on_primary_container (the
   guaranteed-readable pair for the primary_container fill above, same as
   the active-tab text above) that it's pinned there explicitly rather than
   left as a coincidental near-match. Scoped to inside the tag specifically
   so the dropdown list's own option text (a separate popover element, not
   a descendant of the tag) stays whatever color it already is, unaffected.
   -webkit-text-fill-color is required alongside color, not optional
   belt-and-suspenders -- confirmed by testing color alone first: it took
   in getComputedStyle(...).color but the glyphs kept rendering in the old
   dark grey regardless, because Chromium paints text using
   -webkit-text-fill-color when present and this component sets it
   explicitly (same root cause as the date-input fix elsewhere in this
   file). */
[data-testid="stMultiSelect"] span[data-tag],
[data-testid="stMultiSelect"] span[data-tag] * {
    color: var(--m3-on-primary-container, #1E4469) !important;
    -webkit-text-fill-color: var(--m3-on-primary-container, #1E4469) !important;
}

/* Card look for chart_card()'s st.container(border=True) wrapper: no
   border, and a soft shadow instead of Streamlit's default flat
   grey-bordered box. Confirmed via DevTools that every chart_card() across
   every tab (Time Series, Map, Regression, Clustering, both Discover
   Global Warming sub-tabs, and the forecast-metrics tables) reads this
   one shared rule, so any change here applies everywhere at once;
   there's no per-tab styling to have drifted.

   Background is a *nested* color-mix(): white mixed with a small amount
   of surface_container_low (80%/20%) to get a base tone that's mostly
   white with just a hint of the app's blue, then that whole result mixed
   with transparent at 80% opacity for the actual glass translucency.
   This two-step mix is what earlier single-step attempts couldn't get
   right together: surface_container_lowest pushed toward near-white
   (20% saturation) read as plain opaque white with no visible tint at
   any opacity, since blending an already near-white *base* color still
   just gives near-white; primary_container (87% saturation, the same
   blue as the capsules) at 40% opacity read as genuinely glassy but too
   blue -- alpha blending doesn't reduce HSL saturation the way you'd
   expect, so even diluted it still measured well above the sidebar's own
   47% saturation; plain surface_container_low at 50% opacity fixed the
   too-blue problem but then read too close to the page to stand out as
   its own card. Mixing toward white *first*, before applying the
   translucency, is what actually gets "majority white, a little blue
   tint, still see-through" all at once -- the 80% opacity keeps it from
   diluting all the way back down to the very pale page color the way a
   lower opacity did, while the small 20% blue slice keeps it from being
   flatly white with zero tint. Still measures ~9.4:1 text contrast for
   the dark on_primary_container ink used elsewhere in charts (title,
   axis, tick labels).

   Rendered "glassy" via three things together, not blur alone -- a flat
   solid-color page behind this card has no texture for a blur to
   visibly act on, so backdrop-filter by itself would be nearly
   imperceptible here:
     1. Real (if higher than most other elements in this file) opacity --
        80%, mixed toward white as described above rather than the ~94%
        solid tint every other card/capsule uses -- so a little of the
        page still shows through underneath the mostly-white tone.
     2. backdrop-filter blur+saturate, still included for when this *is*
        rendered over something with texture (e.g. content scrolled
        partly behind it) and for the saturate boost, which has a small
        but real effect even over a flat color.
     3. A soft diagonal light-to-transparent gradient layered on top of
        the translucent color-mix() fill, plus a slightly lighter
        semi-transparent top/left border -- these two are what actually
        sell "glass" regardless of what's behind the card, the same way
        real glassmorphism recipes lean on a highlight/sheen rather than
        blur alone to read as glass.
   backdrop-filter needs the -webkit- prefix for Safari; browsers without
   support for it at all still get the gradient/border sheen plus the
   flat translucent background, which reads correctly on its own.

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
    background: color-mix(in srgb, var(--m3-surface-container-lowest, #F9FAFB) 94%, transparent) !important;
    border: none !important;
    outline: none !important;
    border-radius: 10px !important;
    /* The "popped off the page" shadow -- e.g. the "Parameter" dropdown,
       which isn't wrapped in a full chart_card() anymore, still needed
       something to read as raised rather than flat-printed on the page. */
    box-shadow: 0 4px 14px rgba(28, 42, 59, 0.12);
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
/* Number input boxes (e.g. "Trend start year", "Hot day threshold" in the
   Global Warming Trend settings) default to Streamlit's own flat input
   grey, `rgb(240, 242, 246)` -- confirmed via DevTools that the actual
   colored box is [data-testid="stNumberInputContainer"], one level inside
   the outer [data-testid="stNumberInput"] wrapper (which is itself
   transparent). This first went through primary_container/
   on_primary_container -- the same accent pair as the capsules/chips
   (active tab, station tags) -- but a plain data-entry field isn't an
   actionable/selected element the way those are, and M3 reserves
   primary/primary_container for exactly that: filled buttons, chips,
   selected states, not passive input surfaces. Moved to
   surface_container_low/on_surface_variant instead -- the SURFACE
   system's own container role (also what the sidebar uses), at roughly
   half primary_container's saturation (35% vs 87%) and noticeably
   lighter (89% vs 82% lightness), which is both more semantically
   correct and reads as calmer against the rest of the now-toned-down
   UI. Also dropped to 60% opacity (vs. the 94% every other capsule/box in
   this file uses) for a distinctly more transparent, recessed feel
   appropriate to a plain input rather than an accent surface -- still
   comfortably legible (on_surface_variant measures ~4.6:1 against the
   page-blended result, clearing WCAG AA's 4.5:1 for normal text). Text
   color has to be set on the input field *and* both step buttons
   separately since Streamlit renders the -/+ glyphs as a separate
   <button><svg> pair whose fill inherits `color` from here, not from the
   container. */
[data-testid="stNumberInputContainer"] {
    background: color-mix(in srgb, var(--m3-surface-container-low, #D8E2EC) 60%, transparent) !important;
}
[data-testid="stNumberInputField"],
[data-testid="stNumberInputStepDown"],
[data-testid="stNumberInputStepUp"] {
    color: var(--m3-on-surface-variant, #52657A) !important;
}
/* Focus falls on an element nested inside the box, not the box itself, so
   :focus-within on the wrapper is what catches "this control is active"
   and lets us draw a focus ring -- there's no resting border to move away
   from anymore, so this is purely additive on focus. */
[data-testid="stMultiSelect"]:focus-within [data-baseweb="select"],
[data-testid="stSelectbox"]:focus-within [data-baseweb="select"],
[data-testid="stMultiSelect"]:focus-within [role="group"][data-rac],
[data-testid="stSelectbox"]:focus-within [role="group"][data-rac] {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--m3-on-primary-container, #1E4469) 22%, transparent) !important;
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
    background: color-mix(in srgb, var(--m3-surface-container-lowest, #F9FAFB) 94%, transparent) !important;
    border: none !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 14px rgba(28, 42, 59, 0.12) !important;
}
[data-testid="stExpander"] summary {
    background: transparent !important;
}
/* The popover menu (select options list) -- give it the same rounded,
   soft-shadow treatment as everything else instead of BaseWeb's default
   hard-edged white box. The date-input's calendar popover is left alone
   (native), same as the date box itself. */
[data-baseweb="menu"] {
    background: color-mix(in srgb, var(--m3-surface-container-lowest, #F9FAFB) 94%, transparent) !important;
    border-radius: 10px !important;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(28, 42, 59, 0.12) !important;
}
/* Plotly chart toolbar (zoom/pan/download): color comes from style_fig()'s
   modebar config, this is just the hover/active affordance -- a soft
   rounded highlight instead of Plotly's default hard-edged grey square,
   so it reads as a modern icon button rather than a stock widget. */
.modebar-btn:hover, .modebar-btn.active {
    background: color-mix(in srgb, var(--m3-on-primary-container, #1E4469) 12%, transparent) !important;
    border-radius: 6px !important;
}
</style>
"""

# Page canvas: the M3 "surface" role -- the baseline tone the rest of the
# SURFACE ladder (sidebar, cards, popovers) is built on top of. A single
# flat fill, no gradient, same as before -- just sourced from the tonal
# system now instead of an arbitrary gray.
_BACKGROUND_COLOR = SURFACE["surface"]


def render_app_background() -> None:
    """Inject the base CSS, the tone-based SURFACE/PRIMARY custom
    properties, and the static page background."""
    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    # Every --m3-<role> custom property the CSS above references (var(...)
    # calls always carry their own hex fallback too, so this dict is the
    # single source of truth -- nothing here needs to be kept in sync by
    # hand against the CSS block).
    tokens = {**SURFACE, **PRIMARY}
    css_vars = " ".join(f'--m3-{role.replace("_", "-")}: {hex_value};' for role, hex_value in tokens.items())
    st.markdown(
        f'<style>.stApp {{ background: {_BACKGROUND_COLOR}; }}'
        f' :root {{ {css_vars} }}</style>',
        unsafe_allow_html=True,
    )


def render_brand() -> None:
    """Render the "WeatheRe" wordmark as plain text in `primary` at 85%
    opacity -- the same softened blue used for the active tab (label +
    sliding indicator), since both are freestanding text on a light
    SURFACE tone rather than text sitting on a filled capsule (that's
    what on_primary_container is for, see the PRIMARY comment above). The
    opacity is inline here (color-mix works fine as a plain CSS color
    value, including in an inline style attribute) rather than only in
    the stylesheet, since this element's color is set via inline style,
    not a class this file's CSS block can target. Rendered at the
    top-left of the main content area, immediately next to the sidebar --
    this replaces the old st.title("Weather Dashboard"). Deliberately
    normal document flow rather than position: fixed to a hardcoded
    coordinate: an in-flow element at the top of .block-container sits
    right at the sidebar's edge and automatically shifts left with .main
    when the sidebar is collapsed, which a fixed position could not do
    without JS to track sidebar state."""
    st.markdown(
        f'<div class="app-brand" style="text-align: left; font-weight: 700; '
        f'font-size: 1.6rem; letter-spacing: 0.02em; '
        f'color: color-mix(in srgb, {PRIMARY["primary"]} 85%, transparent);">WeatheRe</div>',
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


# on_primary_container (the same accent ink used everywhere else, see the
# PRIMARY comment above) for axis/tick/legend text and gridlines -- reads
# fine over the tinted chart_card() background regardless of which weather
# mood is active, since only the page background (not the accent/ink)
# changes with the mood. _CHART_GRID is the same color as an rgb() triple
# (#1E4469 = rgb(30,68,105)) at low opacity, since Plotly's gridcolor/
# zerolinecolor/linecolor options don't accept CSS custom properties.
_CHART_INK = PRIMARY["on_primary_container"]
_CHART_GRID = "rgba(30, 68, 105, 0.12)"

# Each chart's own headline title (e.g. "Cloud Cover Total over time") --
# kept as its own color, separate from _CHART_INK above, so it matches
# the "WeatheRe" wordmark and active-tab text exactly (same PRIMARY
# "primary" ink, same 85% opacity) rather than the darker
# on_primary_container everything else in a chart (axis titles, tick
# labels, legend) still uses. Plotly's font-color options don't accept
# CSS custom properties or color-mix(), so the 85%-opacity blend that's
# `color-mix(in srgb, ... 85%, transparent)` in CSS has to be spelled out
# here as a literal rgba() alpha instead -- same PRIMARY["primary"] hex
# (#4D77CB = rgb(77,119,203)), same 0.85 alpha.
_CHART_TITLE_COLOR = "rgba(77, 119, 203, 0.85)"


def style_fig(fig: go.Figure) -> go.Figure:
    """Strip a Plotly figure's opaque white chrome so it blends into the
    chart_card() it's rendered in instead of sitting on it as a stark white box."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=_CHART_INK,
        title_font_color=_CHART_TITLE_COLOR,
        # font_color above only sets the *fallback* Plotly text color --
        # Streamlit's own default chart template sets its own explicit,
        # much lighter gray (confirmed via DevTools: rgb(128,132,149)) on
        # tick labels, axis titles, and the legend specifically, which
        # wins over that fallback since it's the more specific setting.
        # Legend/axis title/tickfont colors have to be forced individually
        # to actually override it -- this is why those three were still
        # showing up light gray even though the chart's own main title
        # (set via title_font_color above) was already the right color.
        legend=dict(bgcolor="rgba(0,0,0,0)", font_color=_CHART_INK),
        margin=dict(t=60, b=50, l=40, r=40),
        # Plotly's modebar (the zoom/pan/download toolbar) defaults to
        # its own grey-on-white palette regardless of the figure's own
        # theming -- pinned to the brand accent instead so it doesn't look
        # like a leftover default widget bolted onto a themed chart.
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
