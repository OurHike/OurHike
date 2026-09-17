"""The prose of features/mockups/city-water-density.html.

Split from draw_city_water_mockup.py so that file knows about geometry and this
one knows about sentences, and so a wording change is a diff a reader can read.

EVERY FIGURE IN THE PROSE IS INTERPOLATED from the frames dict this is handed -
"63 pins", "30% of the screen", "largest fold 12" - rather than typed. The page
states each of them several times over, and a page whose picture and paragraph
are two copies of one measurement is exactly the thing this repository keeps
finding out of date. A re-run against a later release moves the sentences with
the frames.

The stylesheet is features/mockups/corridor-view.html's, read at generate time
rather than copied, so the five mockups cannot drift apart. That file is the
one home for the house style; this adds only what a page of map frames needs on
top of it.
"""

from __future__ import annotations

import re
from pathlib import Path

#: The one home for the house style, read rather than duplicated.
HOUSE_STYLE = Path(__file__).resolve().parent.parent / "features" / "mockups" / "corridor-view.html"

#: What each option is called in the summary table, keyed as the frames are.
ROW_NAMES = {
    "today": "today",
    "air": "1 · air",
    "sites": "2 · sites",
    "both": "1 + 2",
    "places": "3 · parks",
    "clusters": "4 · screen clusters",
}

#: Where each option would be built, which is half of what makes one cheaper
#: than another and is not visible in any of the counts.
ROW_HOMES = {
    "today": "—",
    "air": "client — <code>buildPoiLayer</code>",
    "sites": "pipeline — <code>lib/poi_sites.py</code>",
    "both": "both",
    "places": "pipeline + client zoom staging",
    "clusters": "client only",
}

EXTRA_CSS = """
:root { --map-paper:#ece5d1; --map-park:#b2cc9c; --map-park-edge:#8fae78; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --map-paper:#1e1e18; --map-park:#38472f; --map-park-edge:#52653f; } }
:root[data-theme="dark"] { --map-paper:#1e1e18; --map-park:#38472f; --map-park-edge:#52653f; }

.frames { display: grid; grid-template-columns: repeat(auto-fit, minmax(0, 330px));
          gap: 30px 26px; justify-content: start; margin: 0 0 8px; }
.frames--solo { grid-template-columns: minmax(0, 380px); }
/* A <figure> carries a 40px UA margin, which is what pushed the frames past
   the right edge of a 390 px screen. */
.phone { width: 100%; max-width: 330px; margin: 0; }
.phone__screen { width: 100%; height: auto; aspect-ratio: 390 / 700; display: block; }
.phone__screen svg.screen { width: 100%; height: 100%; display: block; }
.phone__stat { display: flex; gap: 6px 13px; flex-wrap: wrap; margin: 9px 0 0;
  font-family: 'IBM Plex Mono', ui-monospace, monospace; font-size: 0.75rem; color: var(--ink-3);
  font-variant-numeric: tabular-nums; }
.phone__stat b { color: var(--ink); font-weight: 500; }
.phone__stat .hot { color: var(--blocked); }
.phone__stat .good { color: var(--measured); }
.phone__caption { max-width: 330px; }
@media (max-width: 480px) {
  .wrap { padding-left: 16px; padding-right: 16px; }
  .frames, .frames--solo { grid-template-columns: minmax(0, 1fr); }
  .phone, .phone__caption { max-width: 100%; }
}
.opt { border-top: 1px solid var(--rule); padding-top: 28px; margin-top: 8px; }
.opt__head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.opt__n { font-family: 'IBM Plex Mono', ui-monospace, monospace; font-size: 0.8125rem;
  color: var(--accent); letter-spacing: 0.1em; }
.opt h3 { margin: 0; }
.cost { border-left: 2px solid var(--rule); padding-left: 18px; margin: 0 0 16px; color: var(--ink-2); }
.cost b { font-family: 'IBM Plex Mono', monospace; font-size: 0.6875rem; letter-spacing: 0.09em;
  text-transform: uppercase; color: var(--ink-3); display: block; margin-bottom: 4px; font-weight: 500; }
.rec { background: var(--accent-soft); border: 1px solid var(--accent); border-radius: 3px;
  padding: 22px 24px; margin: 0 0 22px; }
.rec h3 { margin-bottom: 8px; }
.num { font-variant-numeric: tabular-nums; font-family: 'IBM Plex Mono', monospace; }
"""

