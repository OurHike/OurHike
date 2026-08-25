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
*unstated* on the strength of a truncated read; read whole they **permit reuse, require
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

| decision | choice |
|---|---|
| The map's subject | The centerline is always the **chosen trail**; one trail at a time |
| Other trails | Visible, de-emphasized — **ghosted** (option B below) |
| Tapping a nearby trail | **View-only sheet**; switching stays in the picker |
| Amenity POIs | Chosen trail only |
| Safety POIs (water, closures, serious warnings) | Drawn for **every** trail on screen |
| POIs across orgs | Deduped into **shared records**; the **selected org wins the display** |
| Lines across orgs | The **route owner's line** always renders; landowner copies suppressed |
| Long-term closed trails | Ship, drawn with **the closure treatment** (option A below) |
| Uses | **Hiking only** — bike/horse/XC/snowmobile stay unshipped |
| Blazes | **The paint's real color renders**, palette extended under governance |

*Water, one of the three safety kinds in that row, reached only the A.T. until #1016 —
§11 has what it is measured against now, and why a network POI carries no A.T. mile.*

## 1. The chosen trail and the others — ghosting, specified

WIREFRAMES.md §3 already gives this map two channels: **hue says which blaze, width says
which line the map is about** (through-route 4.5 px, side trails 2.5 px, through-route
sorted last so nothing covers it). Nearby trails take the side-trail width and keep their
real blaze hue — and add the one new value this feature introduces:

- **Nearby trails render at reduced opacity.** `NEARBY_TRAIL_OPACITY = 0.45` —
  `@unvalidated`: picked so the hue stays *identifiable* while the chosen trail is
  *unmistakable*, from the drawn comparison rather than from a measurement. What would
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
  remembers being in. *(Amended 2026-08-25: this used to read "the blaze rows
  (WIREFRAMES.md §2) gain one sentence of state". Those rows were removed as clutter at
  the maintainer's request, and the sentence outlived them — it now sits directly above
  the pin grid, and is the only thing the legend still says about the trail lines.)*
- **Not a contradiction of §3, an extension.** Every line stays solid; the no-dash rule
  holds; the through-route is still the widest and last-drawn. Ghosting adds a third
  channel (opacity) for a distinction the AT-only map never had to draw.

