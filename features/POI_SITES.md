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

And the membership is restricted, not universal:

- **Anchors** are `shelter`, then `campsite`. Exactly one per site.
- **Members** are `privy`, `campsite`, `water`.
- `viewpoint`, `parking` and `resupply` are **never** members in v1. They are co-located with each other and with shelters, but they are not *parts of* a facility — the 64 viewpoint pairs above are the proof, and "parking + resupply" is a trailhead, which is a different feature with a different card.

Running that rule over the real corridor:

```
427 POIs fold into 287 sites (249 shelter-anchored, 38 campsite-anchored)
  folded: 281 privies, 137 campsites, 9 water
  sizes:  159 sites of 2, 119 of 3, 6 of 4, 3 of 5
  150 sites are shelter + privy
  119 sites are shelter + campsite + privy
```

**281 of 316 privies (89%) stop competing for a pin and start riding one that is drawn** — a shelter pin, which places at 91% at z14 and 95% at z15. Against the 3% drawn today, that is the whole of the fix.

### 3. What publishes

Three properties on the POI features `export_poi.py` already writes, not a new artifact:

| property | on | meaning |
|---|---|---|
| `site_id` | every member and the anchor | the anchor's own POI id |
| `site_role` | every member and the anchor | `anchor` or `member` |
| `site_name` | every member and the anchor | the anchor's display name |

A separate `sites.json` was considered and rejected: it would be a second fetch, a second thing `verify_release.py` has to know about, and the client would still need the members. Properties are additive — a client built before this ignores them and behaves exactly as it does today, which is the same backward-compatibility rule `mile`, `capacity`, `description` and `photos` are already held to in `PoiDetail`.

The client groups by `site_id` on load. That is a `Map` build over ~2,800 records, once.

### 4. On the map: one pin, carrying its composition

A site draws **one pin, at the anchor's coordinates, in the anchor's accent and glyph.** A shelter still looks like a shelter; nothing about the existing icon work is discarded. Members draw no pin of their own.

The pin has to say that it stands for more than itself, and there are two ways to do it:

- **A `+N` badge.** Cheap, legible at 38 px, and says nothing about *what*.
- **A footer strip of two or three micro-glyphs.** Answers "is there a privy" without a tap, which is the actual question, and costs legibility at 38 px.

**Recommended: the glyph strip, prototyped against the contrast assertions already in `poiIcons.test.ts`, falling back to `+N` if it cannot clear them.** The recommendation is soft on purpose — this is the one decision in this document that wants a look at a real screen in real sunlight ([#105](https://github.com/OurHike/OurHike/issues/105)) before it is settled.

What this does *not* do is change `icon-allow-overlap`. Sites remove the pins that were colliding rather than permitting overlap; the collision engine keeps doing its job on what is left, and `POI_PRIORITY` keeps deciding a genuinely crowded ridge. Two shelters 400 m apart still collide at z12, correctly.

### 5. On the card: chips that are also the tabs

Under the name, a row of chips — `Privy · 40 m`, `Campsite · 25 m`, `Water · 90 m` — and tapping one swaps the card body to that member's own detail: its photo and gallery, its description, its coordinates, its unverified line.

One control doing two jobs, and the reason to prefer it over a plain tab strip: **the chip's existence is usually the whole answer.** A hiker wants to know there is a privy, not to read the privy's card. Tabs hide that behind a tap; chips answer at a glance and still lead somewhere.

This is not a new idiom. [WIREFRAMES.md §4](../WIREFRAMES.md) was amended on 2026-08-06 ([#298](https://github.com/OurHike/OurHike/issues/298)) to put the download window's sheets under tabs, and the reasoning there transfers exactly — "a stack reads as a list of things to work through rather than as alternatives to choose between". `client/src/screens/Tabs.tsx` exists; reuse it or its pattern rather than inventing a second one. Its rule carries too: **one panel rendered, not three hidden with CSS**, so a hidden member's gallery buttons are not in the tab order or being announced.

Two mechanical gotchas, both already visible in the current code:

- `usePinAnchor` depends on `[map, poi, card]` with a comment explaining that a late-arriving mile changes the card's *height* and a stale measurement leaves a flipped card overlapping its pin. Switching chips changes the height far more than a mile does. The effect has to re-run on the selected member, not only on the POI.
- The chip strip is tapped with a gloved thumb, so `--min-touch-target` applies to each chip. Four chips at 44 px fit a 320 px card; five do not, and the largest real site has five members. The strip scrolls horizontally or the card widens — a decision for whoever builds it, against a real device.

### 6. What a site model quietly breaks

Four things, each small, each a lie on the map if it is missed:

- **The legend counts what is not drawn.** `computeLegendContents` counts every POI in the viewport. With sites, "Privy 3" appears beside a map with no privy pin — and `poiLayers.ts`'s header comment makes "the legend names exactly what is drawn" a structural property of the one-layer design rather than a convention. The count should stay (a hiker wants to know there are three privies ahead) but the row has to be honest about where they are.
- **Hiding a type takes its members with it.** `poiTypeFilter` filters on `poi_type`. Hide shelters and the site pin goes, taking the privy and the campsite that were riding it. The fix is not a cleverer filter expression: rebuild the site features in JS when the hidden set changes and `setData` again — 2,800 points, trivial — so a site whose anchor is hidden redraws as its highest-priority *visible* member and vanishes only when every member is hidden.
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

- **Not a general clustering layer.** Sites are a modelled fact about facilities, capped at three member types. A crowded ridge of viewpoints is still the collision engine's problem and `POI_PRIORITY` is still its answer — and that problem now has a doc, [POI_VISIBILITY.md](POI_VISIBILITY.md), written the same day as this one by a session that could not see it. **The two are complementary and the boundary is clean: this doc owns several waypoints at one place, that one owns many places across one viewport.** Grouping 1,027 stacked points into 435 sites hands real pin budget back at hiking zooms and changes nothing about a corridor view holding 90 waypoints on a screen with room for 26. That doc's cross-reference table states the split from the other side; this doc's measurements are the evidence under both.
- **Not a zoom-dependent reveal.** Drawing member pins again above z16, where they would no longer collide, is a coherent idea and a second code path with a second set of failure modes. Left out of v1; noted below.
- **Not spiderfy.** Fanning members out around the tapped pin on leader lines preserves the count but draws every member at a position it is not at. This app refuses to draw a stale GPS fix like a live one; drawing a privy 80 px from where it is, is the same refusal.
- **Not a change to `icon-allow-overlap`.** Letting pins overlap is the symptom the complaint started from.
- **Not a new download.** Three properties on features already fetched.

---

## Open questions (for you, not decided here)

1. **Two shelters, one site.** Horns Pond has two lean-tos ~40 m apart and is genuinely one place; elsewhere two shelters that close would be a data error. v1 keeps one anchor per site and lets the second shelter keep its own pin, which is safe and slightly wrong at Horns Pond. Is that the right trade, or should anchor-to-anchor merging be in scope?
2. **Trailheads.** `parking + resupply` (26 clusters) and `parking + privy` (13) are a real second grouping with a different card. Deliberately out of v1 — is it v1.1 or v2?
3. **The pin badge.** Glyph strip or `+N`, settled on a real screen rather than here.
4. **The 35 unmatched privies.** Named for something that is not a shelter or campsite — `"Kennebec Privy"`, `"Grafton Notch Parking Area Privy 2"`. They keep their own pins, which is honest. Worth a second pass, or leave them?
5. **Site names.** A site anchored on `"Chairback Gap Lean-to Shelter"` shows that name. Does the card say "Chairback Gap" once at the top and let the chips carry the rest, or repeat the full name per member?
