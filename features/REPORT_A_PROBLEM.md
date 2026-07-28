# OurHike — Report a Problem (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Fleshes out FEATURES.md's existing "hiker-submitted condition reports" line (Community reporting, values #2/#4) with the concrete shape described: report types, location mechanism, and a path toward richer follow-up over time.

**Scope note up front:** like [SEGMENTS.md](SEGMENTS.md) and [VOLUNTEERING.md](VOLUNTEERING.md), this is Post-MVP (Community reporting) - a design ready to build from, not an argument to reprioritize v1. Unlike those two, though, this feature **can't ship without the Phase 2+ backend** - see "Architecture fit" below.

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

This is the first of the three new feature designs (alongside Segments and Volunteering) that **requires the Phase 2+ backend to exist at all**, not just to reach its full version. Segments is entirely client-side; Volunteering's more important half (map display) can run off a static, pipeline-fed file. Report a Problem is inherently dynamic, submitted-by-many-people data that needs moderation before anything becomes visible to other hikers - that's a live backend + database (FastAPI/Postgres, already planned in TECHNICAL_ARCHITECTURE.md), not something the static PMTiles/GeoJSON pipeline can produce. Worth having front of mind when sequencing Phase 2+ work: this feature and the backend that makes it possible are the same milestone, not two separate ones.

## Open questions (for you, not decided here)

- **"Bad hikers" handling.** Recommended above as internal-only/non-public, but the exact routing (does it go to the nearest club, a general moderation inbox, both?) is a real decision, not a data-model detail.
- **Minimal identity for reporters.** No accounts exist yet in the current plan - but *some* way to rate-limit/prevent spam and support the "reporter type" field probably needs at least a lightweight, anonymous-but-distinguishable identity (e.g. a device-local id), short of full user accounts. Worth deciding alongside whatever else eventually needs one (Segments' cross-device sync raised the same fork). **Update 2026-07-28:** [AUTHENTICATION.md](AUTHENTICATION.md) is designed to be built first, specifically so this doesn't need its own bespoke identity scheme.
- **How "verified" actually happens.** FEATURES.md already plans a maintainer verification/flagging workflow in the abstract; this feature is what gives it real content to verify. Worth designing them together rather than this doc assuming a workflow that doesn't exist yet.
- **Possible future extension:** [TRIP_PLANNING.md](TRIP_PLANNING.md) wants hiker-reported trail difficulty (rocky/rough tread that elevation data alone doesn't capture) and floats this reporting infrastructure as the natural home for it, once there's real report volume to learn from - not designed here, just noted so it isn't invented twice.
