# v2 — the work, grouped so it can be picked up

Companion to [ROADMAP.md](ROADMAP.md), which says what the v2 *features* are and why.
**This document is about the other question: given 117 open issues all labelled `v2`, what
can one session finish in one branch without colliding with another session?**

It groups every open issue into twenty-three bodies of work. The grouping is by **conflict
surface and dependency**, not by subject — [BRANCHING.md](BRANCHING.md) §2 is emphatic
about the difference, and the measurement behind it is that twelve of the last
twenty-seven real conflicts were all in `client/src/App.tsx` between branches whose
subjects had nothing to do with each other.

**Every open issue appears exactly once below.** That was checked mechanically rather than
by reading down the list: 117 open, 117 assigned, no duplicates, no omissions, on
2026-08-17. Eight more (#768–#772, #780, #782–#783) were filed 2026-08-18 and added as
group **V** the same day, and two more (#795–#796) were filed 2026-08-18 and added as
group **W** the same day. Four more (#876–#879) were filed 2026-08-20 — the halves of
FIELD_NOTES.md and the volunteering build that PR #873 did not reach — and added to
groups **Q** and **U** the same day. If you add an issue, add it to a group here or the
next person will find it by accident.

*Written at 106 issues; groups **T** and **U** were added the same day when
[HIKE_PLANNING.md](features/HIKE_PLANNING.md)'s and
[VOLUNTEERING.md](features/VOLUNTEERING.md)'s phases were finally filed — see the note
under Gaps, which is what prompted filing them.*

## Before you start anything

1. **Claim the issue.** [CLAUDE.md](CLAUDE.md)'s "Claim the issue before you branch" is
   the most important paragraph in this repository for a session working unsupervised, and
   it has been broken twice. The trigger is *starting work*, not opening a branch — adding
   an issue to a branch you already have needs the same claim a fresh branch would.
2. **Read the group's "what you are walking into" note below.** Several of these bodies of
   work have a decision inside them that has to be taken before code, and taking it
   silently is how two sessions end up having taken it differently.
3. **`scripts/threads.sh --fetch`**, then `scripts/test.sh` before you push.

## How the groups are ordered

Not by priority — by **what unblocks what**. Groups **A**–**C** produce data or identity
that later groups anchor to, and doing them late means redoing work in D–G. Everything
from **H** down is genuinely parallel.

---

## A. Water a hiker can actually reach

**#749 — Every OSM water point inside a 30-mile corridor draws on the map, and most of them are not water a hiker on the trail can reach** ·
**#97 — Validate NHD flowline stream-crossings as a water-source candidate list** ·
**#710 — "Corroborated by both databases" is worth much less in Virginia than in New Hampshire, because OSM's streams there are NHD** ·
**#479 — Act on the A.T. source survey: fix provider labels, ship an open shelter-capacity source, resolve the ATC/PATC/TEHCC asks**

**Why together:** all four are `pipeline/fetch_*water*.py` and `export_poi.py`, and #749 and
#710 are the same question asked twice — *what does a water pin actually claim, and is the
claim true?* Splitting them produces two branches editing the same export function.

**Do this first, and it is the one group where that is not a scheduling preference.**
CLAUDE.md names four ways this app can hurt somebody and *out of water* is one of them.
#749 measures 1,705 water features reaching the map through a gate that is only "within
thirty miles of the trail".

**What you are walking into:** #749 carries three `@unvalidated` measurements it explicitly
declines to guess at, and the issue argues at length that the number must not be picked
before the census is run. **Run the census first** — `spike_osm_water_census.py`, in the
shape the issue describes — and put the distribution in the issue before touching a
threshold. Note also that this is *not* the `wrongWay.ts` asymmetry: over-filtering water
hurts a hiker too, so neither direction is the safe one.

## B. Elevation, and the two ways this repo measures a mile

**#652 — The elevation profile's mile axis is out of order in 18 places, by up to 46 miles** ·
**#133 — Validate the cumulative-ascent threshold against published section figures** ·
**#548 — Survey elevation data sources: is there a better one than 3DEP-via-TNM for v1?**

**Why together:** one file, `pipeline/export_elevation.py`, and #652 is a live `bug` whose
fix moves the axis that #133 validates against. Doing #133 first means validating an axis
that is about to change.

**What you are walking into:** ROADMAP.md's v2 section records that **this repository
measures "a mile" two different ways** — `client/src/lib/trailPosition.ts` and
`export_elevation.py` — and that the elevation ribbon already compares them as if they were
one measurement. That is HIKE_PLANNING.md's Phase A and **it has no issue of its own**
(see *Gaps* below). It is the same subject as #652 and whoever takes this group should
expect to meet it.

There is an open draft PR here already: **#549 — Survey the elevation sources: the data is
right, the catalogue in front of it is not**. Check its state before branching.

## C. POI identity across the ATC's annual refresh

**#671 — Seed the POI identity ledger and reconcile by key, so a re-mint is a blocked diff rather than a silent orphaning** ·
**#672 — Evidence matching for re-keyed POIs: distance, trail position, normalised name, and ATC's own inventory fingerprint** ·
**#673 — Tombstones and superseded_by: an upstream removal never deletes a hiker's content** ·
**#674 — Closures anchor on miles alone, and a re-measure moves every mile** ·
**#675 — Measure the first real ATC refresh: GlobalID survival, tier-2 volume, and where the thresholds land**

**#831 — A tombstone's superseded_by reaches no hiker, because nothing outside the pipeline can read the identity ledger** ·
**#832 — Nothing in this app can report a closure, so the geometry that anchors one is never written**

**Why together:** [features/POI_IDENTITY.md](features/POI_IDENTITY.md) is one design and
these are its five phases. They share the ledger file and the resolver.

**Order is fixed: #671 → #672 → #673, with #674 independent and #675 last** (it can only be
done when a real refresh arrives). #671 is the one worth doing even if the rest waits.

**Where this stands, 2026-08-19.** #671, #672 and the pipeline halves of #673 and #674 are
built. #675 is still waiting on a real refresh and no amount of code advances it. The two
issues added above are the halves that turned out to be blocked on plumbing the design
assumed existed, and they are filed rather than left implicit because closing #673 and #674
would otherwise make them invisible — the *Gaps* failure at the foot of this document,
arriving from inside a group rather than from a doc nobody filed.

**#831 is the one that changes what a hiker sees**, and it is not small: nothing under
`backend/` can read a file or open a socket for data, and the ledger is not even in the
production image. Read its two proposed shapes before picking one. **#832 is client work
and does not collide with the rest of this group** — its hard part is the outbox, which
today can only carry a `ReportDraft`.

**Why this is high in the order:** every group below that attaches something of a hiker's
to a place — a photo (D), a plan, a field note (Q) — anchors on a POI id that today lives
and dies with the upstream key. Building D before C means building it on an anchor that a
single ATC republish dissolves.

## D. Photos

**#360 — Let a hiker add their own photo to a waypoint, and optionally share it** ·
**#571 — Take a photo from the waypoint card, and keep it or throw it away** ·
**#578 — Put the hiker's own photo, and the community's, on the waypoint card** ·
**#576 — Store and serve community waypoint photos, with the caps and the withdrawal the design promises** ·
**#577 — The share sheet: who will see this photo, under what terms, and what cannot be taken back** ·
**#579 — Promote a shared photo to a POI's pinned three, and take one down, from the queue that already exists** ·
**#575 — Several photos per place, and letting the hiker say which one the card shows** ·
**#573 — Save a photo taken inside OurHike to the hiker's own photo library, or stop promising their library has the original** ·
**#361 — Import a trip's photos from the hiker's own library and match them to waypoints** ·
**#570 — Screen a photo for nudity and faces before it can reach the community** ·
**#569 — Decide whether a photo can be shared with a Tramily rather than with everyone** ·
**#568 — Decide whether a waypoint photo may ever be a video or a GIF**

**Why together:** [features/POI_PHOTOS.md](features/POI_PHOTOS.md) and
[features/PHOTO_DOWNLOADS.md](features/PHOTO_DOWNLOADS.md), one subject, and they share
the waypoint card and the backend photo store.

**This is twelve issues and must not be one branch.** Three sub-branches that do not
collide:

- **Capture and local storage** — #571, #578, #575, #573, #360. Client only.
- **Sharing and moderation** — #576, #577, #579, #837, plus #836 on the pipeline side.
  Backend plus the share sheet.
- **Library import** — #361. Independent of both.

**Where this stands, 2026-08-19.** The capture branch is built — PR #834 closes #571,
#575, #573 and #568, and delivers #578's device half (#578 stays open for the community
rung, which needs #576). The three gating decisions are all taken by the maintainer, in
session, and recorded in POI_PHOTOS.md: **#568** (2026-08-18) — a short silent looping
clip only; **#569** (2026-08-19) — sharing is one CC BY-SA 4.0 licence event whatever the
audience, Tramily included; **#570** (2026-08-19) — screening flags for a human and never
decides, split per its deliverable into
**#836 — Run a face-and-nudity check over the Commons fetch, where a stranger's
self-portrait can become a town's illustration** (pipeline, belongs with this group's
sharing work in sequence but touches only `fetch_poi_images.py`) and
**#837 — On-device screening at the share sheet: friction and a queue flag, never a
refusal**. **The sharing slice is built end to end as of 2026-08-20** — #576's store,
#578's rungs, #577's sheet (with the two-hour cooling-off decided in the
maintainer-adopted mockups) and #579's moderation surface all landed on
`claude/photos-work-ulp2yd`, built to the "Sharing a Photo" mockup canvas after its
mockup-stage claims were declared stale by the maintainer in session. **Screening landed
2026-08-20 on both paths:** #837's on-device detector (nsfwjs + BlazeFace, lazy-loaded,
never precached, every failure indistinguishable from "nothing found") runs at the share
sheet with the adopted mockups' friction copy, and #836's fetch-time face check holds a
flagged Commons photo from export and bucket until a person records a verdict in the
committed decisions ledger. The pipeline's nudity half is deliberately out — no
in-the-wheel detector exists, so it is a maintainer dependency decision, held as
**#850 — The pipeline's Commons screen checks faces but not nudity, because a nudity
model means a new heavyweight dependency**. **What is left in this group:** #850's
dependency decision, and #361 behind #101's native pickers.

