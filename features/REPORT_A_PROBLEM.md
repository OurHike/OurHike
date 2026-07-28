# OurHike — Report a Problem (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Fleshes out FEATURES.md's existing "hiker-submitted condition reports" line (Community reporting, values #2/#4) with the concrete shape described: report types, location mechanism, and a path toward richer follow-up over time.

**Scope revised 2026-07-28: moved into v1 MVP.** Originally scoped Post-MVP like [SEGMENTS.md](SEGMENTS.md) and [VOLUNTEERING.md](VOLUNTEERING.md), and for the same reason this feature always needed the Phase 2+ backend that Segments (entirely client-side) and Volunteering (map display can run off a static file) didn't. What changed: [MAP_OPTIONS.md](MAP_OPTIONS.md)'s trail closures and [HIKER_SAFETY.md](HIKER_SAFETY.md)'s serious warning pins both reuse this exact moderation-queue mechanism to get verified/escalated - once those two moved into MVP, building the queue narrowly for just them would have cost nearly as much as building the real thing, so the full six-report-type feature ships as MVP too, rather than the plumbing getting built twice.

---

## The core flow

A hiker taps **Report a Problem** and:

1. **Picks a location** - either an existing map point (a shelter, water source, any POI already shown), or a custom spot: drop a pin, or use current GPS location. This is the same anchoring pattern [SEGMENTS.md](SEGMENTS.md) already uses for segment boundaries - reuse it rather than inventing a second way to pin a place on the map.
2. **Picks a problem type** from a fixed set (below).
3. **Adds whatever detail they have** - v1 is just a note and an optional photo (matching FEATURES.md's existing "text + photo, timestamp + reporter type" line). Structured, type-specific follow-up questions come later - see "Follow-up info, phased" below.
4. The report enters the **moderation queue for club admins** and the **maintainer verification/flagging workflow** - both already planned in FEATURES.md, not new here.

## Problem types

**Blow downs, trash, flooding, shelter repair, animals** are all trail/infrastructure conditions - low-risk to show on the map quickly once verified, the same way a condition report about a water source already works.

**"Bad hikers" needs different handling, flagged explicitly.** This category reports on *people*, not trail conditions - a meaningfully different risk profile:

- It's the one category where a false, exaggerated, or malicious report can cause real harm to a specific person - closer to a harassment vector than a condition report, and value #4 ("trustworthy above all") cuts the other way here: getting this wrong is worse than not having it.
- Recommendation: **this category shouldn't become a public map pin at all.** Route it privately to club maintainers/moderators as an incident note, not a visible marker - the safety-awareness principle already in value #9 ("any feature that connects people needs clear expectations... no incentives to overshare") applies just as much to reporting *on* people as connecting *with* them.
- Whatever exact handling is chosen, it deserves a real moderation conversation before it ships - not a default inherited from the other five types.

## Follow-up info, phased (per your "eventually")

v1 doesn't need type-specific fields - type + location + note + optional photo is enough to be useful and to route into the existing moderation workflow. Structured follow-up is a natural incremental add once there's real report volume to see what's actually missing, e.g.:

- **Animals:** species, count, distance/behavior (fed near a shelter? aggressive? just sighted?)
- **Flooding:** still passable? approximate depth?
- **Blow down:** passable around it, or fully blocking the trail?
- **Shelter repair:** which part (roof, floor, privy, water source nearby)?

None of this needs designing now - the data model just needs room to add per-type fields later without a schema rewrite (see below).

## Data model sketch

```
Report
  id
  type: blowdown | trash | bad_hikers | flooding | shelter_repair | animals
  location reference:
    - existing POI id, OR
    - a dropped/GPS pin (lat/lon)
  reporter_type (thru-hiker / section-hiker / day-hiker / maintainer -
                 FEATURES.md's existing "reporter type shown" line)
  timestamp
  note (free text, optional)
  photo (optional)
  follow_up (type-specific structured fields - empty in v1, additive later)
  status: submitted | verified | resolved | dismissed
  visibility: public | internal-only (bad_hikers defaults to internal-only - see above)
```

## Architecture fit

This is the reason a live backend is now part of v1 MVP at all, not just a Phase 2+ nicety. Segments is entirely client-side; Volunteering's more important half (map display) can run off a static, pipeline-fed file. Report a Problem is inherently dynamic, submitted-by-many-people data that needs moderation before anything becomes visible to other hikers - that's a live backend + database (FastAPI/Postgres, see TECHNICAL_ARCHITECTURE.md's revised Backend section), not something the static PMTiles/GeoJSON pipeline can produce. This feature and the backend that makes it possible are the same milestone, now both MVP.

## Open questions (for you, not decided here)

- **"Bad hikers" handling.** Recommended above as internal-only/non-public, but the exact routing (does it go to the nearest club, a general moderation inbox, both?) is a real decision, not a data-model detail.
- ~~**Minimal identity for reporters.**~~ **Resolved 2026-07-28:** [AUTHENTICATION.md](AUTHENTICATION.md) is now MVP too, built specifically so this doesn't need its own bespoke device-local identity scheme - real accounts exist by the time this feature ships.
- **How "verified" actually happens.** FEATURES.md already plans a maintainer verification/flagging workflow in the abstract; this feature is what gives it real content to verify. Worth designing them together rather than this doc assuming a workflow that doesn't exist yet.
- **Possible future extension:** [TRIP_PLANNING.md](TRIP_PLANNING.md) wants hiker-reported trail difficulty (rocky/rough tread that elevation data alone doesn't capture) and floats this reporting infrastructure as the natural home for it, once there's real report volume to learn from - not designed here, just noted so it isn't invented twice.
- **Related:** [MAP_OPTIONS.md](MAP_OPTIONS.md)'s trail-closure feature reuses this doc's moderation-queue pattern directly (a closure is functionally a condition report that renders as a line instead of a pin) rather than building a second review workflow.
- **Related:** [HIKER_SAFETY.md](HIKER_SAFETY.md) adds a moderator-escalated `severity` tier on top of the report types here (bear sightings under `animals`, dangerous humans under `bad_hikers`), and directly names the "bad hikers" handling above as needing the real moderation-policy conversation this doc already deferred - now with an actual feature waiting on the answer.
- **Related:** [DATA_NUDGES.md](DATA_NUDGES.md) adds a `last_reconfirmed_at` field to the `Report` model above (a fast "still there?" tap that refreshes it without changing `status`, distinct from a "resolved" tap that does), and introduces a separate, lighter `ConditionConfirmation` model for confirmations that were never a problem report to begin with - renamed 2026-07-28 from its original `ConditionCheckIn` to avoid colliding with Community Building's unrelated `CheckIn` (location-sharing) model.
