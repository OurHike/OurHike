# OurHike — Waypoint Visibility (Feature Design Draft v2)

Companion to [MAP_OPTIONS.md](MAP_OPTIONS.md) (which owns the legend and the rest of the map
chrome), [POI_SITES.md](POI_SITES.md) (which owns several waypoints at one place),
[CORRIDOR_VIEW.md](CORRIDOR_VIEW.md) (which owns the map below this doc's seam),
[UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md) (which owns *why* `waypoint_types_shown` exists),
[../WIREFRAMES.md](../WIREFRAMES.md) §1.4 and §2, and [../OurHikeValues.md](../OurHikeValues.md) #4.

**This doc owns one question: what the map does when it cannot draw every waypoint as a pin.**
It does not own the pin artwork ([`client/src/map/poiIcons.ts`](../client/src/map/poiIcons.ts)),
the collision ordering ([`client/src/map/poiLayers.ts`](../client/src/map/poiLayers.ts)'s
`POI_PRIORITY`, which this doc treats as correct and builds on), or which waypoints the pipeline
publishes.

---

## Rewritten 2026-08-13, and the reason is in this doc's own numbers

v1 of this file offered five options, recommended three of them in a sequence, and produced
three issues: [#528](https://github.com/OurHike/OurHike/issues/528) to *report* the deletions,
[#531](https://github.com/OurHike/OurHike/issues/531) to *choose* them better, and
[#532](https://github.com/OurHike/OurHike/issues/532) to decide what to draw *instead of* them.
Three issues, three pieces of UI, every one of them built on accepting that the map deletes
waypoints and arguing about the consequences.

**It dimensioned the problem at the wrong zoom.** Its arithmetic — 70–90 waypoints in a viewport
with room for 26 — is a z9 measurement, and z9 is a zoom at which the screen is 28 × 51 miles of
ground. Run the same arithmetic at the zooms a hiker actually looks at a place from:

| zoom | m/px at 40°N | a 390 × 700 phone map is | waypoints in it, at 1.26/mi | pins that fit down the column |
|---|---|---|---|---|
| 9 | 117 | 28 × 51 mi | 70–90 | ~26 (pins are at 0.6 size here) |
| 12 | 14.6 | 3.5 × 6.4 mi | 10–16 | ~16 |
| 13 | 7.3 | 1.8 × 3.2 mi | 4–8 | ~16 |
| 14 | 3.7 | 0.9 × 1.6 mi | 2–4 | ~16 |

**From z12 up, viewport density is a marginal problem and by z13 it is not a problem at all.**
Which makes the catastrophic drop rates this doc measured — 1% of privies at z12, 21% of
campsites — something other than a density story, and v1 said so itself without following the
thought through: *"The dominant cause at those zooms is co-location, not viewport density."*

So the previous design spent five options and three issues on a density problem that mostly does
not exist at the zooms where waypoints matter, and handed the part that does exist — co-location
— to [POI_SITES.md](POI_SITES.md), where it was already being solved. What is left after that is
small enough not to need a UI at all.

The three ways a waypoint disappears, and the measurements underneath them, survive unchanged
and are the evidence for what replaces the options. They are kept below.

---

## The three ways a waypoint disappears, and only one of them is honest

### 1. The hard floor — nothing at all below zoom 9

`POI_MIN_ZOOM = 9` in [`poiLayers.ts`](../client/src/map/poiLayers.ts):63, set both as the
layer's `minzoom` and as the low anchor of `POI_ICON_SIZE_EXPRESSION`. Below it there are no pins
whatsoever. The app's opening view is the whole corridor — `CORRIDOR_BOUNDS` in
[`App.tsx`](../client/src/App.tsx):240, somewhere around z4–z5 on a phone — so **the first map a
hiker ever sees has zero waypoints on it and no explanation.**

The constant's own docstring makes the argument for it, and the argument is good: *"Eight hundred
POIs on it is not a map, it is a texture."* **The floor is right and was never the defect.** The
defect is that below it the map has nothing to say instead, and [CORRIDOR_VIEW.md](CORRIDOR_VIEW.md)
is the doc that gives it something.

### 2. The collision drop — most of them, most of the time, above zoom 9

`icon-allow-overlap: false` with `icon-padding: 2`. MapLibre's collision engine places pins in
`symbol-sort-key` order and discards every one that would overlap something already placed.
`POI_PRIORITY` decides *who* survives, and decides it well — water first, vistas last, for reasons
the file argues at length.

Nothing decides, or reports, that a loser existed. This is the one the design below is for.

### 3. The type filter — deliberate, and the only one a hiker can see

`attachHiddenPoiTypes` applies the legend's toggles as a layer filter. This is the honest case: a
hiker turned it off, the legend row still shows the count and still reads as the control that
turns it back on, and nothing is claimed. Since
[#530 — Make hiding a waypoint type persist](https://github.com/OurHike/OurHike/issues/530)
landed it survives a reload and reaches an account, and the picker reaches a category with nothing
in the viewport.

---

## How much is actually being dropped

| input | value | source |
|---|---|---|
| corridor length | 2,197 mi | [../WIREFRAMES.md](../WIREFRAMES.md) |
| waypoints published | **2,778** | measured against the live ATC FeatureServer and opentrail.org, 2026-08-12 ([POI_SITES.md](POI_SITES.md)) |
| of which vistas | 1,194 in corridor, of 1,223 | [../pipeline/README.md](../pipeline/README.md) |
| pin size | 38 px + 2 px padding each side = 42 px | `POI_PIN_SIZE`, `icon-padding` |

Simulating MapLibre's placement over the whole corridor — symbols considered in `symbol-sort-key`
order, a box skipped when it overlaps one already placed — the share of each type drawn at all:

| zoom | water | shelter | campsite | parking | privy | viewpoint |
|---|---|---|---|---|---|---|
| 12 | 85% | 82% | 21% | 67% | **1%** | 43% |
| 14 | 95% | 91% | 31% | 81% | **3%** | 75% |
| 16 | 98% | 96% | 61% | 92% | 50% | 90% |

`BASEMAP_MAX_ZOOM` is 14 ([`liveTopo.ts`](../client/src/map/liveTopo.ts):93,
[`export_basemap.py`](../pipeline/export_basemap.py):83), so an offline hiker lives in the top two
rows.

**Read those against the viewport table above and the cause is unambiguous.** At z14 there are
2–4 waypoints in the viewport and room for about 16, and 97% of privies still do not draw. Nothing
about that is a screen running out of room. A privy sits a median 42 m from its shelter and two
pins collide within 154 m at z14; single-link clustering at 60 m puts **37% of every published
waypoint** on top of another one. The pins are not competing for the screen. They are standing on
each other.

---

## The principle this design turns on

v1's principle was **a sampled category is a claim; a count is a fact**, and it is right as far as
it goes. What it missed is that there is a third thing, better than both:

**A dot is a fact too, and it is in the right place.**

Twenty-six pins at z9 is not "some of the waypoints" — a hiker reads pins the way a paper map is
read, *these are the springs on this stretch*, and arbitrary survivors of a geometric collision
test say exactly that, falsely. v1's answer was to caption the falsehood: `Water · 14 · 4 shown`.
That is more honest than silence and it is still a map with ten springs missing from it, now with
a footnote.

The absence of a pin is the strongest statement this map makes about a place. So do not make it.

---

## The design: one seam, two ranks

### The seam

One zoom, `POI_PIN_MIN_ZOOM`, replacing `POI_MIN_ZOOM`. Below it the map is about the trail and
is [CORRIDOR_VIEW.md](CORRIDOR_VIEW.md)'s; above it the map is about places and is this doc's.

**`POI_PIN_MIN_ZOOM = 9`, with pins drawn at 0.8 rather than 0.6 to suit it.**

A day on the A.T. is 16–24 miles, and the window is **twice that**, so the day has ground around
it rather than filling the screen edge to edge. A 390 × 700 phone map covers **50.9 miles at z9**
and 25.5 at z10 — so z9 is the tightest zoom that shows a hiker the day they are about to walk
*and where it sits*.

**The doubling is the point, not slack.** z10 fits a 24-mile day exactly, which means the day
touches both edges and every question that starts *"and then what"* costs a pan.

Measured at z9 by [`pipeline/spike_poi_seam.py`](../pipeline/spike_poi_seam.py) against the live
ATC service, with [`lib/poi_sites.py`](../pipeline/lib/poi_sites.py)'s own folding applied:

| zoom | screen | shelter | privy | campsite | parking | viewpoint | all | load / room |
|---|---|---|---|---|---|---|---|---|
| 8 | 101.9 mi | 51% | 41% | 32% | 4% | 0% | 26% | 140 / 20 |
| **9** | **50.9 mi** | **83%** | **69%** | **59%** | **14%** | **2%** | **46%** | **69 / 20** |
| 10 | 25.5 mi | 93% | 79% | 72% | 38% | 10% | 59% | 35 / 19 |
| 11 | 12.7 mi | 97% | 84% | 79% | 65% | 24% | 70% | 18 / 18 |
| 12 | 6.4 mi | 97% | 86% | 84% | 81% | 44% | 78% | 9 / 17 |

**The things a day is planned around are mostly pins; the vistas are almost entirely dots.** The
screen runs 69 waypoints against room for 20, and that is the design working rather than failing —
the forty-nine that lose are dots, at their real coordinates, tappable.

### The pins got bigger, and it cost almost nothing

Pushing the seam out to z9 draws pins at the low end of `POI_ICON_SIZE_EXPRESSION`'s ramp, where
0.6 gives a 22.8 px pin carrying a **10.6 px glyph** — a mark you can locate but not identify. The
obvious worry is that raising it costs coverage, since bigger pins collide more. Measured at z9:

| min scale | pin | glyph | shelter | privy | campsite |
|---|---|---|---|---|---|
| 0.6 | 22.8 px | 10.6 px | 88% | 74% | 68% |
| **0.8** | **30.4 px** | **14.2 px** | **83%** | **69%** | **59%** |
| 1.0 | 38.0 px | 17.7 px | 73% | 60% | 52% |

**A third more pin costs shelters five points**, because what binds at z9 is the trail's own
density rather than the box. `POI_PIN_MIN_SCALE = 0.8` is the result. `poiIcons.test.ts` holds a
7 px floor on a glyph and neither figure is near it — this is about comfort at arm's length in
sun, not about a minimum.

### It was z12, then z10, both on the same day

Both corrections are kept here rather than tidied away, because in neither case was the arithmetic
wrong.

**z12** came from asking *"at what zoom does the screen stop being oversubscribed with pins?"* —
a pin-legibility test, when this very document says an oversubscribed screen costs **dots, not
deletions**. Legibility is a comfort criterion; nothing true or false hangs on it, so it is the
wrong thing to set a floor with. z12 showed 6.4 miles: a quarter of a day.

**z10** came from fixing that and then sizing the window to *exactly* one day — a day with no
context around it.

The failure mode both share is worth naming: a defensible-sounding criterion, correctly computed,
answering a question nobody was asking. The measurement was never the weak part.

**A third correction, in the simulation rather than the design.** The first run modelled a
full-size 42 px collision box at every zoom, when the ramp draws pins smaller near the seam. That
understates what fits exactly where it matters. The spike now models the ramp, and both anchors
are named constants on both sides so the measurement cannot describe a different map from the one
that ships.

**Getting it wrong would have been cheap, which is why it was worth measuring rather than
agonising over.** Under a design that deletes waypoints, the floor is where truth turns into
fiction and every zoom level matters. Under this one nothing below it is claimed and nothing above
it is hidden, so the seam is a judgement about what makes a better screen, not a threshold
protecting anybody from a false map.

### Above the seam: two ranks, and nothing in neither

Every waypoint in the viewport draws in one of exactly two ways:

- **Rank 1, the pin.** The 38 px icon as today, collision-ordered by `POI_PRIORITY`,
  `icon-allow-overlap: false`, tappable. Entirely unchanged.
- **Rank 2, the dot.** A 3–4 px `circle` layer beneath it, in the type's accent, carrying
  `poi_id`, drawn for **every** waypoint. **MapLibre's collision engine is a property of symbol
  layers; `circle` layers do not participate in it and every feature renders.** So this rank
  cannot drop anything, at any zoom, under any camera.

The collision engine stops being a deletion mechanism and becomes a **promotion** mechanism. It
decides which waypoints get the big treatment. It no longer decides which ones exist.

What that buys, in the terms the old design was arguing in:

- `Privy · 6 · 0 shown` has no subject. There are six privies on the screen, at their real
  coordinates, six of them dots. The count and the map agree because nothing was removed between
  them.
- Density becomes legible rather than reported. A valley with forty water sources looks like forty
  water sources — a stipple of blue where the pins could only ever have shown four.
- The gradient tunes itself. At z13 most waypoints are dots and a few are pins; by z16 nearly
  everything is a pin and the dot underneath it is invisible. No table of zoom tiers, no
  per-category thresholds, nothing to re-derive when a category is added.

### What the dot rank costs, stated before anyone discovers it

**The tap path needs a rule, and it does not have one.** `poiIdAt` in
[`poiTaps.ts`](../client/src/map/poiTaps.ts) takes `queryRenderedFeatures(...)[0]` over a box
whose size is *derived* from `POI_PIN_SIZE` — `POI_TAP_SLOP_PX = (44 - 38) / 2`, 3 px. A 4 px dot
needs 20 px of slop to reach the same touch target, and a 20 px box will routinely hold two
waypoints. The rule, and it should be written as a rule rather than left to `[0]`: **a pin under
the thumb beats a dot under the thumb; among dots, nearest to the centre of the touch wins.** Two
dots genuinely under one thumb is the site card's problem
([POI_SITES.md](POI_SITES.md) §5) where they are one place, and nearest-wins where they are not.

**`poiLayers.ts` argues at length for one layer, and this is a second one.** The argument is worth
reading before dismissing: five layers means five independent collision passes and five pins
stacked on one shelter. It is an argument about *collision*, and the dot layer deliberately does
not collide, so it cannot fragment a placement pass — but the file's header comment has to say
that, rather than have its central claim quietly falsified by a layer nobody explained.

**Hiding a type must hide both ranks.** `poiTypeFilter` applies to `poi_type` and both layers read
the same source, so this is one filter applied twice rather than a new mechanism — but it is the
kind of thing that ships half-done and leaves a dot under a hidden category.

**1,194 vistas as dots is a stipple, and that is the honest picture.** The corridor really does
carry half again as many overlooks as every other waypoint combined. The existing control for
that is the one that already exists: the type picker from
[#530 — Make hiding a waypoint type persist](https://github.com/OurHike/OurHike/issues/530).
Turning vistas off is now visibly worth doing, which is the argument that issue made for itself
and could not previously demonstrate.

### Grouping is POI_SITES.md's, and it stays there

A shelter, its privy and its campsites are **one place with parts**, and the fix is to model the
place: [POI_SITES.md](POI_SITES.md) folds 428 waypoints into 291 sites in the pipeline, with
stable ids, on a rule of name agreement within 150 m or proximity within 60 m. 284 of 316 privies
stop competing for a pin and start riding one that is drawn. That work is issued
([#523](https://github.com/OurHike/OurHike/issues/523),
[#524](https://github.com/OurHike/OurHike/issues/524),
[#526](https://github.com/OurHike/OurHike/issues/526),
[#527](https://github.com/OurHike/OurHike/issues/527)) and this design does not touch it.

**No second grouping mechanism.** Client-side clustering was v1's Option 4 and is refused for the
three reasons [POI_SITES.md](POI_SITES.md) already gives — it re-clusters on every zoom so a tap
at z13 and a tap at z15 hit different things; it has no id, and "the privy at Mt. Algo is
collapsed" is a report a hiker will file; and it answers *how many* when the question is *is there
water*. The two ranks and the site model between them leave nothing for it to do.

### Overlap stays off, and the reason has changed

`icon-allow-overlap: false` stays. This is worth stating because "let the pins overlap" is the
obvious reading of *stop hiding things* and it is the wrong one: overlapping 38 px icons at z13
is a pile, not a map, and it makes both pins unreadable rather than making one of them visible.

What changed is the *reason*. It used to be the only thing standing between a hiker and an
illegible screen, which made it load-bearing and frightening to touch. Now the dot rank guarantees
presence, so the collision setting only governs legibility — and a setting that only governs
legibility can be revisited on a real screen ([#105](https://github.com/OurHike/OurHike/issues/105))
without anything true or false hanging on it.

---

## Below the seam

Not this doc's. [CORRIDOR_VIEW.md](CORRIDOR_VIEW.md) owns it, and the sentence that connects the
two is worth stating here because it is what makes the seam defensible:

**Below the seam the map is not an incomplete map of places. It is a complete map of something
else** — all thirty maintaining-club sections, all of the stretches worth going to. Nothing is
sampled, so nothing needs a caption admitting it was.

**Since #603 it also carries the dot rank**, which is a real qualification of the paragraph above
rather than a footnote to it: the corridor view is now that complete map of something else *plus*
a stipple of every waypoint on the trail. The claim survives because a dot is not a place-card —
nothing about the scatter suggests it is a curated set, and no dot is sampled out — but the view is
no longer showing one subject. See the answered question below for why that trade was taken, and
`client/src/map/poiLayers.ts`'s `POI_DOT_MIN_ZOOM` for the reasoning in the code.

The legend's sentence for this band is now *"Waypoints show as dots at this zoom. Zoom in to see
what each one is."* It replaced `Nothing on this part of the map yet — pan or zoom out to see
more`, which at the opening view was false in both halves — there was plenty here, and zooming
*out* was the wrong direction. The first replacement landed with
[#528](https://github.com/OurHike/OurHike/issues/528) as *"waypoints are drawn from a closer
zoom"*; #603 corrected it again, because once dots draw here that sentence is half wrong too —
they **are** drawn, and what needs a closer zoom is telling one from another.

---

## What this retires, and what it does not

| | |
|---|---|
| **[#531 — Every waypoint category appears at once at z9](https://github.com/OurHike/OurHike/issues/531)** | Superseded. Per-category zoom tiers are a better answer to *which waypoints do we delete*, and the dot rank stops asking. Its four unvalidated numbers go away with it. |
| **[#528 — The map drops most of its waypoints to collision and reports the number as zero](https://github.com/OurHike/OurHike/issues/528)** | Mostly loses its subject: a count of what did not fit has nothing to count. The below-the-seam sentence survives. |
| **[#574](https://github.com/OurHike/OurHike/pull/574)**, its open pull request | The maintainer's call, and untouched here. It is green and its counts are the only honest thing on that panel until this lands. |
| **[#532 — Decide what the zoomed-out map shows](https://github.com/OurHike/OurHike/issues/532)** | Answered — neither of its two options. See [CORRIDOR_VIEW.md](CORRIDOR_VIEW.md). |
| **[#530 — Make hiding a waypoint type persist](https://github.com/OurHike/OurHike/issues/530)** (landed) | Unaffected, and worth more: the type picker now governs both ranks and its effect is finally visible. |
| **[POI_SITES.md](POI_SITES.md)'s issues** | Unaffected and still wanted. They are the grouping half of this. |

---

## Data model

**No new keys, and no new download.** Both ranks read the one POI source the app already holds.
The seam is a client constant. Nothing about what is drawn is stored, and nothing needs to be — a
picture of the current camera is not a preference.

`waypoint_types_shown` is unchanged and already built (#530).

---

## Open questions (real ones, not decided here)

- ~~**The seam's zoom.**~~ **Answered 2026-08-13 — `POI_PIN_MIN_ZOOM = 12`**, by
  [`pipeline/spike_poi_seam.py`](../pipeline/spike_poi_seam.py), which is the measurement this
  doc asked for rather than a number argued into place. See "The seam" above. What it turned up
  along the way reshaped two things here rather than confirming them: site folding is doing more
  of the work than this doc credited it with, and the dot rank is in practice a vista rank.
  *(The constant then kept moving after the answer: the corrections recorded in
  `poiLayers.ts`'s own docstring — z12, then z10, then a floor of 9 with the dot rank drawing
  the texture below it — leave `POI_PIN_MIN_ZOOM = 9` as the shipped value, checked
  2026-08-17 (#661). The spike's measurement stands as the answer to the question it was
  asked; the seam it measured is handled by the dot rank now rather than by the pin floor.)*
- ~~**Whether the dot rank should extend below the seam.**~~ **Answered 2026-08-15 — yes**, on
  [#603](https://github.com/OurHike/OurHike/issues/603), by the maintainer. `POI_DOT_MIN_ZOOM = 0`
  in `client/src/map/poiLayers.ts`; the pin rank keeps `POI_PIN_MIN_ZOOM`, so the two ranks now
  stop in different places on purpose.

  The recommendation here was **no**, and what changed is not the argument but the evidence
  against it. #603 recorded what the corridor view actually is today: the app opens on the whole
  trail, which lands near z4 on a phone, so the first map a hiker ever sees was the trail line and
  nothing else, for the entire z4–z9 band. The "it is a texture" objection is still correct and is
  now answered by size rather than by absence — the dots ramp down to 1.2 px at z0, so what the
  corridor view carries is a stipple, denser where the places are. That is the texture, labelled,
  which is the same move the seam's own docstring made when it stopped drawing nothing.

  It was chosen over the two alternatives in #603's scope precisely because it adds rather than
  reverses: a tighter opening camera would contradict `CORRIDOR_BOUNDS`'s comment, and a camera
  surviving the tab closing would contradict `cameraMemory.ts`'s. Both stand untouched.

  **The cost this doc should keep stating:** the "Below the seam" section above says the corridor
  view is *a complete map of something else*. It now carries a second thing, and that claim is
  softer than it was. ~2,837 circles at z4 — cheap to draw (a `circle` layer runs no collision
  pass), but not free of meaning.
- **Dot size, and whether it varies by `POI_PRIORITY`.** Built uniform — 2.5 px at the seam
  growing to 4 px by z16, the same for every category. A 4 px water dot and a 3 px vista dot would
  carry the priority ordering into the rank that has no ordering, and the argument for the rank is
  that it makes no claim beyond *something is here*. **Still open**, because it is the decision
  most likely to be wrong in a browser and right on a phone, or the reverse:
  [#105](https://github.com/OurHike/OurHike/issues/105)'s real screen in real sunlight, like the
  site pin's badge. The measurement gives it a sharper test than "does it look right" —
  vistas are 42% pinned at the seam, so a corridor of overlooks is the case where the stipple is
  heaviest and where it should be judged.
- ~~**Whether a dot is tappable at all.**~~ **Built tappable**
  ([#597](https://github.com/OurHike/OurHike/issues/597)), with the rule stated in
  `poiTaps.ts` rather than left to `[0]`: a pin under the thumb beats a dot, and among dots the
  one nearest the touch centre wins. The cost is real and was the argument against — a dot needs
  20 px of slop to reach `--min-touch-target` where a pin needs 3, so the dot box routinely holds
  several waypoints. That is exactly why it needed a rule, and having one is what made it safe to
  build. If it grates on a phone the fallback is to make dots inert, which is a one-line change to
  the same function.
- ~~**Default `waypoint_types_shown`**~~ — **decided 2026-08-20** (#865), inherited from
  [UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md)'s resolution: a curated subset, not all-on. Viewpoint
  is one of the four that now starts hidden, so the 1,194 in-corridor vistas this bullet flagged as
  43% of every published waypoint no longer draw on a fresh install — a hiker who wants them back
  turns the category on, same as any other.

## Related

**[POI_SITES.md](POI_SITES.md) is the sibling and the boundary is unchanged:** that doc owns
several waypoints at **one place**, this one owns many places across **one viewport**. What
changed on 2026-08-13 is the balance between them — measured against the viewport arithmetic
above, co-location is nearly the whole of the problem at hiking zooms, so that doc is doing most
of the work and this one is covering its residue.

**[CORRIDOR_VIEW.md](CORRIDOR_VIEW.md) is the other half of this design**, split off rather than
folded in because it is not about visibility at all: below the seam nothing is hidden, because
waypoints are not what that map is for.

[MAP_OPTIONS.md](MAP_OPTIONS.md) §5 owns the legend as a piece of chrome and the rule this doc
inherits — the legend is a view onto categories that already exist, never a second taxonomy.

[UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md) owns the *why* of `waypoint_types_shown`.

[DATA_NUDGES.md](DATA_NUDGES.md) plans to *boost* the prominence of stale POIs to solicit
confirmations. Under two ranks that is a promotion rule — dot to pin — rather than a competing
claim on a scarce slot, which is a considerably easier thing to design. It is Post-MVP either way.

[HIKER_SAFETY.md](HIKER_SAFETY.md) and [MAP_OPTIONS.md](MAP_OPTIONS.md) §4 own the rule this
inherits without restating: closures and serious warnings have no hide affordance anywhere, and
the way that rule is kept is that the affordance is never built. `NEVER_HIDEABLE` in
`legendContents.ts` is the existing guard and stays the only one.