## E. Offline coverage in pieces

**#552 — Decide the unit of offline coverage, and write it down** ·
**#556 — Cut and publish coverage units from the build that already exists** ·
**#557 — Draw the map from several coverage units, and say plainly where they end** ·
**#558 — Let a hiker take the stretch they are walking, without picking it off a list** ·
**#551 — v2: offline coverage in pieces — stop asking for a gigabyte at once** ·
**#447 — The closures baseline is unavailable in exactly the place a hiker is: offline** ·
**#448 — Archive verification hashes on the main thread, so a download freezes the app it is downloading for** ·
**#449 — A whole percent is 7.9 MB, so the download bar sits still while bytes are arriving**

**Why together:** all of it is `client/src/lib/archiveDownload.ts` and the download screen.
#448 and #449 are not part of the coverage-units design at all, but they edit the same file,
and a branch that touches `archiveDownload.ts` for one reason should take the other two
while it is open rather than conflict with them later.

**#552 blocks everything else here and is a decision, not code.** #551 is the umbrella;
#558's own body opens by declaring itself "Blocked on #552 (which unit)".

**Cheap and independent:** #448 and #449 are small, visible, and need no decision. Good
first branch if you want to warm up on this file.

## F. The corridor view

**#595 — The corridor view has nothing to explore, because "popular" has no source behind it yet** ·
**#596 — Count where hikers actually went, from what they chose to publish rather than from analytics** ·
**#598 — Give the corridor view a subject: club sections and stretches worth going to**

