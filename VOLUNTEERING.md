# OurHike — Volunteering / Work Projects (Feature Design Draft v1)

Companion to [FEATURES.md](FEATURES.md), [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](OurHikeValues.md). Expands FEATURES.md's existing one-line "volunteer-opportunity surfacing" item (under Trail magic) into a real design, split into the two sides the user described: a club-side module for managing work projects, and a hiker-facing map display encouraging people to join one.

**Scope note up front:** like [SEGMENTS.md](SEGMENTS.md), this is Post-MVP (Trail magic, value #9) - a design ready to build from, not an argument to reprioritize v1.

---

## The two sides of this feature

**1. Work project management (club-side) — genuinely a different module, per your framing.** Clubs need to create, schedule, and track their own trail-maintenance workdays: a bridge rebuild, a shelter repair day, a blowdown-clearing crew. This is squarely the same territory as FEATURES.md's already-planned "club data-entry tooling" and "per-club admin roles" (Multi-club support, value #7) - just for work projects instead of POI data. It needs real authenticated admin access, which is a genuine departure from the no-account-needed hiker-facing app - but not a new architectural idea: TECHNICAL_ARCHITECTURE.md's Backend (Phase 2+, FastAPI/Postgres) already names "multi-club admin" as exactly this kind of use case. This slots into that existing plan rather than requiring something new.

**2. Map display (hiker-facing) — the more important half, per your note.** Upcoming work projects show up as a map layer, the same way shelters or water sources do: a pin, tappable for details (what, when, where, how to join or who to contact), filterable (e.g. "near me," "this weekend"). No login needed to see these - it's read-only, informational, exactly like every other POI layer in the app today.

Splitting it this way matters for sequencing: **the hiker-facing display doesn't actually need the full admin module to exist first.** A club's project list could start as simple as a hand-maintained GeoJSON file (or a spreadsheet a maintainer fills in) fed through the pipeline the same change-aware way everything else is - the same pattern `sources.json` already uses for hand-added ATC layers. Real self-service club admin tooling can follow once the pattern's proven, rather than blocking the more important, more visible half of this feature on the bigger build.

## Why this matters beyond "a nice feature"

This isn't just a feature - it's a direct expression of two things already core to the project:

- **Value #9 (Be magical)** names this exact behavior already: *"Nudge behavior toward volunteering with trail-maintaining clubs... the forms of magic that sustain the Trail, not just the people passing through it."* This feature is that value made concrete, not a new idea layered on top.
- **The project's own funding mission** (OurHike exists partly to fund ATC and its affiliated maintaining clubs) has a labor side, not just a donation side. Surfacing real volunteer opportunities to the hikers already walking past them is a direct, no-cost way to support the clubs the app is meant to sustain.

## Data model sketch

```
Club  (first-class concept already anticipated by Multi-club support, value #7)
  id, name, region/scope

WorkProject
  id, club_id
  title, description
  location reference (point, or a line segment along the centerline for something
                       like "clear blowdowns miles 40-45" - same anchoring approach
                       as Segments' start/end references)
  scheduled: a date, a date range, or recurring - see open questions
  status: upcoming | completed | cancelled
  signup info: contact details or an external signup link for v1 (simplest possible
               start); an in-app RSVP/capacity system is a natural v2, not required
               to ship the map-display half of this feature
```

## What this deliberately isn't

Per value #1 (hike your own hike, no prescriptive gamification): no leaderboard of volunteer hours, no "you've volunteered less than other hikers" nudging, no public volunteer profile. The feature's job is to make a real opportunity visible at the moment someone might act on it - not to manufacture participation through comparison or guilt. This mirrors the same restraint FEATURES.md and SEGMENTS.md already apply elsewhere.

## Map/UX fit

FEATURES.md's waypoint icon spec (~8 color-coded POI categories, WCAG AA contrast) is the existing visual system for map pins - a work-project pin needs to fit into or sensibly extend that same spec, not invent its own visual language.

## Open questions (for you, not decided here)

- **Scheduling shape.** Single-date workdays are simple to model; multi-day or recurring projects (e.g. "every third Saturday") need a bit more structure. Worth deciding based on what clubs actually run, not guessing.
- **Signup mechanism for v1.** Contact-info-only (simplest, ships fastest) vs. an actual in-app RSVP/capacity count (better hiker experience, real added scope). Recommend starting with the former given the "different module, don't block the map display on it" framing above.
- **Who can post a project before real club admin tooling exists.** A manual, pipeline-fed stopgap (like `sources.json`) needs someone (you, or a club contact) submitting/editing a file - fine for a handful of early-partner clubs, worth knowing it doesn't scale past that without the real admin module.
- **Club admin login, once the real module gets built.** See [AUTHENTICATION.md](AUTHENTICATION.md) - it's designed as the first Post-MVP feature built specifically so this module (and the others) have a real identity layer to build on rather than inventing their own.
