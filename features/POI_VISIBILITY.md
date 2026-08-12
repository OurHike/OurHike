# OurHike — Waypoint Visibility (Feature Design Draft v1)

Companion to [MAP_OPTIONS.md](MAP_OPTIONS.md) (which owns the legend and the rest of the map
chrome), [UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md) (which owns *why* `waypoint_types_shown`
exists), [../WIREFRAMES.md](../WIREFRAMES.md) §1.4 and §2, and
[../OurHikeValues.md](../OurHikeValues.md) #4.

The map draws fewer waypoints than it holds, at every zoom, and says nothing about the
difference. A hiker looking at a ridge with two shelters and a spring on it can be shown one
pin, or none, and there is nothing on the screen — not a count, not a caveat, not a control —
that distinguishes that from a ridge with nothing on it.

**This doc owns one question: what a hiker is told and given when the map cannot draw every
waypoint.** It does not own the pin artwork ([`client/src/map/poiIcons.ts`](../client/src/map/poiIcons.ts)),
the collision ordering ([`client/src/map/poiLayers.ts`](../client/src/map/poiLayers.ts)'s
`POI_PRIORITY`, which this doc treats as correct and builds on), or which waypoints the
pipeline publishes.

---

## The three ways a waypoint disappears, and only one of them is honest

They need separating before anything is designed, because they have different causes,
different fixes, and only one of them is currently visible to a hiker.

### 1. The hard floor — nothing at all below zoom 9

`POI_MIN_ZOOM = 9` in [`poiLayers.ts`](../client/src/map/poiLayers.ts), set both as the
layer's `minzoom` and as the low anchor of `POI_ICON_SIZE_EXPRESSION`. Below it there are no
pins whatsoever. The app's opening view is the whole corridor — `CORRIDOR_BOUNDS`, somewhere
around z4–z5 on a phone — so **the first map a hiker ever sees has zero waypoints on it and no
explanation.**

