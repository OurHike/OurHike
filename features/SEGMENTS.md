# OurHike — Segments (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Describes a proposed feature letting hikers break a hike into a personal, hierarchical set of pieces — and mark them done as they go.

**Scope note up front:** FEATURES.md currently places trip-planning tools under **Post-MVP / Extras**, not the v1 core map app. This document specs the feature so it's ready to build when that time comes, and doesn't assume it's jumping the v1 queue — see "Where this fits" at the end.

---

## The core idea

A **Hike** is the thing a user is planning or doing — a thru-hike, a section-hike, or a day-hike. A **Segment** is a piece of that Hike. Segments can contain other Segments, to whatever depth a user actually wants. There's no fixed unit — "a segment" is just *the next meaningful chunk of trail someone is thinking about*, and what counts as meaningful depends entirely on the scale of the Hike it belongs to.

That's the one mechanism this whole feature rests on: **a Hike is the root of a Segment tree, and a Segment is a node that can have child Segments.** Everything below — the day-hiker/section-hiker/thru-hiker framing — is just different ways people will naturally use that same tree, not different data models.

## How each persona actually uses it

- **Thru-hiker.** The Hike spans the whole trail (Springer to Katahdin, or vice versa). A "segment" is naturally *the plan for one day* — so the top level of the tree is usually ~150-200 day-sized Segments. Someone who wants a coarser view first can add an optional middle tier (by state, or by resupply stretch) and nest the daily Segments underneath — the tree doesn't care, it's the same mechanism at another depth.
- **Section-hiker.** Structurally identical to a thru-hiker — a Hike broken into daily Segments — just scoped to whatever portion of the trail they're actually doing, not the whole thing. Worth noticing there's no real difference between "thru-hike" and "section-hike" other than the Hike's overall start/end; both are "days" all the way down.
- **Day-hiker.** The Hike *is* a single day. A "segment" here means something smaller than a day — a leg between landmarks (trailhead → overlook → summit → back to trailhead). Shallow tree, small number of children, no day-level nesting needed at all.

None of this is enforced by the data model — it's a convention the app can *suggest* (see "Persona-driven defaults" below) but never require, per the user's own framing: customizable to what the hiker actually needs.

## Data model

```
Hike
  id, name, type (thru | section | day) — type is a label/default-suggestion, not a constraint
  trail reference (which centerline this hike is on - see "inheritability" below)
  overall start reference, overall end reference
  planned_start_date (optional - thru-hikers plan loosely, this will shift)

Segment
  id, hike_id
  parent_segment_id (null = top-level, directly under the Hike)
  order (position among sibling segments)
  name (user-editable; app can suggest "Day 4" or "Leg 2" as a starting point)
  start reference, end reference
  planned_date (optional)
  completed_date (set when marked done)
  children: [Segment]  (recursive - same shape all the way down)
```

**Start/end references should point at real trail geography, not free text.** The pipeline already has exactly what's needed for this: the centerline mile-marker points (`half_mile_points_from_springer`, 4,395 points), shelters, campsites, and parking/road-crossing POIs. A Segment's boundary should be one of these — or, if nothing fits, a point the user drops on the map — but always something with real coordinates. This is what makes "completed" mean something concrete (value #4, trustworthy above all) rather than a vague checkbox next to a text label.

## Completion — deliberately simple, not gamified

- **Leaf Segments are marked complete manually**, by the user, when they've actually done that stretch. (A nice-to-have for later: suggest marking it done when GPS shows the user has passed the segment's end point — not required for v1 of this feature.)
- **Parent Segments are never marked complete directly.** Their status is *derived* from children — e.g. "6 of 14 days done" — and a parent only reads as fully complete when every descendant actually is. This avoids the contradictory states you'd get from letting both a day and its parent week be marked independently.
- **This stays a personal record, not a performance.** Value #1 explicitly warns against "prescriptive gamification" — no streaks, no badges, no comparing progress to other hikers, no public profile. It's the digital equivalent of a hiker's own paper log: useful to them, invisible to everyone else, and inherently value-aligned since a hiker only ever loses to no one but themselves for skipping a day.

## Where this data actually lives

