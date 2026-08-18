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

**Update 2026-08-18:** the tree now has a screen. The Plan tab carries **three zooms — Hike → Trip → Days** (#790), which is this document's sentence about Segments holding Segments rendered as a control rather than as a second model. The Days zoom is the timeline that already shipped and is unchanged; the Trip zoom is the "optional middle tier … by resupply stretch" named above, derived from where resupply happens rather than stored; the Hike zoom lists a hike's trips **and the gaps between them**, because a zoom that showed only what had been walked would be a list of achievements, which is the thing the "not gamified" section above exists to prevent.

Three things worth carrying rather than rediscovering:

- **Gaps are derived, never stored** — the complement of what the trips cover, recomputed on every read, so a gap cannot go stale against the record it describes. Same discipline as "parent Segments are never marked complete directly".
- **A gap ROW and "what is left to walk" are not the same set.** A trip on the calendar closes nothing until it is walked, so it stays in the miles-to-go figure; it still gets its own row rather than being buried under a gap row saying the same ground twice. The rows split what is left into "you have a plan for this" and "you have nothing here" — which is the split a hiker deciding what to do next is actually making.
- **The ribbon above the rows is an orientation, not a measuring device.** A phone-width ribbon carrying 2,197 miles is roughly 7½ miles per pixel, so a three-day trip is eight pixels: every figure stays in the rows underneath, where it can be read. Its job is "where in this hike am I looking", plus scrubbing to somewhere else.

The Plan tab's anti-gamification guard — no rendering of any plan may contain a percentage, "behind", "ahead of", "on track" or a streak — is held by a test, and now covers these surfaces too. They show far more of a plan than the timeline does, which makes them where a score would arrive uninvited.

**Update 2026-08-18, later the same day:** the gaps got their own screen (#791) — **What's left**, reached from the hike zoom. Three decisions in it are worth keeping:

- **Both ends of every gap are start candidates**, offered side by side, and the direction falls out of which one is picked. Nothing new is stored: the route builder already derives which way a route walks from its own ends. Flip-floppers are the design rather than an edge case, so nothing on the screen calls a piece "next", numbers the cards, or draws them as steps — trail order is one *sort*, offered beside "nearest me" and "fits my days".
- **A sort that cannot be computed honestly is not offered.** No fix, no "nearest me" — rather than a "nearest" that is quietly trail order.
- **The sliver question is settled the way this document's own instincts point.** Gaps under 0.2 mi (`MIN_GAP_MI`, tagged `@unvalidated`) get no card, because a 0.1-mile card makes the screen look broken — and the remainder is counted and printed anyway: "1 short stretch adding up to 0.1 mi… still trail nobody has walked." Neither extreme chosen silently.

**Update 2026-08-18, third:** two things this document did not have a shape for, both from a maintainer walkthrough of the built screens.

**A rest rhythm** (#798). A plan can carry *a zero or a nearo every n walking days*, stored on the plan so a re-lay reproduces it rather than throwing away the seven zeros somebody added by hand. A zero needs nothing new — this document already says a zero is a Segment whose start and end are the same stop — and a **nearo** is a rest that walks to the first place to sleep inside a window, falling back to a zero where there is none and saying which it is. The rhythm has no opinion attached: nothing suggests one, warns about its absence, or counts the rests taken.

**Groups** (#800), which are **not** hikes, and the distinction is worth keeping sharp because the two look alike in a list. A Hike has two ends; that is what makes #790's ribbon and #791's gaps mean anything. A group — "every Sunday", "with Dad", "2026 season" — has none. So a trip has **at most one hike** (its parent in this document's tree) and **any number of groups**, settled by the case that forces it: the same walk is in *the entire AT* and in *my section this year*. A group's screen therefore has no ribbon and no gaps, and says so rather than leaving a hole where they would be.

## Open questions (for you, not decided here)

- **Naming.** "Hike" and "Segment" are working names, not committed terminology — easy to change before anything's built.
- **Completion granularity.** This doc assumes a simple done/not-done per leaf Segment. A richer `not-started / in-progress / completed` state is a small extension if partial-day tracking ever matters.
- **Whether boundaries must be real geographic references.** Recommended above for trustworthiness, but a looser "just name your segments, no map pins required" version is simpler to build first and could be a deliberate v0 within this feature.
- **Persona-driven templates.** Should picking "thru-hike" at Hike creation auto-generate ~180 empty daily Segments to fill in, or start empty and let the user add them as they plan? Either is consistent with the data model; it's a pure UX call.
