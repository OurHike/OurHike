# OurHike — Co-located Waypoints (Feature Design Draft v1)

Companion to [../WIREFRAMES.md](../WIREFRAMES.md) (§1.4 lanes, §1.5 canvas, Interactions), [POI_PHOTOS.md](POI_PHOTOS.md), [SPUR_TRAILS.md](SPUR_TRAILS.md) and [MAP_STYLE_SPEC.md](MAP_STYLE_SPEC.md).

A shelter, its privy, its campsites and its water source are one place with parts. The map treats them as four unrelated points that happen to be near each other, and then resolves the crowding by drawing one of them and silently discarding the rest.

**The complaint is that pins overlap. The measurement says something worse: they don't overlap, they disappear.** `client/src/map/poiLayers.ts` sets `icon-allow-overlap: false` on purpose, so MapLibre never draws two colliding pins — it drops the one that loses `POI_PRIORITY`. Privies lose to shelters. At zoom 14, **3% of the A.T.'s 316 privies are drawn anywhere on the trail.** The hiker sees a clean map and concludes there is no privy.

Everything below is measured against the live ATC FeatureServer and the opentrail.org API on 2026-08-12, not estimated.

Work: [#523](https://github.com/OurHike/OurHike/issues/523) publishes the grouping, [#524](https://github.com/OurHike/OurHike/issues/524) draws the pin, [#526](https://github.com/OurHike/OurHike/issues/526) puts the members on the card, [#527](https://github.com/OurHike/OurHike/issues/527) repairs the four places that assume one pin per POI, and [#529](https://github.com/OurHike/OurHike/issues/529) is the water gap this turned up, which is a sourcing problem no display change closes.

---

## What is actually happening

### 1. Co-location is the normal case, not an edge case

Share of shelters and campsites with at least one other waypoint within R metres:

| from a **shelter** (n=280) | 15 m | 30 m | 60 m | 100 m | 250 m |
|---|---|---|---|---|---|
| privy | 2% | 23% | **67%** | **86%** | 88% |
| campsite | 14% | 24% | 40% | 49% | 55% |
| water | 0% | 1% | 3% | 4% | 8% |
| anything at all | 22% | 45% | 82% | 91% | 94% |

| from a **campsite** (n=232) | 15 m | 30 m | 60 m | 100 m | 250 m |
|---|---|---|---|---|---|
| privy | 4% | 19% | 49% | 75% | 86% |
| shelter | 17% | 28% | 48% | 61% | 69% |
| water | 0% | 1% | 2% | 4% | 10% |

Single-link clustering over all 2,778 published points at 60 m gives 435 clusters holding 1,027 points — **37% of every waypoint on the trail is stacked on another one.** The composition is not arbitrary:

| clusters at 60 m | composition |
|---|---|
| 90 | privy + shelter |
| 74 | campsite + privy + shelter |
| 64 | viewpoint + viewpoint |
| 29 | campsite + privy |
| 26 | parking + resupply |
| 23 | parking + viewpoint |

The 64 viewpoint pairs matter as much as the 90 shelter+privy pairs, and in the opposite direction: two overlooks 50 m apart are **two overlooks**, not one place with two parts. Any rule that groups by distance alone merges them. That is the first constraint on the design.

### 2. The collision engine resolves crowding by deletion

Two pins collide when their centres are closer than `POI_PIN_SIZE` (38 px) plus `icon-padding` on each side — 42 px. In metres, at latitude 40:

| zoom | m/px | pins collide within |
|---|---|---|
| 12 | 14.6 | 615 m |
| 13 | 7.3 | 307 m |
| 14 | 3.7 | 154 m |
| 15 | 1.8 | 77 m |
| 16 | 0.9 | 38 m |
| 17 | 0.46 | 19 m |

A privy sits a median 42 m from its shelter. It therefore cannot be drawn until **zoom 16**. Simulating MapLibre's placement (symbols considered in `symbol-sort-key` order, a box skipped when it overlaps one already placed) over the whole corridor, the share of each type that gets drawn at all:

| zoom | water | shelter | campsite | parking | privy | viewpoint |
|---|---|---|---|---|---|---|
| 12 | 85% | 82% | 21% | 67% | **1%** | 43% |
| 13 | 90% | 86% | 25% | 74% | **2%** | 61% |
| 14 | 95% | 91% | 31% | 81% | **3%** | 75% |
| 15 | 98% | 95% | 41% | 86% | **8%** | 85% |
| 16 | 98% | 96% | 61% | 92% | 50% | 90% |
| 17 | 99% | 98% | 79% | 96% | 87% | 94% |

`pipeline/export_basemap.py`'s `BASEMAP_MAX_ZOOM` is 14, so an offline hiker lives in the top four rows of that table. **The privy layer, added at real download cost in [#510](https://github.com/OurHike/OurHike/issues/510), effectively does not exist on the map**, and two thirds of campsites are missing alongside it.

This is not a bug in the collision ordering. `POI_PRIORITY` is doing exactly what its comment says — deciding who survives, with water first — and it is the right answer to the question it was asked. The question was wrong. Where two pins describe *parts of the same place*, "which one survives" has no acceptable answer.

### 3. Even where two pins are drawn, only one can be tapped

`poiIdAt` in `client/src/map/poiTaps.ts` takes `queryRenderedFeatures(...)[0]`. Its comment reasons that the top pin is the one someone could aim at, and that collision makes the choice rare — both true. Neither helps here: the second POI has no pin, so there is nothing to aim at, and no gesture anywhere in the app reaches it.

---

## Why not a geospatial cluster

Clustering is the reflex answer and it is the wrong one here, for three reasons worth writing down because they will be proposed again.

**It re-clusters on every zoom.** A hiker who taps a group at z13 and again at z15 taps two different things with the same appearance. Nothing else on this map changes identity when the camera moves.

**It has no id.** `pipeline/lib/poi_schema.py`'s `unify_poi` docstring already commits to deterministic ids "since a future Report/Closure references this id and it has to stay stable across repeated pipeline runs". A cluster computed on a phone is exactly what cannot be referenced — and "the privy at Mt. Algo is collapsed" is a report a hiker will want to file.

**It answers with a number.** A circle reading "4" tells a hiker there are four things and not one of the four things they wanted to know. The question at a shelter is never *how many* — it is *is there a privy, and is there water*.

The A.T.'s co-location is not a rendering accident to be smoothed over. It is a fact about the trail: ATC builds a privy for a shelter and names it after the shelter. **Model the fact; do not paper over the symptom.**

---

## Design

### 1. The grouping happens in the pipeline

`export_poi.py` resolves co-located waypoints into a **site** — one anchor plus its parts — and publishes the grouping as properties on the POIs it already writes. The client never computes a group.

Four reasons, in order of weight:

- **Stable ids.** A site is a thing reports, closures and future field notes will reference. The pipeline is the only place that can mint an id that survives a pan.
- **The evidence lives upstream.** The grouping signal is ATC's own naming (below), which is in raw source columns the client never sees — `export_poi.py` reads `Name`; the client receives a unified record.
- **Testable against the corridor.** pytest over all 2,778 real points, with the ratios in this document as regression targets. A client-side grouping is testable only against fixtures someone wrote by hand.
- **Computed once, not per frame.** 2,778 points is nothing on a laptop and is not nothing on a cold phone with a map redrawing.

The cost, stated honestly: a wrong grouping is baked in and a hiker cannot undo it. A privy attached to the wrong shelter is a false statement of the kind this app exists not to make. §2 and §6 are the mitigations.

### 2. The rule is name agreement **and** proximity — never either alone

ATC names these things systematically. `"Mt. Algo Shelter Privy"`, `"Imp Shelter Campsite"`, `"Crystal Mtn Campsite Privy"` — child name = parent name + type word. Every one of the 316 privies and 232 campsites carries a non-empty `Name`.

Measured, with a deliberately naive matcher (lowercase, strip punctuation, strip the trailing type word, look the remainder up among shelter and campsite names):

| | resolves to a parent | median distance | p99 | max |
|---|---|---|---|---|
| privies | 239/316 (76%) | 42 m | 104 m | 124 m |
| campsites | 140/232 (60%) | 37 m | 603 m | **903 km** |

Read those two rows together, because between them they settle the rule.

**Name agreement is a far better signal than distance.** Every one of the 239 name-matched privies is within 150 m of its named parent, and 98% are within 100 m. Name and geometry agree, independently, on the same answer — which is the strongest evidence available here that the convention is real and not a coincidence of wording.

**Name agreement alone is unsafe.** The 903 km match is a generic campsite name colliding with a same-named place at the other end of the trail. A name-only rule ships that.

So: **join on normalised-name agreement within 150 m, or on distance alone within 60 m of an anchor.** Neither gate on its own; the name gate is loose because the name is carrying the argument, the distance-only gate is tight because geometry is all it has.

**And a hard ceiling of one mile on a site's radius, whatever gate admitted the member.** It cannot bind today and that is the point of it: the widest gate is 150 m and the furthest member measured is 143 m, so every real pairing clears it by a factor of ten. What it guards is the next edit to those gates — nothing else stops someone raising the name radius to 2 km on a hunch, and the failure that reappears the moment they do is the 903 km match, published into artifacts a hiker cannot undo. It is applied as `min()` against each gate rather than as a separate check, so widening a gate cannot bypass it.

And the membership is restricted, not universal:

- **Anchors** are `shelter`, then `campsite`. Exactly one per site.
- **Members** are `privy`, `campsite`, `water`.
- `viewpoint`, `parking` and `resupply` are **never** members in v1. They are co-located with each other and with shelters, but they are not *parts of* a facility — the 64 viewpoint pairs above are the proof, and "parking + resupply" is a trailhead, which is a different feature with a different card.

Running that rule over the real corridor. The first column is what this document projected from the naive matcher; the second is what `pipeline/lib/poi_sites.py` actually produces, measured 2026-08-12 against all 828 shelters, campsites and privies on the live service:

| | projected | measured |
|---|---|---|
| POIs folded | 427 | **428** — 284 privies, 144 campsites (water excluded, see below) |
| sites | 287 | **291** (250 shelter-anchored, 41 campsite-anchored) |
| privies folded | 281 / 316 (89%) | **284 / 316 (90%)** |
| campsites folded | 137 / 232 (59%) | **144 / 232 (62%)** |
| sizes | 159 of 2, 119 of 3, 6 of 4, 3 of 5 | **166 of 2, 116 of 3, 6 of 4, 3 of 5** |
| furthest member | — | **143 m** — the 150 m gate binds, and nothing like the 903 km match survives |

Measured compositions: 115 shelter + privy, 113 shelter + campsite + privy, 40 campsite + privy, 11 shelter + campsite.

The measured figures come out slightly *better* than projected, for one normalisation reason this document did not predict — §2a. **The water row is excluded from the measurement rather than reported as zero**: those 9 points come from opentrail.org, whose API needs more than a bare GET, so they were not in the measured set. `water` is an ordinary member type in the rule and unit tests cover it.

**284 of 316 privies (90%) stop competing for a pin and start riding one that is drawn** — a shelter pin, which places at 91% at z14 and 95% at z15. Against the 3% drawn today, that is the whole of the fix.

### 2a. Which normalisation steps earn their place

Recovering the parent's name from the child's is where this gets subtly wrong, and #523 asked for it to be measured rather than assumed. Each candidate below was added *alone* on top of `{privy, campsite, shelter}` and run over all 828 points:

| step | worth |
|---|---|
| strip a trailing sibling number | **privies 86% → 89%.** The largest single win. 53 of the 828 names end in a digit: `"Mt. Wilcox South Shelter 2"`, `"Grafton Notch Parking Area Privy 2"` |
| strip a trailing `group` | **+4 privies, +7 campsites, +4 sites.** `"Eckville Shelter Group Campsite"` → `Eckville Shelter`; and `"Osgood Tentsite Privy"` → `"Osgood Tentsite Group Campsite"`, which is 60.5 m away and so needs the name gate, the distance gate having just missed it |
| strip a trailing plural `shelters` | **+2 campsites, +1 site.** ATC names a campsite after a *pair*: `"Tumbling Run Shelters Campsite"` |
| fold `Lean-to` / `Lean to` | **nothing.** Punctuation is collapsed to spaces before the type-word list is consulted, so both already spell `lean to`. The folding code was written, measured at zero, and deleted |
| strip `tentsite`, `campground`, `leanto`, `hut`, `cabin`, `site`, `privies`, `campsites` | **nothing, each.** `"Osgood Tentsite Privy"`'s parent is `"Osgood Tentsite Group Campsite"`, so `tentsite` is on *both* sides and stripping it from one would break the match |

Two of the three hypotheses in #523 were wrong, and the one it got right — the trailing digits — is the one that mattered most.

`group` also introduced the only ambiguity worth a tie-break. It makes `"Laurel Ridge Campsite"` and `"Laurel Ridge Group Campsite"` reduce alike, so `"Laurel Ridge Campsite Privy"` matches both — and nearest-wins picked the group site: 10 m closer, and not what the privy is called. **An anchor whose whole name the child's name contains beats one that merely reduces alike**, which picks the one ATC named it after.

### 3. What publishes

Three properties on the POI features `export_poi.py` already writes, not a new artifact:

| property | on | meaning |
|---|---|---|
| `site_id` | every member and the anchor | the anchor's own POI id |
| `site_role` | every member and the anchor | `anchor` or `member` |
| `site_name` | every member and the anchor | the anchor's display name |

A separate `sites.json` was considered and rejected: it would be a second fetch, a second thing `verify_release.py` has to know about, and the client would still need the members. Properties are additive — a client built before this ignores them and behaves exactly as it does today, which is the same backward-compatibility rule `mile`, `capacity`, `description` and `photos` are already held to in `PoiDetail`.

The client groups by `site_id` on load. That is a `Map` build over ~2,800 records, once.

**And the anchor's `description` names its parts** *(added 2026-08-13, [#614](https://github.com/OurHike/OurHike/issues/614))*. Folding a privy onto a shelter's pin took away the only place the privy described itself: `lib/poi_description.py` still composes "Multi-seat moldering privy. Built 2019." for it, attached to a feature that now draws nothing. So the anchor's own sentence carries them:

> Two-storey clapboard shelter, sleeps 14, with a fireplace, a fire ring and a porch. Built 1915. **Nearby: a multi-seat moldering privy 40 m away, a group campsite 25 m and water 90 m.**

**A separate sentence, never the `with` clause.** A shelter does not have a privy and a water source *inside* it — "with a fireplace and a porch" lists what the shelter has, and the parts are separate points a short walk away. Three rules fell out of writing it:

- **Each part gets the adjectives that tell one from another, and not its whole card.** "a moldering privy", because §5's own question is *which* privy; not "8 tent pads", which lands a number directly against the distance and stops the sentence being readable. The counts stay on the part's own card, where the chips below reach them.
- **Metres, whole ones, rounded exactly as the chips round them.** The same fact reading `40 m` on a chip and `131 ft` in the sentence above it is drift on one card.
- **Ordered by the member order the pin and the chips use** — privy, water, campsite — not nearest-first, so the sentence, the footer strip and the chip row cannot disagree about which part comes first.

This overlaps the chips below on type and distance, deliberately. The chip is a *control* — its job is to lead somewhere; the sentence is what a hiker skims before deciding whether to tap anything, and it is what a client built before the chips still shows.

### 4. On the map: one pin, carrying its composition

A site draws **one pin, at the anchor's coordinates, in the anchor's accent and glyph.** A shelter still looks like a shelter; nothing about the existing icon work is discarded. Members draw no pin of their own.

The pin has to say that it stands for more than itself, and there are two ways to do it:

- **A `+N` badge.** Cheap, legible at 38 px, and says nothing about *what*.
- **Micro-glyphs, one per member category.** Answers "is there a privy" without a tap, which is the actual question, and costs legibility at 38 px.

**Settled on micro-glyphs**, which is what [#524](https://github.com/OurHike/OurHike/issues/524) built. *Where* they go took two more passes, and the real screen this section asked for is what decided both:

| | where | anchor glyph | member glyph | icon box |
|---|---|---|---|---|
| #524, then [#604](https://github.com/OurHike/OurHike/issues/604) | a white footer strip across the disc | 11.1 px | 9.6 px at one member, 7.5 at three | 38 px |
| [#611](https://github.com/OurHike/OurHike/issues/611) | 21 px badges on the rim, upper right | **17.7 px** | **10.7 px at every count** | 58 / 70 / 72 px |

The strip could only be made by taking the anchor's own glyph down to 11.1 px, and every site pin paid that — including the 57% carrying a single member. A shelter carrying a privy was a less legible shelter than one carrying nothing, which is a strange thing for a pin to say. **Badges hang off the outer circle instead, crossing the halo ring and never the disc**, so the anchor keeps the full 17.7 px a plain pin draws at and a site pin is a plain pin again. Each badge is the same pin language at badge scale: the category's accent, its glyph in halo white, a white ring, the dark hairline outside.

The badge went out at 14 px and came back at 21 — the same real screen, saying the smaller one read as too quiet. So the member glyph now beats the strip at every count rather than trading against it: 10.7 px where the strip's most generous case was 9.6 and its three-member case 7.5. **A badge is also the same size whatever a pin carries**, where the strip divided a fixed span and so shrank all three glyphs to fit a third member.

Two things the size costs, both real:

- **The anchor no longer outranks its members by much.** 17.7 px against 10.7, where the 14 px badge made it 17.7 against 7.1. A site pin now says two things loudly instead of one loudly and one quietly. It is still a shelter first, and that is the thing to watch if a badge is ever grown again.
- **Three badges no longer fit inside the corner.** At 21 px they cannot fan across a quarter turn without touching, so a three-member pin puts its outer two about 7° past twelve and past three o'clock. One member (57% of sites) still sits square in the corner and two (42%) stay well inside it; only the 1% carrying three spills, and that 1% is #529's water gap rather than the trail.

**What it costs beyond that is the collision box.** Badges hang past the rim, so the image grows — symmetrically, which is what lets the disc stay on the hiker's coordinate with no `icon-offset` in `poiLayers.ts` at all. Padded per member count rather than once for every site pin, because the padding *is* the collision box: 58 px carrying one member, 70 carrying two, 72 carrying three, against 38 for every other waypoint on the map. At z14 that is a site pin evicting a losing neighbour from 229 m, 274 m or 281 m rather than from 155 m. Set against it, the same grouping took 428 members out of the source altogether — those stopped asking for a box at all. If it bites, the two ways out are to pad the top and right only and re-centre with a data-driven `icon-offset`, or to take the badge back towards 14 px.

**And it costs rasterising time**, which is worth writing down because it is the one cost that was found by CI rather than by looking. The images are 2.2× the pixels they were before badges, and building all 46 of them is a few hundred milliseconds on the main thread — enough, unoptimised, to time out tests that mount a map. Two things pay for it: the rasteriser skips any pixel whose samples cannot reach the pin or a badge (about half of a three-member image is empty corner), and `buildPoiIcons` is built once per process rather than once per map, since every trip to the More tab and back was paying the whole bill again for an answer that cannot change.

What this does *not* do is change `icon-allow-overlap`. Sites remove the pins that were colliding rather than permitting overlap; the collision engine keeps doing its job on what is left, and `POI_PRIORITY` keeps deciding a genuinely crowded ridge. Two shelters 400 m apart still collide at z12, correctly.

### 5. On the card: chips that are also the tabs

Under the name, a row of chips — `Privy · 40 m`, `Campsite · 25 m`, `Water · 90 m` — and tapping one swaps the card body to that member's own detail: its photo and gallery, its description, its coordinates, its unverified line.

One control doing two jobs, and the reason to prefer it over a plain tab strip: **the chip's existence is usually the whole answer.** A hiker wants to know there is a privy, not to read the privy's card. Tabs hide that behind a tap; chips answer at a glance and still lead somewhere.

This is not a new idiom. [WIREFRAMES.md §4](../WIREFRAMES.md) was amended on 2026-08-06 ([#298](https://github.com/OurHike/OurHike/issues/298)) to put the download window's sheets under tabs, and the reasoning there transfers exactly — "a stack reads as a list of things to work through rather than as alternatives to choose between". `client/src/screens/Tabs.tsx` exists; reuse it or its pattern rather than inventing a second one. Its rule carries too: **one panel rendered, not three hidden with CSS**, so a hidden member's gallery buttons are not in the tab order or being announced.

Two mechanical gotchas, both already visible in the current code:

- `usePinAnchor` depends on `[map, poi, card]` with a comment explaining that a late-arriving mile changes the card's *height* and a stale measurement leaves a flipped card overlapping its pin. Switching chips changes the height far more than a mile does. The effect has to re-run on the selected member, not only on the POI.
- The chip strip is tapped with a gloved thumb, so `--min-touch-target` applies to each chip. Four chips at 44 px fit a 320 px card; five do not, and the largest real site has five members. The strip scrolls horizontally or the card widens — a decision for whoever builds it, against a real device.

**Built in [#526](https://github.com/OurHike/OurHike/issues/526), and three things it settled that this section left open.**

**The strip scrolls; the card keeps its width.** Not really a choice by the time it was measured: `.poi-card` is `min(264px, …)`, not the 320 px this section reasoned from, and the body's padding leaves the strip 240 px — so two chips fit and the three-chip case, which is 41% of all sites, already overflows. Widening the card trades against `poiCardPlacement.ts`'s edge margins on a 360 px phone, and wrapping is worse than either: a strip that gains a row changes the card's *height*, and a card hanging below its pin is positioned by its measured height, so it would push itself over the pin it describes. Horizontal scroll costs nothing and does not care how many parts a site has — which matters, because the size distribution above is partly [#529](https://github.com/OurHike/OurHike/issues/529)'s water gap and moves as that closes.

**The chips are not a `role="tablist"`.** The rule this section insists carries — one panel rendered, not three hidden with CSS — is honoured: there is one media box and one body, both driven from the selected part. The ARIA pattern is not, and the reason is the card's own layout. The photo, the gallery and its buttons are as part-specific as the text is, and they sit *above* the strip; a `tabpanel` under the name could only contain the text while claiming to control an image that changed silently above it. Putting the media inside a panel means the strip precedes the photo, which moves the media box off the card's top edge and re-parents the close button out of the corner it is drawn for. So: plain buttons, `aria-current` on the one being read, and no `aria-controls` claim the markup cannot honour.

**The distance is computed on the phone, in metres, from the anchor.** Nothing publishes it (§3 is three properties and none of them is a distance), so it is `siteDistanceMeters` in `client/src/map/poiSites.ts` — the pipeline's own equirectangular `distance_m` from `pipeline/lib/spurs.py`, ported rather than re-derived, so the number on the chip is the measurement that admitted the member to the site. Measured from the anchor and not from whichever chip was last tapped, so the row's numbers do not rewrite themselves on every tap. Metres because a site is under 150 m across by construction and "131 ft" is not a figure anybody paces — which does mean this is the first distance in the app's chrome that ignores `UnitSystem`, and is worth revisiting if a hiker asks.

### 6. What a site model quietly breaks

Four things, each small, each a lie on the map if it is missed:

- **The legend counts what is not drawn.** `computeLegendContents` counts every POI in the viewport. With sites, "Privy 3" appears beside a map with no privy pin — and `poiLayers.ts`'s header comment makes "the legend names exactly what is drawn" a structural property of the one-layer design rather than a convention. The count should stay (a hiker wants to know there are three privies ahead) but the row has to be honest about where they are.
- **Hiding a type takes its members with it.** `poiTypeFilter` filters on `poi_type`. Hide shelters and the site pin goes, taking the privy and the campsite that were riding it. The fix is not a cleverer filter expression: rebuild the site features in JS when the hidden set changes and `setData` again — 2,800 points, trivial — so a site whose anchor is hidden redraws as its highest-priority *visible* member and vanishes only when every member is hidden. *(Built 2026-08-13, [#607](https://github.com/OurHike/OurHike/issues/607), and it bit hardest where this sketch did not look: the legend's `onlyType` control. Filtering to privies drew **32 of the trail's 316** — only those that never folded — because the 284 folded ones were gone from the source and their shelters were gone from the map. Three things the sketch did not say. The "Verified?" toggle opens the identical hole through `poiFilter`'s other clause, so the composition takes both, not the hidden set alone. The footer strip lists **drawn** members only — a shelter pin keeping its privy glyph on a map where the hiker turned privies off is the legend-versus-map drift this very section exists to catch. And one residue, stated rather than buried: only `SITE_ANCHOR_TYPES` have member variants in the icon matrix, so a promoted member that is not one of them carries its siblings silently — a water source promoted over a still-visible privy shows no privy glyph. It bounds at the 9 water points that fold corridor-wide, and closing it means widening the matrix rather than changing this rule.)*
- **Search must still find the parts.** `searchPoi` indexes names; `"Mt. Algo Shelter Privy"` must stay findable and must open its site card **on the privy chip**, not on the shelter.
- **The lanes ribbon has a dead control.** `WaypointLanes.tsx` renders each cluster as a `<button>` with no `onClick` — WIREFRAMES.md §1.4's count pill, built but inert. Sites give it the thing it should open.

---

## Water is a data gap, and no display change closes it

The motivating example is a shelter with a campsite, a privy **and a water source**. Three of those four will render. The fourth mostly will not, and it is worth being blunt about why before anyone builds a card that implies otherwise:

- **3%** of shelters have a mapped water source within 60 m. **8%** within 250 m.
- Only 9 water points fold into the 287 sites.
- ATC's shelter layer has **no water field** — all 130 columns checked — and only 29 of 280 shelters mention water, spring or creek anywhere in their free text.
- Every water point the app has comes from opentrail.org: 174 for 2,197 miles.

Nearly every A.T. shelter has water in reality. The app does not know where it is. That is a sourcing problem — OSM `natural=spring` / `amenity=drinking_water` over the corridor, NHD (already flagged exploratory in [../ROADMAP.md](../ROADMAP.md)), or a club-supplied list — and it belongs in its own issue, ahead of any display work that would otherwise render 97% of shelters as having no water when what the app means is that nobody told it.

---

## What this deliberately isn't

- **Not a general clustering layer.** Sites are a modelled fact about facilities, capped at three member types. A crowded ridge of viewpoints is not this doc's problem — it belongs to [POI_VISIBILITY.md](POI_VISIBILITY.md), written the same day as this one by a session that could not see it. *(That doc was rewritten 2026-08-13 and its answer changed: `POI_PRIORITY` decides which of that ridge's viewpoints gets a **pin**, and the ones that lose draw as dots rather than disappearing. The measurements below are what pushed it — at hiking zooms co-location is nearly the whole of the loss, so this doc turns out to be doing most of the work and that one covers the residue.)* **The two are complementary and the boundary is clean: this doc owns several waypoints at one place, that one owns many places across one viewport.** Grouping 1,027 stacked points into 435 sites hands real pin budget back at hiking zooms and changes nothing about a corridor view holding 90 waypoints on a screen with room for 26. That doc's cross-reference table states the split from the other side; this doc's measurements are the evidence under both.
- **Not a zoom-dependent reveal.** Drawing member pins again above z16, where they would no longer collide, is a coherent idea and a second code path with a second set of failure modes. Left out of v1; noted below.
- **Not spiderfy.** Fanning members out around the tapped pin on leader lines preserves the count but draws every member at a position it is not at. This app refuses to draw a stale GPS fix like a live one; drawing a privy 80 px from where it is, is the same refusal.
- **Not a change to `icon-allow-overlap`.** Letting pins overlap is the symptom the complaint started from.
- **Not a new download.** Three properties on features already fetched.

---

## Open questions (for you, not decided here)

1. **Two shelters, one site.** Horns Pond has two lean-tos ~40 m apart and is genuinely one place; elsewhere two shelters that close would be a data error. v1 keeps one anchor per site and lets the second shelter keep its own pin, which is safe and slightly wrong at Horns Pond. Is that the right trade, or should anchor-to-anchor merging be in scope?
2. **Trailheads.** `parking + resupply` (26 clusters) and `parking + privy` (13) are a real second grouping with a different card. Deliberately out of v1 — is it v1.1 or v2?
3. ~~**The pin badge.** Glyph strip or `+N`, settled on a real screen rather than here.~~ **Settled** — see §4. Micro-glyphs rather than `+N`, on badges around the rim rather than in a strip across the disc. The real screen decided it twice: once against a member glyph too small to read ([#604](https://github.com/OurHike/OurHike/issues/604)), and once against the white bar itself ([#611](https://github.com/OurHike/OurHike/issues/611)). What is still open there is narrower and worth carrying forward: a badge says nothing about whether *that privy* is verified, where the rim says it for the anchor.
4. **The 32 unmatched privies** (35 as projected; `group` found three of them). Named for something that is not a shelter or campsite — `"Kennebec Privy"`, `"Bromley Summit Privy"`, `"Guilder Pond Parking Area Privy"` — or distinguished by a word the rule has no reading of: `"Backpacker Campsite Upper Privy"` and `"...Lower Privy"` are two privies at one campsite, and `"501 Shelter Winter Privy"` is a seasonal second one. They keep their own pins, which is honest. Worth a second pass, or leave them?
5. ~~**Site names.** A site anchored on `"Chairback Gap Lean-to Shelter"` shows that name. Does the card say "Chairback Gap" once at the top and let the chips carry the rest, or repeat the full name per member?~~ **Answered by [#526](https://github.com/OurHike/OurHike/issues/526): the heading names the part on screen, and the site is named once on the strip.** The lines underneath the heading decided it rather than any argument about repetition — the coordinates, the unverified sentence and the provenance line all belong to the part being shown, and a privy's coordinates under a shelter's name is exactly the kind of quiet false statement the card exists not to make. The site's own name goes on the chip strip's group label, where it is read once, costs no height, and comes off the anchor chip rather than out of a second field that could disagree with it. Which is also why the card reads nothing from `site_name`: the anchor is in the roster, so its display name is already there.
