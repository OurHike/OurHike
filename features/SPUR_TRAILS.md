# OurHike — Spur Trails (Feature Design Draft v1)

Companion to [TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md), [MAP_OPTIONS.md](MAP_OPTIONS.md), [HIKER_SAFETY.md](HIKER_SAFETY.md) and [../WIREFRAMES.md](../WIREFRAMES.md).

The blue-blazed offshoots that lead from the AT to a water source, a shelter, a privy, a viewpoint or a parking area. A thru-hiker makes this decision a dozen times a day — *is it worth walking down there, and how far back up?* — and today the app draws the line but says nothing about where it goes.

They are not all short. The median is 385 feet, but the longest in ATC's own data is **4.53 miles** — a nine-mile round trip. Nothing in this design gates on length, for reasons set out below.

**Scope note up front: most of this already exists.** The lines are already fetched, already blue, already rendered. What is missing is small and specific, and is named in "The actual gap" below. That framing matters, because the instinct with a feature like this is to build a `Spur` model and a new pipeline stage, and neither is needed.

---

## What the real data already gives us

Confirmed against the live ATC FeatureServer and the real downloaded `side_trails.geojson` (1,200 features), 2026-07-30.

**ATC already classifies spurs.** `side_trails.Type` is a proper ArcGIS coded-value domain, fetched the same way [TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md) fetches `Blaze`:

| code | meaning | features |
|---|---|---|
| `0` | Access (eg Parking) | 192 |
| `1` | Alternate Route | 86 |
| `2` | Significant Non-Blaze | 0 *(see the gotcha below)* |
| `3` | **Spur (eg View, Camp)** | **784** |
| `4` | Other | 58 |
| `5` | Unknown | 5 |

So "which of these is a spur" is a decode, not an inference. That is worth stating plainly because the alternative — guessing from length or geometry — would have been both harder and less accurate than a field the trail's own maintainers fill in.

**Their length spans two orders of magnitude.** Real `Length_Ft` distribution across 1,161 side trails with a length:

| percentile | length |
|---|---|
| p25 | 162 ft (0.03 mi) |
| p50 | 385 ft (0.07 mi) |
| p75 | 1,016 ft (0.19 mi) |
| p90 | 3,257 ft (0.62 mi) |
| p95 | 0.40 mi |
| p99 | 1.31 mi |
| max | **4.53 mi** |

The median is 385 feet and the longest is 4.53 miles — a **62x spread**, with 23 spurs over half a mile and 10 over a mile.

**That range is the design constraint, and it argues against any length threshold anywhere in this feature.** The obvious instinct — "most are tiny, so only bother with the timing estimate on long ones" — gets it backwards at both ends. A 4.53 mi spur is a **nine-mile round trip**, an afternoon's decision that absolutely needs stating. And a 385 ft spur costs nothing to label honestly, so suppressing it buys nothing but an inconsistency the hiker has to learn. Any cutoff would be wrong on one side of itself.

**Length is already measured.** `Length_Ft` is GPS-surveyed by ATC (`GNSS_3DLen` too), so spur distance needs no geometry computation at all.

**The blue is already handled.** [TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md)'s normalized `blaze_color` already renders `side_trails` in their real blaze colour through one shared `match` expression — 641 of them blue. Nothing about spur rendering needs a second mechanism.

### Data-quality gotcha, same shape as the `Blaze` one

60 features carry the literal string `"Signficant Non-Blaze"` in `Type` instead of the code `"2"` — **including the misspelling** (missing `i`, "Signficant"). This is exactly the class of mess `Blaze` already had with its `"Unknown"` and `"Gold"` values, and it must be handled the same way: decode against the real domain, fall through to a documented default for anything that does not decode, and **warn loudly** rather than silently dropping the feature. Sixty dropped side trails would be sixty missing shelter approaches.

## The actual gap

**Nothing connects a spur to what it leads to.** We have spur LineStrings and shelter/water/viewpoint Points, and no relationship between them. So the app can draw a blue line but cannot say "this goes to Rocky Run Shelter, 0.2 mi."

That link has to be computed. Measured on real data — the far endpoint of each `Type=3` spur against all 2,532 shelter/campsite/viewpoint/parking/privy points (n=300 sample):

| | distance to nearest POI |
|---|---|
| p25 | 0 m |
| p50 | **1 m** |
| p75 | 46 m |
| p90 | 199 m |

**231 of 300 within 50 m; 265 of 300 within 150 m.** Half of all spurs end essentially *on* their destination. So a nearest-POI-to-far-endpoint join is not a heuristic that might work — it demonstrably resolves ~88% of spurs.

The remaining ~12% matter too, and are covered under "What happens when it doesn't resolve" below.

## Design

### 1. Resolve the destination at export, not on device

A new `pipeline/export_spurs.py` (or an addition to `export_trails.py` — see open questions) emits, per spur:

```
Spur                      (not a new model - a side_trail with Type=3, enriched)
  id                      the existing stable trail-line id
  blaze_color             already normalized by lib/blaze.py
  length_ft               ATC's own GNSS measurement, not recomputed
  junction_point          the endpoint nearer the AT centerline
  junction_mile           that point snapped to a centerline mile, via
                          MAP_OPTIONS.md's existing ST_LineLocatePoint math
  destination_poi_id      nearest POI to the FAR endpoint, or null
  destination_distance_m  how far that POI actually was - published, not hidden
```

**Computed in the pipeline because it is static.** Spur geometry and POI positions both come from the same periodic ATC refresh; nothing about this changes between refreshes, so resolving it per-device per-launch would be repeated work for an identical answer. It also keeps the client free of a spatial join.