**Why together:** [features/CORRIDOR_VIEW.md](features/CORRIDOR_VIEW.md), and #595 is a
statement that the view has no data behind it while #596 is where that data would come from.

**What you are walking into:** #596 is a privacy-shaped problem wearing a metrics hat —
counting where hikers went, from what they *published*, rather than from analytics. Read
[features/EVENTING.md](features/EVENTING.md) first; it settled that unique-user counts need
no identifier, and the same reasoning applies here. Do not invent a second telemetry path.

## G. Spurs, and the line you tapped

**#136 — Publish the mile at which each spur joins the AT** ·
**#134 — The line-detail sheet that shows a spur's destination** ·
**#161 — Export the centerline as merged chains, so per-zoom line simplification can come back on** ·
**#501 — SPUR_TRAILS.md still asks which POI types are destinations; export_spurs.py already answered**

**Why together:** `pipeline/export_spurs.py` and `export_trails.py` on one side, the line-detail
sheet on the other. #136 is the pipeline half of #134's client half — one branch, or the sheet
renders a field nothing supplies, which is the exact failure ROADMAP.md records for the
closure and warning sheets.

**#501 is a five-minute docs fix** and should be taken by whoever is in this file anyway.

**Where this stands, 2026-08-19.** All three remaining issues are built on one branch:
#136's `junction_mile` publishes on the marker-calibrated axis every other mile shares,
#134's line-detail sheet renders it with the destination and round trip, and #161's
centerline merges into chains at export with the client's `tolerance: 0` reverting
per phone, keyed off the shape of the data actually stored there. What #675-style
follow-through remains is operational rather than code: the first merged data release
shows a deliberate trails feature-count drop (the manifest's `constituent_count` is
what the quality gates now track across it), and phones only pick the faster path up
on their next trail-data download.

## H. App store packaging

**#101 — Wrap the PWA with Capacitor** ·
**#102 — iOS build and TestFlight beta** ·
**#103 — Android build and internal testing track** ·
**#104 — Store listing assets and privacy policy**

**Why together:** one sequence, and #101 blocks #102 and #103 absolutely.

**Mostly not a coding task.** #102 and #103 are `blocked-external` — they need developer
accounts, signing certificates and store review. **#104 is the one that can start today**
and has the longest lead time.

## I. Standing the backend up for real

**#600 — Nothing owns standing up the production backend, and the image has never run against a real Docker daemon** ·
**#95 — Backend has never run against real Postgres outside CI** ·
**#92 — Real Apple OAuth has never been exercised end to end** ·
**#279 — Replace the password sign-in path with an emailed code** ·
**#255 — PATCH null semantics are opposite in sibling endpoints: hikes 500s on an explicit null, closures silently ignore one** ·
**#247 — POST /wrong-way-events requires a hike_id the client will never have** ·
**#320 — Backend test harness drops every table in whatever DATABASE_URL names — add a guard** ·
**#322 — Backend endpoint and error-path test gaps** ·
**#658 — Backend audit follow-ups: inputs nobody has been bitten by yet, and a moderation trail with gaps**

