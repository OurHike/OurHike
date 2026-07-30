# OurHike — Trip Planning (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). **Builds directly on [SEGMENTS.md](SEGMENTS.md) rather than replacing it** - see "This is not a second hierarchy" below, worth reading first if these two docs seem to overlap.

**Scope note up front:** same as Segments - Post-MVP (Extras), a design ready to build from, not an argument to reprioritize v1.

---

## This is not a second hierarchy

The day → section → thru-hike structure described for this feature is the same Hike → Segment tree [SEGMENTS.md](SEGMENTS.md) already designs - a thru-hiker's "day" and a section-hiker's "day" are both just Segments at whatever depth fits. Worth saying plainly rather than quietly building two competing data models: **Trip Planning is the set of tools that help a hiker fill in and adjust that tree well - it's not a different tree.** Everything below assumes Segments' data model and adds to it, rather than restating it.

## Day-hikers get a lighter front door into the same structure

A day-hiker shouldn't have to think about "hierarchy" at all. The natural entry point: tap waypoints directly on the map (or pick existing POIs) in the order you'll visit them, and the app creates one Segment per leg between consecutive waypoints automatically - trailhead → overlook → summit → back to trailhead becomes 3 Segments without the hiker ever seeing the word "segment." Thru/section-hikers get the fuller planning tools below because they need them; day-hikers get the same underlying model with the simplest possible surface on top of it.

## Bulk plan adjustment

Real plans slip - a zero day, hiking further than planned, weather. The single most valuable operation: **select a Segment and shift it plus every later sibling (and their descendants) by a chosen date delta**, in one action, instead of hand-editing dozens of individual days. That covers the common case (everything after today moves back a day). Bigger restructuring - splitting one long day into two, merging two short ones - is a real need too, but a deeper editing problem worth designing separately once the basic shift operation exists; flagged in open questions rather than solved here.

## Planning assistance: surfacing what's actually along the way

The real planning problem isn't "pick a mileage number" - it's "pick an endpoint that actually has what I need." When a hiker is choosing where a Segment ends, the app should surface what's genuinely nearby using data the pipeline already has:

- **Shelters, water sources, and resupply points within a reasonable window of a candidate endpoint** - all three already exist in the pipeline (ATC shelters/campsites, opentrail.org water/resupply, ATC communities).
- **Shelters near reliable water, specifically called out.** A real, common thru-hiker planning heuristic - camping where water is close by beats a shelter with a long water carry. This is a cheap proximity join (shelter-to-nearest-water distance), and worth **precomputing in the pipeline** as an attribute on each shelter feature, not computed live on the client - matches the existing pattern of shipping a lean, pre-joined dataset rather than raw layers.
- **Carry the existing honesty caveat into planning, not just the live map.** FEATURES.md is already explicit that opentrail.org's water/resupply data is unverified/approximate. A planning tool that says "camp here, water's 200ft away" needs to carry that same "reported, unconfirmed" framing - it'd be worse to be confidently wrong in a planning tool than on the map itself, since a plan gets acted on in advance, away from the actual water source to double-check.

## Difficulty: distance, elevation gain *and* loss, and an honest limit

**Distance** is already computable from existing centerline geometry between two points - nothing new needed.

**Elevation gain/loss and the full profile chart moved into MVP, 2026-07-28 - see FEATURES.md.** Pulled out of this Post-MVP doc on its own, without the rest of Trip Planning, given real competitive weight (FarOut's signature feature) and a genuine safety angle (a big climb ahead affects pacing and daylight decisions, value #4). Worth recording the design correction that happened getting there: the first version of this doc suggested sampling elevation only at the existing centerline mile-marker points (`half_mile_points_from_springer`, every 0.5 mile) via USGS's live point-query API (EPQS) - fine for confirming the data exists, but that sampling density is exactly what makes other apps' gain/loss feel wrong (it misses real small ups-and-downs between sample points, undercounting true total gain). The corrected approach: bulk-download real 1-meter DEM tiles from USGS 3DEP (`prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/` - confirmed to exist on the exact same S3 infrastructure the topo quads already come from) and sample elevation locally, as densely as needed, directly along the actual trail geometry - not sparse live API calls. This also sidesteps the noise problem live phone GPS/barometer-based apps have, since it's surveyed data, not a live sensor reading.

Once this exists as an MVP feature, Trip Planning's job is just to **reuse it per-Segment** - show the same profile/gain-loss/time-estimate for whatever stretch a Segment covers - not redesign elevation handling here.

**A real, standard formula exists for turning distance + elevation into an estimated time** - Naismith's Rule (a base pace per horizontal distance, plus additional time per unit of ascent) is a long-established hiking-planning method, not something to invent from scratch. Worth adopting a well-known formula here the same way this project has preferred established tools over custom ones elsewhere (Ruff over hand-rolled linting, Supabase over hand-rolled auth) - "informational, not prescriptive" per FEATURES.md's own framing of trip planning tools, so it should read as a helpful estimate, not a guarantee. **Extended 2026-07-30:** [PERSONALIZED_PACE.md](PERSONALIZED_PACE.md) keeps Naismith as the base and cold-start default, then layers manual adjustment and on-device learning on top - because the rule is a *comparative* instrument (this stretch is harder than that one) rather than a personal prediction, and it ignores descent and steepness non-linearity entirely.

**Checked, and even accurate elevation data doesn't fully solve "hard because of how the trail was built":** the ATC's own centerline data has a `Surface` field, which looked promising - but the real values are 85%+ "Native Soil or Rock" (2,432 of ~2,850 non-null features), meaning it mostly distinguishes natural tread from pavement/boardwalk/gravel-road crossings, not rocky-and-slow from smooth-and-fast *within* natural trail - which is most of the trail, and exactly the distinction that actually matters here (this is the real, well-known "why is Pennsylvania's rock disproportionately hard despite unremarkable elevation" problem). No existing data source in the pipeline captures this. Two honest paths forward, neither solved in this doc:
- The real long-term fix is probably **hiker-reported difficulty**, feeding off the same reporting infrastructure [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) already establishes - but it needs real report volume to mean anything, the same caution FEATURES.md already applies to water-reliability prediction.
- Until then, ship distance + gain/loss as a genuinely useful estimate, and be explicit in the UI that it doesn't capture tread roughness - honest about the gap (value #4) rather than implying a number solves something it doesn't.

## Open questions (for you, not decided here)

- **Structural bulk-editing** (splitting/merging days, not just shifting dates) - flagged above as a real need, not designed here.
- **Exact "nearby" radius** for surfacing shelters/water/resupply around a candidate endpoint - a real tuning decision once there's a map in front of you, not a data question.
- **Whether hiker-reported difficulty ever becomes its own rating mechanic** (separate from Report a Problem's condition reports) or folds into that system directly - worth deciding once Report a Problem has real usage to learn from.
