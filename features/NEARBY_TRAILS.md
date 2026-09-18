# OurHike — Nearby Trails (Feature Design Draft v1)

Companion to [TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md) (whose palette this extends),
[MAP_OPTIONS.md](MAP_OPTIONS.md) and [../WIREFRAMES.md](../WIREFRAMES.md) §3/§7 (whose line
and closure rules this inherits), [POI_VISIBILITY.md](POI_VISIBILITY.md) and
[CORRIDOR_VIEW.md](CORRIDOR_VIEW.md) (the seam), [POI_DEDUPLICATION.md](POI_DEDUPLICATION.md)
(whose merge rules go cross-org here), [HIKER_SAFETY.md](HIKER_SAFETY.md) and
[../OurHikeValues.md](../OurHikeValues.md) #4 and #7.

Answers [#772 — Design the map when trails cross: one chosen centerline, every other trail
visible, and safety pins that ignore the choice](https://github.com/OurHike/OurHike/issues/772),
inside [#768](https://github.com/OurHike/OurHike/issues/768)'s trails-within-reach-of-NYC
program. Every measurement cited below is the
[#771](https://github.com/OurHike/OurHike/issues/771) spike's
(`pipeline/spike_nyc_trails.py`, 2026-08-18) unless dated otherwise.

**Status, 2026-08-24: shipping.** The map
([#783](https://github.com/OurHike/OurHike/issues/783)), the labels
([#930](https://github.com/OurHike/OurHike/issues/930)), the palette
([#782](https://github.com/OurHike/OurHike/issues/782)) and the data behind them
([#950](https://github.com/OurHike/OurHike/issues/950), `pipeline/export_nearby_trails.py`)
all exist, and 3,663 trail lines from NYS OPRHP and NYNJTC now reach hikers.

The licence hold that stood between this doc and a phone came off on 2026-08-24, and how it
came off is worth recording rather than smoothing over. OPRHP's terms had been logged as
_unstated_ on the strength of a truncated read; read whole they **permit reuse, require
attribution, and say "non-commercial purposes"**. The maintainer determined that OurHike
satisfies the non-commercial condition — the trail line sits in the tier PRICING_MODEL.md
keeps free for everyone — and separately authorised NYNJTC's public extracts, which state
nothing at all. Both determinations and the argument against the first are in
`sources.json`. OPRHP's attribution is now a rendered condition, not a note: `map/credits.ts`
puts it in the corner whenever their lines are drawn.

§9 is the section to read next: its offline requirement is the one this build still does not
meet.

---

## The ground this designs for, measured

The app's map has always had one subject: a linear trail with side trails hanging off it.
Harriman–Bear Mountain is what the second trail system actually looks like: **993 segments,
316 miles, 109 named trails, 263 junctions** — one junction every 1.2 trail-miles — with the
AT and the Long Path running through the middle. Only 56 of the 109 names merge into a single
walkable chain, and the worst "multi-part trails" are place-labels for path networks (Beaver
Pond Campground: 34 disjoint parts). Along the AT through the parks, **48% of sampled points
sit within 150 m of a different marked trail**.

So this doc answers: what does the map draw when the chosen trail is one line among forty,
what happens when a hiker taps one of the others, and which org's version of a shared thing
wins.

## The decisions, dated

All taken by the maintainer on 2026-08-18, in the planning conversation and against the
canvas of drawn alternatives ("Nearby Trails Options"); this doc records and specifies them,
it does not relitigate them.

| decision                                        | choice                                                                 |
| ----------------------------------------------- | ---------------------------------------------------------------------- |
| The map's subject                               | The centerline is always the **chosen trail**; one trail at a time     |
| Other trails                                    | Visible, de-emphasized — **ghosted** (option B below)                  |
| Tapping a nearby trail                          | **View-only sheet**; switching stays in the picker                     |
| Amenity POIs                                    | Chosen trail only                                                      |
| Safety POIs (water, closures, serious warnings) | Drawn for **every** trail on screen                                    |
| POIs across orgs                                | Deduped into **shared records**; the **selected org wins the display** |
| Lines across orgs                               | The **route owner's line** always renders; landowner copies suppressed |
| Long-term closed trails                         | Ship, drawn with **the closure treatment** (option A below)            |
| Uses                                            | **Hiking only** — bike/horse/XC/snowmobile stay unshipped              |
| Blazes                                          | **The paint's real color renders**, palette extended under governance  |

_Water, one of the three safety kinds in that row, reached only the A.T. until #1016 —
§11 has what it is measured against now, and why a network POI carries no A.T. mile._

## 1. The chosen trail and the others — ghosting, specified

WIREFRAMES.md §3 already gives this map two channels: **hue says which blaze, width says
which line the map is about** (through-route 4.5 px, side trails 2.5 px, through-route
sorted last so nothing covers it). Nearby trails take the side-trail width and keep their
real blaze hue — and add the one new value this feature introduces:

- **Nearby trails render at reduced opacity.** `NEARBY_TRAIL_OPACITY = 0.45` —
  `@unvalidated`: picked so the hue stays _identifiable_ while the chosen trail is
  _unmistakable_, from the drawn comparison rather than from a measurement. What would
  settle it: the same outdoor pass #105 owes the rest of the chrome, in sunlight, on both
  sheets. The chosen trail renders at full opacity, full width, on top.
- **Labels dim with their lines** — a full-strength name on a ghosted line points at the
  wrong thing.
- **The chosen decision survives every appearance.** Under red-light mode every blaze
  collapses to one hue (MAP_STYLE_SPEC.md), and ghosting is an opacity fact, not a hue
  fact — the chosen trail stays the brightest line on the screen. This is the argument that
  beat the halo option (a new device whose meaning red light would have erased) and the
  house-rule option (which left the chosen trail leading by width alone in a forty-line
  park).
- **What the legend says**: one sentence of state — "Other trails are dimmed; the trail
  you chose is full-strength" — rather than a new control. Nothing here is hideable:
  nearby trails are context, and context that can be switched off is a mode nobody
  remembers being in. _(Amended 2026-08-25: this used to read "the blaze rows
  (WIREFRAMES.md §2) gain one sentence of state". Those rows were removed as clutter at
  the maintainer's request, and the sentence outlived them — it now sits directly above
  the pin grid, and is the only thing the legend still says about the trail lines.)_
- **Not a contradiction of §3, an extension.** The through-route is still the widest and
  last-drawn. Ghosting adds a third channel (opacity) for a distinction the AT-only map
  never had to draw. _(Amended 2026-09-08,
  [#1283](https://github.com/OurHike/OurHike/issues/1283): this said "every line stays
  solid; the no-dash rule holds". For two days it did not — a nearby trail was also a
  **dot rhythm**, a fourth channel on a layer of its own under the chosen system's solid
  lines, because at the opening camera opacity alone could not say which of a
  country's worth of threads the map was about. Amended again 2026-09-10,
  [#1374](https://github.com/OurHike/OurHike/pull/1374): the maintainer took the dots
  off a z13 frame — "the dashes are distracting" — so every line stays solid and the
  no-dash rule holds once more. The layer split #1283 built stays: its untaken half
  draws under the chosen system's and at the network's far weight below the seam, which
  with opacity is what now separates the two. Ghosting is unchanged throughout;
  the argument above for opacity over a halo or a hue was never about the dash.
  WIREFRAMES.md §3 carries both amendments, the through-route badge, and where the
  near-white ink still applies.)_

The tradeoff this choice accepts, stated so nobody rediscovers it: blaze identity weakens
on exactly the trails a hiker might be thinking of taking. Two things recover it — the hue
is dimmed, never removed (the maintainer's rule: _"the color of the trail blazes should be
the color on the map"_), and the tap sheet below shows the blaze at full strength.

_(Amended 2026-09-17, [#1575](https://github.com/OurHike/OurHike/issues/1575): the hue is off the map's lines by default now — every trail is one red until the hiker switches "Blaze colors" on in the legend, the maintainer's request of that day: "Showing the blaze color can be distracting and feel like I'm living in a rainbow". Ghosting is unchanged, because it is an opacity fact: under the one red it is opacity and width that separate the chosen system from the rest, exactly as under red light. The tap sheet and the legend's "Trails in view" rows show the blaze at full strength whichever way the switch is set.)_
- **Every badged trail takes the A.T.'s prominence below the seam (2026-09-18,
  [#1586](https://github.com/OurHike/OurHike/issues/1586))** — a casing under the corridor-view
  sketch's through-routes, the A.T.'s own far weight, and a seam handoff at the line's own
  tier (WIREFRAMES.md §3's amendment of that date has the rule and what "long-distance"
  means to the map: _"those named with pills showing"_). Ghosting is untouched: the Long
  Path outside the chosen system is a cased, ghosted line, which is exactly what the untaken
  A.T. is at the opening camera — the parity the maintainer asked for.

## 2. Tapping a nearby trail — a sheet that informs and does not switch

Tapping any line already opens a sheet naming the blaze and its source (WIREFRAMES.md §3;
[#134](https://github.com/OurHike/OurHike/issues/134)'s line-detail sheet is the pattern).
A nearby trail's sheet carries: the name, the blaze chip at full color, the length and the
park, the provenance line (§6 below) — **and no switch action**. Where the trail is one the
client's trail registry knows by name (`lib/trails.ts` — the A.T., and since
[#1288](https://github.com/OurHike/OurHike/issues/1288) the Long Path), its own mark sits
beside the name; a trail with no recorded mark gets none, never a placeholder, and every
mark in that registry is a third-party trademark whose permission is recorded on its org's
row in `pipeline/sources.json`'s `org_marks`. Switching trails stays in
the picker ([#558 — Let a hiker take the stretch they are walking, without picking it off a
list](https://github.com/OurHike/OurHike/issues/558) is that flow's home).

**And since [#1476 — Tapping a trail says how far it goes and never how much it climbs,
though every edge's gain is already measured and cut into the cell the tap just
loaded](https://github.com/OurHike/OurHike/issues/1476), how much it climbs.** The sheet
had always said how far a trail goes and never how much it rises, on every trail including
the A.T., and nineteen flat miles and nineteen miles over five Harriman knobs are not the
same walk. The figure was already published — `export_network_elevation.py` measures
`[gain_ft, loss_ft]` along every edge of the junction graph and `cut_trail_graph.py` files
it into the same cells — and had exactly one reader, `lib/dayHikeCard.ts`, for a *resolved
day hike*. A hiker who never opened the builder had never seen it.

`lib/lineClimb.ts` is the sum, and it is written in feet over edges rather than over a
concatenated profile, which is what keeps [#559](https://github.com/OurHike/OurHike/issues/559)'s
phantom ~36,800 ft out of it: `ENDPOINT_SNAP_M` lets two edges meeting at one node sit
metres apart on the ground, and the step between them is never a term here because there is
nothing to sum across. Three absences are told apart rather than flattened into "unknown",
because two of them are things a hiker can act on and one is not — a **hole in the DEM**
(no total, and say how much of the trail it is), a line running **past the cells this phone
holds** (no total, and point at the download), and **no figures on this phone at all** (say
nothing, because a permanent "climb unknown" on every line is the caveat-on-every-line that
buries the two a hiker's safety turns on). The figure that does print carries the estimate
sentence `DayHikeCard` gives it: the maintainer's decision of 2026-08-25 was to ship it
*and* frame it, and the two measurements either side of it — a dead band reading +18.8%
against a maintaining club on rolling ground, and junction-chopping understating a
continuous profile by a median 6.9% — have never been netted against each other.

Why, argued: making a nearby trail the chosen one swaps the mile frame, the elevation
ribbon, the Naismith numbers and the amenity POI set **at once** — the whole context a hiker
is navigating by. At 263 junctions per park, a one-tap switch on the map is an accidental
context loss waiting to happen, and an accidental one in exactly the moment (a junction,
deciding) when a wrong screen costs the most. The cost accepted: the on-the-ground moment —
standing at a junction wanting to take the other trail — is served by two screens instead
of one tap. **Revisit trigger, named**: if field testing (#106) shows hikers at junctions
reaching for the sheet expecting a switch, this decision earns a re-argument with that
evidence; until then it stands.

**Re-argued 2026-09-09, for the badge only ([#1306](https://github.com/OurHike/OurHike/issues/1306) —
First launch takes no trail: every line dotted until the hiker takes one from its badge or
legend row).** _(The title's "dotted" is the dot rhythm of #1283, gone since 2026-09-10 —
"untaken" is the word now, and the argument below did not depend on the dots.)_ The case above is against a one-tap switch on a _line_ at a junction, and it
still holds for lines: a tap on any line opens the sheet and switches nothing. A through-route's
**badge** is a different thing — a deliberate thumb target the design chose over bare along-line
names precisely so there would be one — and the maintainer's call is that a tap on it _takes_ the
trail, as does a tap on the trail's row in the legend's "Trails in view" block. Nothing is taken
on first launch. What taking changes is the lines (full strength against ghosted, and the
taken trail's own weight below the seam — solid against dotted until 2026-09-10) and the
legend's `taken`; the mile frame, the ribbon, the numbers and the POI set stay the A.T.'s, which is what
keeps this outside the argument above rather than a reversal of it.

## 3. Closed trails — the closure vocabulary, reused

OPRHP marks trails `Closed` long-term (125 statewide) — distinct from the live
temporary-closures layer. They ship, drawn with **the closure treatment**: the red
barrier tape, the map's one permitted non-solid trail-line treatment (WIREFRAMES.md §3's
stated exception, §7's spec). One vocabulary for "do not walk this", which is the argument that
won: a hiker learns one mark.

**Built 2026-08-24 ([#964](https://github.com/OurHike/OurHike/issues/964)), and it turned out to be two feeds rather than one.** OPRHP's long-term `Closed` status ships on the line as this section describes. Their _temporary_ closures do not work that way at all: they are polygons over ground, with the reason as prose and no dates, and two of the four do not touch the A.T. — so they are derived onto the trail lines by intersection, split at the boundary, and carry `closure_kind: "area"` against the status feed's `"long_term"`. That property exists because this paragraph asks the sheet to say different things about the two, and `trail_status` cannot tell them apart. **The sheet's half landed with [#1142 — The tapped-line sheet reads a temporary closure in the long-term voice](https://github.com/OurHike/OurHike/issues/1142)**: an area-derived record's sentence is now the closing organization's — "Temporarily closed by …" with their reason verbatim and no date, since the layer publishes none — attributed through `closure_source` (shipped since the same change) and the published stewards table, never through the trail line's own org.

What keeps the two kinds of closed apart is the **sheet, not the line**: a long-term closed
trail's sheet says "Closed by NYS OPRHP" with the layer's own edit date; a temporary
closure's says its reason and reporting date as today (ClosureSheet). `Proposed` (19) and
blank/Unknown (24) segments do not ship at all — a proposed trail is not ground, and an
unknown status drawn as walkable is a guess (omit rather than guess).

## 4. Blazes beyond seven — the palette grows, under governance

The maintainer's decision, verbatim: _"we will need to bring in more colors for the blazes.
Long [Path] is indeed aqua. Some way to stop sprawl is needed, but the color of the trail
blazes should be the color on the map."_

_(Superseded in part 2026-09-17, [#1575](https://github.com/OurHike/OurHike/issues/1575): the colour is on the map while the legend's "Blaze colors" switch is on, and the map ships with it off — one red line for every trail. The palette, its governance and the mapping table below are untouched; what changed is whether the map's lines wear the hue by default. §1's amendment has the rest.)_

The need is measured: OPRHP's statewide layer carries **Aqua (166), Pink (171), Light Blue
(115), Teal (80), Brown (116), Black (50), Lime (35)** beyond the client's seven paints —
and Aqua is not noise, it is the Long Path's real paint (107 Aqua + 28 Teal rows on OPRHP's
own LP segments, agreeing with NYNJTC's data). NJ's layers carry their own `TRL_COLOR`
domain.

The mechanism, which is where sprawl stops:

- **One governed palette, closed.** `client/src/lib/blaze.ts`'s `BLAZE_COLORS` is the
  entire set of hues this map will ever paint. It grows by pull-request review, never by
  data arrival: a new color is admitted only with (a) a real trail wearing it, (b) a hex
  that passes contrast on both the day and dark sheets next to its nearest palette
  neighbour, and (c) no change to the red-light collapse (which already erases hue
  honestly).
- **Every source normalizes INTO it.** `pipeline/lib/blaze.py` gains per-source mapping
  tables — reviewed files, the `shelter_capacity.json` posture — that map raw values onto
  palette members: OPRHP's `Teal` → `Aqua` (two spellings of one paint on the ground),
  `Light Blue` likely → its own member (a real distinct paint in these parks), `Lime` →
  measured before mapped. Anything unmapped falls to `Unknown` neutral **with the loud
  pipeline warning §3 of WIREFRAMES already requires** — a color the map has never heard of
  must never invent a paint.
- **First admissions**: Aqua is in (the Long Path forces it). Every other candidate waits
  for the mapping-table review, with the OPRHP counts above as the docket.

**Built 2026-08-22 (#782).** `client/src/lib/blaze.ts` admits **Aqua at `#0d8f96`**,
`pipeline/lib/blaze.py` gains `map_source_blaze`, and the docket lives in
`pipeline/reference/blaze_mapping.json`. Five things the build settled that this section
left open:

- **The admission bars are the palette's own numbers, and they are enforced rather than
  described.** There is no standard for "two trail lines a hiker can tell apart at a
  junction" — WCAG is about text on a background — so inventing a threshold would be a
  number with nothing behind it. `blazeGovernance.test.ts` computes a no-regression bar
  instead: separation ≥ **24.178** (Blue/Purple, the closest pair already shipping), day
  contrast ≥ **2.076** (Yellow's) and night contrast ≥ **2.66** (Purple's). A future
  admission that fails one fails CI. White is exempted by name from the day bar, because
  white paint on white paper is 1.02 and its width and casing are what carry it.
- **Aqua's hex is measured, not picked**: ΔE 36.6 from its nearest neighbour, 3.90 day,
  4.80 night. Chosen over `#00a0a8`, which separates slightly better and reads worse on the
  day sheet — the one a hiker holds in the sun. `@unvalidated` all the same: arithmetic is
  not legibility, and **#105 — Outdoor usability pass** is what would settle it.
- **"Deferred" is a third disposition, not a flavour of unmapped.** A value somebody looked
  at and declined to paint renders the same neutral as one nobody has seen, and they are
  not the same event — collapsing them is how an oversight hides inside a docket. The
  mapping table records `why` and `settles_it` for each, and a test refuses a deferral
  missing either. Deferred today: Light Blue (115), Pink (171), Brown (116), Black (50),
  Lime (35).
- **A mapping row naming a paint the client cannot draw is refused, not warned.** A warning
  would ship every trail wearing it as neutral grey, indistinguishable from "this source
  had no blaze data" — the silent-wrong the loud warning exists to prevent, arriving by the
  one path the warning cannot see. It is a file a person edited, so the failure belongs at
  the edit.
- **The mapping applies to the DECODED value, not the raw one.** OPRHP's layer is coded, so
  mapping the code would tie a reviewed file to an ArcGIS numbering that can change under
  us. A source with no table takes the decode-only path unchanged, which is what makes this
  A.T.-safe: nothing about the seven colours already shipping goes through the new code.

And one thing found while building it: **#657's `NO_BLAZE_COUNTS` was not waiting on this
issue.** Its comment said the legend's blaze rows "need the reviewed colour mapping #782 is
deciding", and a trail feature already carries `blaze_color` on every source shipping — so
counting what the map drew never needed the table. The rows are live now
(`client/src/map/drawnBlazes.ts`), which is also this section's own completion condition
demonstrated rather than asserted: nothing in that module names a colour, so Aqua counts the
day a trail wears it.

**Amended 2026-08-25 — the rows are gone, and so is `drawnBlazeCounts`.** The legend's blaze
rows were removed as clutter at the maintainer's request (WIREFRAMES.md §2 has the decision
and what it costs), so the measurement that fed them came out rather than staying as a
number nothing reads. The completion condition it demonstrated is therefore no longer
demonstrated by anything, which is the honest statement of where this leaves §4: the closed
palette and its admission bar are untouched and still govern what the MAP paints, but no
panel now names those colours for a hiker. `drawsNearbyTrails` is what remains in
`client/src/map/drawnBlazes.ts`, feeding the ghosting sentence above.

## 5. One place, one line, many orgs

Cross-org rules, recorded from the maintainer's decisions and the spike's evidence:

- **Lines: the route owner's geometry renders, everywhere.** The AT is ATC's line; the
  Long Path is NYNJTC's; the landowner's copy of a marquee route is suppressed as a
  duplicate (proximity + name). The evidence that this is a real rule and not tidiness:
  OPRHP's AT copy agrees with ATC's line at 1.8 m median _and_ diverges past 150 m on 14%
  of the in-park length, peaking at 1.24 km — an old alignment, rendered, would be a wrong
  map. The agreeing case (Long Path: 3.3 m median, 97% within 150 m) shows the dedupe is
  tractable.
- **POIs: deduped into shared cross-org records; the selected org wins the display.**
  POI_DEDUPLICATION.md's proximity-proposes-name-decides extends across orgs; precedence
  gains a second axis — the org whose route the hiker chose supplies the card's voice.
  Two edges closed here rather than inherited silently: when the selected org has no value
  for a field, the other org's value shows _with its own attribution_ (omit-rather-than-guess
  governs unknowns, not known-by-someone-else); and a safety-relevant fact only one org
  carries **never loses to precedence** — safety completeness outranks display preference.
- **What "the org" means is deliberately not settled here.** The AT in NY has a joint
  superowner, per-section landowners with final say, and per-section maintainers —
  [#780 — Research route ownership](https://github.com/OurHike/OurHike/issues/780) owns
  that lattice, and this doc's "selected org" resolves against whatever #780 lands.
- **Two trails on one treadway draw as two halves of one line, 2026-09-10
  ([#1384 — Two trails on one treadway: draw both](https://github.com/OurHike/OurHike/issues/1384)).**
  The maintainer, looking at Harriman: "If 2 trail lines overlap, could we show both
  somehow?" — and, shown the options, chose the two-tone: each blaze on its own side.
  The data half is `pipeline/lib/concurrency.py`, run inside `export_nearby_trails.py`:
  where trail A's lines lie within **10 m** of trail B's for **50 m or more**, both
  measured there against UA's 2026-09-10 lines (the shared-kilometres curve flattens at
  8–10 m and ATC's own side trails, which share no ground with the centerline, produce
  nothing over 50 m), a pair of features on one chord — A's properties on one, B's on
  the other, each naming the other in `concurrent_with` and `concurrent_source`, `concurrent_side` +1 and −1 —
  goes into `concurrent_trails.geojson` and from there **into the vector tiles only**,
  never into `nearby_trails.geojson`, which eleven scripts read as the network's
  topology. The A.T.'s centerline is in the pool (its raw fetch, simplified to the same
  1 m) and is always the +1 half; its side trails are not. **A stretch is kept only when
  the two halves carry two different real blazes**: the first run over real data found
  the A.T.'s most frequent partners were other organizations' copies of the A.T. under
  their own names ("APPALACHIAN TRAIL", New Hampshire's "MOOSE MTN"), blazed "Unknown",
  and the Whites' trails in the A.T.'s own White — one trail spelled twice, not two
  trails — and none of that survives the rule. The module docstring carries every
  number. The client half offsets each half to its side and is the front-end overhaul's
  ([#1373](https://github.com/OurHike/OurHike/issues/1373)).

## 6. Provenance in the display voice

**Half built as of 2026-08-24, and the half that exists is the half a licence requires.**
OPRHP's terms make attribution a condition of using their data, so `map/credits.ts` carries
it as an atom and the map corner names both stewards whenever their lines are drawn — the
same mechanism, and the same "credit only what is actually on screen" rule, that governs
OpenStreetMap's. The sources screen ([#927](https://github.com/OurHike/OurHike/issues/927))
names them too, now that `reaches_hikers` is true for the three shipped sources.

**Still missing: the per-trail line in the tap sheet.** Tapping a nearby trail does not yet
say "Trail data: NYS OPRHP" beside that particular trail, in the voice this section
specifies. The corner satisfies the licence; the sheet is what satisfies the hiker asking
whose line they are looking at. The pipeline already records each source's steward and
attribution in the export manifest, so whoever builds it has one place to read from.

Every nearby-trail sheet carries a source line — "Trail data: NYS OPRHP" — and OPRHP's own
licence text disclaims accuracy, so the line's job is honesty, not decoration. The wording
ships from the pipeline's per-source attribution fields (sources.json), never hardcoded;
a source whose steward disclaims accuracy may not render in the same voice as a surveyed
one ("never let a display outrun its source"). The exact sentence is settled with the
first shipped rendering; the canvas mock's wording is a placeholder and says so.

## 7. Wrong-way in a network — historical, feature removed

`trailPosition.ts` used to feed `wrongWay.ts`'s "lost" inference from
distance-to-_the_-centerline alone (both files, along with the wrong-way alert itself,
are gone as of [#93](https://github.com/OurHike/OurHike/issues/93)/[#308](https://github.com/OurHike/OurHike/issues/308)'s
resolution — see [features/HIKER_SAFETY.md](HIKER_SAFETY.md) §5). Kept here because the
underlying measurement outlives the feature it was made for: half the AT's length in
Harriman runs within 150 m of a different marked trail, so "off the chosen trail" usually
means "on another one," not lost — a real false-positive risk for any future detection
built against centerline distance alone.

If a similar feature is built again, the network-aware shape this section used to sketch
is worth re-deriving fresh against whatever detection logic exists at that time, rather
than resurrected from here: broadly, a position within threshold of _any_ shipped trail
line is not "off trail," and "off the chosen trail but on another mapped one" reads as a
much lower-stakes signal than actually being lost.

## 8. The seam, and what sits below it in a park

POI_VISIBILITY.md owns z≥9; CORRIDOR_VIEW.md owns z0–8 with club sections as its subject.
Forty short trails are not a below-seam subject — at z7 Harriman is one green shape. The
extension, not a fork: **below the seam, the network ground's subject is the park** — the
unit polygons already registered (`oprhp_park_polygons`, 858 statewide) with the marquee
routes (AT, Long Path) still drawn through them, exactly as club sections tile the AT.
Tapping a park below the seam says who runs it and what the big routes through it are.

**Half built (2026-08-24, #950).** The half that shipped is the negative one: the
network's full lines draw only at z≥9, so 3,663 lines cannot smear across a corridor view
whose subject is the thirty club sections. The half that did not is everything positive
this section describes — park polygons are fetched but not exported, nothing distinguishes
a marquee route from a short park trail, and there is no below-seam park tap.
[#557 — Draw the map from several coverage units, and say plainly where they end](https://github.com/OurHike/OurHike/issues/557)
is where the positive half belongs.

**The absence half was withdrawn on 2026-08-27 (#1135 — Decide what the opening map
draws: every mapped trail, and no waypoints below the seam).** This section used to end
"the Long Path is absent below z9 rather than drawn at the wrong prominence", and the
maintainer's call made a third option of that dilemma: below the seam the whole network
draws from a 100 m overview of itself (`export_nearby_trails.py`'s `write_overview`,
255 KB gzipped for all 7,670 line-miles, `trail_status` kept so closed ground stays
taped), ghosted under the A.T. exactly as the full lines are above the seam — presence
at the _right_ prominence, which the dilemma's two horns both lacked. The smear #950 cut
stays cut: the overview is 31 merged features, not 21,805. What #557 still owns is
unchanged — the park as the below-seam _subject_, tappable, with marquee routes told
apart from park trails.

**And a through-route in the overview wears its badge, from the registry where the
published sketch has no name (2026-09-11, [#1374](https://github.com/OurHike/OurHike/pull/1374)).**
`write_overview` has named the trails clearing `NAMED_TRAIL_THRESHOLD_MILES` since #1307,
with `through_route: true` beside the name, and `test_export_nearby_trails.py` pins it.
The copy in the bucket does not carry that yet: measured live on 2026-09-11, UA's
`network_overview.geojson` is **38 features and not one of them named** — `source`,
`blaze_color` and `trail_status` only — because the publish that would refresh it is held
back with `nearby_trails.geojson`, which `publish.py` gates on `reaches_hikers` and two
New Jersey sources have carried `false` since #1293. The visible cost was the maintainer's
own frame: the A.T. on its pill over the Hudson and the Long Path in aqua beside it
wearing nothing, because `map/trailsInView.ts` skips a feature with no name. So the client
falls back to `lib/trails.ts`'s name for a source the badge already marks
(`map/trailBadges.ts`'s `registryNameForSource`) — the same claim `BADGE_MARK_BY_SOURCE`
already makes about which registry trail a line is, and firing for those two sources
alone, so a park's folded haze stays unnamed and off the list. **Both halves stand**: the
fallback is what a hiker sees today, and the republish is what makes the data say it
itself.
**And the badge stops at the waypoint seam (2026-09-14).** The maintainer, reading the
built map: _"when a user zooms in close enough to see a POI, the trail pills (AT & LP)
should hide."_ `buildTrailBadgeLayer` now carries `maxzoom: POI_PIN_MIN_ZOOM` — the seam
constant itself, not a literal that agrees with it, for the same reason
`POI_DOT_MIN_ZOOM` is that constant: the corridor view has one seam for waypoints, and a
badge ceiling that drifted from it would put pills back onto a map that had just filled
with pins. The argument is [POI_VISIBILITY.md](POI_VISIBILITY.md)'s own: below the seam the
map is "a complete map of something else" and the badge is how a hiker tells which line is
which; above it the map has shelters, water and warnings on it, each a pin competing with
the pill for the same ground. maplibre reads `maxzoom` as exclusive, so the badge is gone
on the first frame a waypoint can draw rather than sharing that frame with it. The badge
still has **no floor** of its own — the line layers' floors are the badge's, the review of
#1374 — so this is a ceiling added, not a window narrowed at both ends.

The stretch model (CORRIDOR_VIEW's `named` basis) carries over unchanged — "Breakneck
Ridge loop" is a stretch with a citation like "Franconia Ridge" is.

## 9. What this needs from the offline unit

Not the decision — that is [#552](https://github.com/OurHike/OurHike/issues/552)'s — but
the requirement it must satisfy: **a download named "Harriman" contains every shipped
trail and every safety POI inside its boundary**, not just the chosen trail's. The
safety-always rule is a promise about the screen, and a unit cut trail-shaped would break
it exactly where trails cross. (The spike's scale numbers make this cheap: the two parks'
full trail geometry is 0.7 MB gzipped.)

**Half met since [#1082](https://github.com/OurHike/OurHike/issues/1082), and the half
matters.** [#950](https://github.com/OurHike/OurHike/issues/950) drew this map from a
network artifact `client/src/lib/nearbyTrailData.ts` fetched and did **not** store, so a
phone with no signal drew no nearby trails at all. That was a deliberate hold rather than
an oversight — what a download contains is #552's decision, and building a second store
beside `lib/trailData.ts`'s in advance of it would be a shape to unpick later. #1082 closed
the half that was a launch cost rather than a coverage decision: the last verified copy of
the **whole** artifact is now kept and served with or without signal, refreshed only when
the manifest's hash moves. So a phone that has once fetched and verified the network — an
online launch where the manifest answered, which is every ordinary one — draws every
nearby trail offline thereafter: a superset of any boundary, with no boundary machinery
to unpick. What
remains outstanding is the paragraph above as written: a **named** download whose contents
a hiker can reason about, the safety POIs inside it included, cut to #552's unit. The
cache is not that and does not claim to be — it appears in no download UI and answers no
question about what is on the phone.

**The number that decision has to weigh has moved, and it is the reason to take it.** The
whole exported network was 1.72 MB gzipped on 2026-08-24, when the export clipped every
organization's layer to a bounding box around New York City. The maintainer removed that
clip on 2026-08-25 and registered NYS DEC in the same change
([#1019](https://github.com/OurHike/OurHike/issues/1019)) — _"Include all of DEC, NYNJTC &
NYSP. Don't limit data from orgs based on geography"_ — and the artifact measured **7.34 MB
gzipped, 23.5 MB raw, 21,805 features** the same day. Since
[#1082](https://github.com/OurHike/OurHike/issues/1082) a phone pulls that once per
_publish_ rather than once per launch — the ordinary launch asks the manifest a ~KB
question and keeps the stored copy — but every phone still parses the whole state to draw
any of it. A per-region cut is the obvious answer and it is
[#552](https://github.com/OurHike/OurHike/issues/552)'s to make, not this doc's.

**The whole-file cache was withdrawn on 2026-09-07, and the reason is the number above
having moved again.** The artifact was promoted that day at 228,820,578 bytes raw — nationwide
USFS trails, [#1231](https://github.com/OurHike/OurHike/issues/1231) — and every phone that
fetched it whole crashed its map ([#1254 — A launch artifact the phone cannot hold is fetched, parsed and drawn anyway, and today's data made that a frozen first page and a crashed map](https://github.com/OurHike/OurHike/issues/1254)).
[#1257 — Deliver the network lines and the junction graph in pieces a phone can read by range, so no growth in the data can freeze or crash it](https://github.com/OurHike/OurHike/issues/1257)
changes the shape rather than the data: the same lines are cut into z9–z14 vector tiles
(`nearby_trails.pmtiles`, `export_nearby_trails.py`'s `write_tiles`) and the map reads them by
byte range as the camera asks, a few kilobytes a tile, whatever the archive weighs — the way
the hiking sheet has always been read. What that costs, stated: **a tile lives in the
browser's HTTP cache and nowhere else, so with no signal the map above the seam draws no
nearby trails.** The corridor-view sketch below the seam is still cached and still draws.
That is the state this section described before #1082 and the state #1254's budget had
already left every phone in; it is honest rather than good, and it is the paragraph above
as written: a **named** download of the network, cut to #552's unit, is now #1257's second
stage, on `cut_cells.py`'s per-family machinery, rather than a cache that quietly held the
whole state.

**Stage 2 landed the same day.** `cut_cells.py` cuts `nearby_trails.pmtiles` into
`nearby_trails_cell_<name>.pmtiles` as a third family (no shared context: z9 nationwide is
9,653,907 bytes for a zoom the sketch draws below and the cells draw above, so z9 rides in
the cells), `publish.py` ships the cells inside the lines' own `reaches_hikers` gate, and the
client's "take this stretch" tap takes the network cells under the hike with the basemap's
(`client/src/lib/coverageCells.ts`'s `NETWORK_CELLS`, priced as one decision by
`priceStretches`). `map/networkTiles.ts` asks a held cell before the bucket, so a phone that
took its stretch draws every organization's trail on it with no signal — which is this
section's promise as written, at #552's unit, for the first time. A phone holding the whole
hiking sheet is the one still outside it: the stretch card stands down for it, and nothing
else offers the network cells yet.

**Stage 3 (2026-09-08) cut the junction graph derived from these lines the same way** —
`cut_trail_graph.py`, `trail_graph_cells.json`, every edge filed whole into every cell within
the seam margin — but the graph's cells are not a download: the day-hike builder loads the
cells a hiker is planning in and keeps them per cell (`features/HIKE_PLANNING.md`, _The graph a
phone keeps is the cells it planned in_). The whole 78.6 MB `trail_graph.json` of 2026-09-07
stays in the bucket and no current client fetches it.

## 10. POI density, measured

Amenities-chosen-only was decided partly on an unmeasured fear: Harriman-scale POI
density. **Measured 2026-08-27 ([#936](https://github.com/OurHike/OurHike/issues/936)),
against OPRHP's live facilities layer — `pipeline/spike_oprhp_poi_density.py`, re-runnable.**
The layer still holds 8,823 points statewide, and the two parks hold **312** of them, every
row flagged `Public_ = Y`.

**The fear was right about amenities and empty about safety**, which is the opposite way
round from how it was carried:

| on one 390 × 700 phone screen at z12              | in the two parks | most in one screen |
| ------------------------------------------------- | ---------------- | ------------------ |
| water — the safety kind this layer could supply   | **0**            | **0**              |
| toilets — #936's wider reading of safety-relevant | 9                | 5                  |
| amenities OurHike has a pin for                   | 148              | **50**             |

Read the last row against [POI_VISIBILITY.md](POI_VISIBILITY.md)'s own table, which puts
**~16 pins down the column** at z12: relaxing the chosen-trail-only rule over Harriman
would ask a screen with room for sixteen to draw fifty. **So the amenity half of the split
now stands on evidence rather than on a worry** — this is the first number behind it, and
it supports the rule as shipped. The densest screen is centred near 41.2431, −74.1158, and
what fills it is unremarkable: 49 `Scenic View`, 36 `Group Camp`, 25 `Parking Area`, 11
`Lean-to` across Harriman.

**The safety half needs nothing.** OPRHP's facilities layer carries no `Drinking Fountain`
and no `Water Spigot` in either park — not few, none — so the always-draw rule costs this
layer nothing at all, and POI_VISIBILITY.md's dot rank is not needed to absorb it.

### The rule got an exception the same day, and it is bigger than the fear

**Everything above is about a layer OurHike did not publish. Hours later it published one**
— [#1097](https://github.com/OurHike/OurHike/issues/1097), acting on
[pipeline/POI_COVERAGE_SURVEY.md](../pipeline/POI_COVERAGE_SURVEY.md), ships **8,480 of
NYS DEC's and NYS OPRHP's waypoints** as `nearby_poi.geojson`: shelters, campsites,
privies, viewpoints, parking areas and trail bridges, statewide, with **no clip at all**.
Six of those types are amenities. So the chosen-trail-only rule this section had just
finished supporting now has a named exception, and pretending otherwise would leave the
strongest argument in this file pointing at a world that ended.

Measured the same way, by the same file (`spike_oprhp_poi_density.py --artifact`, so the
figures are comparable by construction rather than by assertion):

| densest z12 screen, 390 × 700 | every category on | default visibility |
| ----------------------------- | ----------------: | -----------------: |
| Harriman / Bear Mountain      |                64 |             **26** |
| Catskills                     |                34 |                 22 |
| Adirondacks                   |               114 |            **107** |

Against **~16 pins down the column**. The Adirondack figure is the one to look at and is
not Harriman's problem at all: 105 of those 107 are DEC primitive tent sites strung along
the Saranac lake shores, which no survey starting at the A.T. corridor would have
predicted.

**Two things stop this being as bad as the numbers read, and neither makes it fine.**
MapLibre culls rather than stacks (`icon-allow-overlap: false`), and since
[#597](https://github.com/OurHike/OurHike/issues/597) a culled waypoint draws as a dot
rather than vanishing — so the Adirondack screen is ~16 pins and ~91 dots, not 107 pins.
And four of the six types (resupply, crossing, viewpoint, parking) start hidden under
[#865](https://github.com/OurHike/OurHike/issues/865)'s default, which is what the second
column measures. What neither fixes is the count competing for the screen, which is what
this section was measuring when it concluded fifty was too many.

**The maintainer took this decision knowingly on 2026-08-27**, after being shown these
figures and the contradiction: ship, and record the collision here rather than quietly
widen the rule or quietly break it. Recorded, then, in the plainest form — **the amenity
half of #783's split is no longer true of every organization on the map.** It holds for
the A.T. corridor, where `export_poi.py` still clips amenities to it; it does not hold for
DEC and OPRHP, whose amenities ship statewide.

**What closed it**, and what it cost ([#1113](https://github.com/OurHike/OurHike/issues/1113)):
`export_nearby_poi.clip_to_network` clips the amenity types to `NETWORK_BUFFER_FEET`
around `nearby_trails.geojson`, exactly as §11 buffers water — the same 500 ft, one number
with one home, rather than a second radius here that could drift from it.

Measured 2026-09-04 through `spike_oprhp_poi_density.py --artifact` on both sides, so the
before and after are the same arithmetic:

| densest z12 screen, default visibility | published | clipped |
| -------------------------------------- | --------: | ------: |
| Harriman / Bear Mountain               |        26 |  **19** |
| Catskills                              |        22 |  **22** |
| **Adirondacks**                        |   **107** |  **35** |

**Targeted, which is the point.** The Adirondack screen falls by two thirds — those 105
tent sites sit along the Saranac lake shores and are reached by water rather than by trail
— while the Catskills does not move at all. 5,115 of 21,379 waypoints drop.

**And it does not reach POI_VISIBILITY.md's ~16.** Sweeping every window rather than the
three named regions, the worst screen as published is the Adirondacks at 106; after the
clip the worst is Allegany at 53, filled by OPRHP crossings, campsites and privies that
survive because they genuinely _are_ trail-adjacent. So the clip is a large improvement
and not a fix, and #1105's "fifty is too many" is still open for that screen — which is
worth writing down, because "clip to the ring" reads like an answer.

**`parking` and `trailhead` are exempt**, from the measurement rather than from taste. A
uniform ring drops 49% of DEC's parking areas and 12% of OPRHP's, the largest per-type
losses in the clip; exempting them changes _no_ figure in the table above, because both
start hidden under #865's default, and keeps 2,493 more waypoints. A hiker who turns
parking on pays for it and is a hiker asking for parking. #981 is the supporting argument:
a lot is "an annotation on a start, never a precondition", so the type whose whole purpose
is to sit off the tread is the wrong one to measure against tread.

### What this does not measure, and it is the bigger half

**This answers the question §10 asked, which was about OPRHP's facilities layer. It is not
the density of safety pins over Harriman.** Since §11 widened the water gate, a nearby
trail's water comes from NHD and OSM rather than from a park's own facilities inventory —
so the number that decides whether the always-draw rule crowds a screen is a count of NHD
crossings and OSM water over 316 miles of Harriman trails, which nobody has run.
[#1028](https://github.com/OurHike/OurHike/issues/1028) is the nearest thing to a hint at
its scale (3,370 unnamed `nhd_crossing` rows in the ledger) and is about a different
question. **That count is the real follow-up**, and it is worth being explicit that the
zero above does not stand in for it: this layer contributing no water is a fact about
OPRHP's inventory, not a fact about how much water Harriman has.

### The ring got a second exception, and this one is about ground rather than type

**A city park is not a corridor, and the ring asks a corridor's question**
([#1493](https://github.com/OurHike/OurHike/issues/1493)). "How far is this from a published
line" is the right test along 2,190 miles of trail and the wrong one inside a park, where the
park *is* the destination and the path through it is incidental.

Measured 2026-09-15 against the UA release the day [#1474](https://github.com/OurHike/OurHike/issues/1474)
published, with the 500 ft ring rebuilt in EPSG:5070 from the 698 published lines around
Central Park — the reconstruction reproduces the published clip exactly, so these are the real
gate rather than an estimate of it:

| Central Park                 | source | published |
| ---------------------------- | -----: | --------: |
| NYC Parks drinking fountains |    180 |    **31** |
| NYC public restrooms         |     41 |     **8** |

**182 of 221 — 82% — and Central Park is the favourable case**, because NYC Parks actually
mapped its paths. The losses fall on the Great Lawn, the Reservoir's outer edge, and
playgrounds set back from a drive.

**So a POI source may name a boundary layer** in `boundary_source`, and a point inside one of
that layer's polygons is kept however far it sits from a line. This is the structure #1311
already built — `keep_within_corridor` asks *"inside the polygon OR within `NETWORK_BUFFER_FEET`
of a line"* — given a second kind of polygon rather than a new concept. NYC Parks Properties
(`enfh-gkve`, 2,059 boundaries) is the first, and it carries `gispropnum`, the same property
number the fountains already do.

**It is an `OR`, never a replacement**: 34 fountains ship today from *outside* every boundary,
near a line and off a property, and a rule that only asked the boundary question would drop
them.

| what the boundary admits  |   raw | ships today | inside a boundary |
| ------------------------- | ----: | ----------: | ----------------: |
| fountains                 | 3,195 |         982 |  **3,114 (97.5%)** |
| restrooms                 |   975 |         249 |    **717 (73.5%)** |

**Those two figures do different work, and saying so is the point.** For restrooms the boundary
genuinely discriminates — it drops 258 libraries, privately owned public spaces and transit
entries. For fountains it is close to a blanket exemption, because NYC Parks' fountains are in
NYC parks. Calling that anything other than what it is would be dressing it up.

**What this costs on screen, recorded rather than resolved.** Measured with
`spike_oprhp_poi_density.py`'s own method over the published artifact, filtered to
`DEFAULT_SHOWN_TYPES`:

| worst z12 screen, default visibility | pins | where                        |
| ------------------------------------ | ---: | ---------------------------- |
| before the NYC POI layers            |   55 | −78.845, 42.003 (Allegany)   |
| as #1474 published                   |  233 | −74.024, 40.649 (Brooklyn)   |
| under this rule                      |  656 | −74.009, 40.649 (Brooklyn)   |

The 233-pin window holds 190 fountains and 43 restrooms and nothing else. **The maintainer's
call of 2026-09-15, with these numbers in front of them, is that this is normal for New York
City** — §10's ~16-pin target and [#1105](https://github.com/OurHike/OurHike/issues/1105)'s
"fifty is too many" were both derived for hiking zooms in wilderness, not for a borough with a
fountain every few blocks. Density travels separately, and POI_SITES.md's co-location
clustering is the mechanism that would actually answer it.

## 11. Water on every trail on screen, and what it is measured against

The decisions table promises safety POIs on _every_ trail on screen, and §9 calls that
"a promise about the screen". Closures kept it from the start (`apply_area_closures`,
#964). **Water did not, for as long as this network has been drawn**, and the reason was
that all three stages of the water build took the A.T. as their subject — the reach gate
measured against ATC's four layers, crossings intersected ATC's centerline alone, and the
POI clip was the 30-mile buffer of that same centerline. An OSM spring fifty feet off a
Harriman trail was fetched, clipped into the corridor, and then refused for being far from
the A.T. Four organizations shipped that way.
[#1016](https://github.com/OurHike/OurHike/issues/1016) closed that. All three stages now
read `nearby_trails.geojson`:

- **The reach gate's union gained a fourth member** — this artifact, beside ATC's
  centerline, side trails, shelters and campsites. The radius did not move; only what it
  is measured from. A point records which organization's trail it passed on.
- **Crossings are computed against a `routes` table** that is the centerline plus these
  lines, so a stream crossing a Long Path section is a crossing.
- **The corridor is widened** by `NETWORK_BUFFER_FEET` around these lines — 500 ft, not
  thirty miles, because this table's decisions give the network no town-scale context:
  amenity POIs stay chosen-trail-only, and the ring exists only so the clip can never be
  what decides whether a safety POI reaches a hiker.

**One artifact, so this needs no code per organization.** Registering a Catskills or NJ
layer in `sources.json` brings its water with it on the next run, the shape #1011 gave the
DEM index, and `pipeline/tests/test_water_covers_trail_sources.py` fails if a registered
trail-line source ever falls out of that again.

**But only once that organization's data reaches hikers.** The artifact holds every
_exported_ source, held back or not, so a reviewer can look at the map before a licence
answer arrives — and `reaches_hikers: false` is the state every organization is registered
in. Both water builds filter on that same field, so a review-only steward's lines gate no
published water pin: deriving one would be that organization's data reaching a hiker, drawn
over ground where the app shows no trail, since `publish.py` holds the whole artifact back
when any source in it is held back.

### A network POI carries no A.T. mile, and that is deliberate

`export_poi.attach_miles` projects onto the nearest point of the A.T. and always succeeds —
there is no distance at which it declines — so widening the water build put real POIs
miles off the A.T. in front of a function that would hand each one a perfectly formed
mile. That number is not decorative: `client/src/lib/dayPlanner.ts` treats every POI
carrying a `mile` as a candidate stop between two points of an A.T. day, and `cascade.ts`
does the same. A hiker planning their water around a spring that is a four-mile bushwhack
off their route is the confidently-wrong answer FEATURES.md ranks as worse than an honest
unknown.

So a POI whose only walk is off the A.T. is published **without** a mile. Every client
consumer already skips an absent one. What it costs is a place in an A.T. itinerary, which
is a place these pins should never have had; what a network POI still needs is its own way
to say how far along _its_ trail it sits, which is
[#953](https://github.com/OurHike/OurHike/issues/953)'s question and not answered here.

### What is not measured

**No count in this section comes from a run over real layers.** How many water points the
widened gate admits, how many crossings 316 miles of Harriman trails add, and what that
does to §10's density question are all unmeasured — the change was written where no
fetched layers exist. Every stage prints its own per-source counts, so the first real
publish answers all three in its log rather than in this document. §10's subject is
therefore live now: the safety-relevant subset it says nobody has counted is no longer
empty by construction, and counting it is the follow-up it always asked for.

## Open questions (for the maintainer, gathered)

- **`NEARBY_TRAIL_OPACITY = 0.45`** is `@unvalidated` — settle it outdoors with #105's
  pass, on both sheets.
- **Junction-switch revisit trigger** — if #106's field testing shows hikers expecting the
  sheet to switch, §2 re-argues with that evidence.
- **The palette docket** — which of Pink / Light Blue / Brown / Black / Lime are real
  distinct paints deserving admission, decided at the mapping-table review with the counts
  in §4.