**Why together:** `backend/`, one suite, one deployment.

**#600 is the keystone** — nothing else here is provable without a backend that runs
somewhere. **#320 is a safety fix and should go first regardless**: a test harness that
drops every table in whatever `DATABASE_URL` names is one mis-set environment variable away
from dropping production.

**Correction to a standing belief:** CLAUDE.md used to say the sandbox has no Postgres. It
does — `backend/scripts/local-postgres.sh` starts it, and the session-start hook now does
too. A connection-refused failure means that script has not been run, not that the check
cannot run here.

**#255 and #247 are contract bugs** — small, well-specified, and good for a short session.

## J. What it costs and who pays

**#395 — Put a ceiling on the bill before the app is public** ·
**#393 — What OurHike costs to run, who pays for it, and the guardrails that keep a bad week off a personal credit card** ·
**#403 — Spike: Improve cost-detection script for CI**

**Why together:** one subject, and #393 is the design #395 is the urgent slice of.

**#395 is the one with a deadline attached to reality** — the app is public now. Worth
reading as *already overdue* rather than as planning.

## K. Safety surfaces built but not trusted

**#93 — Wrong-way alert thresholds are wireframe placeholders, not validated numbers** ·
**#308 — WrongWayCue.tsx is still referenced by 0 non-test files, and mounting it is a decision rather than wiring** ·
**#105 — Outdoor usability pass — sunlight glare and gloved, one-handed use** ·
**#106 — Real-trail field testing**

**Why together:** all four need a person on a trail with a phone, and #93 and #308 are one
decision wearing two numbers.