FEATURES.md's current plan is a **no-account-needed PWA** — fast onboarding, no signup wall. Segments and completion state fit that directly: store them client-side, in the same IndexedDB the offline map cache already uses (per TECHNICAL_ARCHITECTURE.md's client section). No backend, no accounts, nothing new to run or pay for (value #8) — a hiker's plan just lives on their device, same as their downloaded map data.

**Known trade-off worth naming now, not discovering later:** this means no cross-device sync without introducing accounts, which is a bigger, separate decision (and would connect to the multi-club/backend work already flagged as Phase 2+ in TECHNICAL_ARCHITECTURE.md). Fine for v1 of this feature; worth being upfront that "plan on my phone, check on my laptop" isn't included unless that tradeoff gets revisited deliberately. **Update 2026-07-28:** that revisit now has a real answer - see [AUTHENTICATION.md](AUTHENTICATION.md), scoped as the first Post-MVP feature to build, partly for this exact reason.

**Export should reuse the format FEATURES.md already commits to.** "User data export (routes, saved hikes) in open formats (GPX/GeoJSON/CSV)" is already a Post-MVP line item (value #6 — belongs to the trails, not the platform). A Hike and its Segments map onto that cleanly: each Segment as a GeoJSON `LineString` feature (or a GPX track segment) along the centerline between its start/end references, with `name`/`status`/dates as properties. Building Segments with this in mind means the export item isn't a separate design problem later — it's the same data, serialized differently.

## Inheritability check (value #7)

Nothing here should assume "the Appalachian Trail" specifically — a Hike references *a* trail centerline, and Segment boundaries reference *that* trail's own mile-markers/POIs. The moment a second club's trail data exists in the same schema, Segments work for it identically. Worth keeping in mind if/when the "trail reference" field above gets implemented — it should point at a trail id, not assume there's only ever one.

**Related:** [TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md) - since Segments already tie to real trail-line geometry, a planned hike's segments can render in their real blaze color for free, with no changes needed here. **Update 2026-07-28:** [MAP_OPTIONS.md](MAP_OPTIONS.md) upgrades the "user drops a pin" boundary case above - instead of storing the raw tapped coordinate, it snaps onto the nearest point on real trail geometry (DuckDB's `ST_LineLocatePoint`/`ST_LineInterpolatePoint`), and uses this doc's `Hike.type` field to prefer the main centerline over a side trail for thru/section hikes. [HIKER_SAFETY.md](HIKER_SAFETY.md) reuses the same snap-to-trail math again for its off-trail alert, and reads a Hike's overall start/end reference directly to know which direction is "the wrong way." [DATA_NUDGES.md](DATA_NUDGES.md) flags (not fully designed yet) that marking a day's Segment complete at a shelter could piggyback on the same moment as its overnight condition check-in, one interaction instead of two. [COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md)'s Tramily feature shares a Hike directly with other accounts rather than inventing a second route structure to share. [PRICING_MODEL.md](PRICING_MODEL.md)'s thru-hike pass reads this doc's `Hike.type` field directly to scope itself to a whole-AT attempt.

## Where this fits

FEATURES.md's v1 MVP is deliberately narrow (trail line, water, crossings, shelters/campsites, resupply, GPS, search) and explicitly defers "trip planning tools" to Post-MVP/Extras. This document doesn't argue that should change — it's here so that when trip planning *does* get picked up, there's a real design to build from instead of starting cold. If/when it's time to schedule this, FEATURES.md's "Extras" section is the natural place to expand past its current one-line mention, and a ROADMAP.md Phase 2+ (or later) item would track the actual build.

**Update 2026-07-28:** [TRIP_PLANNING.md](TRIP_PLANNING.md) is that build - waypoint-based day-hike planning, bulk multi-day adjustment, POI-aware planning assistance, and a distance/elevation difficulty estimate, all built on top of the Hike/Segment tree here rather than a second structure.

**Update 2026-08-05:** and it is now scheduled - **v2's first feature**, spiked in [HIKE_PLANNING.md](HIKE_PLANNING.md). That spike checked this document's tree against everything a multi-day plan actually needs and concluded it holds without a second model: a **zero day is a Segment whose start and end are the same stop**, needing no `kind` field, and a **section is derived from where resupply happens** rather than hand-built - which answers the persona-driven-templates question below with "generate days from the route and the target, then group them by where supplies come from." It adds three fields to `Segment` (a stop reference, a `pinned` flag and a `generated` flag) and changes nothing here.

## Open questions (for you, not decided here)

- **Naming.** "Hike" and "Segment" are working names, not committed terminology — easy to change before anything's built.
- **Completion granularity.** This doc assumes a simple done/not-done per leaf Segment. A richer `not-started / in-progress / completed` state is a small extension if partial-day tracking ever matters.
- **Whether boundaries must be real geographic references.** Recommended above for trustworthiness, but a looser "just name your segments, no map pins required" version is simpler to build first and could be a deliberate v0 within this feature.
- **Persona-driven templates.** Should picking "thru-hike" at Hike creation auto-generate ~180 empty daily Segments to fill in, or start empty and let the user add them as they plan? Either is consistent with the data model; it's a pure UX call.