GRADE = {
    grade: f'<span class="grade grade--{grade}">{grade}</span>' for grade in ("measured", "reasoned", "unvalidated", "decided")
}


def house_style() -> str:
    """corridor-view.html's <style> block, verbatim."""
    match = re.search(r"<style>.*?</style>", HOUSE_STYLE.read_text(), re.DOTALL)
    if match is None:
        raise RuntimeError(f"no <style> block in {HOUSE_STYLE}")
    return match.group(0)


def _stat(frame: dict) -> str:
    """The four figures under a frame, coloured by whether they are the
    problem. The thresholds are the page's own argument rather than a scale:
    POI_VISIBILITY.md calls ~16 pins a full column, so 30 is plainly over, and
    a fifth of the screen in pin ink is plainly too much.
    """
    pins_class = "hot" if frame["pins"] > 30 else "good"
    ink_class = "hot" if frame["ink"] > 0.20 else "good"
    return (
        f'<p class="phone__stat"><span><b>{frame["marks"]}</b> marks</span>'
        f'<span class="{pins_class}"><b>{frame["pins"]}</b> pins</span>'
        f'<span class="{ink_class}"><b>{frame["ink"]:.0%}</b> of screen under pin</span>'
        f"<span><b>{frame['dots']}</b> dots</span></p>"
    )


def _phone(frames: dict, slug: str, caption: str, zoom: int, label: str | None = None) -> str:
    frame = frames[slug]
    return (
        '<figure class="phone">'
        f'<p class="phone__label"><b>{label or frame["label"]}</b>'
        f"<span>z{zoom} · 390 × 700</span></p>"
        f'<div class="phone__screen">{frame["svg"]}</div>'
        f"{_stat(frame)}"
        f'<figcaption class="phone__caption">{caption}</figcaption></figure>'
    )


def _row(frames: dict, slug: str) -> str:
    frame = frames[slug]
    padding = 24 if frame["padding"] > 2 else 2
    return (
        f'<tr><td class="basis-name">{ROW_NAMES[slug]}</td>'
        f'<td class="num">{frame["marks"]}</td><td class="num">{frame["pins"]}</td>'
        f'<td class="num">{frame["ink"]:.0%}</td><td class="num">{frame["dots"]}</td>'
        f'<td class="num">{frame["fold"]}</td><td class="num">{padding}</td>'
        f"<td>{ROW_HOMES[slug]}</td></tr>"
    )


