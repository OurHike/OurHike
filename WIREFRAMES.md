# OurHike — v1 MVP Wireframes

Companion to [FEATURES.md](FEATURES.md), [ROADMAP.md](ROADMAP.md), [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md), [TESTING.md](TESTING.md), and everything in [features/](features/). Extracted and reconciled 2026-07-28 from the interactive wireframe set at the link below (16 design turns, low-fidelity) — this file is the durable, versioned spec that survives in git history; the live link is the visual reference for exact layout, spacing, and copy.

**Live source:** [claude.ai/design — "Hiking App UI Wireframes"](https://claude.ai/design/p/0cacd2b5-3cc3-4e6d-8d2b-eda5d3a68bf6?file=OurHike+Wireframes.dc.html). Frame ids below (`12a`, `14d`…) are anchors in that file — open it and jump to `#12a`.

## What this is, and isn't

`OurHike Wireframes.dc.html` is a **design reference**, not production code: a self-contained prototype (custom `<x-dc>` runtime + `support.js`) that shows structure, states, and copy. The task is to recreate these screens in the actual codebase — React + TypeScript + Vite, MapLibre GL JS + PMTiles, Capacitor — using this repo's own patterns, not to port the wireframe's inline styles or markup.

**Deliberately not vendored into this repo:** the raw `.dc.html` / `support.js` prototype files. They're a generated, throwaway rendering harness (`support.js` literally starts `// GENERATED ... do not edit`), need their own copy of the design-system bundle to render, and would only go stale the moment the design evolves — the same reasoning [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) already applies to fetched/generated pipeline data never entering git. This file is the durable extraction instead. If you need to re-pull the source (e.g. after new wireframe turns), it's reachable through the `claude_design` MCP tool using the project URL above.

## Fidelity: apply the real design system

The wireframes are monochrome-leaning lofi — layout and hierarchy only. Real styling comes from the **OurHike Design System**, already in this repo at [.claude/OurHike Design System/](<.claude/OurHike Design System/>):

- Tokens: `tokens/colors.css`, `typography.css`, `spacing.css`, `effects.css`
- **Working React components, not just HTML demos:** `components/core/{Button,Badge,Card}.jsx`, `components/forms/{Input,Select}.jsx`, `components/navigation/{NavBar,Footer}.jsx`, `components/feedback/Callout.jsx` — plain function components styled via the CSS custom properties in `tokens/`, each with a sibling `.d.ts`. Per its own `SKILL.md`: "If working on production code, you can copy assets and read the rules here." These are a real starting point for the client, not disposable.
- Type: Bitter (display), Public Sans (UI/body), IBM Plex Mono (coordinates, mile markers, sizes).

Where a wireframe _does_ commit to an exact value, it's because the value carries meaning, not style — those are listed under **Load-bearing values** below and must survive implementation regardless of visual restyling.

---

## Screens / views

### 1. Map screen — the ~80% of v1 (`12a`, `5a`, `4b`)

**Purpose:** know where you are, what's ahead, and whether to trust it.

**Layout, top to bottom:**

1. **Status strip** — time, GPS/offline state, sync age. Plus the states where the map is drawing less than a hiker expects and would otherwise have to guess why: the live sheet failed to load, Data Saver is overriding the background, nothing is downloaded yet, (2026-08-05, [#216](https://github.com/OurHike/OurHike/issues/216)) the view is zoomed out past what the download covers, and (2026-08-07, [#314](https://github.com/OurHike/OurHike/issues/314)) the two ways a map goes blank with nothing else to show for it — a download that is on the phone and not drawing, and being offline with no download to draw at all. (2026-08-26, [#1047](https://github.com/OurHike/OurHike/issues/1047)) it also says **"Alerts hidden"** while a hiker has the alert marks switched off in the legend, which is the one flag here somebody put there themselves — a map with the closure bands cleared and a map with no closure on it for forty miles are the same picture, and this strip is what keeps those two apart once the legend is shut. Those last two of the background states are the reason this strip is no longer silent about the background while offline: "Offline" explains a missing live sheet and explains nothing whatever about a damaged archive or a sheet deleted an hour ago. Each is a sentence rather than an icon, and each names its own cause — they are opposite in kind and one word of the wrong one is a map lying about what it is doing with someone's data.
2. **Header (read-only zone).** Trail + state eyebrow — the trail's own mark (14px, from `lib/trails.ts`'s `TRAILS` registry) ahead of the name, where one is known — current mile + direction (`mi 1,407.2 · NOBO`) in mono. Right side: two 38px icon buttons, gap 7px — **legend** (list icon) then **search**. Nothing else lives here.

   **Amended 2026-08-07 ([#312](https://github.com/OurHike/OurHike/issues/312)) — the mono slot says why, when there is no mile.** It rendered `Looking for GPS…` for every mile-less state, and that one sentence covered six situations, three of which never resolve: permission denied, geolocation unsupported, and location switched off — which is what skipping onboarding's location step leaves behind. Telling someone at a junction to keep waiting for a number that is never coming is the same failure as a stale position drawn like a live one. The slot now carries whichever of eight lines is true (`client/src/lib/positionLine.ts`), each no longer than the sentence it replaced so the header cannot reflow: the mile, `Looking for GPS…` while it genuinely is, `No GPS signal` for a lost fix, `Location is off`, `Location blocked`, `No GPS on this phone`, `Off the trail`, and `No trail data` — the last two kept apart because "off the trail" to someone standing on it, whose download simply has not landed, is a confident false claim about the one thing this line answers.

3. **Elevation ribbon.** SVG profile (`viewBox="0 0 100 40"`, `preserveAspectRatio="none"`), 54px tall, left-inset 36px for lane labels. Shaded area under the line, a highlighted upcoming-climb region, a vertical "you are here" rule, min/max ft labels, and a callout: `+640 ft · 2.6 mi · ≈1h 10m`.
4. **Three waypoint lanes**, 19px each, dashed top rules, mono 7.5px labels in the left gutter: `WATER`, `SLEEP`, `ELSE`. Pins position by percentage along the mile window; overlapping pins collapse into a count pill (category glyph + count).
5. **Map canvas.** Trail lines, waypoint pins, GPS dot. Bottom-left: scale bar (64px, three-sided box) above the credit strip. Bottom-right, 10px inset: a vertical stack, gap 8px, of **compass** and **locate** (42px each). Zoom buttons are **web only** — pinch covers mobile and the thumb zone is reserved for locate.

   **Amended 2026-08-07 ([#312](https://github.com/OurHike/OurHike/issues/312)) — locate is offered only while location is on.** It was attached unconditionally, which meant a hiker who had declined the location step still got a browser permission prompt from it, its fix went to MapLibre's blue dot and nowhere else (so the canvas drew a position while the header said `Looking for GPS…`), and with both live it was a second high-accuracy watch on one battery. Compass and scale bar stay in every case — north-up and a scale are as useful on a map you are reading as on one you are standing in.

   **The credit strip, as built 2026-08-06 — one line, and only the maps on screen.** This mockup's `USGS US Topo · © OSM` was never what shipped: the shorthand does not satisfy ODbL (see Assets below), and the string that replaced it was composed from every source the app _can_ draw rather than the ones it is drawing. With the live sheet on — the default — that read `USGS US Topo · © OpenStreetMap contributors · OpenFreeMap © OpenMapTiles · © OpenStreetMap contributors · Elevation: USGS 3DEP via AWS Terrain Tiles`: five clauses, OpenStreetMap printed twice, and USGS credited on a phone holding none of its tiles. Two to three wrapped lines of small type, permanently, in a strip that costs the map its own height.

   It is now assembled per screen from one atom per source (`client/src/map/credits.ts`) and laid out by `chrome/MapAttribution.tsx`: below the 900px breakpoint it collapses to the OpenStreetMap credit — the one licence here demanding prominence, shown in full, never truncated — plus a count of what a tap reveals; at desktop widths the whole list fits on one line and nothing is hidden. What the strip names moves with the phone: no corridor archive, no USGS credit; the downloaded background, no OpenFreeMap or elevation credit.

6. **Tab bar** — Trail / More, with the OurHike icon (mark only, no
   wordmark) at the left end, ahead of the tabs. It is the page's bottom-left
   corner and the only one here that is neither map nor a thumb target; it costs
   the tabs about 32px of shared width and the map nothing. Above 900px
   this same bar is the left sidebar and the mark moves to the foot of it, icon
   over wordmark — see WEBSITE.md §6. **Amended 2026-08-05: Downloads was the
   middle tab and is now a window** (§4). The tab bar is the most expensive
   space in the app and a one-off errand had a third of it; the download is
   reached from the background picker instead, which is the control someone is
   already looking at when they want it. It returns as a tab in v2, when there
   is more than one package to manage. **Amended 2026-08-18: Plan is the middle
   tab** (#756) — v2's first feature, a surface a hiker stands in every evening
   of a thru-hike rather than an errand, drawn second on every bar in the v2
   wireframes. The standard the Downloads removal set is what it was measured
   against; `client/src/chrome/tabs.ts` carries the argument.

**Interaction rules:** everything tapped mid-walk sits in the lower third; everything read but not touched sits above. Locate is blue while tracking, grey when the fix is lost (`7b`).

### 2. Legend (`12b`)

Bottom sheet from the header icon. **Counts are only what's in the current viewport**: a 2-column grid of pin types with counts, and a **"Verified?"** filter under the grid. Rows are tappable to hide — **except the closure row and the serious-warning row**, which carry an "Always shown" tag and no hide affordance.

**Amended 2026-08-26 ([#1047](https://github.com/OurHike/OurHike/issues/1047)) — the panel gains an "Alerts" switch, and those two rows stop saying "Always".** The maintainer's call, quoted in full in [MAP_OPTIONS.md](features/MAP_OPTIONS.md)'s "Reroutes / closures": a hiker may take the alert marks off the map, and the app gives them back the next time the map opens.

What that changes here, precisely:

- **A new switch under the grid**, beside "Verified?" and the drought row and shaped like the latter — a name, a sentence, a checkbox. It is not a grid row, because the grid rows write `waypoint_types_shown` and this must never be written anywhere. It covers all three alert marks at once (closure bands, ATC bands and dots, serious-warning pins) — [ATC_TRAIL_UPDATES.md](features/ATC_TRAIL_UPDATES.md) draws an ATC band in the closure's exact colour and weight on purpose, so clearing one and leaving the other would look like a broken control.
- **The two safety rows keep having no toggle of their own** and now name the switch instead: "Alerts" while they are drawn, "Alerts off" while they are not, greying out with it. A row promising "Always shown" six lines above a switch that plainly is not always would be the panel contradicting itself in one screenful. Where no switch is offered at all, the original tag is exactly right and stays.
- **The sentence under the switch says what it does not take away** — the header's "Trail closed 2.1 mi ahead" and its siblings are untouched, in both states, because the moment that matters is *before* the tap.
- **The status strip (§1) says "Alerts hidden"** for as long as they are.

**Amended 2026-08-25 — the blaze rows are gone.** This section used to open the panel with them: "blaze rows (white / blue / unknown, line swatch on a topo-tinted chip), then a 2-column grid…". They shipped under [#782](https://github.com/OurHike/OurHike/issues/782) and were removed at the maintainer's request — *"the legend doesn't need the color of the blaze included… it's too cluttered"* — so the panel now begins at the pin grid.

Recorded rather than struck out, because the rows were **the only key this app had for its line colours**, and a reader arriving at §3 should know the key it implies is not on screen. §3 is unchanged and so is the paint: `map/style.ts` still colours a trail by its blaze over [`client/src/lib/blaze.ts`](client/src/lib/blaze.ts)'s closed palette, and that palette's admission bar still holds. What went is the panel that named those colours.

Two things carry the naming instead, and neither is a full replacement: a blaze name **is** a colour word, so a line is closer to self-describing than a pin is, and **tapping a line still names its blaze in full** — §3's sheet heads "White blaze · Appalachian Trail" (`client/src/lib/lineDetail.ts`). Neither answers "what is on this screen" without a tap, which is what the rows answered. **`@unvalidated`** — nobody has watched a hiker try, and what would settle it is somebody reading this panel where two trail systems overlap and reporting whether the lines are legible without a key.

One sentence in the panel still speaks about the lines: the ghosting note (§1 of [NEARBY_TRAILS.md](features/NEARBY_TRAILS.md)), which now sits directly above the pin grid. The empty-viewport sentence narrowed its noun to match — it reads **"No waypoints on this part of the map yet"**, because it used to be suppressed by the blaze rows and would otherwise now claim an empty map over a drawn trail.

**Amended 2026-08-15 ([#723](https://github.com/OurHike/OurHike/issues/723)) — the grid is every hideable category, in view or not, and only the grid.** This section used to read "lists **only what's in the current viewport**" and "Full 10-category list lives in Settings, not here", and both halves of that were wrong for one reason: **a row is not only a count, it is the hide switch**, and a switch that exists only while something of its category is on screen is a switch a hiker cannot find when they want it.

That was not a rare case. [POI_VISIBILITY.md](features/POI_VISIBILITY.md)'s own density table puts **2–4 waypoints in a 390 × 700 phone map at z14** and 4–8 at z13, so at the zooms someone actually reads a place from, this panel was routinely offering **two** of its eight toggles. It was reported from an Android phone as exactly that. Sending a hiker to Settings to turn privies back on is the mistake [MAP_OPTIONS.md](features/MAP_OPTIONS.md) §4 already reversed once for the background picker — "the moment someone wants to change it is the moment the map is not showing what they expected".

So `withEveryType` (`client/src/lib/legendContents.ts`) pads the grid to `HIDEABLE_TYPES`, in that fixed order, and **nothing else on the panel sees the padded list.** The separation is the load-bearing part, because the failure it prevents is the panel claiming presence:

- A padded row reads `Privy 0`, which is an accurate sentence about this rectangle, and it carries **no drawn count at all** — "none of them fitted" and "there were none" are different claims and only one of them is true here.
- The empty-state sentences, the "turn Verified? off" sentence, the below-the-pin-floor sentence and the drop summary are all still decided by the viewport, never by the padded list. "Nothing on this part of the map yet" still appears, over eight rows of zero. **Amended 2026-08-18 ([#777](https://github.com/OurHike/OurHike/issues/777)):** the drop summary also subtracts the categories the hiker hid. Their absence is the filter's doing, not the camera's, so counting them had "zoom in to see the rest" promising pins no zoom draws — that line speaks about the viewport *as filtered*, which is what the map is drawing from.
- **Safety rows are not padded.** `closure` and `serious-warning` are not in `HIDEABLE_TYPES`, have no switch to reach, and a standing "Closure 0" would be this panel making a claim about closures that nothing asked for. **Amended 2026-08-27 ([#1051](https://github.com/OurHike/OurHike/issues/1051)):** they are not padded and they *are* present — `withSafetyKey` appends a row for each, carrying the icon, the name and the tag and **no number in any state**. The objection above is to the NUMBER and it survives intact; what it was accidentally also preventing was the row. Both rows had rendered in `client/src/chrome/Legend.test.tsx` and nowhere a hiker could reach, for as long as they had existed: `computeLegendContents` counts `MapPoint`s, a closure reaches the shell as a mile-marker range and a serious warning as a moderated report, and neither is one. So **the only key this app has had never named its two loudest symbols** — a hiker who saw the barred red band across the trail, or the red triangle pin bigger than every other mark on the map, had nowhere in the app to look it up. Tapping does answer (§7's closure sheet, HIKER_SAFETY.md's warning sheet), and "tap the thing you do not recognise" is a worse instruction for a hazard than for a spring. A key entry that waits for the viewport is not a key, which is why these two do not.
- The fixed order is a second thing worth having: the counts come out of a `Map` filled in whatever order the points were encountered, so the grid used to re-shuffle itself as the hiker walked.

Settings keeps its own copy of the list (`client/src/screens/Settings.tsx`), which is where somebody setting the app up rather than reading a map will look — one list, two homes, and the same `HIDEABLE_TYPES` behind both.

The sheet stays capped at 60% of the screen and scrolls, which [MAP_OPTIONS.md](features/MAP_OPTIONS.md) §4 documents and this does not change — a panel that covers the map should not grow to hold a longer list. What changes is that the scroll is now the normal case rather than the occasional one, and the list is its own affordance: two rows in a sheet with room for eight gave a hiker no reason to think anything was below them, and eight rows cut off mid-grid do. The sheet contains its own overscroll (`overscroll-behavior: contain`, so a flick past the end cannot reach Chrome for Android's pull-to-refresh — reasoned from the documented chaining behaviour, not measured on a handset) and pads its foot past `env(safe-area-inset-bottom)`, because it is positioned against the initial containing block and its bottom edge is the viewport's.

**Amended 2026-08-12 ([#572](https://github.com/OurHike/OurHike/issues/572)) — every row carries the map's own icon, and the row itself is the control.** Two halves of one gap, both of them old.

The panel named categories the map draws as pins and drew none of them, so the one screen whose whole job is to teach "this shape means water" never showed the shape. The icons come from `client/src/map/MapIcon.tsx`, which draws from the map's own `pinGeometry()`, `GLYPHS`, `POI_COLORS` and `RIM_DASHES` rather than from a second drawing of a pin. That constraint is the point of the file: a legend that approximates the map is worse than one that shows nothing, because it teaches a symbol the map does not use. So a closure shows the barrier tape (it is a line, not a pin) and a serious warning the hollow hazard triangle. The one place it parts company with the map is **size** — the warning pin is 44px there against a waypoint's 38 because it has to win a glance across a moving screen, and in a key read a row at a time a taller row buys no urgency and costs the grid its alignment. What carries the recognition instead is what carries it on the map: the only outline among solids.

**The confidence variants are gone, and are a filter instead.** "Water 2" and "Water · Unverified 1" were two rows of a grid whose columns are about 116px wide beside a desktop map, so half the labels wrapped onto a second line and the panel was twice as long as the map it describes — all to carry a distinction a *viewport count* cannot act on. Which particular spring is unconfirmed is a question about one spring, and the map already answers it per pin with the broken rim, as does the waypoint card in words. So one row per category, drawn with the solid-rimmed pin (a key whose symbol changed as the hiker panned would not be a key), and one **"Verified?"** checkbox under the grid for the hiker who wants only what somebody has confirmed exists.

Three things follow and all three are load-bearing. The counts move with the filter — a row reading "Water 3" over a map drawing two is the exact lie this panel exists to prevent — so `computeLegendContents` takes the flag rather than the shell filtering afterwards. It is **one** filter expression with the category toggles (`poiFilter` in `client/src/map/poiLayers.ts`), not a second `setFilter` write that would silently win. And it **cannot reach a closure or a serious warning**: a filter that empties the row by arithmetic is the same failure as a button that hides it, and easier to ship without noticing. (That rule was once stated as "no off switch for a safety layer, anywhere in the app". [#1047](https://github.com/OurHike/OurHike/issues/1047) narrowed it to what this sentence is actually about — **nothing STORED reaches a closure**. The Alerts switch above does take the marks off the canvas, and is deliberately not routed through this filter or any other saved value.) When the filter empties the panel it says so in its own words rather than borrowing "nothing on this part of the map yet", which would be a false claim about a stretch with six unconfirmed springs on it — and it stays on screen to be switched back off, because a filter that disappears along with everything it hid is a trap.

"Rows are tappable to hide" is stated above because it has been the spec since before this panel was built. What shipped was a 20px dot at the end of a 44px row that read as tappable across its full width, so a tap on the word "Water" did nothing and said nothing about having done nothing. The icon, the name and the count now sit inside one button. A category that is off greys its pin, strikes its name through and reports `aria-pressed="false"` — **pressed means shown**, which is the opposite of the dot's polarity: that control was a *hide action* and pressed meant the action was engaged, where the row is the *category* and greys out when it is off. A row that plainly reads as off must not announce itself as pressed. Three channels say so and none of them is hue, for the same reason the pins and the closure band avoid relying on one (§3, §7) — this is a panel read at arm's length in direct sun.

### 3. Trail line rendering — blazes (`11a`, `11b`, `11c`)

One normalized `blaze_color` attribute per line feature; one MapLibre `match` expression on `line-color`. No per-layer hardcoding.

**Every trail line is solid.** Colour says which blaze; **width** says whether a line is a system's through-route or a side trail hanging off it. The two channels are keyed off two different attributes — `blaze_color` for the hue, the pipeline's own `source` for the width — in one `match` expression each.

**A side trail is never drawn over the through-route it branches from.** Every trail line is in one layer, so within it the painter's order is the order features arrive in — which is export order, which is nobody's decision. Side trails and the centerline share geometry often (a spur is digitized from the AT's own vertices, and ATC's side trails run coincident with the centerline for a stretch before branching), and where they do, whichever feature was written last owned the pixels. On screen that was the AT showing grey and blue stretches punched through its white — read by a hiker as "the blaze changes here", which is a false statement in the one place this map cannot afford one. `line-sort-key`, off the same `source` attribute that decides width, decides it instead: the primary tier sorts above everything else. Within a tier, one line covering another is two lines of equal standing overlapping, which is honest, and needs no further rule.

**Through-route is a role, not a name for the AT.** Today the AT holds it alone, so the widest line on the map _is_ the AT. That will not hold forever — the NYNJTC alone maintains several trail systems — and the tier is a list (`PRIMARY_TRAIL_SOURCES`) precisely so a Long Path or Highlands Trail import joins it beside the AT rather than displacing it, and so a `centerline` feed that itself grows past the AT needs no code change. Worth being straight about the cost: with two through-routes drawn, width answers "through-route or spur" and stops answering "which trail is this". Telling two through-routes apart falls back to hue — which is the channel this section exists because we cannot rely on. If that day arrives before a third channel does, it is a real regression to design for, not a detail.

| blaze                     | source                                                                   | line treatment                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| White                     | `centerline` (3,025 segments), flat per-source default in `sources.json` | solid 4.5px, hairline dark casing overhanging 1px each side — the through-route width, shared by any source in the primary tier |
| Blue (code 1)             | 641 `side_trails`                                                        | solid 2.5px, same hairline casing                                                                                               |
| Yellow (5)                | 20                                                                       | as side trails                                                                                                                  |
| Orange (4)                | 6                                                                        | as side trails                                                                                                                  |
| Red (3)                   | 2                                                                        | as side trails                                                                                                                  |
| Green (6)                 | 4                                                                        | as side trails                                                                                                                  |
| Purple (7)                | 2 (+3 White, 2 Other)                                                    | as side trails                                                                                                                  |
| Neutral grey              | 484 `None` + 24 empty + 9 `"Unknown"` + 3 `"Gold"`                       | as side trails, in the neutral grey `#8a8271`                                                                                   |
| Black (8)                 | 0 today                                                                  | wide casing, no fill — drawn by absence                                                                                         |
| _anything imported later_ | a `source` key this build has never seen                                 | as side trails — drawn, and never claiming the through-route tier by default                                                    |

**Rules that must survive:** decode the coded domain from the FeatureServer's own field metadata (don't hardcode the table); anything that doesn't decode falls to neutral grey **with a loud pipeline warning**; a through-route is the widest line on the map, which is what keeps the map's subject findable with hue removed by greyscale, glare or colour vision deficiency; **a through-route is also drawn last, so nothing else can cover it**; tapping any line opens a sheet naming the blaze and its source, and says plainly when it's unknown.

**No dashed trail lines (decided 2026-08-03).** Not per-blaze, not as the secondary accessibility cue, not for a hue pair that turns out hard to tell apart — a dashed line over a dark casing reads as its gaps, which is the defect this section's "Superseded" note records. **Closures are the one exception**, and they earn it by not being a trail: barrier tape along closed geometry (§7), structurally unlike any blaze rather than a rhythm to be told apart from one — and since 2026-08-27 not a dash at all but a repeating image, which is what let its dark edging stop being a line underneath that filled every gap. A second cue for the warm hues has to come from somewhere else — casing weight, or a label at high zoom.

**Scoped to above the seam, 2026-08-20 ([#598](https://github.com/OurHike/OurHike/issues/598)).** The rule above governs the map a hiker **navigates by** — at and over `POI_PIN_MIN_ZOOM`, where the line is a thing to follow. Below the seam it does not apply, and the maintainer's call is that it never did: down there the trail is *representational*, 2.5 px standing for 2,197 miles, with no contours behind it and nobody following it.

The 2026-08-03 decision supports the scoping rather than resisting it, and its own "Superseded" note is the evidence: what failed was a line that "read as a dotted grey-and-white thread **through the contours**" — a navigational-zoom failure, at a zoom that draws contours, for a hiker tracing a route. Neither condition holds at the corridor view's opening camera.

What uses it today is [features/CORRIDOR_VIEW.md](features/CORRIDOR_VIEW.md)'s attribution layer: the 38.5 miles ATC's centerline records no maintaining club for draw dashed, in the same neutral grey this section already spends on "we do not know this", and stop at the seam (`client/src/map/corridorLayers.ts`). They carry their own solid casing, because the grey sits **over** the blaze and a dash alone would show the white line through every gap — which is the 2026-08-03 defect exactly, reproduced one layer up. The rule that survives unscoped: **nothing may recolour a blaze at a zoom a hiker navigates by**, which `client/src/map/style.test.ts` now asserts rather than merely stating.

**Superseded 2026-08-03 — lines used to be dashed**, on a per-blaze rhythm (white 10/6, yellow 6/5, red 15/5, undecoded a sparse dotted 4/6), and the rhythm was the hue-independent channel. On screen that made a line alternate between its blaze colour and the casing showing through each gap, and the centerline's blaze is very nearly white — so the AT read as a dotted grey-and-white thread through the contours rather than as a trail. Solid lines with width as the second channel replace it. Two things were genuinely given up and are worth reopening if they bite: yellow/orange/red side trails were separable by rhythm and are now separable by hue alone, and an undecoded blaze no longer _reads_ as uncertain from its dotted rhythm (it is still the neutral grey, and the tap sheet still says so in words).

### 4. Downloads (`10a`, `10b`, `6d`, `7a`) — ⚠ see Known Deviations, below

Wireframed as a per-section list with a per-section detail override. **This interaction model is superseded — see "Known deviations" below before building.** What still carries over: the Light / Standard / Fine (z11 / z12 / z13) detail choice itself, and the measured sizes.

**Amended 2026-08-05 — a window, not a screen.** With the per-section model retired there is exactly one package, started once and deleted maybe never, and a permanent tab for it (§1.6) bought a screen almost nobody opens twice. It is a modal window now (`client/src/screens/DownloadsDialog.tsx`), opened over whatever is showing, with the same contents as before: the detail choice, the progress and resume states, the delete, the install prompt and the build's own "no data source configured" warning. Three things follow from the move and all three are deliberate:

- **The way in is a link at the foot of the legend (§2) and at the foot of Settings (§10)**, from one component (`client/src/chrome/DownloadsLink.tsx`), worded for the phone it is on — _choose_ what to download, or _change_ what's downloaded. Last on both screens on purpose: it is the only route to the window, which is why it is carried, and a once-a-season errand, which is why it does not get the top of a panel someone opens all day. On a desktop the legend is full height and the link is pushed to the foot of it. **Amended 2026-08-12:** in the legend the background picker came down to join it, so everything about the downloaded map is one block at the foot and it is that block the desktop panel pushes — see [features/MAP_OPTIONS.md](features/MAP_OPTIONS.md) §1 for why.
- **The tap has an effect before the transfer does.** Tapping Download fetches the trail's own data first — the canary, and 12.3 MB of it in the shipped bucket — and until 2026-08-09 the card said nothing at all for the whole of that wait, going on offering the button that had just been pressed. On a first run that reads exactly as a download that did not start. The card now states the step and why it comes first, the levels grey out because the transfer begins the moment it lands, and the footer link says `Getting trail data…` — with no bar, because four fetches of unannounced size have no honest percentage and a bar stuck at 0 is the very thing being explained. A tap while the launch fetch is already running now joins it rather than pulling the same megabytes a second time.
- **While a download is actually running, that link carries a thin bar and a figure** — `Downloading 38%`, or `Checking 38%` for the local re-read (§7a) — and carries nothing at all the rest of the time. This is the _only_ place a transfer is visible from outside its own window, and it has to be: the download belongs to the shell, so shutting the window leaves it running with nothing on screen admitting it, and the app reads as idle while it spends someone's data by the mile. Which figure it shows is decided once (`client/src/lib/downloadActivity.ts`) off the same per-sheet statuses the cards render, so the footer and the card can never disagree about one download. A _stopped_ transfer gets no bar — "stopped" is not "in progress", and the resume is inside the window.
- **Picking "Downloaded" on a phone with no download opens the window on its own**, without waiting to be asked twice, and the choice is still saved so it takes effect the moment the archive lands. That is what keeps the link above from having to be prominent: the one moment someone asks for a map this phone cannot draw is already handled where they asked (`client/src/chrome/BackgroundPicker.tsx`, §2).
- **The map is not torn down to look at it.** A trip to the old tab unmounted the map screen and rebuilt it on the way back — the bug the camera-restore code exists to paper over. A window costs none of that.
- **On a desktop it is a centred panel** on a dimmed page rather than a takeover of a 1440px browser (WEBSITE.md §6).

**Amended 2026-08-06 — one download, several archives ([#192](https://github.com/OurHike/OurHike/issues/192)).** The offline map program ([#184](https://github.com/OurHike/OurHike/issues/184)) puts a raster sheet, a vector basemap and a DEM on the same phone. That is a fact about storage, not a decision to hand a hiker: they are **the background data**, downloaded and reclaimed as one thing, and what is chosen about them is what the background _is_ — its detail level here, which sheet is drawn from it in the background picker (§2). The window still holds one card with one button; the archives are combined into one state before they reach the screen (`client/src/lib/backgroundStatus.ts`), so progress, failure and eviction are each stated once, about the whole. This is emphatically not the per-section list returning: sections were a choice somebody had to get right mile by mile, and a wrong answer cost them map where they were walking.

**One bundle now, a choice later.** Decided 2026-08-06: the USGS raster is an optional second sheet a hiker opts into, not part of the background everyone gets ([#237](https://github.com/OurHike/OurHike/issues/237)). It is the whole background today only because it is the only piece the pipeline publishes — once the vector sheet and the DEM exist, bundling all three would hand every hiker hundreds of megabytes of raster on top of the sheet that replaced it.

**The background data is shared between trails; the trail's own data is not.** The DEM and the raster cover ground that the AT and NYNJTC's network both stand on, so they are keyed by what they are and never by which trail wanted them — adding a second trail must not re-download them ([#193](https://github.com/OurHike/OurHike/issues/193)). What _is_ per-trail is the corridor sheet: the centerline, the spurs, the POIs and the elevation profile. Those are small, they are what makes this an app rather than a map viewer, and they are downloaded by default wherever they are missing — so they never appear in this window as something to choose, and deleting the map no longer takes them with it.

**Amended 2026-08-06 — one sheet at a time, under tabs ([#298](https://github.com/OurHike/OurHike/issues/298)).** Stacking the sheets was right while there was one and nearly right with two; the sheets are expected to keep coming, and a stack reads as a list of things to work through rather than as alternatives to choose between. The window draws a tab per sheet (`client/src/screens/Tabs.tsx`), built from whatever the catalog offers, so the sheet after the USGS raster needs no change here. One panel is rendered — not three hidden with CSS — so a hidden sheet's buttons, radios and space warnings are not in the tab order or being announced. With one sheet there is no strip.

**Every sheet shows the same Light / Standard / Fine ladder, greyed where it has none.** Since [#276](https://github.com/OurHike/OurHike/issues/276) the two sheets have two different level sets — the raster's three tiers, the hiking sheet's own basemap cuts — and under tabs that difference is what a hiker sees when they switch: three rows become two, and the row that vanished is the cheapest one. A missing row cannot say whether this map has no Light version or whether the app forgot to ask. So the ladder is the same under every tab and a rung a sheet does not have renders disabled, reading "Not offered". The same greying carries a second case: rungs that exist but cannot be chosen right now, because bytes are already here or on their way — changing detail then means downloading again, and a note says so rather than the control vanishing.

**The hiking sheet has all three rungs as of [#1107](https://github.com/OurHike/OurHike/issues/1107)**, so no rung of it is greyed today: it was z13 Standard and z14 Fine when the paragraph above was written, and the Light row was the greyed example for as long as the ladder had one. Light is a z12 basemap cut paired with a DEM on a harder corridor taper (`pipeline/LIGHT_DOWNLOAD.md`). The rule stands unchanged for the sheet after this one, which will reach the window before the pipeline cuts every level of it — and it is still what a sheet with no dial wired at all renders.

**Amended 2026-08-07 — a finished download that cannot be read says so here ([#334](https://github.com/OurHike/OurHike/issues/334)).** The card's states are all states of the _transfer_, and every one of them is about bytes arriving. An archive that arrives whole and is then damaged — truncated, half evicted, corrupt — is outside that vocabulary entirely: the transfer finished, the bytes are on the phone, and the card correctly says so while the map draws nothing. [#314](https://github.com/OurHike/OurHike/issues/314) gave the map screen the words for that; this window, the one screen where a hiker can act on it, still read green. So the downloaded state now carries an alert above its byte count when the map could not draw from the archive, ending in the one fix (delete, download again) and the one cost (it needs signal). The byte count and the date stay and stay true — withdrawing them would answer one false statement with another, and they are what says how much space deleting gives back. Only the map can find this out, by asking the archive for a tile and being refused, so the fact is observed on the map screen, held by the shell, and handed to this window — which is why it survives the map being unmounted on the way to the More tab.

**Amended 2026-08-07 ([#352](https://github.com/OurHike/OurHike/issues/352)) — the alert says what was observed and stops there.** It ended "the file is damaged or incomplete", which reads as a diagnosis and is only a safe one for the USGS archive: pmtiles answers empty for a tile it does not hold and rejects only on a read failure. The hiking sheet's flag covers its package _and_ the network fallthrough behind it, so a hiker who opened the app already panned past what their package covers, with no signal, was told their download was corrupt. What the app knows is that the map screen could not draw from it, and that deleting and downloading again is the way back; the cause is a guess and is no longer stated as one.

Onboarding still ends on the download (§5), but over the map rather than instead of it — and asks its map-size question in this window's shape.

### 5. Onboarding — Tier 1 (`13a` chosen, `13b` rejected, `13c` sequence)

Three screens, each skippable, each with a step counter:

1. **What OurHike is** — the real logo mark (see `.claude/OurHike Design System/` → `components/core/Logo.jsx`, chosen 2026-07-28 — supersedes this turn's original type-only wordmark), a small map vignette, two short paragraphs: what it does offline, and that the ATC and the other organizations who keep these trails open take members and donations directly while OurHike takes no cut and holds no money. "No account. Nothing to sign up for." **Amended 2026-08-27:** this read "that paid memberships fund the ATC and volunteer clubs", which put OurHike's money in a place it has never gone - see [features/ONBOARDING.md](features/ONBOARDING.md) Tier 1 for the maintainer's wording and the guard on the shipped copy.
2. **Map size** — the whole corridor at Light 64 MB / **Standard 314 MB** (recommended) / Fine 1.18 GB. ⚠ The wireframe copy adds "...or take single sections later, in Downloads" — **drop that clause**, see Known Deviations. **Amended 2026-08-06 ([#277](https://github.com/OurHike/OurHike/issues/277)/[#298](https://github.com/OurHike/OurHike/issues/298)):** the sizes above are the USGS raster's, which is not the download this step is sizing — #277 moved it to the hiking sheet's own Standard / Fine levels, the map a newcomer actually leaves first run with. #298 then gave it the download window's shape: the same tab strip, the same level ladder, the same greying (§4), because this step and that window are two consecutive views of one decision and looked like two different ones. The USGS tab is named and priced here and configures nothing — every rung under it is greyed, pointing at Downloads — which keeps #277's rule while letting a newcomer see what the optional map would cost. What this step does _not_ carry at all is the download itself: no progress, no buttons, nothing on the phone to delete. That belongs to the window, one screen later.
3. **Location permission** — asked as an overlay **on top of the already-downloading map**, so the reason is visible. Copy: works with no signal, position never leaves the phone.

**Never asked here:** notifications (belongs to the wrong-way alert, at hike start) and **accounts** (asked at first contribution — see Reporting below). The step counter is derived from the live step list, and a skipped step still counts so the total never grows mid-flow.

**Amended 2026-08-06 — over the map, all three of them.** Step 3 was always specified as an overlay on the map so the reason for asking was visible; the same argument holds for the other two, and they were an opaque full-page screen. So the map is behind all three now (`client/src/App.tsx`'s onboarding branch): the corridor view the map screen itself opens on, drawn under a card anchored to the bottom of the screen and capped short of filling it. The "small map vignette" in step 1 is that map rather than a picture of one. What is behind the steps is the canvas and **nothing else** — no header, no tab bar, no legend — and it is `inert`, which is not only about stray taps: MapLibre's locate control would otherwise raise the OS location prompt before the step whose whole job is to explain why we are asking. The credit line the live sheet's licences require is rendered over the map's top-left corner, since the bottom corners are where the card is.

**Amended 2026-08-20 ([#857](https://github.com/OurHike/OurHike/issues/857)) — the centerline, and nothing else on it.** "The canvas and nothing else" above was about chrome; this is the same rule applied to what is drawn *on* the canvas. Behind the steps the map carries the trail line and no waypoints: the shell holds the POIs, the spur destinations, the elevation profile and the centerline index until the steps are done and fills them in then (`client/src/lib/useTrailData.ts`'s `centerlineOnly`), and no pin artwork is rasterised for a map with none on it. Measured on a 4×-throttled phone profile, replaying first run with a release already downloaded, doing all of it behind the card cost **5,479 ms** of blocking work and left the second Skip unclickable for 3.4 s — for pixels the card was covering. The download itself still runs while the steps are read; this is about what the shell does with what has landed. **And on a phone holding nothing, the centerline is now committed as soon as it is fetched and checked rather than with the rest of the release ([#863](https://github.com/OurHike/OurHike/issues/863))** — measured, the lines were in hand at 4.8 s and the release finished at ~12 s, which is longer than it takes to click through three steps, so first run's map was empty for the whole flow. Only when there is no release to keep whole, and marked as unfinished so the next launch completes it.

### 6. Reporting (`14a`–`14d`) — supersedes turn `8` — ⚠ see Known Deviations

> **Rebuilt 2026-08-27 ([#1133](https://github.com/OurHike/OurHike/issues/1133)) as a window, not a screen.** What this section describes below is still the content — the six tiles, the two people-cards, the 911 line, the form's fields — and all of it survived. What changed is the container and the moment of filing, and both are worth stating here because the rest of this section reads differently under them:
>
> - **A dialog over the screen you were on**, not a route that swaps the shell. The tab bar stays visible behind the scrim. That is what removed the need for a `Cancel` at all — there is nothing to back out of when nothing was replaced.
> - **One tap on a tile files the report**, into the outbox, immediately. The form below is no longer a gate in front of it; it is an optional receipt afterwards, offering the same note and photo to whoever has something to add.
> - **An 8-second `Undo` in place of the Cancel.** The report is *held* in the outbox for that window rather than sent, so taking it back deletes something never transmitted. `client/src/lib/outbox.ts` holds the mechanism and a 60s ceiling on any hold, so a bug here cannot silently strand a report forever.
> - **Two types still open a form**, and this is the exception the design turns on: a **closure** needs two miles, and **something unsafe happened** is private to moderators. `client/src/reporting/categories.ts` states the rule negatively, so a type added later defaults to *not* filing on a tap.
> - **The anchor is stated rather than asked** — every entry point supplies one — with a `Change` control listing the places today's walked miles covered, nearest first, for the blow-down noticed and remembered a mile later. It never counts them ([features/DATA_NUDGES.md](features/DATA_NUDGES.md)).
>
> The icon gap under **Known deviations** is closed for this screen: the tiles carry real Lucide paths (`client/src/reporting/icons.ts`), not emoji, at 1.5px stroke.

Six condition types in a 2-col grid (`14a`, updated 2026-07-30 to add invasive species):

| tile             | Lucide icon | subtitle                                   |
| ---------------- | ----------- | ------------------------------------------ |
| Blow down        | `tree-pine` | —                                          |
| Flooding         | `waves`     | —                                          |
| Trash            | `trash-2`   | —                                          |
| Shelter repair   | `hammer`    | —                                          |
| Animals          | `paw-print` | Sightings, food raids, anything aggressive |
| Invasive species | `leaf`      | Plants or pests that shouldn't be here     |

Only the last two carry a subtitle, and that asymmetry is the point: they genuinely overlap (a feral hog is both), so the difference has to be legible where someone is choosing rather than in a data dictionary nobody reads. `animals` is a safety encounter — the type [HIKER_SAFETY.md](features/HIKER_SAFETY.md) escalates to `severity: serious`; `invasive_species` is an ecological observation with no personal-risk dimension. See [features/REPORT_A_PROBLEM.md](features/REPORT_A_PROBLEM.md) for why they are separate types rather than one.

Then a separate section, **"About people on the trail,"** with two full-width cards, deliberately not icon buttons:

- **Something unsafe happened** (amber) — threats, robbery, being followed. Private to club moderators, never a public pin with a name. Its own form has chips (Threatened / Followed / Theft / Assault / Harassment / Other), a note, GPS location, and opens with an honest limit: **call 911 if you're in danger now; this reaches volunteers, sometimes days later.** If moderators confirm a pattern it can become an unnamed warning.
- **Say thanks to a maintainer** (green) — pick the club or a specific crew, tap what made the difference (blazes / blow down cleared / shelter / privy / bridge / tread work), leave a note. Negative feedback is nudged to the club directly rather than a public complaint.

  **Amended 2026-08-27 (#1133): this is no longer only a row inside the problem picker.** It was the seventh item in a list of hazards, which is a strange place to keep the one warm thing the app does. It now has two entry points of its own — the foot of Today, beside "Report a problem" at equal width and equal weight, and a plate on a place's card under "Something wrong here?", in the same construction with a green accent. A third, the map's long-press plate, shipped in [#1137](https://github.com/OurHike/OurHike/issues/1137) — press and hold anywhere on the map and a small plate opens at that point carrying both actions, which is the only way to name a stretch with no waypoint on it. The card's is the one that carries a `poiId`, so the thanks can be routed to whoever looks after *that* place. See [features/SAYING_THANKS.md](features/SAYING_THANKS.md) for why none of the three names a maintainer in its own words.

**Report form:** note (free text), optional photo, location (existing POI, dropped pin, or GPS), "signed as `<trail name>` · `<reporter type>`," and the report's **real timestamp — the moment of writing, not of sending**.

**Sign-in happens at the first contribution, not in onboarding.** The report is written and saved first; then Google / Apple / email, then trail name + reporter type (thru / section / day / maintainer; maintainer is club-granted and stays unverified until confirmed). A green callout states that reading the map — water, shelters, closures, warnings — never needs an account.

Which of the three a given build actually offers is deployment configuration, not a screen decision — a provider whose credentials do not exist reaches an error page rather than an account, and Apple's cost more than the other two. See [features/AUTHENTICATION.md](features/AUTHENTICATION.md).

**Four states, always visible to the reporter:** Waiting → Confirmed → Fixed, or Not confirmed. "Not confirmed" carries no penalty, deliberately.

**Public read of a report:** trail name + reporter type + exact date + maintainer confirmation badge + note + photo. (Hiding name/date is the Post-MVP anonymity window.)

### 7. Closures (`15a`)

A closure is a **line**, not a pin: **barrier tape** (14px) laid along the closed trail geometry — red diagonals at 55°, each carrying a 1.25px dark edge, with nothing at all between them, so the trail underneath stays readable through its own closure. Structurally distinct from a red _blaze_ (thinner, solid, hairline casing) so the two survive greyscale. The width is a ratio to the blaze widths above, not a free value: the tape stays more than twice the widest blaze on the map, so widening a trail line has to widen the tape with it.

> **Was a barred band until 2026-08-27**, and the change is worth recording because the spec was not wrong so much as unbuildable as written. "A barred red band with a hard casing" was drawn as a dashed 10px line over a *solid* 14px casing, so the casing showed through every gap — 5px of red, then 3.5px of `#14130f`, all the way along. 41% of the band's length was the darkest ink on the sheet, and it read as a railway. The tape is the same 14px of total ink and the same red, with the casing moved onto each stripe as an edge, where it cannot fill a gap because nothing is under one.

- Header banner when one is ahead: "Trail closed 1.4 mi ahead · Storm damage · mi 1,408.6 – 1,411.0".
- Tap sheet: reason (plain language), mile range, status (`open | closed | reroute-available`), closed-since + expected reopen, marked by (club admin, through the same moderation queue as reports), and a link to the club's reroute notice.
- **OurHike does not compute detours** and says so.
- **Sync age lives on the closure itself** ("Your copy is 3 days old…") — a downloaded map is most dangerous when it's stale about closures.
- **Not a setting.** `show_closures` is not in `UserPreferences` and never syncs. Since [#1047](https://github.com/OurHike/OurHike/issues/1047) the legend does carry an Alerts switch that clears the band from the canvas — held in memory, never written, and back on at the next open, with the header banner and the "Alerts hidden" flag on the status strip untouched throughout (§2).

### 8. Serious warnings (`15b`)

`severity: normal | serious` on the existing `Report` model, **set by a moderator, never self-declared**.

- Pin: 44px — one full touch target, and deliberately the biggest thing on the map — red, `triangle-alert`, high-contrast halo — a variant inside the same icon spec, not a new visual language. (Was 34px until 2026-08-03, when the POI pins went up to 38px for legibility; a warning pin the water pins had caught up with would have stopped outranking anything.)
- Route banner on map open: "2 serious warnings on your route," with See both / Dismiss.
- Detail: "Confirmed by club moderators" badge + date (backed by `verified_at`, stamped when a moderator confirms), where the warning is, what it says, and an explicit "why you weren't pinged."
- **What the detail sheet deliberately no longer says** (#292). It specified two more things, and neither had anything behind it:
  - *The corroboration sentence* ("several separate reports over four days…") needed a count that does not exist and cannot be derived. Producing one means designing a corroboration model, and §1 above already calls that threshold "real moderation policy, not a data-model question" — deferred to #235. With no source, the choices were a hard-coded string, which is a fabricated evidence claim on a safety warning about a person, or a blank where the justification should be.
  - *Reporter attribution*, named or withheld. #252 closed by removing reporter identity from the public read path entirely, so identity is now withheld from **every** report — which means a line explaining why *this* one is anonymous implies the others are named. #245 took `marked_by` off the closure sheet the same way and for the same reason: a field nothing can fill is a quiet lie, and deleting is the reversible way to end it.
- **Warnings never push.**

### 9. Wrong-way / off-trail alert (`15c`) — the only notification

Three beats:

1. **In-app cue** while the app is open: "You may be off the trail — about 90 ft from the white blazes for the last 12 minutes," with Show me the way back / I'm fine.
2. **Push**, only after sustained divergence: "You've been heading south for 25 minutes. Your hike is set NOBO." It won't ask again.
3. **Permission asked when a hike direction is set**, not at launch — before a direction exists there's nothing to be wrong about.

Two detection modes: distance-from-centerline (reuses `ST_LineLocatePoint` snap math) and reversed bearing vs. the `Hike`'s direction (needs a trailing GPS window, a minimum-movement threshold, a minimum persistence). Thresholds in the wireframe (90 ft, 12 min, 25 min) are **placeholders for field testing under canopy**. Web push requires the PWA added to the Home Screen on iOS; the Capacitor build is the reliable channel.

### 10. Settings (`16a`)

**Amended 2026-08-18 — this screen outgrew one scroll.** Five groups below, plus
three more added after this wireframe was drawn (`Your hike`, `Contribute`, `Report
a bug`), are ten sections on one flat page with no sub-navigation, reached from a
tab still labelled `More`. [features/MORE_TAB.md](features/MORE_TAB.md) is the
design doc for turning that into sections a hiker can navigate, and for whether
`More` is still the right word for the tab now that there is enough behind it to
have an opinion. What follows here is still each control's own spec; that doc is
about the container, not the controls.

Five groups over one canonical `UserPreferences` model, then an About block that is
not one of them:

- **You** — trail name (Linked / on-this-device), reporter type, account.
- **The map** — background source (the OSM-schema vector topo sheet has been the default — and offline-capable — since #237; the downloaded USGS quad sheet is the full-detail alternative, not the default this line used to call it), detail for new downloads, roads & walkability _(Later)_.
- **Display** — theme (Light / Dark / Auto, a segmented control like the background picker above it; Auto is last, after the two concrete choices, so the group reads as a spectrum ending in "let the phone decide"), units (Feet / Metres, the same segmented control; built 2026-08-13, [#619](https://github.com/OurHike/OurHike/issues/619)).

  The units row was the standing example of the _(Later)_ treatment for a year and is now the standing example of it being temporary. It is labelled by the unit rather than by the system — a hiker asks "can I get this in metres?", not "is this app imperial?" — and each segment names the distance unit that rides along with it, because choosing metres is also choosing kilometres and finding that out afterwards on the closure banner is a surprise four words prevent. Its description carries the exception under both options: **mile markers stay in miles either way.** The choice reaches every screen and the canvas alike, which is the standard [CONTRIBUTING.md](CONTRIBUTING.md) states and `client/src/test/unitDisplay.test.ts` enforces.
- **Safety & privacy** — **Use my location** (added 2026-08-07, [#312](https://github.com/OurHike/OurHike/issues/312) — the section's one live switch), wrong-way alert toggle, "hide my name on reports for…" _(Later)_, and a red locked callout: **closures and serious warnings are always shown; there is no switch, here or anywhere.**

  The location row is not a new preference — it is the first control for one that existed and could only ever be written once, by onboarding's completion handler. That step is skippable, correctly, so "Not now" during setup disabled GPS for the life of the install with no way back and a header still claiming to look for it. The switch governs both consumers together: the watch in `lib/useGeolocation.ts` and the map's locate control (§1.5). Turning it on does not grant browser permission — it starts the watch, which asks; a browser that has already been told no surfaces as `Location blocked` in the header rather than as a switch that appears to have done nothing.

- **Your data** — export reports/routes (GPX, GeoJSON), last synced + Sync, sources & attribution.

Later rows are shown at reduced opacity with a "Later" tag rather than hidden.

**About this build** (added 2026-08-08, [#378](https://github.com/OurHike/OurHike/issues/378)) — version, commit and build time, with a **Copy build details** button. Reference material rather than a preference, so it takes no `UserPreferences` key and sits below every group that can be changed — but _above_ the download link, which keeps the foot of the screen for the reason §2's note gives.

The commit is there because the version alone cannot identify most builds: `client/package.json` reads `0.0.0` until the first tag, so `main`, every preview and every laptop share it, and the section says as much rather than letting `0.0.0` pass for a version someone could look up. The build time is there because a service worker can serve a bundle long after a newer one deployed, which is otherwise invisible from the phone. The copy button is not a convenience — seven characters of hex retyped from a phone into an email is exactly what arrives with a digit changed — and the three rows stay readable either way, so a browser that refuses the clipboard costs accuracy rather than the feature. RELEASING.md §4 has the version meanings.

**Report a bug** (added 2026-08-13, [#626](https://github.com/OurHike/OurHike/issues/626)) — four options, each opening the GitHub issue form that fits, directly below About this build and still above the download link. Reference material like the section it follows, and it takes no `UserPreferences` key either.

Its placement is the mechanism, not a layout preference: About this build ends by saying the build is worth quoting in a report, and these links carry those exact three lines into the form's `Device and conditions` field, from the same `BuildInfo` the rows above render. Nobody retypes a commit hash. The `area` dropdown is preselected the same way, which is why `client/src/test/issueFormPrefill.test.ts` reads `.github/ISSUE_TEMPLATE/` itself — GitHub matches a prefilled dropdown by its option _text_, so a label reworded in the form and nowhere else stops preselecting silently rather than failing.

The options are worded for the person holding the phone rather than for the tracker they land in — _the app itself_, _something on the map is wrong_, _reports, syncing or signing in_, _something else_ — because someone watching a pin sit in the wrong place is not thinking in client/backend/pipeline. `client/src/lib/bugReport.ts` does that mapping so the hiker does not have to.

Two things it must say and does. **A trail condition is not a bug**, stated above the options rather than under them: this section sits one word from "Report a problem" (§6), which is the flow a blowdown goes through and the one a moderator reads, and somebody who has already tapped has already gone to the wrong place. And **every one of these links needs signal** — in an app whose whole premise is working without it, these four are the one part of Settings that cannot, so the section says so and points at the copy button immediately above as what to do out of range.

It closes by inviting whoever writes code to the repository. This project is built to be handed to the clubs that maintain the trails rather than owned by whoever wrote it, and the moment someone has gone looking for where to report a defect is the one moment they are already pointed at it. Deliberately **not** prefilled: `navigator.userAgent`. It would answer the form's "phone and browser" better than a hiker can, and the build is a fact about our software where the device is a fact about them — see IDENTITY_AND_PRIVACY.md.

### 11. Data staleness (`16b`)

A third visual channel, independent of confidence:

| tier          | age              | treatment                                          |
| ------------- | ---------------- | -------------------------------------------------- |
| Fresh         | ≤ ~14 days       | pin + green ring                                   |
| Ageing        | ~14–60 days      | pin, no ring                                       |
| Stale / never | months, or never | pin faded to ~50%, dotted border, grey dotted ring |

Confidence stays separate, and carries three values rather than two: a solid pin is upstream data nobody disputes, a dashed pin means _never verified to exist_, and a dashed pin with a distinct marker means _reported missing_ — corroborated field reports that the thing upstream published is not there. Staleness means _when a human last said it was fine_, which is a different question from all three. Always state it in words too: "Last confirmed in May · 78 days ago", "2 hikers reported this missing, most recently 4 days ago."

A one-tap "Was it flowing?" updates the date and changes nothing else — this is `FIELD_NOTES.md`'s `FieldNote` (2026-08-09; `DATA_NUDGES.md`'s `ConditionConfirmation` is the same model under its earlier name). **It does need an account**, which this section previously said it did not: that predates Authentication moving into MVP, and the "distinct accounts on distinct days" rule behind _reported missing_ cannot be counted without one. **Boosting** stale POIs' prominence to solicit confirmations is Data Nudges — Post-MVP; today staleness is described, never amplified.

### 12. Other states already wireframed

`7a` download in progress / failed mid-way (structure likely still applies to a single whole-corridor download, see Known Deviations) · `7b` no GPS fix · `7c` empty offline search (says the thing may exist outside what you downloaded) · `9b` off-corridor with the dashed "edge of downloaded area" boundary · `9c` offline outbox (reports wait, with their original timestamps) · `9d` sunlight/greyscale pass · `7f` web shell.

---

## Interactions & behavior

- **Search** takes over the header and collapses the ribbon to one line; local GeoJSON only, no network path, and says so on empty results.
- **Legend** opens as a bottom sheet from a header icon; counts recompute per viewport, and the rows they sit on are every hideable category (§2).
- **Tapping a pin** opens the waypoint card (`6a`–`6b`): a card floating beside the pin itself, photo slot on top, that tracks the pin through every pan and zoom and flips above/below to stay readable. It names the waypoint, its category, its mile, its coordinates and which source listed it — and says in words, not only through the pin's broken rim, when nobody has confirmed the thing exists. **Amended 2026-08-27 ([#953](https://github.com/OurHike/OurHike/issues/953)):** the type-and-mile line also says how far along the trail the place is and which way — `0.3 mi ahead`, `0.3 mi behind`, or `0.3 mi away` where the app has not settled which way the hiker is walking. That last wording is the rule rather than a fallback: "ahead" said to a southbounder walking away from a spring is the opposite of the truth, so the word tracks the *observed* direction only, and the line is absent altogether where the app has no mile for the hiker or none for the place. The design pass behind [#941](https://github.com/OurHike/OurHike/issues/941) drew this line as `0.3 mi ahead, 20 ft off trail`; **the second half is not shipped and is not a rendering detail** — a waypoint's distance *from* the centerline is a fact no artifact carries, and `client/src/lib/wrongWay.ts` records that 72% of shelters sit past `OFF_TRAIL_THRESHOLD_FT`, which makes "20 ft" a mock-up's round number rather than a typical value. The photo slot shows the category's own silhouette unless the download carries a photo for that waypoint — the pipeline can attach openly-licensed, recent Wikimedia Commons photos ([features/POI_PHOTOS.md](features/POI_PHOTOS.md)), each rendered with the credit line its licence requires; most waypoints have no eligible photo and keep the silhouette. A tap on bare map dismisses the card; the legend and the card still never stack — opening either closes the other. The hit area is the pin plus enough slop to reach the 44px minimum touch target, because this is tapped with a gloved thumb.
  **Amended 2026-08-12 ([#524](https://github.com/OurHike/OurHike/issues/524), [#526](https://github.com/OurHike/OurHike/issues/526)) — one pin per _place_, and its parts reachable from the card.** A shelter, its privy and its campsites are one place with parts, and the map drew them as unrelated points a median 42 m apart. `icon-allow-overlap: false` then resolved the crowding by deletion rather than by overlap: at zoom 14, 3% of the trail's 316 privies were drawn anywhere at all, and two thirds of campsites were missing with them. Co-located facilities now fold into a **site** in the pipeline — one pin, in the anchor's own accent and glyph, carrying a mark that says what else is there — and the card grows a row of chips (`Privy · 40 m`) that are also its tabs, so the parts are answered at a glance and readable in one tap. [features/POI_SITES.md](features/POI_SITES.md) is the design, including why this is a modelled fact about facilities rather than a geospatial cluster. *(Amended 2026-08-16 — the chip is a pin and nothing else. `Privy · 40 m` did not fit: at the card's real 240 px, three chips wanted 406. The row is pins now, and the category and distance of the part being read are on the meta line under it. POI_SITES.md §5 carries the measurements and what still scrolls.)*
  **Amended 2026-08-23 ([#941](https://github.com/OurHike/OurHike/issues/941)) — the card peeks, and everything above is what it opens to.** The paragraph above describes one card carrying the whole record, and by the time conditions ([features/FIELD_NOTES.md](features/FIELD_NOTES.md)) and photographs ([features/POI_PHOTOS.md](features/POI_PHOTOS.md)) had both landed on it, a tapped water pin answered with a 16:10 photo box, a paragraph of provenance and a set of coordinates **above** the one-tap answer the hiker had stopped to give. So the tap now opens a **peek**: the name, the category, the mile, the existence sentence where it is true, one condition line, and the two ends of that type's scale as buttons — still tethered to its pin, still flipping above and below, because position is what says which pin was tapped. One deliberate pull opens the rest **in place**, and it is one continuous scroll rather than lanes: Conditions (the history and the composer, under `Say something back`), then `About this place` (the description, the photograph and its credit, the coordinates and the source). On a phone the opened card lets go of the pin and becomes a sheet against the map's bottom edge; above the 900px breakpoint it is a 320px column docked to the map's right, opposite the legend's rail.
  Two things about the peek are rules rather than layout. The existence sentence is **never** behind the pull — a hiker cannot act on "nobody has confirmed this spring exists" if they have to go looking for it (`OurHikeValues.md` #4). And the peek shows the category's silhouette and **never** a photograph, because a Commons photo is only ours to show while its credit shows with it, and the peek has no line to spend on an attribution string; the photograph and its credit arrive together on the pull, or not at all.

- **Locate** follows MapLibre `GeolocateControl` (`trackUserLocation` for continuous); **compass** is `NavigationControl`, tapping resets north-up. Scale bar is `ScaleControl`, imperial by default.
- **Motion:** 120–200 ms ease fades/colour transitions only; buttons press to 97%. No bounce, no spring (design-system rule).
- **Offline everywhere:** every write (report, thanks, confirmation) queues in an outbox with its authored timestamp and syncs later. Nothing blocks on network.
- **Loading/empty/error states are first-class:** download failure resumes rather than restarts; no-GPS shows the last known position with its age; empty search explains the boundary.
  - **One exception, added 2026-08-06 ([#197](https://github.com/OurHike/OurHike/issues/197)):** an archive that arrives complete and matches neither the SHA-256 the bucket published when the attempt started nor the one it publishes now is discarded, not kept for a resume, and the window says so and offers a clean re-download. Those bytes are the right length and the wrong file — resuming onto them can only rebuild the same wrong map — so this is the one failure where "keep what arrived" would be the dishonest choice. A bucket republished mid-download is _not_ that case: those bytes are a whole, newer archive, and they are kept.
  - **A state for local work, added with it:** before a resume asks the network for anything, the phone may re-read the bytes it already holds to check them. That is seconds of nothing for a gigabyte, and it looks exactly like a stalled transfer — so the window says "Checking the part already on this phone", shows how far through it is, and says plainly that this part needs no signal. Someone in a dead spot otherwise cannot tell a busy phone from a dead connection, and the two ask for opposite responses.

## State management

**Client:**

- `UserPreferences` (the single model above) in IndexedDB; syncs when an account is linked.
- Downloaded-package registry — **shape depends on resolving Known Deviations #1** below (whole-corridor vs. per-section).
- Live map state: viewport, visible-layer set, legend contents (derived), GPS fix + accuracy + age.
- Outbox: queued reports / thanks / confirmations with authored timestamps.
- Ephemeral `WrongWayCheck`: `{distance_from_nearest_trail_line, bearing_delta_from_hike_direction, sustained_since}`.

**Server (FastAPI + Postgres):**

- `User` (OAuth/email, verified, optional MFA, `display_name` = trail name, role incl. club admin / maintainer).
- `Report` — `type`, location (POI ref or lat/lon), `reporter_type`, `timestamp`, note, photo, `follow_up` (empty in v1, additive later), `status: submitted | verified | resolved | dismissed`, `visibility: public | internal-only`, `severity: normal | serious`. **Type enum needs a decision — see Known Deviations #2.**
- `Closure` — geometry range along the centerline, reason, `status: open | closed | reroute-available`, dates, marked-by.
- Moderation queue over `Report` + `Closure` (one workflow, not two).

## Load-bearing values

Meaning, not decoration — keep these regardless of restyling:

- Naismith: 5 km/h + 1 h per 600 m ascent, **rounded to 5 minutes, always prefixed `≈`, never shown as an arrival clock**, no descent credit (a known weakness of the rule — don't silently "improve" it). **Superseded in part 2026-07-30 — see [features/PERSONALIZED_PACE.md](features/PERSONALIZED_PACE.md).** Descent is now in scope, but deliberately and in a _separate_ estimator: plain `naismithTime()` keeps no descent term, so nothing silently improves. The rounding, the `≈` and the no-arrival-clock rule all still hold, and matter more once an estimate is personalized and therefore invites more trust.
- Download sizes: whole-corridor archive at z11 ≈ 64 MB, z12 ≈ 314 MB (default), z13 ≈ 1.18 GB (see `pipeline/README.md`).
- Trail lines are solid, with no dashes anywhere but a closure — **above the seam** (`POI_PIN_MIN_ZOOM`); below it the rule is scoped off, see §3. A through-route is the widest line on the map (table above), and the neutral-grey fallback is `#8a8271`.
- Closure = barrier tape (red diagonals, each dark-edged, transparent between); blaze = solid line + hairline casing. The tape stays more than twice the widest blaze.
- Staleness ring semantics (green / none / grey dotted) and the ~14 day / ~60 day tier edges.
- Control sizes: 42px map controls, 38px header buttons, ≥44px effective touch targets.
- The four report states' exact words: Waiting, Confirmed, Fixed, Not confirmed.

---

## Known deviations from the live wireframe — read before implementing

The wireframes were drawn iteratively across 16 turns while the feature docs kept evolving; two spots fell out of sync. Neither is a formatting nitpick — both change what actually gets built.

### 1. Downloads: whole-corridor, not per-section (resolved — follow ROADMAP.md)

[ROADMAP.md](ROADMAP.md) Phase 2 already decided this on 2026-07-28: **"chunking decided: whole corridor, one package"** — a hiker downloads the entire trail's data at once. That decision is settled and this file defers to it.

The wireframe (turns `6d`, `7a`, `7c`, `9c`, `10a`, `10b`) shows a **per-section** list — ~30–50 mile rows, a per-section detail-override sheet, roll-up totals, "mixed-detail seam" messaging. That model was drawn by explicit product direction _after_ the whole-corridor decision, so the wireframe and the roadmap directly disagree. **Build to ROADMAP.md, not the wireframe, here:**

- One package for the whole corridor, not a section list.
- Keep the Light / Standard / Fine (z11 / z12 / z13) detail choice — but as the _only_ download's detail, not a per-section override. The measured sizes (64 MB / 314 MB / 1.18 GB) are already whole-corridor figures, so they apply directly with no per-section ratio math needed.
- Drop: section list, per-section override sheet, roll-up "bytes remaining" math, mixed-detail-seam messaging.
- Fix the onboarding "Map size" screen (`13a`/`13c`) copy to remove "...or take single sections later, in Downloads" — there's no section granularity anywhere in the app.
- `7a`'s in-progress/failed states likely still apply structurally (a single download can still be mid-transfer or fail partway) — just against one package, not per-section rows.

### 2. Reporting: the "unsafe behaviour" / "say thanks" split isn't in the data model yet (resolved 2026-07-29 — see the block quote at the end)

[REPORT_A_PROBLEM.md](features/REPORT_A_PROBLEM.md) defines exactly six report types — `blowdown | trash | bad_hikers | flooding | shelter_repair | animals` — and explicitly flags `bad_hikers` handling as **"an open question, not decided [there]."**

Turn 14 of the wireframe answers that open question, but not by simply routing `bad_hikers` internal-only as the doc anticipated. It replaces the single `bad_hikers` type with **two** new cards:

- **"Something unsafe happened"** — this maps cleanly onto `bad_hikers` → `visibility: internal-only`, consistent with the doc's own recommendation.
- **"Say thanks to a maintainer"** — a **new, positive-report type with no prior design anywhere in the repo.** It's not a condition report and doesn't obviously belong in the `Report` model's `type` enum as written (wrong shape: no location-of-hazard, no moderation-queue need in the same sense, arguably not `internal-only` vs `public` at all but club-facing-only).

This is a real product/data-model decision — whether "say thanks" is a seventh `Report` type, a separate model entirely, or something else — not something to resolve silently in a docs-hygiene pass. Recommend picking this up explicitly in the next planning round, before backend/report work starts, since [MAP_OPTIONS.md](features/MAP_OPTIONS.md)'s closures and [HIKER_SAFETY.md](features/HIKER_SAFETY.md)'s warnings both build on the same `Report`/moderation-queue mechanism and would inherit whatever shape this takes.

> **Resolved 2026-07-29 — see [SAYING_THANKS.md](features/SAYING_THANKS.md).** A thanks is a comment about a specific place: the **seventh `Report` type**, same fields plus photos, optionally tagging a maintainer. It skips the moderation queue (there is nothing to verify), gets its own two states (`Sent` / `Delivered`) because "Not confirmed" on a thank-you note would be insulting, and gets a new `club_only` visibility rather than reusing `internal_only`, which was named for the `bad_hikers` safety case and means a different audience.
>
> The decision pulled in a dependency: to thank a maintainer you cannot name, the app must know who looks after which stretch **and when**, so [VOLUNTEERING.md](features/VOLUNTEERING.md) now carries a versioned `MaintainerAssignment` model. Lookups are always as-of the thanks' authored date, never "now" — a thanks written in June about a section reassigned in July belongs to the June maintainer.

---

## Design tokens & components

Real values live in this repo, not in this file — see [.claude/OurHike Design System/](<.claude/OurHike Design System/>) (`tokens/`, `components/`, `guidelines/`). The wireframe's own working palette was an approximation for layout purposes only; don't carry its hex values into real code.

## Assets

- **Icons:** Lucide line icons throughout (1.75–2.1px stroke). ~~⚠ **Known implementation gap:** the built report-type picker (`client/src/screens/ReportTypePicker.tsx`) uses emoji glyphs, not Lucide.~~ **Closed 2026-08-27 (#1133)** — for that screen only, and by replacing it: `ReportTypePicker.tsx` is gone and the report window carries real Lucide paths inline (`client/src/reporting/icons.ts`, ISC, at 1.5px stroke rather than Lucide's own 2). **The gap itself is not closed** — the rest of the app still draws its own glyphs, and the argument below for doing it in one pass rather than one tile at a time still holds. What changed is that the report picker is no longer the example. — `droplet`, `house`, `tent`, `mountain`, `signpost`, `square-parking`, `tree-pine`, `waves`, `trash-2`, `hammer`, `paw-print`, `shield-alert`, `heart-handshake`, `triangle-alert`, `octagon-alert`, `compass`, `locate-fixed`, `list`, `search`, `bell`, `lock`, `clock`, `refresh-cw`, `badge-check`, `shield-check`.
- **Real logo mark chosen 2026-07-28** — see `.claude/OurHike Design System/` → `components/core/Logo.jsx` (React) and `assets/logo-icon.svg` (standalone, for favicons/app icons). Supersedes every "no logo yet" note elsewhere in this doc and in the design system's own readme.
- **No photography shipped as app assets** — placeholders only. The one photographic surface is the waypoint card's photo slot, filled from _data_ (per-POI Wikimedia Commons photos with per-photo licences, `features/POI_PHOTOS.md`), not from bundled assets.
- **Map data:** USGS US Topo (public domain), ATC GIS layers, OpenStreetMap (ODbL — **visible "© OpenStreetMap" attribution required**, and due now rather than later: the OSM-schema vector basemap has shipped OSM data since #237. The Protomaps context extract this clause used to wait on was cancelled, #196), USGS NHD, USGS 3DEP 1m DEM.

## Screen map

Which repo docs each screen derives from — useful when a frame's intent isn't obvious from the HTML alone:

| Screens                                      | Repo files it derives from                                                                                                                                                                                                          |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Map approaches `1a`–`1d`                     | FEATURES.md (v1 MVP, UX principles), TECHNICAL_ARCHITECTURE.md                                                                                                                                                                      |
| Ribbon + search `3a`–`3c`                    | FEATURES.md (search/filter, "use the app less often")                                                                                                                                                                               |
| Ribbon density + icons `4a`–`4e`             | FEATURES.md (waypoint icon spec), MAP_OPTIONS.md (legend), TRIP_PLANNING.md (Naismith time — MVP)                                                                                                                                   |
| Lanes + clustering `5a`–`5c`                 | FEATURES.md (waypoint icon spec, outdoor usability pass)                                                                                                                                                                            |
| POI detail `6a`–`6b`, `2a`–`2b`              | OurHikeValues.md (#4), FEATURES.md (data sources), DATA_NUDGES.md (staleness)                                                                                                                                                       |
| Search `6c`, `2c`                            | FEATURES.md (basic search/filter by POI type)                                                                                                                                                                                       |
| Downloads `6d`, `2d`–`2e`, `10a`–`10b`       | ROADMAP.md Phase 2 offline download flow; `pipeline/README.md` z11/z12/z13 sizes — **see Known Deviations #1**, per-section framing is superseded                                                                                   |
| Reporting `14a`–`14d` (supersedes `8a`–`8e`) | REPORT_A_PROBLEM.md (types, reporter_type, statuses), AUTHENTICATION.md (sign-in at first contribution), IDENTITY_AND_PRIVACY.md (trail name + who-sees-what) — **see Known Deviations #2**, type split isn't in the data model yet |
| Safety `15a`–`15c`                           | MAP_OPTIONS.md §4 (closures as a line, never a stored preference, no reroute computation), HIKER_SAFETY.md §1 + §5 (moderator-set severity, no push for warnings; wrong-way cue → push)                                                          |
| Blaze colours `11a`–`11c`                    | TRAIL_BLAZE_COLORS.md (coded domain + real counts, neutral fallback, accessibility), SEGMENTS.md (segments inherit line colour)                                                                                                     |
| Route setup / direction `6e`                 | SEGMENTS.md, TRIP_PLANNING.md, MAP_OPTIONS.md (snap-to-trail)                                                                                                                                                                       |
| Component inventory `6f`, `2m`               | all feature docs                                                                                                                                                                                                                    |
| Download states `7a`                         | ROADMAP.md Phase 2 offline download flow                                                                                                                                                                                            |
| No GPS fix `7b`                              | ROADMAP.md Phase 2 "You are here," MAP_OPTIONS.md (GeolocateControl)                                                                                                                                                                |
| Empty offline search `7c`                    | FEATURES.md (offline-first), ROADMAP.md                                                                                                                                                                                             |
| Day-hiker map `7e`                           | SEGMENTS.md (day-hike persona), TRIP_PLANNING.md                                                                                                                                                                                    |
| Web shell `7f`, `2i`                         | FEATURES.md (web-only payments), MAP_OPTIONS.md (web legend panel)                                                                                                                                                                  |
| About / attribution `9a`, `2g`               | ROADMAP.md (OSM attribution), MAP_OPTIONS.md (settings), HIKER_SAFETY.md (anonymity window)                                                                                                                                         |
| Off-corridor `9b`, `2h`                      | pipeline/BASEMAP.md (context through z9 travels inside every package since #189; the Protomaps extract was cancelled, #196)                                                                                                                                                                                     |
| Offline outbox `9c`                          | REPORT_A_PROBLEM.md (backend), DATA_NUDGES.md                                                                                                                                                                                       |
| Sunlight pass `9d`                           | ROADMAP.md Phase 2 outdoor usability pass                                                                                                                                                                                           |
| Settings `16a`                               | IDENTITY_AND_PRIVACY.md (canonical `UserPreferences`), UX_CUSTOMIZATION.md, MORE_TAB.md (sectioning + tab naming, 2026-08-18)                                                                                                       |
| Data staleness `16b`                         | DATA_NUDGES.md                                                                                                                                                                                                                      |

## Not yet wireframed

The source handoff's own "not yet wireframed" checklist listed several screens that the Screens/views section above (and the Screen map) already shows as drawn — closures, serious warnings, the wrong-way alert, settings, staleness, and onboarding all have frame ids. That checklist wasn't kept in sync with the later turns; reconciled against the actual screen inventory, what's genuinely still open is:

- A club-side moderator queue view (admin UI for the `Report`/`Closure` moderation workflow) — optional for MVP, hikers never see it.
- Anonymity window (Post-MVP, HIKER_SAFETY.md).
- Weather relay + elevation-aware conditions (Post-MVP, HIKER_SAFETY.md).
- Segments / Trip Planning (Post-MVP).
- Volunteering work-project pins (Post-MVP).
- Roads/walkability overlay (Post-MVP, MAP_OPTIONS.md).
- Auto-rotate (Post-MVP, UX_CUSTOMIZATION.md).
- Persistent waypoint/layer prefs (Post-MVP, UX_CUSTOMIZATION.md). _Theme override was here until 2026-08-06 and metric units until 2026-08-13; both are built — see that doc._
- Community Building — Tramily, check-ins, mentions (Post-MVP).
- Pricing tiers / paywall UI (Post-MVP, PRICING_MODEL.md).
- Trail names as a distinct onboarding tier (Post-MVP, ONBOARDING.md).

## Test plan

See [TESTING.md](TESTING.md)'s **Client (React/TypeScript)** section — the behaviors these screens need covered (blaze normalization, Naismith, download sizing, staleness tiers, the wrong-way detector, offline outbox, moderation invariants) before implementation starts.
