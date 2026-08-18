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
- **What the legend says**: the blaze rows (WIREFRAMES.md §2) gain one sentence of state —
  "Other trails are dimmed; the trail you chose is full-strength" — rather than a new
  control. Nothing here is hideable: nearby trails are context, and context that can be
  switched off is a mode nobody remembers being in.
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
The stretch model (CORRIDOR_VIEW's `named` basis) carries over unchanged — "Breakneck
Ridge loop" is a stretch with a citation like "Franconia Ridge" is.

## 9. What this needs from the offline unit

Not the decision — that is [#552](https://github.com/OurHike/OurHike/issues/552)'s — but
the requirement it must satisfy: **a download named "Harriman" contains every shipped
trail and every safety POI inside its boundary**, not just the chosen trail's. The
safety-always rule is a promise about the screen, and a unit cut trail-shaped would break
it exactly where trails cross. (The spike's scale numbers make this cheap: the two parks'
full trail geometry is 0.7 MB gzipped.)

## 10. POI density, honestly

Amenities-chosen-only was decided partly on an unmeasured fear: Harriman-scale POI density.
It is still unmeasured — OPRHP's facilities layer holds 8,823 points statewide and nobody
has counted the two parks' safety-relevant subset at z12. If safety-only still overwhelms
the screen, the dot rank (POI_VISIBILITY.md) absorbs it before anything new is invented.
Measuring this is the registration follow-up's job, not this doc's guess.

## Open questions (for the maintainer, gathered)

- **`NEARBY_TRAIL_OPACITY = 0.45`** is `@unvalidated` — settle it outdoors with #105's
  pass, on both sheets.
- **Junction-switch revisit trigger** — if #106's field testing shows hikers expecting the
  sheet to switch, §2 re-argues with that evidence.
- **The palette docket** — which of Pink / Light Blue / Brown / Black / Lime are real
  distinct paints deserving admission, decided at the mapping-table review with the counts
  in §4.
