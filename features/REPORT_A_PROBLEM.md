# OurHike — Report a Problem (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Fleshes out FEATURES.md's existing "hiker-submitted condition reports" line (Community reporting, values #2/#4) with the concrete shape described: report types, location mechanism, and a path toward richer follow-up over time.

**Scope revised 2026-07-28: moved into v1 MVP.** Originally scoped Post-MVP like [SEGMENTS.md](SEGMENTS.md) and [VOLUNTEERING.md](VOLUNTEERING.md), and for the same reason this feature always needed the Phase 2+ backend that Segments (entirely client-side) and Volunteering (map display can run off a static file) didn't. What changed: [MAP_OPTIONS.md](MAP_OPTIONS.md)'s trail closures and [HIKER_SAFETY.md](HIKER_SAFETY.md)'s serious warning pins both reuse this exact moderation-queue mechanism to get verified/escalated - once those two moved into MVP, building the queue narrowly for just them would have cost nearly as much as building the real thing, so the full six-report-type feature ships as MVP too, rather than the plumbing getting built twice.

---

## The core flow

**Revised 2026-08-27 (#1133) to describe what shipped.** The four steps below
are what this section said, and the order is what changed: the flow asked for a
location, then a type, then detail, then filed. It now files on the type and
asks for the rest afterwards. Both versions are recorded because the argument
for the change is entirely in the difference.

A hiker taps **Report a problem** — from Today's foot, from a place's card, or
from the map — and:

1. **The window opens over whatever they were looking at**, rather than
   replacing it. It is a dialog, not a route: the screen behind it stays, so
   nobody loses their place to file a blow-down.
2. **Where the report is going is stated, not asked.** Every entry point
   supplies an anchor — the place's card knows the place, the map's long-press
   knows the point, Today knows the fix. A `Change` control re-anchors to a
   place today's walked miles covered, for the one case the stated anchor gets
   wrong: something noticed and remembered a mile later.

   **The hiker is standing at it, except when they are not.** Press and hold
   (#1137) is the entry point that broke that assumption: it anchors wherever
   the finger landed, which may be fifteen miles up the trail. So an anchor
   that carries no mile no longer borrows the hiker's — a report filed at a
   pressed point with the fix's mile printed over it is a position claim that
   resolves to somewhere real and wrong, which is worse than no mile at all.
   Off the corridor the report keeps its coordinates and drops the mile, which
   is what the data model below has always allowed ("Null off-trail").
3. **One tap on a type files the report**, into the outbox, at once. There is
   no submit button and nothing to abandon.
4. **An 8-second `Undo` stands where the Cancel used to.** The report is held
   in the outbox for that window rather than sent, so taking it back is a
   delete of something never transmitted, not a withdrawal of something
   published.
5. **Detail is optional and comes after.** A note, and a photo, on the receipt
   — the same fields, no longer in the way of the thing a hiker actually came
   to do.
6. The report enters the **moderation queue for club admins** and the
   **maintainer verification/flagging workflow** — both already planned in
   FEATURES.md, unchanged by any of the above.

**Two types never file on a tap**, and this is the load-bearing exception
rather than a detail: a **closure** needs two miles, and **something unsafe
happened** is a report about a person that routes privately to moderators
(see "Problem types" below). Both open a form. `reporting/categories.ts` states
that rule negatively — a type added later defaults to *not* filing — because a
new type quietly inheriting one-tap filing is the wrong direction to fail in.

**What the old ordering cost, which is why this changed.** Asking for a
location first is the right shape for a report filed at a desk and the wrong
one for a report filed standing in front of the problem, where the location is
the thing the phone is most sure of and the hiker is least interested in
confirming. Three screens of ceremony before anything is recorded is three
chances to give up, in weather, one-handed, on a phone with one bar.

**What it is not**, and the cost this change accepts: a tap is now
unrecoverable after eight seconds without an edit path. That is a real trade
and the `Undo` is the whole of the mitigation. It was chosen over a confirm
step because a confirm step is the ceremony this change exists to remove, and
over an indefinite edit window because a report already in a club's queue is
not the app's to silently rewrite.

## Problem types

**Blow downs, trash, flooding, shelter repair, animals, invasive species** are all trail/infrastructure conditions - low-risk to show on the map quickly once verified, the same way a condition report about a water source already works.

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
- **Invasive species:** which species (if known), rough extent, spreading or contained?

None of this needs designing now - the data model just needs room to add per-type fields later without a schema rewrite (see below).

## Invasive species (added 2026-07-30)

An eighth type, for problem plants or animals disrupting the local environment
- hemlock woolly adelgid, Japanese knotweed, feral hogs. A hiker submits a
description, photos, location and whatever else they noticed, exactly like any
other condition report; nothing about the shape of the report is special.

**Why it is not folded into `animals`.** That type is scoped to *safety*
encounters - [HIKER_SAFETY.md](HIKER_SAFETY.md) uses it for bear sightings and
escalates it to `severity: serious` when a moderator confirms a pattern. An
invasive report is an *ecological* observation with no personal-risk dimension:
knotweed is not dangerous to the hiker who reported it, and routing it through
the same type would mean either diluting the safety signal or treating a plant
sighting as a hazard.

**The real overlap, worth naming.** Some invasives *are* animals, and some are
genuinely a safety concern - a feral hog is both. A hiker could reasonably pick
either type, so the two need distinguishing at the point of choice rather than
in a data dictionary nobody reads: `animals` is for an encounter that worried
you, `invasive_species` for something spreading where it should not be. A
report filed under the "wrong" one is not a failure - moderators see both, and
a genuinely dangerous invasive can still be escalated through the normal
severity path.

**Visibility is public**, like every other condition type. Nothing about an
invasive report identifies a person, so none of the `bad_hikers` reasoning for
`internal_only` applies. It goes through the same moderation queue as the rest
- unlike `thanks`, there is something here to verify.

## Data model sketch

```
Report
  id
  type: blowdown | trash | bad_hikers | flooding | shelter_repair | animals
      | invasive_species | thanks
  location reference:
    - existing POI id, OR
    - a dropped/GPS pin (lat/lon)
  mile (optional - where along the centerline, as the reporting phone
        measured it; the backend holds no trail geometry to derive one.
        Null off-trail, and for a phone with no trail index yet)
  reporter_type (thru-hiker / section-hiker / day-hiker / maintainer -
                 FEATURES.md's existing "reporter type shown" line)
  timestamp
  note (free text, optional)
  photo (optional)
  follow_up (type-specific structured fields - empty in v1, additive later)
  status: submitted | verified | resolved | dismissed
  visibility: public | internal-only | club-only
              (bad_hikers defaults to internal-only - see above; thanks is
               club-only - see SAYING_THANKS.md)
```

## Architecture fit

This is the reason a live backend is now part of v1 MVP at all, not just a Phase 2+ nicety. Segments is entirely client-side; Volunteering's more important half (map display) can run off a static, pipeline-fed file. Report a Problem is inherently dynamic, submitted-by-many-people data that needs moderation before anything becomes visible to other hikers - that's a live backend + database (FastAPI/Postgres, see TECHNICAL_ARCHITECTURE.md's revised Backend section), not something the static PMTiles/GeoJSON pipeline can produce. This feature and the backend that makes it possible are the same milestone, now both MVP.

## Open questions (for you, not decided here)

- **"Bad hikers" handling.** Recommended above as internal-only/non-public, but the exact routing (does it go to the nearest club, a general moderation inbox, both?) is a real decision, not a data-model detail.
- ~~**Minimal identity for reporters.**~~ **Resolved 2026-07-28:** [AUTHENTICATION.md](AUTHENTICATION.md) is now MVP too, built specifically so this doesn't need its own bespoke device-local identity scheme - real accounts exist by the time this feature ships.
- **How "verified" actually happens.** FEATURES.md already plans a maintainer verification/flagging workflow in the abstract; this feature is what gives it real content to verify. Worth designing them together rather than this doc assuming a workflow that doesn't exist yet.
- **Possible future extension:** [TRIP_PLANNING.md](TRIP_PLANNING.md) wants hiker-reported trail difficulty (rocky/rough tread that elevation data alone doesn't capture) and floats this reporting infrastructure as the natural home for it, once there's real report volume to learn from - not designed here, just noted so it isn't invented twice.
- **Related:** [SAYING_THANKS.md](SAYING_THANKS.md) adds the `thanks` type above (2026-07-29), resolving WIREFRAMES.md's Known Deviations #2. It is the one type that deliberately does *not* use this doc's moderation queue or its four states - there is nothing to verify about gratitude, and "Not confirmed" on a thank-you note would read as a rejection. It also adds optional `maintainer_id`/`club_id` attribution, resolved by location against VOLUNTEERING.md's `MaintainerAssignment` records.
- **Related:** [MAP_OPTIONS.md](MAP_OPTIONS.md)'s trail-closure feature reuses this doc's moderation-queue pattern directly (a closure is functionally a condition report that renders as a line instead of a pin) rather than building a second review workflow.
- **Related:** [HIKER_SAFETY.md](HIKER_SAFETY.md) adds a moderator-escalated `severity` tier on top of the report types here (bear sightings under `animals`, dangerous humans under `bad_hikers`), and directly names the "bad hikers" handling above as needing the real moderation-policy conversation this doc already deferred - now with an actual feature waiting on the answer.
- **Related:** [DATA_NUDGES.md](DATA_NUDGES.md) adds a `last_reconfirmed_at` field to the `Report` model above (a fast "still there?" tap that refreshes it without changing `status`, distinct from a "resolved" tap that does), and introduces a separate, lighter `ConditionConfirmation` model for confirmations that were never a problem report to begin with - renamed 2026-07-28 from its original `ConditionCheckIn` to avoid colliding with Community Building's unrelated `CheckIn` (location-sharing) model.