The constant's own docstring makes the argument for it, and the argument is good: *"Eight
hundred POIs on it is not a map, it is a texture."* Two things about that sentence are worth
recording. It was written on 2026-08-07. Two days later
[fb73359](https://github.com/OurHike/OurHike/commit/fb73359) added vistas, parking areas and
privies — "roughly doubling the 2,532 POIs already shipping." **The floor's justification got
stronger, not weaker, and the floor itself is not the defect.** The defect is that it is
silent.

### 2. The collision drop — most of them, most of the time, above zoom 9

`icon-allow-overlap: false` with `icon-padding: 2`. MapLibre's collision engine places pins in
`symbol-sort-key` order and discards every one that would overlap something already placed.
`POI_PRIORITY` decides *who* survives, and decides it well — water first, vistas last, for
reasons the file argues at length.

Nothing decides, or reports, that a loser existed. This is the big one, and it is the one that
can cost somebody water.

### 3. The type filter — deliberate, and the only one a hiker can see

`attachHiddenPoiTypes` applies the legend's hide toggles as a layer filter. This is the
honest case: a hiker turned it off, the legend row still shows the count with a "Show" control
beside it, and nothing is claimed. It is also the *only* control that exists, it is ephemeral
(`useState` in [`App.tsx`](../client/src/App.tsx), lost on reload), and it can only be reached
for a type that has points inside the current viewport.

---

## How much is actually being dropped

| input | value | source |
|---|---|---|
| corridor length | 2,197 mi | [../WIREFRAMES.md](../WIREFRAMES.md) |
| waypoints published | **2,778** | measured against the live ATC FeatureServer and opentrail.org, 2026-08-12 ([POI_SITES.md](POI_SITES.md)) |
| of which vistas | 1,194 in corridor, of 1,223 | [../pipeline/README.md](../pipeline/README.md) |
| pin size at z9 | 38 px × 0.6 = 23 px, +2 px padding | `POI_PIN_SIZE`, `POI_ICON_SIZE_EXPRESSION`, `icon-padding` |

**Corrected 2026-08-12.** This table said ~4,553, reasoned from fb73359's commit message
rather than from a corridor-clipped count, and [POI_SITES.md](POI_SITES.md) measured 2,778 four
minutes after this doc landed. The measurement is right and the reasoning was sloppy in a way
that was avoidable from the same desk: POI_PHOTOS.md's *"all 817 corridor POIs"* plus the 1,988
corridor-clipped facility features is 2,805, which is the measurement, near enough. Everything
derived below moved with it.

### Across a viewport, which is what this doc owns

At z9 and 40°N, one CSS pixel is `40,075,017 × cos(40°) / (512 × 2⁹)` ≈ **117 m**. A 390 × 700
px map area is therefore about 28 × 51 miles of ground — and because the trail meanders inside
that box, something like 55–70 *trail* miles. At 2,778 over 2,197 miles — **1.26 waypoints per
mile** — that is **70–90 waypoints inside the viewport**.

A 700 px column of screen divided by ~25 px of pin-plus-padding holds **about 26 pins** where
the trail runs straight down it, somewhat more where it wanders sideways.

So at the very zoom where pins first appear at all, the map is drawing on the order of
**26 of 70–90** — and the number it reports is zero. Below z9 the ratio is not "worse", it is
categorical: 2,778 held, 0 drawn, nothing said.

### At one place, which POI_SITES.md owns — and it is the bigger half

The open question this section used to carry — *nobody has counted* — has been answered, by
[POI_SITES.md](POI_SITES.md), which simulates MapLibre's placement over the whole corridor.
**The loss is not uniform, and the shape of it is not what the arithmetic above predicts:**

| zoom | water | shelter | campsite | parking | privy | viewpoint |
|---|---|---|---|---|---|---|
| 12 | 85% | 82% | 21% | 67% | **1%** | 43% |
| 14 | 95% | 91% | 31% | 81% | **3%** | 75% |
| 16 | 98% | 96% | 61% | 92% | 50% | 90% |

Two things follow, and both are load-bearing for everything below.

**`POI_PRIORITY` is working.** At the zooms an offline hiker actually has —
`BASEMAP_MAX_ZOOM` is 14 — water and shelters place at 91–95%. The categories being destroyed
are the ones the ordering deliberately ranks last, which is the ordering doing its job rather
than failing at it.

**The dominant cause at those zooms is co-location, not viewport density.** 37% of every
published waypoint sits within 60 m of another; a privy sits a median 42 m from its shelter and
therefore cannot be drawn beside it until z16. That is a different problem with a different fix
— model the place, draw one pin, put the parts on the card — and it is
[POI_SITES.md](POI_SITES.md)'s, not this doc's.

**This doc's problem is what is left after that fix**, and it does not go away: a corridor view
holding 70–90 waypoints on a screen with room for 26 is a density problem no grouping rule
touches, and the silence about it is the same silence either way. The two are complementary,
and neither is a reason to defer the other.

---

## The principle this design turns on

**A sampled category is a claim; a count is a fact.**

Twenty-six pins at z9 is not "some of the waypoints". A hiker reads pins the way a paper map is
read — *these are the springs on this stretch* — and twenty-six arbitrary survivors of a
geometric collision test say exactly that, falsely. The absence of a pin is the strongest
statement this map makes about a place, and right now it is unsigned.

That gives the design its shape, and it is the same shape the rest of this app already has —
`StatusStrip`'s `Zoomed out past your download` (#216), the credit strip that names only the
sheets actually on screen, `positionLine.ts`'s eight distinct reasons for a missing mile:

- **Never drop a waypoint silently.** If the map cannot draw it, something on the screen says
  so and says how many.
- **Where a category cannot be drawn substantially completely, prefer the count to the
  sample.** 142 water sources and 1,223 vistas cross that line at very different zooms, so this
  is a per-category judgement, not one threshold.
- **Spend the budget on what matters first, and let the hiker re-spend it.** The screen holds a
  fixed number of pins. Which ones is currently decided entirely by `POI_PRIORITY` and
  geometry; a hiker who never wants to see a privy should be able to give those slots back to
  water.

"Make all POIs visible" is worth stating plainly as impossible in the literal form: 2,778 pins
needing 25 px of clearance each want about 1.7 million px² of exclusion area, and a 390 × 700
phone screen has 273,000 — six times short, before a single pin is placed badly. What is
achievable is that **nothing is ever hidden without being counted, and the hiker chooses what
occupies the space.** Everything below serves that.

---

## The options

Five were considered. Two are recommended for v1, one is recommended as the control story, and
two are written up with the reasons they are not being built yet, so the next person does not
re-derive them.

### Option 1 — Say what is hidden *(recommended, first)*

Nothing about what is drawn changes. What changes is that the map stops being silent.

The mechanism already exists on both sides and has never been connected. The legend knows what
is *present*: `computeLegendContents(bbox, points)` in
[`legendContents.ts`](../client/src/lib/legendContents.ts) counts every waypoint in the
viewport rectangle. The map knows what is *drawn*: MapLibre's own `queryRenderedFeatures`
excludes, in its documented words, *"symbol features that have been hidden due to text or icon
collision"* (verified against `maplibre-gl` 6.0.0's `.d.ts`, not assumed). **Two numbers, both
already computable, never compared** — precisely the shape of #216, where the pipeline exported
from z6, the app opened at z4, and nothing anywhere compared the two.

What a hiker sees:

- **In the legend**, where a row's counts differ: `Water · 14 · 4 shown`. The legend's whole
  promise is "what am I looking at right now," and it has been quietly answering a different
  question — what is inside this rectangle — since the day collision culling arrived.
- **A single line at the head of the legend** when anything is dropped: *"38 of 112 waypoints
  fit at this zoom. Zoom in to see the rest."*
- **Below the floor**, the honest sentence instead of an empty panel: *"Waypoints appear as you
  zoom in — 312 on this stretch."* Today the legend renders `Nothing on this part of the map
  yet — pan or zoom out to see more`, which at the opening view is false in both halves.
- **On the map itself**, a small count chip, so this is answerable without opening the legend.
  The status strip is the wrong home: it is a row of narrow flags about connectivity, GPS and
  data age, and a number that changes on every pinch does not belong beside them.

Cost: low. Confined to `Legend.tsx`, `legendContents.ts`, a probe in the map layer and the
wiring in `App.tsx`. No change to the collision ordering, so no regression risk to the one
decision this file already got right. **This is the option that most directly answers "better
callout to what is being hidden vs. what is shown," and nothing else here should land before
it** — every other option changes what is drawn, and changing what is drawn while the map is
still silent about drops just moves the lie.

One caveat worth designing around rather than discovering: `queryRenderedFeatures` reflects the
*last rendered frame*, so the count has to be recomputed on `idle` rather than `move`, and it
will lag a fling by a frame. That is acceptable for a count and is not acceptable for anything
a hiker acts on, which is the reason this option stops at counting.

### Option 2 — Admit categories by priority instead of all at once *(recommended, second)*

Replace the single hard floor with a per-category one, ordered by the priority list that
already exists:

| from zoom | admitted |
|---|---|
| z7 | water, shelter |
| z8 | campsite, resupply |
| z10 | parking, privy, crossing |
| z11 | viewpoint |

At z7 a hiker sees springs and shelters — sparse enough to place, and exactly the categories
worth crossing a state line for — instead of nothing at all. The map fills in as they zoom, and
the *first* thing to appear is the thing they most need rather than an arbitrary all-or-nothing
threshold two zoom levels further in.

This is the grain of the existing design rather than a new idea in it: `POI_PRIORITY` already
says water outranks vistas when they collide, and this says the same thing about when they
appear. It is one expression, one layer, no new source, and no change to the tap path.

**Two things about it are load-bearing and easy to get wrong.**

The first is a real MapLibre constraint, checked in the style-spec source rather than assumed:
`["zoom"]` *"may only be used as input to a top-level `step` or `interpolate` expression"*, and
`findZoomCurve` recurses only through `let` and `coalesce`. So the tiering cannot be `["all",
<hidden-types filter>, ["step", ["zoom"], …]]`. The `step` has to be the outermost expression,
with the hide filter repeated inside each branch. Discovering that from a CI failure costs a
full round trip; it is written here instead.

The second is the honest limit: **this option does not make a low-zoom map truthful, and must
not be mistaken for doing so.** The corridor carries 142 water sources; a z7 view holds a large
share of the trail on a screen with room for ~26 pins, so what appears is still a sample, still
collision-ordered, still a claim. Option 2 makes the sample *better chosen*; only Option 1 makes
it *labelled*. They ship together or Option 2 makes things worse, by putting confident-looking
springs on a corridor view that previously admitted it was showing nothing.

The zoom tiers in the table are also the part of this doc most exposed to
[POI_SITES.md](POI_SITES.md)'s measurement, and they have not been re-derived against it. That
table stops at z12; these tiers live at z7–z11, where nothing has been simulated. **The
simulation method now exists, which is the change** — these four numbers should be produced by
it rather than argued into place.

Note also that Option 2 is very nearly free in a cruder form — lowering `POI_MIN_ZOOM` from 9
to 7 would let `symbol-sort-key` produce a roughly water-first result on its own, since the
collision engine places in sort-key order. That was considered and rejected: it makes the
tiering an emergent property of a sort that exists for a different reason, so the next person
to reorder `POI_PRIORITY` for a collision reason would silently change which categories exist
at which zoom. An explicit table is worth its expression.

### Option 3 — Control that persists, and a way to see one category alone *(recommended, third)*

The user-facing half, and the one the preferences model has been ready for the longest.

`waypoint_types_shown` is declared in
[`client/src/lib/userPreferences.ts`](../client/src/lib/userPreferences.ts), in
[`backend/app/schemas/preferences.py`](../backend/app/schemas/preferences.py), in
[IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)'s canonical model, and is **read by
nothing.** The legend's toggles write to a `useState` set instead. Three consequences:

- Hiding privies does not survive a reload, and never reaches an account.
- A type can only be toggled while it has points in the viewport, because the legend's rows are
  derived per-viewport by design.
- WIREFRAMES.md §2's *"Full 10-category list lives in Settings, not here"* has no Settings
  screen to live on.

What ships:

- **The legend's toggles write `waypoint_types_shown`**, through the same `updatePreferences`
  path every other map preference uses. The stored key is *shown*, not *hidden*, which is the
  right way round for a list that grows: a category added by a later release is visible by
  default rather than invisible to everyone who ever opened this screen. `[]` keeps meaning
  "all", exactly as it does today.
- **A full category list in Settings**, beside the detail picker, which is where the wireframe
  already put it.
- **"Only this" from a legend row** — one tap to show a single category. At a crowded zoom this
  is the difference between four water pins drawn and forty, and it answers *where is the next
  water* in two taps rather than by zooming in and panning along the trail.

The last point is what makes the control worth having rather than tidy: **hiding a category
hands its collision budget to the ones left.** With Option 1 shipped, that is visible as it
happens — turn off vistas and the legend's `4 shown` becomes `11 shown`. Control that visibly
buys something gets used; a checklist of categories does not.

Safety rule, unchanged and inherited: closures and serious warnings have no hide affordance
anywhere, and the way that rule is kept is that the affordance is never built
([HIKER_SAFETY.md](HIKER_SAFETY.md), [MAP_OPTIONS.md](MAP_OPTIONS.md) §4). `NEVER_HIDEABLE` in
`legendContents.ts` is the existing guard and stays the only one.

### Option 4 — Cluster bubbles on the map *(considered, not recommended for v1)*

MapLibre's GeoJSON source clusters natively — `cluster`, `clusterRadius`, `clusterMaxZoom`,
`clusterProperties` — so the low-zoom map could carry count bubbles that expand on tap. This is
the conventional answer and it is genuinely tempting: it makes density visible, it gives a way
to *reach* what is hidden rather than only knowing it exists, and `clusterProperties` can
accumulate a per-cluster minimum of `POI_PRIORITY`, which would let a cluster containing water
render as a droplet with a count badge rather than as an anonymous grey blob. That refinement
matters — replacing a spring with a numbered circle is a real regression, and priority-styled
clusters are the version that is not.

It is not recommended for v1 for three reasons, in increasing order of weight:

1. **It fights the file's own central decision.** `poiLayers.ts` opens with an argument for one
   layer and one placement pass; clustering means a cluster layer, an unclustered layer, and a
   count label layer over a source whose contents change shape by zoom.
2. **It breaks the tap path.** `poiTaps.ts` resolves a tap to a `poi_id` property; cluster
   features carry no such property, `getClusterExpansionZoom` is async, and the waypoint card
   assumes a single POI. All soluble, none free.
3. **At the corridor view it does not answer the question.** A 2,197-mile line of bubbles
   reading 312, 289, 410 is a density map of a uniformly dense trail. It tells a hiker planning
   at home almost nothing that the legend's one-line count does not, for considerably more
   code.

Worth reopening the moment the low-zoom decision below is taken, and worth preferring over
Option 5 if the answer is "the map itself must carry it."

### Option 5 — Drive the waypoint lanes from the viewport instead of the GPS fix *(considered, not recommended yet)*

The strongest idea here, and the one most likely to be wrong for a reason that only shows up on
a real screen.

The three waypoint lanes under the elevation ribbon (WIREFRAMES.md §1.4,
[`waypointLanes.ts`](../client/src/lib/waypointLanes.ts)) already solve this exact problem in
the one dimension that matters: they cluster overlapping waypoints into count pills, they never
drop anything silently, and their lanes — `WATER` / `SLEEP` / `ELSE` — are the same hiker
priority ordering `POI_PRIORITY` uses. **The trail is one-dimensional and so are they**, which
is why they do not have the map's problem at all.

They are also unavailable exactly when they would help most. `App.tsx` gates them on
`ribbon !== undefined`, which needs a published elevation profile *and* a GPS fix *and* that fix
landing on the centerline. A hiker planning at a kitchen table gets neither pins nor lanes.

The change is small — the lanes want a mile window, and the viewport already implies one; the
per-POI mile already exists client-side, computed by `locateOnTrail()` for `searchablePois`, so
no pipeline work is needed. Zooming out would then make the lane strip *denser* rather than
making the screen emptier, which is the right direction.

Held back because a 2,197-mile window collapses the lanes into a handful of pills reading in
the hundreds, and whether that reads as useful or as noise is a question for a real screen, not
an argument. It also puts a second, differently-derived window next to the ribbon's, and
WIREFRAMES.md §1.3–1.4's whole point is that the two agree about what stretch they are showing.

---

## What is recommended, in what order

1. **Option 1 — say what is hidden**
   ([#528](https://github.com/OurHike/OurHike/issues/528)). Nothing else lands first. It is the
   smallest change, it carries no risk to the collision ordering, and every other option is
   more honest with it in place than without.
2. **Option 3 — control that persists, plus "only this"**
   ([#530](https://github.com/OurHike/OurHike/issues/530)). Independent of Option 2, and the
   direct answer to *give the user more control over what is being displayed*.
3. **Option 2 — priority-tiered admission**
   ([#531](https://github.com/OurHike/OurHike/issues/531)). After Option 1, never before it.
4. **Options 4 and 5 — a decision, not a build**
   ([#532](https://github.com/OurHike/OurHike/issues/532)). Both answer "what should the
   zoomed-out map actually show," they answer it differently, and neither is worth building on
   an argument.

**Branch collision, worth knowing before two of these start at once**
([../BRANCHING.md](../BRANCHING.md) §2): Options 1 and 3 both edit `App.tsx`, which is the
repository's single worst conflict surface — 12 of 27 recorded conflicts. Option 2 touches
`poiLayers.ts` and its test and nothing else, so it can run in parallel with either. Sequence 1
before 3, or accept the conflict knowingly.

---

## Data model

No new keys. `waypoint_types_shown` already exists in
[IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)'s `UserPreferences`, defaults to `[]`
meaning all, and syncs with everything else the moment an account is linked. Option 3 is the
first thing to read it.

Everything else here is derived per-frame from state the app already holds: the POI array, the
viewport, and what MapLibre reports as rendered. Nothing is stored, and nothing needs to be —
a count of what is hidden right now is not a preference and must never be cached across a
camera move.

---

## Open questions (real ones, not decided here)

- ~~**The measured drop rate.**~~ **Answered 2026-08-12 by [POI_SITES.md](POI_SITES.md)** — see
  "How much is actually being dropped" above. It measured z12–z17 per category, and the answer
  reshaped this doc rather than confirming it: the loss is concentrated in the categories
  `POI_PRIORITY` ranks last, and co-location rather than viewport density is what destroys them
  at the zooms an offline hiker has. What survives as a live question is the z7–z11 band, which
  nothing has simulated.
- **The zoom tiers themselves.** z7 / z8 / z10 / z11 are reasoned from the priority list and
  from what fits, not validated, and they sit in exactly the unsimulated band above. Produce
  them from POI_SITES.md's method rather than moving them by argument. They are four numbers in
  one table and cheap to change, which is the argument for the explicit table over the emergent
  version.
- **Whether the count chip belongs on the canvas at all.** It is one more thing over a map whose
  every pixel is contested, and the legend is one tap away. A real screen answers this;
  [#105](https://github.com/OurHike/OurHike/issues/105)'s outdoor pass is where it would be
  asked.
- **Default `waypoint_types_shown`** — all-on (today's implicit behaviour) vs. a curated subset.
  Inherited unchanged from [UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md)'s own open list; the
  visibility argument gives it real weight, since the 1,194 in-corridor vistas are **43% of
  every waypoint published** and are last in the priority order for exactly that reason. One
  toggle hands nearly half the map's pin budget back.
- **Whether "only this" should survive a pan.** A momentary lookup and a persistent preference
  are different things ([UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md) makes the same distinction
  about search); "only water" probably wants to be momentary and probably wants an obvious way
  out, and the difference is worth a real opinion rather than a default.

## Related

**[POI_SITES.md](POI_SITES.md) is the sibling, and the boundary between them is worth stating
once so neither grows into the other.** Both were written on 2026-08-12, four minutes apart, by
sessions that could not see each other; both are about pins that do not get drawn. They are not
the same problem:

| | POI_SITES.md | this doc |
|---|---|---|
| the crowding | several waypoints at **one place** — 37% within 60 m | many places across **one viewport** |
| the fix | model the place, draw one pin, parts on the card | count what is dropped, let the hiker choose, admit by priority |
| where it lands | the pipeline, mostly | the client, entirely |
| what it cannot fix | a corridor view with 90 waypoints and room for 26 | a privy 42 m from its shelter |

That doc's measurement is this doc's evidence, and its site model **reduces the pressure this
one operates under without removing it** — grouping 1,027 stacked points into 435 sites hands
real budget back at hiking zooms and changes nothing about z9. Neither is a reason to defer the
other.

[MAP_OPTIONS.md](MAP_OPTIONS.md) §5 owns the legend as a piece of chrome and the rule this doc
inherits — the legend is a view onto categories that already exist, never a second taxonomy.

[UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md) owns the *why* of `waypoint_types_shown` and the
distinction between an in-the-moment filter and a persistent display preference. Option 3 builds
both halves it describes; this doc does not restate its reasoning.

[DATA_NUDGES.md](DATA_NUDGES.md) plans to *boost* the prominence of stale POIs to solicit
confirmations. That is a competing claim on the same scarce pin slots, and it is Post-MVP; it
should be designed against this doc's budget rather than against an empty screen.

[ELEVATION_PROFILE.md](ELEVATION_PROFILE.md) owns the ribbon window that Option 5 would have to
agree with.