**Do not "fix" #308 by mounting the component.** ROADMAP.md records that it is unmounted
*deliberately*: its thresholds are placeholders (#93), it is the only notification this app
sends, and a false alarm spends the trust budget the single alert was designed around.
`wrongWay.test.ts` states the asymmetry outright — false negatives are acceptable, false
positives are the failure the module exists to prevent. **#93 is the prerequisite and it is
field measurement, not code.**

## L. Client performance and the App.tsx chokepoint

**#722 — 860 ms of MapLibre parsing sits in front of the first paint, and nothing can render until it finishes** ·
**#327 — App.tsx is the repository's merge-conflict chokepoint: 12 of the last 27 conflicts, more than the next six files combined** ·
**#288 — The outbox's four mutators are non-atomic read-modify-writes over one key** ·
**#657 — Client audit follow-ups: drifted lists, dark machinery, and comments the code outgrew**

**#327 is special and needs scheduling, not just picking up.** It is a decomposition of the
file every other client branch edits. BRANCHING.md §4 says land the hot-file branch first;
this *is* the hot file. **Do it when few client branches are in flight, and tell the other
sessions.** Doing it alongside D and E in flight will cost more than it saves.

**#288 is a correctness bug** — four non-atomic read-modify-writes over one key, in the
outbox that holds a hiker's unsent reports.

## M. The suites themselves

**#343 — Client suite flakes under full-run load: two different map tests failed in two consecutive runs, both pass alone** ·
**#323 — Client suite: remove the sleep-then-assert-absence waits and fix the App.flows navigator stub** ·
**#324 — Test-suite hygiene: network guards, a shared DuckDB fixture, and untested helper modules** ·
**#318 — Exercise the archive download engine against a real IndexedDB** ·
**#319 — check-build-output.mjs needs tests of its own** ·
**#502 — The API seam checks field presence and nullability, but not that a type narrowed** ·
**#503 — The client suite's CI scope list has no guard, so #317 can happen again** ·
**#253 — BASEMAP.md's "it is only reordering" is inferred from five agreeing metrics, not proved** ·
~~**#488 — Decide whether the auth-redirect check runs daily, given only one scheduled workflow may reach Supabase**~~ ·
**#660 — Automation audit follow-ups: the ledger's hand copy, the pins that float, and guards that grep for prose**

**Why together:** they are all "the tests are not telling us what we think they are", and
#343 and #323 are plausibly the same root cause.

**#343 and #323 first, as one branch.** CLAUDE.md's rule — *"tests that depend on ordering
get run several times before they are pushed… prove it holds by running the file three
times"* — was written from these exact failures. #323 removes sleep-then-assert waits;
#343 is what those waits were hiding.

**#503 is a guard against a regression that already happened once** (#317) and is cheap.

**#488 resolved 2026-08-20.** Went with the guard-amendment option: `test_supabase_keepalive_workflow.py`
had already stopped enforcing "exactly one" in favour of a named `SCHEDULED_ROSTER` (#656, before
this issue was ever filed against the older wording), so the redirect check joined it as a fourth
entrant rather than reopening that design question. It now runs daily at 09:45 UTC as
`check-auth-redirects.yml`, reporting through the same tracking-issue mechanism as its two siblings
rather than failing the run — the thing #488's own body flagged as needed "once the schedule exists."

## N. The pipeline and the publish path

**#750 — The published-data smoke test has not hashed trails.geojson or any poi_*.geojson since #717, because it refuses the gzip publish.py deliberately stores** ·
**#172 — spurs.json can publish partial or empty with every check green** ·
**#446 — Nothing catches a closures column renamed out from under the publisher** ·
**#173 — check_freshness.py fetches whatever URLs the state file names, with no scheme or host check** ·
**#465 — Stop re-downloading photos we already have on every release** ·
**#463 — A job that proposes parsed ATC updates as a pull request, never publishes them** ·
**#321 — Pin the Python dependency sets and cache the DuckDB spatial extension in CI** ·
**#248 — Cutting a package from a sharded build: extract_package.py takes one source, and seam tiles have no rule** ·
**#250 — The sharded regional build: no workflow, no cadence, and nothing that publishes** ·
**#278 — Offer quad_sheet_z14 as the USGS sheet's full-detail tier, once a full raster run publishes it** ·
**#855 — Withdraw the USGS raster sheet from the app and stop building it, until it earns the compute back** ·
**#99 — Expand the unified POI schema beyond its first slice** ·
**#100 — Build the dbt ELT transform layer before NYNJTC's own trail network arrives** ·
**#659 — Pipeline audit follow-ups: a narrow z14 band, hashes trusted across a gap, and the retry library nobody calls**

**#750 is in flight** on `claude/v2-roadmap-issues-evc1gc` (PR #751) — do not take it.

**#855 is in flight** on `claude/disable-usgs-raster-builds-cj3s7g` — do not take it. It is the
decision *not* to fund a full raster run, which is exactly what **#278** waits on, so **#278 is
blocked for as long as #855 holds** and the "sharded regional build" cluster below is two issues
rather than three until then.

**Three clusters that do not collide:**

- **Checks that pass when they should not** — #172, #446, #173, #750. One theme: a green
  check over an artifact nobody verified. This is the highest-value cluster here.
- **The sharded regional build** — #248, #250, #278. One design, currently half-built.
- **Schema and transform** — #99, #100. **#100 is timing-driven rather than
  sequence-driven**: ROADMAP.md says NYNJTC's own non-AT network is expected on a
  near-term timeline, and this is what makes onboarding it "new rows and new staging
  models" rather than a second parallel pipeline. If that timeline is real, this rises.

**#321 has bitten this session.** The pinned requirements will not install on a Python
older than 3.12, and the sandbox default is 3.11 against CI's 3.14.

## O. The record: docs that disagree with the code

**#601 — The two documents that say what is left both list issues that are already closed** ·
**#661 — The record beyond #601: three docs still say nothing is published, the runbook's key step is dead, and the front door describes the reversed architecture** ·
**#175 — Review follow-ups: tests that cannot fail, comments that overclaim, and small duplications** ·
**#257 — Cohesion review follow-ups: five small mismatches, none worth its own issue** ·
**#315 — Safety-review follow-ups: smaller items, none worth its own issue** ·
**#273 — client/README.md's Deploying section names the wrong GitHub Pages Source setting** ·
**#108 — Write the inheritance guide aimed at the next club**

**Why together:** docs, and they overlap heavily — #661 is explicitly "beyond #601".
**Take #601 and #661 as one branch**; splitting them means two branches editing ROADMAP.md
and LAUNCH_CHECKLIST.md, and LAUNCH_CHECKLIST.md is fourth on BRANCHING.md's conflict table.

**These are now more wrong than when they were filed.** v1 has launched, `v1-mvp` has been
removed from every open issue, and ROADMAP.md still describes that label as "what still
blocks launch" and links to it. Add that to #601.

**#175 is the one to read carefully** — "tests that cannot fail" is a real finding and the
kind this repository cares about most.

## P. The web surface

**#116 — Build the real website** ·
**#135 — The full elevation chart the desktop has room for** ·
**#206 — Design spike: carry the brand on a phone without spending map pixels**

**Why together:** the one place a desktop layout exists or does not. ROADMAP.md records
that `site/index.html` is the Downloads screen restyled at phone width and **the client has
no `@media` rule anywhere** — so FEATURES.md's promise of the "same core experience on
phone and web" is not met today.

**#206 is a spike and blocks nothing.** Photography sourcing has the longest lead time of
anything in this group.

## Q. Field notes and freshness

**#256 — The POI staleness tiers have no producer and no consumer** ·
**#876 — Disputes: not_found, the existence axis, and the fix that files upstream (FIELD_NOTES.md §4, unbuilt)** ·
**#878 — Nothing notices when the POI id under a field note stops existing** ·
**#879 — A field note cannot carry the photo the contribution opt-in promises**

**Where this stands, 2026-08-20.** FIELD_NOTES.md steps 1–4 and its flag-and-hide are
built on `claude/v2-features-overnight-pyqhse` (PR #873), as the foundation under
**#759 — The Volunteer tab and the contribution toggle**: the `FieldNote` record, the
write path from the card, the roll-up wired to `staleness.ts` (both halves of #256), and
`conditions/notes.json` beside the closures. The three issues added above are the halves
that would otherwise have gone invisible when #256 closed — the *Gaps* failure at the
foot of this document, pre-empted this time: #876 is the doc's step 5 whole, #878 its §7
orphan backstop, and #879 the note-photo question the build deliberately declined to
answer by accident. **#877 — A flagged note and a claimed hour both wait in queues no
screen shows** is the client moderation surface this group and group **U** now share; it
is listed under U, where the club side lives.

**What you are walking into:** the day-one rendering is DECIDED — maintainer, 2026-08-20,
recorded on #256: never-confirmed is its own tier rendered neutral, except water, which
wears a faint "No recent word" invite; `FRESH_MAX_DAYS = 14` and `AGEING_MAX_DAYS = 60`
stand, tagged `@unvalidated`, with real confirmation volume named as what settles them.
Do not re-open that from the code side; field data is what moves it next.

## R. Launch, community, and the things money touches

**#109 — Soft launch with NYNJTC** ·
**#110 — Feature gating and experimentation (self-hosted GrowthBook)** ·
**#107 — Web-only donation/payment flow** ·
**#98 — Confirm opentrail.org data-reuse terms with the maintainer**

**#110 is recommended first** and ROADMAP.md says why: every feature built afterwards gets
real evidence instead of a guess. Given that groups A–G are about to be built against
guesses, this argument is stronger now than when it was written.

**#98 is `blocked-external` and is a licensing question, not a code one.** It has been open
since 3 August. It gates whether opentrail-derived data may ship at all, which makes it
cheap to ask and expensive to keep not asking.

**#107 depends on P** — checkout has exactly one place it is allowed to live, and the site
as shipped has no page for it.

## S. Ops, automation, and the bot dashboards

**#681 — The workflow list sorts into no families, because two naming conventions disagree about which end the word goes** ·
**#438 — Document that the pooler username's prefix is the database role, not a literal `postgres`** ·
**#478 — Upstream data freshness** ·
**#732 — Published data smoke test** ·
**#738 — Deployed app reachability**

**#478, #732 and #738 are not work.** They are tracking issues opened, updated and closed
by scheduled workflows via `.github/scripts/tracking-issue.js`. They carry `v2` because
every open issue was labelled, and the label may not survive the bot's next rewrite.
**Do not "fix" them by closing them** — the job that owns each one closes it when the
underlying check goes healthy.

What they are useful for is *reading*: #732's current contents are the symptom that
produced #750, and #738 records a real If-Range gap (#566) that the client compensates for.

**#438 and #681 are small, real, and good first issues.**

## T. Planning a hike — v2's first feature

**#753 — Publish a mile on every POI, because this codebase measures a mile two different ways and a plan cannot survive that** ·
**#754 — spike_day_planner.py has never been run against real data, so every number in HIKE_PLANNING.md's Finding 3 is arithmetic rather than measurement** ·
**#755 — The route builder: drop points on the trail and get distance, gain, loss and an honest ≈time** ·
**#756 — Multi-day plans: days as Segments, the timeline, zero days and resupply, and food counted in days rather than calories** ·
**#757 — The auto-generated plan: a shortest path over ~3,000 edges, on the phone, with no backend and no network** ·
**#758 — The cascade: when today changes, what happens to the rest of the plan**

**Why together:** [features/HIKE_PLANNING.md](features/HIKE_PLANNING.md)'s five-phase build
order, plus the spike run its own closing line calls "the first thing to close".

**Order is the doc's and it is real: #753 → #755 → #756 → #757 → #758**, with #754
independent and wanted before #757 is designed.

**#753 is the one to do first and the one to do even if nothing else here happens.** It is
group **B**'s subject from the other side — the client and the pipeline measure a mile
differently, and the elevation ribbon already compares the two as though they were one
measurement. Harmless over a ten-mile window, not harmless summed across a 2,190-mile plan.
It is also what every mile-range scope in [PHOTO_DOWNLOADS.md](features/PHOTO_DOWNLOADS.md)
needs, which makes it a prerequisite of group **D** as well.

**The standing trap in this feature:** value #1 forbids prescriptive gamification, and a
planner is two design decisions from a schedule that scolds. No progress bars against plan,
no "behind schedule", no streaks. #756 is where that arrives without anyone deciding to add
it.

## U. Volunteering — v2's second feature

**#759 — The Volunteer tab and the contribution toggle — which is where DATA_NUDGES.md finally ships** ·
**#760 — Volunteer opportunities on a map, the next fourteen days — the first layer in this app whose data expires** ·
**#761 — Hours, self-logged, and the private impact record that must not become a scoreboard** ·
**#762 — In-app signup and club confirmation — an introduction, never an enrolment** ·
**#763 — Ridge Runner At-Large, and the club-side work-project module** ·
**#877 — A flagged note and a claimed hour both wait in queues no screen shows**

**Why together:** [features/VOLUNTEERING.md](features/VOLUNTEERING.md)'s five phases, each
useful alone by design.

**Where this stands, 2026-08-20.** Phases A and C are built and B is half built, all on
`claude/v2-features-overnight-pyqhse` (PR #873): #759 whole (the fourth tab, the opt-in,
the card and lane surfaces, places-passed-today — on the FieldNote foundation group **Q**
records), #761 whole (the outbox's fifth cargo, the bounded-claims backend, the dashboard
under §5's four rules, with the claimed-counts-until-disputed decision recorded on the
issue), and #760's list half (the reviewed file with UA-only samples, the 14-day window,
the 48-hour ceiling). **#760 stays open for its map-pin half** — a pin needs a tap and a
tap needs a sheet, its own small design. #762's endpoints for hours confirmation exist;
the signup model and every screen are still its to build, and #877 is where the
club-facing queue screens (notes and hours both) now live. #763 stays `blocked-external`.

**#759 is worth doing whether or not the rest follows** — the doc says so outright. It is
the piece that touches every hiker rather than the few who attend a workday, and it ships
[DATA_NUDGES.md](features/DATA_NUDGES.md), designed in July and never built. It is also the
natural partner of group **Q**'s **#256**, since the field-note roll-up and the contribution
toggle are the producer and the prompt for the same staleness tiers.

**#763 is `blocked-external`** — the Ridge Runner name needs a conversation with ATC, and
the doc is explicit that it should happen *before the name reaches a screen, not after*.
Worth raising alongside the other ATC asks in **#479**.

**Two guardrails that are easy to breach here.** The anti-gamification rule has a stated
boundary — it targets *comparison and pressure*, not *memory* — and #761 is the phase that
tests it. And this feature must never become the second thing that sends a notification;
[HIKER_SAFETY.md](features/HIKER_SAFETY.md)'s wrong-way alert stays the only one.

## V. Trails within reach of NYC — the second trail system, for real

**#768 — v2: trails within reach of NYC — the AT stops being the only trail on the map** ·
**#769 — Register the NYS OPRHP ArcGIS org: the trails, blazes and closures behind the Parks Explorer app** ·
**#770 — Survey the trail sources within a day of NYC: DEC's Catskills, the NJ side, the counties, and what only OSM covers** ·
**#771 — Spike: Harriman's crossing trails next to the AT — find what a trail network breaks that a linear trail never could** ·
**#772 — Design the map when trails cross: one chosen centerline, every other trail visible, and safety pins that ignore the choice** ·
**#780 — Research route ownership: the AT in NY has thirty owners, a landowner with final say per section, and a maintainer besides** ·
**#782 — Grow the blaze palette under governance: the Long Path's aqua is real paint, and sprawl stops at a reviewed mapping table** ·
**#783 — Draw the ghosted network and its view-only sheet: NEARBY_TRAILS.md's map, built**

**Why together:** one maintainer scope call (2026-08-18, recorded in #768), and the
children are one program: register, survey, spike, design — plus the ownership research
the display decisions turned out to need. #769 and #770 are parallel (both done);
#771 wants #769's fetch but can probe the org directly; #772 consumes #771's findings
and #780's definition of "the org" — the maintainer's cross-org POI and line-precedence
decisions of 2026-08-18 are recorded on #772's thread and presume it.

**What you are walking into:** three things, each named in the issues so nobody
re-discovers them. The licence on every new source here is **pending the maintainer's own
outreach** to OPRHP and NYNJTC — fetch-and-review only, nothing publishes to hikers, the
same posture as the club PDFs' registry entries. **#100 — Build the dbt ELT transform
layer before NYNJTC's own trail network arrives** is where new-source staging models
belong — its Phase A is already merged, so do not build a parallel ingestion path. And
**#552 — Decide the unit of offline coverage, and write it down** should be answered with
#771's crossing-density numbers in hand: a network park is not a linear stretch, and the
spike exists partly to give that decision evidence.

## W. The More tab, reorganized

**#796 — Reorganize the More tab into sections a hiker can navigate, instead of one long scroll** ·
**#795 — Rename the More tab to Settings, now that it has real sections**

**Why together:** both are [features/MORE_TAB.md](features/MORE_TAB.md), one screen, and
they touch the same file (`client/src/chrome/tabs.ts`) — not the hot-file conflict
BRANCHING.md's table tracks (that is `App.tsx`; `tabs.ts` is small and low-traffic), but
real enough that one branch covers both if that is more convenient than two.

**What you are walking into:** the doc argues the tab name the way
[VOLUNTEERING.md](features/VOLUNTEERING.md) argued `Volunteer`'s, against three rejected
alternatives, and lands on `Settings` — a recommendation, not a ruling. It also flags,
without resolving, two seams for whoever is next in **T** or **U**: `Your hike`'s home once
the `Plan` tab (group T) is fully built, and how this screen's `Contribute` section reads
next to **#759**'s condition-nudge surface once group U's first phase ships.

---

## Sequencing, in one paragraph

**A, B and C first** — they set data and identity that D, E, F, G and Q anchor to.
**#320, #395 and #750 are urgent for reasons unrelated to sequencing** (a table-dropping
test harness, an uncapped bill on a public app, a smoke test checking nothing).
**#327 needs a quiet window** in the client. Everything else is parallel. Where two groups
touch `client/src/App.tsx`, BRANCHING.md §4 applies: land the `App.tsx` branch first.

## Questions that need answering before the work does

These are the decisions a session cannot take for itself, gathered so they can be answered
in one sitting rather than discovered one at a time.

1. **#552 — Decide the unit of offline coverage.** Blocks four issues in group E. This is
   the single highest-leverage answer on the list.
2. ~~**#568, #569, #570** — video/GIF, Tramily-scoped sharing, and screening before a photo
   reaches the community.~~ **Answered 2026-08-18/19, by the maintainer in session, all
   three** — a short silent looping clip only; one CC BY-SA licence event whatever the
   audience; flag-for-a-human, never block (split into #836 and #837). Recorded in
   POI_PHOTOS.md, and group D's sharing branch is unblocked.
3. ~~**Is NYNJTC's non-AT network actually coming soon?**~~ **Answered 2026-08-18: yes,
   and the scope is wider than NYNJTC** — the maintainer's call recorded in **#768 — v2:
   trails within reach of NYC — the AT stops being the only trail on the map** targets the
   Hudson Highlands core plus the Catskills plus everything NYNJTC maintains, with
   maintainer outreach to OPRHP and NYNJTC in motion. #100's timing question is settled:
   it rises, and its Phase A is already merged.
4. **Who is field-testing, and when?** Group K is four issues that no amount of code
   advances. #93 gates #308, which gates the app's only notification.
5. ~~**What are `FRESH_MAX_DAYS` and `AGEING_MAX_DAYS` supposed to be?**~~ **Answered
   2026-08-20, by the maintainer in session (recorded on #256):** they stand at 14 and
   60, tagged `@unvalidated` with real confirmation volume named as what settles them —
   and the day-one question underneath got the real decision: never-confirmed is its own
   neutral tier rather than `stale`, except water, which wears a faint "No recent word"
   invite because the OSM/USGS water data is unverified by FEATURES.md's own admission.
6. ~~**Is `post-mvp` still a meaningful label?**~~ **Answered 2026-08-17: no, and it has
   been removed** from all 44 open issues that carried it. It had come to sit on issues
   that were all also `v2`, so it no longer distinguished anything. Note the label itself
   still exists and closed issues still carry it — deleting the label is a repo-settings
   action. ROADMAP.md's `post-mvp` row is now false and is #601's to fix, along with its
   `v1-mvp` row.

## Gaps — designed features with no issues filed

**Two of the three are now closed.** When this document was first written, three of
ROADMAP.md's named v2 features had **no open issues at all** — they were invisible to
anyone reading the tracker rather than the roadmap, which meant "finish every open issue"
and "build v2" were not the same programme.

- **[features/HIKE_PLANNING.md](features/HIKE_PLANNING.md)** — **filed**, as group **T**
  (#753–#758): its five phases plus the spike run.
- **[features/VOLUNTEERING.md](features/VOLUNTEERING.md)** — **filed**, as group **U**
  (#759–#763): its five phases.
- **[features/FIELD_NOTES.md](features/FIELD_NOTES.md)** — **closed 2026-08-20, the
  third of three.** Steps 1–4 and flag-and-hide are built (group **Q**, PR #873), and
  the remainder is filed rather than invisible: **#876** (disputes, the doc's step 5),
  **#878** (the §7 orphan backstop), **#879** (the note-photo question), and **#877**
  (the moderation screens, listed under **U**).

**The lesson is worth keeping even though two of the three are fixed:** a feature that is
designed and unfiled looks identical, from the issue list, to a feature nobody has thought
about. The roadmap is not a tracker and was never meant to be one, so the gap is silent by
construction. Anyone scoping a new feature doc should file its build order at the same
time.

Two other things ROADMAP.md names that have no issues and are not features:
**DATA_NUDGES.md** ships inside #759, and **EVENTING.md** is measurement rather than a
build — the nearest filed thing is **#110 — Feature gating and experimentation
(self-hosted GrowthBook)** in group R.