The tradeoff this choice accepts, stated so nobody rediscovers it: blaze identity weakens
on exactly the trails a hiker might be thinking of taking. Two things recover it — the hue
is dimmed, never removed (the maintainer's rule: *"the color of the trail blazes should be
the color on the map"*), and the tap sheet below shows the blaze at full strength.

## 2. Tapping a nearby trail — a sheet that informs and does not switch

Tapping any line already opens a sheet naming the blaze and its source (WIREFRAMES.md §3;
[#134](https://github.com/OurHike/OurHike/issues/134)'s line-detail sheet is the pattern).
A nearby trail's sheet carries: the name, the blaze chip at full color, the length and the
park, the provenance line (§6 below) — **and no switch action**. Switching trails stays in
the picker ([#558 — Let a hiker take the stretch they are walking, without picking it off a
list](https://github.com/OurHike/OurHike/issues/558) is that flow's home).

Why, argued: making a nearby trail the chosen one swaps the mile frame, the elevation
ribbon, the Naismith numbers and the amenity POI set **at once** — the whole context a hiker
is navigating by. At 263 junctions per park, a one-tap switch on the map is an accidental
context loss waiting to happen, and an accidental one in exactly the moment (a junction,
deciding) when a wrong screen costs the most. The cost accepted: the on-the-ground moment —
standing at a junction wanting to take the other trail — is served by two screens instead
of one tap. **Revisit trigger, named**: if field testing (#106) shows hikers at junctions
reaching for the sheet expecting a switch, this decision earns a re-argument with that
evidence; until then it stands.

## 3. Closed trails — the closure vocabulary, reused

OPRHP marks trails `Closed` long-term (125 statewide) — distinct from the live
temporary-closures layer. They ship, drawn with **the closure treatment**: the red barred
band over its casing, the map's one permitted dashed rhythm (WIREFRAMES.md §3's stated
exception, §7's spec). One vocabulary for "do not walk this", which is the argument that
won: a hiker learns one mark.

**Built 2026-08-24 ([#964](https://github.com/OurHike/OurHike/issues/964)), and it turned out to be two feeds rather than one.** OPRHP's long-term `Closed` status ships on the line as this section describes. Their *temporary* closures do not work that way at all: they are polygons over ground, with the reason as prose and no dates, and two of the four do not touch the A.T. — so they are derived onto the trail lines by intersection, split at the boundary, and carry `closure_kind: "area"` against the status feed's `"long_term"`. That property exists because this paragraph asks the sheet to say different things about the two, and `trail_status` cannot tell them apart. **The sheet itself is still not built.**

What keeps the two kinds of closed apart is the **sheet, not the line**: a long-term closed
trail's sheet says "Closed by NYS OPRHP" with the layer's own edit date; a temporary
closure's says its reason and reporting date as today (ClosureSheet). `Proposed` (19) and
blank/Unknown (24) segments do not ship at all — a proposed trail is not ground, and an
unknown status drawn as walkable is a guess (omit rather than guess).

## 4. Blazes beyond seven — the palette grows, under governance

The maintainer's decision, verbatim: *"we will need to bring in more colors for the blazes.
Long [Path] is indeed aqua. Some way to stop sprawl is needed, but the color of the trail
blazes should be the color on the map."*

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
  OPRHP's AT copy agrees with ATC's line at 1.8 m median *and* diverges past 150 m on 14%
  of the in-park length, peaking at 1.24 km — an old alignment, rendered, would be a wrong
  map. The agreeing case (Long Path: 3.3 m median, 97% within 150 m) shows the dedupe is
  tractable.
- **POIs: deduped into shared cross-org records; the selected org wins the display.**
  POI_DEDUPLICATION.md's proximity-proposes-name-decides extends across orgs; precedence
  gains a second axis — the org whose route the hiker chose supplies the card's voice.
  Two edges closed here rather than inherited silently: when the selected org has no value
  for a field, the other org's value shows *with its own attribution* (omit-rather-than-guess
  governs unknowns, not known-by-someone-else); and a safety-relevant fact only one org
  carries **never loses to precedence** — safety completeness outranks display preference.
- **What "the org" means is deliberately not settled here.** The AT in NY has a joint
  superowner, per-section landowners with final say, and per-section maintainers —
  [#780 — Research route ownership](https://github.com/OurHike/OurHike/issues/780) owns
  that lattice, and this doc's "selected org" resolves against whatever #780 lands.

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

## 7. Wrong-way in a network

`trailPosition.ts` and `wrongWay.ts` infer "lost" from distance-to-*the*-centerline. The
spike's number says what that inference does in Harriman: half the AT is within 150 m of a
different marked trail, so "off the chosen trail" usually means "on another one" — not
lost, and alerting on it is the false positive `wrongWay.test.ts` exists to prevent.

The answer for now, honoring [#93](https://github.com/OurHike/OurHike/issues/93): **the
wrong-way alert stays scoped to the AT corridor's isolation profile and does not arm on
network ground** until its thresholds are field-validated there. The network-aware design,
sketched for when that work happens: a position within threshold of *any* shipped trail
line is not "off trail" — the alert's question becomes "off the network", and "off the
chosen trail but on the Ramapo-Dunderberg" is a banner-grade note at most, never the app's
one notification.

## 8. The seam, and what sits below it in a park

POI_VISIBILITY.md owns z≥9; CORRIDOR_VIEW.md owns z0–8 with club sections as its subject.
Forty short trails are not a below-seam subject — at z7 Harriman is one green shape. The
extension, not a fork: **below the seam, the network ground's subject is the park** — the
unit polygons already registered (`oprhp_park_polygons`, 858 statewide) with the marquee
routes (AT, Long Path) still drawn through them, exactly as club sections tile the AT.
Tapping a park below the seam says who runs it and what the big routes through it are.

**Half built (2026-08-24, #950).** The half that shipped is the negative one: the
network draws only at z≥9, so 3,663 lines cannot smear across a corridor view whose
subject is the thirty club sections. The half that did not is everything positive this
section describes — park polygons are fetched but not exported, nothing distinguishes a
marquee route from a short park trail, and there is no below-seam park tap. The
consequence to know about is that **the Long Path is absent below z9 rather than drawn
through its parks**, which is not what the paragraph above asks for. Drawn at the wrong
prominence was judged worse than absent; a reviewer may disagree, and
[#557 — Draw the map from several coverage units, and say plainly where they end](https://github.com/OurHike/OurHike/issues/557)
is where the positive half belongs.
The stretch model (CORRIDOR_VIEW's `named` basis) carries over unchanged — "Breakneck
Ridge loop" is a stretch with a citation like "Franconia Ridge" is.

## 9. What this needs from the offline unit

Not the decision — that is [#552](https://github.com/OurHike/OurHike/issues/552)'s — but
the requirement it must satisfy: **a download named "Harriman" contains every shipped
trail and every safety POI inside its boundary**, not just the chosen trail's. The
safety-always rule is a promise about the screen, and a unit cut trail-shaped would break
it exactly where trails cross. (The spike's scale numbers make this cheap: the two parks'
full trail geometry is 0.7 MB gzipped.)

**Not met by what shipped, and this is the gap to know about.**
[#950](https://github.com/OurHike/OurHike/issues/950) drew this map from a network artifact
`client/src/lib/nearbyTrailData.ts` fetches and does **not** store, so a phone with no
signal draws no nearby trails at all. That was a deliberate hold rather than an oversight —
what a download contains is #552's decision, and building a second store beside
`lib/trailData.ts`'s in advance of it would be a shape to unpick later — but the paragraph
above is a requirement this build does not satisfy, and it should be read as outstanding
rather than as described-and-done. The whole exported network is 1.72 MB gzipped
(measured 2026-08-24), which is the number that decision has to weigh.

## 10. POI density, honestly

Amenities-chosen-only was decided partly on an unmeasured fear: Harriman-scale POI density.
It is still unmeasured — OPRHP's facilities layer holds 8,823 points statewide and nobody
has counted the two parks' safety-relevant subset at z12. If safety-only still overwhelms
the screen, the dot rank (POI_VISIBILITY.md) absorbs it before anything new is invented.
Measuring this is the registration follow-up's job, not this doc's guess.

## 11. Water on every trail on screen, and what it is measured against

The decisions table promises safety POIs on *every* trail on screen, and §9 calls that
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
*exported* source, held back or not, so a reviewer can look at the map before a licence
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
to say how far along *its* trail it sits, which is
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