**`destination_distance_m` is published rather than thresholded away** so the client can present a 1 m match differently from a 140 m one, and so a future tightening of the rule does not require a re-export to evaluate.

### 2. Orientation: which end is the junction

The endpoint nearer the AT centerline is the junction; the other is the destination. This is a real computation, not a property of the data — `side_trails` coordinate order is not guaranteed to run away from the trail, exactly as `export_elevation.py` already found for `centerline` segments (its `ordered_oriented_parts()` exists for the same reason).

**Degenerate case worth naming:** a spur that rejoins the AT at both ends is an alternate route, not a spur — and ATC already codes those separately as `Type=1`. If one appears under `Type=3` anyway, both endpoints resolve near the centerline and the destination should come back null rather than picking whichever endpoint won by a metre.

### 3. What the hiker actually sees

**On the map:** unchanged. Blue line, already shipped.

**Tapping a spur** opens the same line-detail sheet [WIREFRAMES.md](../WIREFRAMES.md)'s blaze section already specifies ("tapping any line opens a sheet naming the blaze and its source"), with the spur's own facts added:

> **Blue blaze · spur**
> To **Rocky Run Shelter** — 0.2 mi each way
> ≈10 min down, ≈15 min back
> Joins the AT at mi 1,043.2

**The round trip is the decision, so state both halves.** A hiker at a junction is deciding whether to spend the time, and the walk back up is the part that hurts — spurs to water in particular tend to go *down*. This matters more the longer the spur: the 4.53 mi outlier reads as a pleasant detour until it is stated as nine miles there and back. Reuse [`lib/naismith.ts`](../client/src/lib/naismith.ts) unchanged for both directions; it already refuses to give an arrival clock, and the return leg is exactly where a false precision would be most annoying.

**No length threshold, at either end.** Every spur states its distance and its round trip, whether it is 385 feet or 4.53 miles. Suppressing the line on short spurs would save nothing and make the sheet inconsistent; suppressing it on long ones is unthinkable, since a nine-mile round trip is precisely the case a hiker most needs told. The numbers simply get small on small spurs, which is the correct behaviour rather than a case to special-case.

### 4. What happens when it doesn't resolve

~12% of spurs have no POI within a sensible distance of their far end. Some genuinely lead somewhere unmapped; some lead to a viewpoint or campsite ATC has not digitised.

**The spur is still drawn, and the sheet says what is actually known:** blue blaze, spur, length, junction mile, and no destination line at all. Not "Unknown destination", which reads as a data error rather than the ordinary situation it is — the same restraint [`describeStewards`](../client/src/lib/maintainerLookup.ts) already applies to an unassigned trail section.

## How this composes with what already exists

- **[TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md)** — rendering is already done. This adds no styling.
- **[MAP_OPTIONS.md](MAP_OPTIONS.md)** — its junction disambiguation rule ("a thru/section hike snaps onto `centerline`, a day hike onto whichever line is closest") already anticipates spur junctions exactly. No change needed; this feature just gives that rule better data to work against.
- **[HIKER_SAFETY.md](HIKER_SAFETY.md)** — already flags "extra sensitivity specifically near known `side_trails` junctions, since that's genuinely where a missed blaze turn actually happens" as a real later refinement. `junction_mile` is precisely the data that refinement needs, so this feature is a prerequisite for it rather than a separate thread.
- **[SEGMENTS.md](SEGMENTS.md)** — a segment that detours to a shelter already renders blue for free, per TRAIL_BLAZE_COLORS' own note. Unchanged.
- **Naismith / the elevation ribbon** — reused as-is. A spur's own elevation profile is a genuinely nice-to-have and deliberately not in v1 (see open questions).

## What this deliberately isn't

- **Not a routing feature.** OurHike says a spur exists, where it joins, and roughly how long it takes. It does not navigate down it, and [MAP_OPTIONS.md](MAP_OPTIONS.md)'s closure section already commits to the same restraint for detours.
- **Not a new data model.** A spur is a `side_trail` with `Type=3` and two computed fields. Introducing a `Spur` entity would duplicate blaze normalization, corridor clipping and export plumbing to express one join.
- **Not a filter/toggle.** Blue-blazed spurs are how you reach water. Hiding them is not a setting anyone should want, and the app already has a strong position on hideable safety-relevant layers.

## Open questions (for you, not decided here)

- **How confident a destination match has to be before it is named.** 150 m captures 88% of spurs; 50 m captures 77% with far higher confidence. Note this is about *match quality* — how far the spur's far end sits from the POI it apparently serves — and is unrelated to how long the spur is; a 4.53 mi spur can end a metre from its shelter. Recommend publishing `destination_distance_m` and choosing the display threshold client-side, so the call can change without re-exporting, but the actual number wants a look at real mismatches rather than a percentile.
- **Which POI types count as destinations.** The measurement above pooled shelters, campsites, viewpoints, parking and privies. A privy is a real destination but a strange thing to name as one; parking is arguably an "Access" (`Type=0`) concern rather than a spur one.
- **Whether `Type=0` (Access, 192 features) deserves the same treatment.** Parking approaches behave like spurs and would benefit identically, but "spur to a road" is a different decision from "spur to water" and may want different copy.
- **Spur elevation profiles.** `export_elevation.py` samples the centerline only. Sampling spurs too would let the sheet say "0.2 mi, 180 ft down" — which is the honest version of the decision a hiker is making, since the descent is the hidden cost. Real work, not free, and not v1.
- **Whether this is MVP.** The rendering half already ships. The destination link is a contained pipeline addition on data we already hold — small enough to argue for MVP, but it is a scope call, not a technical one.
