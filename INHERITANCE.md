# OurHike — Inheritance Guide

For a club that is not the ATC, weighing whether to run OurHike for their own trail
network. [Closes #108](https://github.com/OurHike/OurHike/issues/108).

[CONTRIBUTING.md](CONTRIBUTING.md) is the guide for a developer joining *this* project.
This is the different document that issue asked for: what a second club actually
inherits, what they would have to build, and what it costs — written now rather than
earlier, because [OurHikeValues.md](OurHikeValues.md) value #7 says this should be
possible in principle, and only a second network actually arriving could show which of
that was true. NYNJTC's own Long Path and Highlands Trail landed in the map in
2026-08-25/27 ([#950](https://github.com/OurHike/OurHike/issues/950),
[#1078](https://github.com/OurHike/OurHike/issues/1078),
[#1083](https://github.com/OurHike/OurHike/issues/1083)), so this guide is written
against that exercise rather than against the architecture's intentions alone.

One framing worth being precise about before anything else: value #7 was written
asking "could another **ATC-affiliated club** pick this up" — one of the thirty clubs
that maintain a section of the Appalachian Trail. NYNJTC is that, but the exercise this
guide draws on is bigger than that framing anticipated: NYNJTC's *own*, entirely
separate, non-A.T. trail network (the Long Path, the Highlands Trail) is what actually
shipped. That is the harder case, and it is the one this guide answers.

Every claim below carries what it rests on, per [CLAUDE.md](CLAUDE.md): **measured**
(a figure, dated, reproducible), **reasoned** (follows from something already true
here), or **`@unvalidated`** (picked, unchecked, with what would settle it named).

## The two questions only you can answer

Before anything below matters:

1. **Do you have your own trail centerline data**, in a form that reaches a stable
   URL or an ArcGIS/OGC service — or a folder of shapefiles and someone willing to
   write a small manifest for it (see "Registering your data," below)?
2. **Do you have a moderator willing to work a report queue** — someone who can act
   on a hiker's "this bridge is out" the way [features/REPORT_A_PROBLEM.md](features/REPORT_A_PROBLEM.md)
   assumes a human, not a script, closes the loop?

If the answer to either is no, the rest of this document describes a tool you cannot
yet use — not because it is unfinished, but because those two things are not software.

## What you get for free — confirmed by NYNJTC actually doing it

The clearest evidence here is not architectural intent, it is that a second, unrelated
trail network went into production **without a pipeline fork**:
[features/NEARBY_TRAILS.md](features/NEARBY_TRAILS.md) records it as "the extension,
not a fork." Specifically, measured against the code:

- **The schema does not assume one trail.** `pipeline/lib/poi_schema.py`'s
  `unify_poi()` takes `trail_id` as a caller-supplied argument, "never hardcoded to
  'AT'" (its own docstring) — a promise the schema made before a second trail existed
  to test it against, and #950 is that test passing.
- **The source-registry mechanism is generic, and proven at some scale.**
  `pipeline/sources.json` holds **47 entries across 14 organizations** (counted from
  the file, 2026-09-27) — the New York–New Jersey Trail Conference (5), NYS DEC (8),
  NYS OPRHP (4), NYC Parks (4), NYC DOT (3), Mohonk Preserve, the Georgia AT Club, USDA
  Forest Service and more, beside ATC's 13. `discover_sources.py` is provider-agnostic
  by design (`pipeline/README.md`). The one place this is still a code change rather
  than a form: `export_poi.py`'s `DIRECT_SOURCES` is a Python tuple of literals, so
  *adding* a source today still needs a maintainer to write a few lines — see
  "What's still to design," below.
- **Blaze colors are a data-driven lookup, not an AT palette with exceptions.**
  `client/src/lib/blaze.ts`'s `BLAZE_COLORS` and `normalize_blaze_color` already
  handle a second organization's coded domain, and OPRHP's "Teal"/aqua was added to
  the palette by review (`pipeline/reference/blaze_mapping.json`,
  [#782](https://github.com/OurHike/OurHike/issues/782)) — a reviewed data file, not a
  code fork. The AT centerline's "always white" default is itself a per-source
  config value in `sources.json`, not a hardcoded assumption
  ([features/TRAIL_BLAZE_COLORS.md](features/TRAIL_BLAZE_COLORS.md)).
- **The dbt transform layer took the load.** [pipeline/DBT.md](pipeline/DBT.md)'s
  Phase D (closed 2026-08-27 under
  [#100](https://github.com/OurHike/OurHike/issues/100)) built staging models for
  twenty newly-registered sources — Long Path, Highlands Trail, four OPRHP layers,
  Mohonk, all eight DEC layers — as "new rows and new staging models," which is
  exactly what that phase was built to make true rather than aspirational.

## What is AT-specific — values, not mechanism

The corridor concept generalizes; today's *numbers* do not:

- `client/src/App.tsx:597` hardcodes `CORRIDOR_BOUNDS`, a single bounding box
  (`[[-84.73, 34.2], [-68.3, 46.34]]`) framing the whole Appalachian Trail on first
  open. `pipeline/export_drought.py:93` and `pipeline/spike_water_conditions.py:99`
  each separately hardcode `CORRIDOR_BUFFER_DEG = 0.09` — a duplicated literal, not a
  shared config value.
- Some identifiers still carry the organization's name rather than a neutral key:
  `client/src/chrome/poiSources.ts:20-21` keys the shelter and campsite layers
  `atc_shelters` / `atc_campsites`, spelling out "the Appalachian Trail Conservancy's"
  in the label text. This is not hidden — it is worth naming because
  [#1083](https://github.com/OurHike/OurHike/issues/1083) found and fixed the same
  pattern already once (`AtcNoticeList.tsx`, a component whose own comment admitted it
  "said 'Appalachian Trail Conservancy' in five places as a literal," before it became
  the generic `NoticeList.tsx`). **A second club should expect more of these** — they
  get found when a second organization's data actually exercises the code path, not
  before.

## What genuinely assumes one trail today

This is a correction to the issue's own framing as much as an answer to it. Issue #108
said this work was "most of which #100's Phase D is meant to address" — Phase D's own
closing comment (2026-08-27) scoped itself narrower than that: it re-audited the
`poi_type` literals and the `poi_type_mapping` seed's vocabulary, and it staged twenty
sources. It did not touch any of the following, which are real, and are not yet
designed anywhere in this repository:

- **The map still frames one corridor.** `CORRIDOR_BOUNDS` above is a single box, not
  a list. [features/SOURCE_REGISTRY.md](features/SOURCE_REGISTRY.md)'s own three-stage
  sketch names this directly: stage 1 (what exists today, NYNJTC included) is "still
  A.T.-shaped: one corridor, one download"; stage 2, "multi-trail," is explicitly
  *not* built.
- **The map draws one trail as "the" trail at a time.**
  [features/NEARBY_TRAILS.md](features/NEARBY_TRAILS.md) settled this on 2026-08-18:
  "the centerline is always the chosen trail; one trail at a time." Every other trail
  on screen is a ghosted, view-only line. A club whose own network *is* the map, not a
  guest on someone else's, would need this decided differently.
- **Long-hike completion tracking is hard-gated to the A.T. by name, not by
  capability.** `client/src/lib/hikeText.ts:170`, `setupRefusal()`: *"This build can
  only measure a hike on the Appalachian Trail."* The comment above it explains why —
  "a figure on any other trail would be an A.T. mileage wearing somebody else's
  name" — which is a correct safety-against-false-precision argument
  (`trailHasMileAxis`), not an oversight. It does mean a club whose trail has no
  published mile-marker axis gets a real, working map and no percent-complete number,
  by design, until that trail publishes one.
- **A day hike off the A.T. has nothing to plan against.**
  [features/HIKE_PLANNING.md](features/HIKE_PLANNING.md) records that a Harriman day
  hike — real trails, already on the map, via NYNJTC/OPRHP data — reaches a route
  builder with "nothing to ask for"
  ([#928](https://github.com/OurHike/OurHike/issues/928)): trip planning assumes a
  single mile-axis trail, which the A.T. has and a state park network does not.
- **The off-trail warning names the A.T. in its copy.** `client/src/screens/GpsTrace.tsx:242`:
  *"…because you are more than three miles from the Appalachian Trail."* A cosmetic
  instance of the same pattern as the hardcoded corridor bbox above — a string, not an
  architecture problem, but one a club would see on day one.

None of this blocks what NYNJTC actually has today — trail lines, waypoints, alerts,
notices. It bounds what a club gets if their trail has no single mile axis, or if they
want their own network to be the map's subject rather than a guest on the A.T.'s.

## What it costs to run

The honest floor here is that **no invoice exists yet at any meaningful scale** —
everything below the small-print line is `@unvalidated`, and both issues it comes from
are open, `night-shift-hold`, and explicitly the maintainer's decision to make, not
this guide's to resolve
([#393](https://github.com/OurHike/OurHike/issues/393),
[#395](https://github.com/OurHike/OurHike/issues/395)).

**Measured, today:**
- Baseline hosting is **~$2/month** — one Fly.io `shared-cpu-1x`/256MB machine — plus
  a Supabase free-tier project (#393).
- The published bucket is **3.94 GB**, costing **$0.059/month** at R2's
  $0.015/GB-month; a national-scale estimate (not yet built, see #250 above the
  queue) runs to ~12 GB, **~$0.20/month**
  ([pipeline/NATIONAL_SCALE.md](pipeline/NATIONAL_SCALE.md), measured 2026-09-16).
- Retained release history (current + candidates + a 90-day prune window) runs
  **~8–12 GB under `releases/` plus ~15 GB under `_internal/`**, on the order of
  **$0.40/month** at the same rate
  ([pipeline/DATA_RELEASES.md](pipeline/DATA_RELEASES.md)).
- **R2 egress is free at any volume.** This is the single property holding the whole
  curve down: the same map data served to 1,000,000 hikers a month would cost
  **~$36,000/month** on S3-style $0.09/GB egress, and costs $0 here
  (#393, modeled).
- Cost per hiker: **~$0** to browse and download (R2 storage plus a few Class B
  operations, no egress); **~$0.04/year** for a hiker who signs in and files reports
  (one Supabase MAU at $0.00325/month); **~$0.0004** per uploaded report photo
  (#393).

**`@unvalidated`, and named as such by the issue that produced them:** a scale model
at 200,000 and 1,000,000 monthly active users, projecting **~$370–430/month** and
**~$3,250–4,050/month** respectively. #393 says plainly that every rate in it "comes
from third-party 2026 pricing summaries and vendor documentation reachable
indirectly... not from the vendors' own pricing pages," because `fly.io`,
`supabase.com` and `developers.cloudflare.com` were unreachable from the sandbox that
produced it. What would settle it: checking Supabase's MAU-overage rate and compute
tiers against their own current pricing page, and instrumenting the real ratio of
monthly-active to registered users from live traffic once there is any.

**What actually drives the bill, and what does not.** At the 1,000,000-user model,
backend hosting is ~3% of the total and Supabase authentication is ~75% of it —
because R2's free egress, no-account browsing, and photo delivery by redirect rather
than proxy (`backend/app/core/photos.py`) hold the map-serving side near zero
regardless of scale (#393). A second club inherits that shape unchanged: the map is
cheap because of how it is served, not because of how much of it exists.

## Registering your data

The mechanism [features/SOURCE_REGISTRY.md](features/SOURCE_REGISTRY.md) designs — an
organization submits a form, a probe checks the endpoint, a bot opens a pull request —
**is a design draft, not yet built.** What actually happened for NYNJTC was a
maintainer reading `discover_sources.py`'s output and hand-writing entries into
`sources.json` and matching dbt staging models. So "before starting" today means, in
practice: **finding someone who can make that pull request**, not filling out a form
that does not exist. The registry document is still the right map of what your data
needs to arrive as — a stable endpoint (ArcGIS FeatureServer, a GeoJSON/GeoPackage at
a fixed URL, or a folder of shapefiles with a small manifest naming which files and
what CRS) plus a settled licence and attribution, which
[CONTRIBUTING.md](CONTRIBUTING.md#a-note-on-data-and-licences) is explicit must be
settled *before* a byte enters the build, because a commit here cannot be retracted.

## Accounts and setup

Mechanically the same steps as the first club's launch, because nothing about them was
written A.T.-specific: [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) is the literal
runbook — a Cloudflare account for R2 (data) and Pages (previews), a static host for
the built client, a Supabase project for authentication, and DNS for a custom domain
if you want one. Every step in it is "sign up for a service and paste a value into a
secret," not code, and every free-tier note in it is either measured (Pages: "no limit
... at this size") or points at the same #393/#395 cost questions above.

## What is still to design — named, not invented here

Per [CLAUDE.md](CLAUDE.md)'s "an honest unknown outranks a confident answer": these are
real gaps, not oversights, and designing them now — before a second club's actual
constraints are known — would mean guessing.

- **Multi-trail, plural corridors.** `SOURCE_REGISTRY.md`'s own stage 2. Needed the
  moment two clubs' networks, or one club's network and the A.T., need to coexist as
  equals rather than one being "the chosen trail" and the other a ghost.
- **A self-serve registration form.** Today: a maintainer's pull request. The design
  for the form exists (`SOURCE_REGISTRY.md`); the backend tables, probe, and bot do
  not.
- **Per-organization admin UI, per-trail moderation queues, and storage/cost
  accounting per organization** — `SOURCE_REGISTRY.md`'s stage 3, "any club stands up
  their own trail on shared infrastructure." Naming it is what that document does;
  building it from here, before a second club that needs it exists, would be
  inventing requirements nobody has stated.
- **Who pays, and what happens under a spend spike** — #393 and #395, both the
  maintainer's decision and both currently open.

## Sources this guide rests on

`pipeline/sources.json` (2026-09-27), `pipeline/DBT.md`, `pipeline/NATIONAL_SCALE.md`
(2026-09-16), `pipeline/DATA_RELEASES.md`,
[features/SOURCE_REGISTRY.md](features/SOURCE_REGISTRY.md),
[features/NEARBY_TRAILS.md](features/NEARBY_TRAILS.md),
[features/TRAIL_BLAZE_COLORS.md](features/TRAIL_BLAZE_COLORS.md),
[features/HIKE_PLANNING.md](features/HIKE_PLANNING.md),
[LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md), and issues
[#100](https://github.com/OurHike/OurHike/issues/100),
[#393](https://github.com/OurHike/OurHike/issues/393),
[#928](https://github.com/OurHike/OurHike/issues/928),
[#950](https://github.com/OurHike/OurHike/issues/950),
[#1078](https://github.com/OurHike/OurHike/issues/1078),
[#1083](https://github.com/OurHike/OurHike/issues/1083).