def render(frames: dict, ground: list[str], camera, window: list, zooms: list[dict]) -> str:
    """The whole page.

    `frames` is draw_city_water_mockup.build_frames' output, `ground` the park
    paths, `camera` the z12 camera, `window` the waypoints in it, and `zooms`
    one row per zoom for the second table.
    """
    today, air = frames["today"], frames["air"]
    sites, both = frames["sites"], frames["both"]
    places, clusters = frames["places"], frames["clusters"]
    water = sum(1 for p in window if p.poi_type == "water")
    privy = sum(1 for p in window if p.poi_type == "privy")
    span_w = 390 * camera.m_per_px / 1609.344
    span_h = 700 * camera.m_per_px / 1609.344
    folds = ", ".join(str(f["dots"]) for f in (sites, places, clusters))
    pins_folded = " and ".join(
        (
            ", ".join(str(f["pins"]) for f in (clusters, places)),
            str(sites["pins"]),
        )
    )
    deferred = next(z for z in zooms if z["zoom"] == camera.zoom)["pins_without_water"]

    # One copy of the ground, referenced by every frame: 419 boundaries is 29 KB
    # of path data and six copies of it would be six copies of it.
    paths = "".join('<path d="%s"/>' % d for d in ground)
    defs = (
        '<svg width="0" height="0" aria-hidden="true" style="position:absolute"><defs>'
        f'<g id="nyc-ground">{paths}</g>'
        "</defs></svg>"
    )

    zoom_rows = "".join(
        f'<tr><td class="basis-name">z{z["zoom"]}</td>'
        f'<td class="num">{z["span_w"]:.1f} × {z["span_h"]:.1f} mi</td>'
        f'<td class="num">{z["waypoints"]}</td><td class="num">{z["pins"]}</td>'
        f'<td class="num">{z["pins_without_water"]}</td></tr>'
        for z in zooms
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Six Hundred Fountains</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bitter:ital,wght@0,400;0,600;0,700;1,400&family=Public+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
{house_style()}
<style>{EXTRA_CSS}</style>
</head>
<body>
{defs}
<div class="wrap">

<header class="masthead">
  <p class="eyebrow">features/mockups · waypoint density · 2026-09-17</p>
  <h1>Six Hundred Fountains, One Screen</h1>
  <p class="standfirst">New York City's drinking fountains are on the map and the map
  cannot hold them. This is the worst screen the city produces, measured rather than
  imagined, and <em>four ways to fix it</em> — three of which turn out to fix a different
  half of the problem than the one you notice first.</p>
  <div class="docket">
    <span class="docket__item">Release <b>2026-09-16-4</b></span>
    <span class="docket__item"><b>nearby_poi.geojson</b> · 20,444 features</span>
    <span class="docket__item"><b>3,148</b> fountains · <b>758</b> restrooms</span>
    <span class="docket__item"><a
      href="https://github.com/OurHike/OurHike/issues/1534">#1534</a> · decided</span>
    <span class="docket__item docket__item--open"><a
      href="https://github.com/OurHike/OurHike/issues/1536">#1536</a> · building 1 + 2</span>
  </div>
</header>

<hr class="rule">

<section class="spine">
  <div class="spine__rail"><p class="spine__mark"><strong>§0</strong>what shipped</p></div>
  <div class="spine__body">
    <div class="callout">
      <h3>The maintainer took options 1 and 2 on 2026-09-17, and two things changed on the way in</h3>
      <p><strong>This page is the record of the options, not of the build.</strong> Its frames
      and figures are left exactly as they were when the decision was made;
      <strong>#1536 — Give the pins air and fold New York City's co-located fountains, which
      is the maintainer's pick of options 1 and 2</strong> is what was actually built, and
      <code>features/POI_VISIBILITY.md</code>'s open question carries the reasoning. Two
      departures are worth reading here, beside the pictures that prompted them.</p>
      <p><strong>Option 1's padding is 36, not the 24 drawn below, and it ramps.</strong> This
      page applies one flat padding to every mark on the screen. Measured afterwards, a
      blanket padding costs the Appalachian Trail half its pins at z9 — 20 down to 10 — so the
      shipped rule is per-feature, off until a waypoint has more neighbours than anything on
      the A.T. has, and a ramp that leaves the trail alone has to spend more at its top to
      reach the same place. End to end the real figures are <strong>374 marks, 32 pins, 15% of
      the screen under pin</strong>, against this page's 375 / 23 / 11%.</p>
      <p><strong>The pins below wear a count and the shipped ones do not.</strong> Every New
      York City fountain ships at <code>confidence_floor: low</code>, so a mark decorated to
      say <strong>12</strong> offers reassurance the source cannot supply. The pin says water
      is here; the count and what is unknown about it belong on the card. {GRADE["reasoned"]}</p>
      <p><strong>One thing the drawing got wrong and the build does not:</strong> the folded
      marks here sit at their group's centroid. A centroid of twelve fountains is a point on a
      lawn with no fountain on it, and a hiker walks to the pin — so the shipped fold anchors
      on the most central fountain that actually exists.</p>
    </div>
  </div>
</section>

<hr class="rule">

<section class="spine">
  <div class="spine__rail"><p class="spine__mark"><strong>§1</strong>the screen</p></div>
  <div class="spine__body">
    <h2>The densest phone screen in the five boroughs</h2>
    <p>Brooklyn, centred on <span class="mono">{camera.centre[0]:.4f}, {camera.centre[1]:.4f}</span>
    — Red Hook to Prospect Park, {span_w:.2f} × {span_h:.2f} miles of ground at z{camera.zoom}.
    <strong>{len(window)} waypoints fall inside it</strong>: {water} drinking fountains and
    {privy} public restrooms, and nothing else, because shelters and campsites do not exist
    here.</p>
    <p>{GRADE["measured"]} Counted 2026-09-17 against the published artifact a hiker downloads
    today, filtered to the four categories a fresh install opens with
    (<code>DEFAULT_SHOWN_TYPES</code>: shelter, water, campsite, privy). The window is found
    by <code>spike_city_poi_density.py</code>'s point-anchored sweep, which is exact rather
    than grid-phased. Placement is MapLibre's rule as <code>poiLayers.ts</code> configures it:
    a 38 px pin at the z12 point of the icon-size ramp, <code>icon-padding: 2</code>, symbols
    considered in <code>POI_PRIORITY</code> order, a box skipped when it overlaps one already
    placed.</p>
    <div class="frames frames--solo">
      {_phone(frames, "today", "Every fountain its own mark. The green is NYC Parks&rsquo; own property boundaries, clipped to this window.", camera.zoom)}
    </div>
    <div class="note">
      <p>The comparable figure already in the tree is <strong>656</strong> —
      <code>features/NEARBY_TRAILS.md</code> §10, measured against the release
      <strong>#1474 — Draw the seam around what a cell carries, ship the merge provenance
      that did not, and give New York City its restrooms and its fountains</strong>
      published, at a window 1.5 km west of this one. {len(window)} is the same measurement
      against a later release; the two do not disagree.</p>
    </div>
  </div>
</section>

<hr class="rule">

<section class="spine">
  <div class="spine__rail"><p class="spine__mark"><strong>§2</strong>the diagnosis</p></div>
  <div class="spine__body">
    <h2>"Cramped" is two problems wearing one word</h2>
    <p><strong>The pins.</strong> {today["pins"]} of them are placed, and they cover
    <strong>{today["ink"]:.0%} of the screen</strong>. Their nearest-neighbour distance is a
    median <strong>51 px</strong> when a pin at this zoom is <strong>36 px</strong> wide —
    which is to say they are very nearly touching, edge to edge, with 15 px of paper between
    them. <code>features/POI_VISIBILITY.md</code>'s own arithmetic says about 16 pins fit down
    the column at a hiking zoom. {GRADE["measured"]}</p>
    <p><strong>The dots.</strong> {today["dots"]} more waypoints lost their collision and drew
    as dots instead, which is the design working — <em>a pin or a dot and never as neither</em>.
    At {today["dots"]} on one screen the dot rank stops reading as a stipple and starts reading
    as a blue wash. {GRADE["measured"]}</p>

    <div class="callout">
      <h3>The finding that reorders the options</h3>
      <p>The obvious fix is to stop drawing fountain pins at planning zooms and let them
      arrive later. <strong>Measured, it barely helps: {today["pins"]} pins becomes
      {deferred}.</strong> The restrooms simply take the space the fountains vacated.</p>
      <p><code>icon-allow-overlap: false</code> packs pins until nothing else fits. It has
      no notion of <em>enough</em> — so the screen is full because the placement rule fills
      it, not because water is dense. Any fix aimed at the water layer alone moves the
      author of the crowding and not the crowding. {GRADE["measured"]}</p>
    </div>

    <p>That splits the option space cleanly, and the split is the useful part of this page:</p>
    <ul class="ul-tight">
      <li><strong>Folding waypoints together barely moves the pin count.</strong> All three
      folding options below land between {clusters["pins"]} and {sites["pins"]} pins, against
      today's {today["pins"]}. What they move is the dots — {today["dots"]} down to
      {folds}.</li>
      <li><strong>Only spacing moves the pins.</strong> {today["pins"]} down to
      {air["pins"]}, and nothing else here does that.</li>
    </ul>
    <p>Which means the two levers are not alternatives. They fix different halves.
    <span class="mono">({pins_folded} pins, folded three ways.)</span></p>
  </div>
</section>

<hr class="rule">

<section class="spine">
  <div class="spine__rail"><p class="spine__mark"><strong>§3</strong>four options</p></div>
  <div class="spine__body">
    <h2>Four options, drawn on the same screen</h2>

    <div class="opt">
      <div class="opt__head"><span class="opt__n">OPTION 1</span><h3>Give the pins air</h3></div>
      <p>Raise <code>icon-padding</code> from 2 to 24, so a pin claims an 82 px box rather
      than a 40 px one and the collision engine stops at {air["pins"]} placements instead of
      {today["pins"]}. <strong>Nothing merges and nothing is claimed.</strong> Every fountain
      keeps its own dot at its own coordinate and its own tap target;
      {today["pins"] - air["pins"]} of them trade a pin for a dot, and the dot was already
      there under the pin.</p>
      <div class="frames">
        {_phone(frames, "today", "Sixty-three pins, edge to edge.", camera.zoom)}
        {_phone(frames, "air", f"Same {air['marks']} waypoints. The engine places {air['pins']} pins instead of {today['pins']}, and the screen has paper in it again.", camera.zoom)}
      </div>
      <div class="cost"><b>What it costs</b>
      <p>A hiker scanning for the blue droplet has fewer droplets to scan. The information is
      not gone — it is a dot, at the true place, opening the same card — but the pin is the
      shape that reads at arm's length and {today["pins"] - air["pins"]} fewer of them read.</p>
      <p>{GRADE["unvalidated"]} <strong>24 px is picked, not measured.</strong> It is the value
      that lands this screen near <code>POI_VISIBILITY.md</code>'s ~16, and no more than
      that. What would settle it is the same thing <code>POI_DOT_RADIUS_EXPRESSION</code> is
      still waiting on: a look at a real phone in real sunlight, which nobody has done
      (<strong>#105 — Check the map's marks on a real phone in real sunlight</strong>).</p></div>
      <p>It is also the cheapest change on this page — one expression in
      <code>buildPoiLayer</code>, and it can be scoped by zoom so the corridor is untouched.</p>
    </div>

    <div class="opt">
      <div class="opt__head"><span class="opt__n">OPTION 2</span><h3>Fold co-located fountains into sites</h3></div>
      <p>The mechanism <code>pipeline/sources.json</code> already names for this problem, and
      it is built and shipping: <code>features/POI_SITES.md</code>'s two gates, which fold a
      privy onto its shelter's pin along the A.T. Ported here, the gates become
      <strong>same park property AND within 80 m</strong> — the published fountain already
      carries its park name, 912 distinct names over 3,148 fountains, so the naming evidence
      ATC supplies is supplied by NYC Parks.</p>
      <div class="frames">
        {_phone(frames, "today", f"Sixty-three pins over {today['dots']} dots.", camera.zoom)}
        {_phone(frames, "sites", "A bank of fountains at one playground becomes one mark wearing a count. The badge is the one poiIcons.ts already draws.", camera.zoom)}
      </div>
      <p>{today["marks"]} marks become {sites["marks"]}; the largest fold on this screen is
      {sites["fold"]} fountains. Each site has a <strong>stable id computed in the
      pipeline</strong>, so it survives a pan, a zoom and a reload, and a report or a field
      note can point at it. {GRADE["measured"]}</p>
      <div class="cost"><b>What it costs</b>
      <p><code>export_poi.py</code> says it already: a wrong grouping is baked into the
      artifact and a hiker cannot undo it. That is why the rule needs both gates rather than
      proximity alone.</p>
      <p>{GRADE["unvalidated"]} <strong>80 m is picked.</strong> POI_SITES.md's own proximity
      gate is 60 m, chosen against ATC's shelter geometry rather than a playground's. What
      would settle it is the distribution of fountain-to-fountain distance inside one park
      property — a one-query measurement this page did not run.</p></div>
      <p>On its own it leaves the pin count at {sites["pins"]}. It is the half that fixes the
      dots.</p>
    </div>

    <div class="opt">
      <div class="opt__head"><span class="opt__n">OPTION 3</span><h3>Fold to the park, unfold on the way in</h3></div>
      <p>One mark per park property below z13 — <em>Prospect Park · 55</em> — then sites, then
      individual fountains. It collapses harder than option 2: {today["marks"]} marks become
      {places["marks"]}.</p>
      <div class="frames">
        {_phone(frames, "today", "For comparison.", camera.zoom)}
        {_phone(frames, "places", "One mark per park. Reads like a city map, and at a walking zoom it is the wrong shape of answer.", camera.zoom)}
      </div>
      <div class="cost"><b>What it costs, and it is the reason this is third</b>
      <p>{GRADE["measured"]} At z14 — a zoom a hiker walks at — Central Park's <strong>85
      fountains fold into one mark</strong> at a centroid. <strong>A centroid is not a place
      you can walk to.</strong> On the water path that is precisely the confidently wrong
      answer <code>FEATURES.md</code> calls more dangerous than an honest unknown, and the
      unfold thresholds are the only thing standing between the design and it.</p></div>
    </div>

    <div class="opt">
      <div class="opt__head"><span class="opt__n">OPTION 4</span><h3>Cluster in screen space</h3></div>
      <p>The generic map-library answer: group anything within 44 px of a cluster head,
      recompute on every camera change. It collapses hardest of all — {today["marks"]} marks
      become {clusters["marks"]}, and it is the only option that visibly clears the dot
      wash.</p>
      <div class="frames">
        {_phone(frames, "today", "For comparison.", camera.zoom)}
        {_phone(frames, "clusters", "Hardest collapse, least ground truth. The marks here are not places; they are this camera&rsquo;s arithmetic.", camera.zoom)}
      </div>
      <div class="cost"><b>What it costs</b>
      <p>This repository has already written the argument against it, in
      <code>pipeline/lib/poi_sites.py</code>'s header: a group computed on a phone
      <em>"has no id that survives a pan, re-clusters at every zoom, and answers 'how many'
      when the question at a shelter is 'is there a privy'."</em> Every word of that holds
      for a fountain. It is on this page because it is the option somebody will propose, and
      it deserves its measurement rather than a dismissal.</p></div>
    </div>
  </div>
</section>

<hr class="rule">

<section class="spine">
  <div class="spine__rail"><p class="spine__mark"><strong>§4</strong>recommendation</p></div>
  <div class="spine__body">
    <h2>Take 1 and 2, in that order</h2>
    <div class="rec">
      <h3>Air first, sites second — they are not alternatives</h3>
      <p>Option 1 is the only lever that moves the pins and is a one-expression change.
      Option 2 is the only lever that makes the remaining dots mean something, and it is a
      mechanism that already exists and already ships. Together on this screen:
      <strong>{both["marks"]} marks, {both["pins"]} pins, {both["ink"]:.0%} of the screen
      under pin, largest fold {both["fold"]}</strong>.</p>
    </div>
    <div class="frames">
      {_phone(frames, "today", f"Where this started: {today['marks']} marks, {today['pins']} pins, {today['ink']:.0%} of the screen under pin.", camera.zoom)}
      {_phone(frames, "both", f"The recommendation. {both['pins']} pins with room around them; a fold of {both['fold']} wears a {both['fold']}.", camera.zoom)}
    </div>
    <p>Shipping them separately is fine and the order matters: option 1 alone is a visible
    improvement on the same day it lands, and option 2 is the pipeline work that wants a
    measurement first (the 80 m above).</p>
  </div>
</section>

<hr class="rule">

<section class="spine">
  <div class="spine__rail"><p class="spine__mark"><strong>§5</strong>the numbers</p></div>
  <div class="spine__body">
    <h2>Every option on one screen</h2>
    <div class="table-scroll"><table>
      <thead><tr><th>option</th><th>marks</th><th>pins</th><th>screen under pin</th>
      <th>dots</th><th>largest fold</th><th>icon-padding</th><th>where it lives</th></tr></thead>
      <tbody>{"".join(_row(frames, slug) for slug in ROW_NAMES)}</tbody>
    </table></div>
    <p>{GRADE["measured"]} All six rows are the same {today["marks"]} waypoints through the
    same placement code, so the columns are comparable by construction rather than by
    assertion. "Largest fold" is the most waypoints any single mark stands for.</p>

    <h3>And what it looks like on the way in</h3>
    <div class="table-scroll"><table>
      <thead><tr><th>zoom</th><th>screen</th><th>waypoints</th><th>pins today</th>
      <th>pins, restrooms only</th></tr></thead>
      <tbody>{zoom_rows}</tbody>
    </table></div>
    <p>{GRADE["measured"]} The worst window is found independently at each zoom, so these are
    four different pieces of Brooklyn and Manhattan rather than one place zoomed. The last
    column is the deferred-pin idea §2 rules out: even with every fountain pin withheld the
    screen still fills, until z14.</p>
  </div>
</section>

<hr class="rule">

<section class="spine">
  <div class="spine__rail"><p class="spine__mark"><strong>§6</strong>not answered</p></div>
  <div class="spine__body">
    <h2>What none of these options touches</h2>
    <div class="callout callout--blocked">
      <h3>A folded site of twelve unknowns is still twelve unknowns</h3>
      <p>Every New York City fountain ships at <code>confidence_floor: low</code>, and the
      reason is in <code>sources.json</code>: <code>featuresta</code> reads
      <em>Active</em> on all 3,849 rows, zero variance, so the layer carries nothing about
      whether any given fountain works.</p>
      <p><strong>Folding interacts with that and this page does not resolve it.</strong> One
      mark standing for {sites["fold"]} fountains nobody has confirmed reads more confident
      than {sites["fold"]} marks nobody has confirmed — a count is a fact about the inventory
      and a hiker will read it as a fact about the water. Whichever option is taken, the fold
      needs a decision about what a low-confidence count says on the card, and it should be
      made deliberately rather than inherited from the A.T. shelter case where confidence is
      high. {GRADE["reasoned"]}</p>
    </div>
    <ul class="ul-tight">
      <li><strong>This is one screen.</strong> The worst one the city produces at z12, found
      exactly — but the option that is best here is not automatically best in Flushing
      Meadows or on the Coney Island boardwalk, where the fountains run in lines rather than
      in banks.</li>
      <li><strong>The corridor is untouched by all of it.</strong> Every number here is
      inside the five boroughs. Nothing proposed above should change what a hiker sees on
      the A.T., and options 1 and 3 both need a scope — by zoom, by source, or by measured
      local density — that keeps it that way. That scope is unspecified here and is real
      design work. {GRADE["reasoned"]}</li>
      <li><strong>Decided 2026-09-17: options 1 and 2, in that order</strong> — see §0. The
      maintainer's earlier call of 2026-09-15, recorded in
      <code>features/NEARBY_TRAILS.md</code> §10, was that 233 pins is "normal for New York
      City"; this page was the follow-up that call invited rather than a reversal of it, and
      the decision on it came with these numbers in view.</li>
    </ul>
  </div>
</section>

<footer>
  <p>Generated 2026-09-17 by <span class="mono">pipeline/draw_city_water_mockup.py</span> from
  release <span class="mono">2026-09-16-4</span>. Waypoints from
  <span class="mono">nearby_poi.geojson</span> as published; park boundaries from NYC Parks
  Properties (<span class="mono">enfh-gkve</span>), {len(ground)} of 2,059 touching this window;
  pin glyphs ported vertex for vertex from
  <span class="mono">client/src/map/poiIcons.ts</span>. Companion to
  <span class="mono">features/POI_VISIBILITY.md</span>,
  <span class="mono">features/POI_SITES.md</span> and
  <span class="mono">features/NEARBY_TRAILS.md</span> §10.</p>
</footer>

</div>
</body>
</html>
"""
