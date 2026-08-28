---
name: release-train
description: Drive a release end to end - data promotion, migrations, gates, review, notes, draft - so the maintainer's part reduces to the approve, merge and publish clicks that are structurally theirs. Use when the maintainer asks to cut, prepare or run a release, to promote data to production, or names this skill. Covers the order the jobs run in, which button the maintainer is handed at each step, and the traps that have already cost version numbers and cancelled runs.
user-invocable: true
---

# The release train

[RELEASING.md](../../../RELEASING.md) owns the release process - the why, the
gate table (§8), the environments, the rules. What it deliberately does not
hold is an operational order, and the order is what gets dropped between
sessions: v1.1.1 was cut this way, every step reconstructed from the design
prose. This file is that order, written once. It restates as little of
RELEASING.md as possible and cites the rest by section; where the two could
ever disagree, RELEASING.md wins and this file has a bug.

The division of labour is §12's, unchanged: **the agent runs every job, and
the maintainer presses every button that ships something.** Nothing below
pushes a tag, publishes a draft, merges to `main`, or approves a deployment -
each of those is a hand-off, made at the moment it is ready so nobody has to
remember what comes next.

## Tell the maintainer the shape first

Before dispatching anything, say what their part will be, in order. It is
four buttons and one phone:

1. **Approve** each production-environment run the train queues - the data
   publish, and the migration if there is one. **Within the hour of being
   told**: a pending approval is cancelled by the next hourly conditions
   bake (measured, 2026-08-19, in `publish-vector-data.yml`'s header and
   [#838 — v3: shipping anything takes thirty workflows and a maintainer who
   remembers all of them](https://github.com/OurHike/OurHike/issues/838)).
   If one dies unapproved, the train re-dispatches it - annoying, not fatal.
2. **The UA smoke** (gate 7): install the PWA from UA, download the smallest
   archive, go offline, confirm the map still draws. The one gate no
   workflow answers.
3. **Merge the release pull request** - notes and version bump together -
   once it is green.
4. **Publish the draft GitHub release.** Publishing creates the tag, the tag
   deploys production (`pages.yml`), and that is the ship (§12).

## Phase 0 - the number and the name

Read the diff since the last tag and propose the version by §4's rule (what
it costs a *hiker*: MAJOR re-download or re-install, MINOR new behaviour,
PATCH fixes only) and the name by §5 (the trail northbound; a patch inherits
its minor's name). Confirm both with the maintainer before anything runs.

**A version number is single-use, and there is no undo** (§4). Immutable
releases means a tag name is spent the moment a release uses it - v1.0.1 and
v1.1.0 were both lost learning this. Decide the number as if it can never be
taken back, because it cannot.

## Phase 1 - data: current in UA, then promoted

`scripts/pipelines.sh --since v<previous>` answers which publishing paths
this whole cycle staled - the same script every pull request runs, pointed at
the release span instead of a branch.

For each stale dispatchable path (`publish-vector-data.yml`,
`build-basemap.yml`, `build-dem.yml`):

- **UA first, always.** If the standing per-merge rule (CLAUDE.md, "A
  pipeline change is not finished at the merge") kept UA current, this is
  already done - check the workflow's last successful UA run against the
  merges that staled it, and dispatch the UA leg only if something is newer.
- **Then production**: dispatch with `publish: true`,
  `data_environment: production`. Read the dispatch form's other inputs
  against what the cycle changed (tick `include_elevation` when the diff
  reached elevation, and so on - each input's description says what reusing
  the previous run's output means). Hand the maintainer the run URL for
  approval - button 1, with the within-the-hour warning.

`publish-conditions.yml` needs nothing (hourly, both environments);
`build-raster.yml` is withdrawn for v2 (#855) and stays that way unless the
maintainer says otherwise.

After each publish completes, dispatch `verify-release.yml` against the
environment just written (gate 6) - its `base` input for UA, its default for
production - and read the battery's summary rather than assuming green.

**The backend needs no step here, and that is a fact worth knowing rather than
an omission.** Render tracks `main`, so it redeploys on every merge and is
always ahead of the app the tag ships
([../../../backend/HOSTING.md](../../../backend/HOSTING.md)). The skew that
would hurt - a new client against an old backend, which 422s the whole
preferences document and can strand a field note in the outbox for the life of
the build - cannot happen in that direction. If that tracking setting ever
changes, this phase gains a step: deploy, confirm `/openapi.json` carries the
new fields, then continue.

## Phase 2 - migrations

New revisions under `backend/alembic/versions/` since the last tag mean a
production migration. **The timing is a judgement no workflow can make**
(`migrate.yml`'s header: expand-and-contract, §8c - the previous release is
still serving during the rollout), so put the question to the maintainer
explicitly before dispatching. Then: `migrate.yml` with `target: production`
- the UA leg runs first in the same run and production refuses to start
unless UA really applied (gate 5). Approval button, same hourly warning.

## Phase 3 - the gates a dispatch answers

- **Gate 11**: dispatch `release-gate.yml` with the version. Red means an
  open `release-blocker` and the train stops here until it is fixed - §8b,
  a safety-critical finding is never a follow-up.
- **Gate 1**: confirm the four suites are green on `main`'s head - the
  post-merge runs, not a pull request's scoped ones.
- **Gate 9**: read the "Upstream data freshness" tracking issue. STALE
  upstreams are news to record in the notes, not an automatic stop - the
  daily job's own rule - but *knowingly* changed is the standard, so say
  what changed and that the data shipped anyway, or rebuild first.
- **Gate 7**: hand the maintainer the UA smoke - the phone, button 2. Its
  result goes in the notes.

## Phase 4 - the release review (§9)

`/code-review` over `v<previous>..HEAD` at high effort, plus a read of the
combined diff for anything touching position, water, hazard, or the map
drawing at all (§8b's set). Every finding lands in exactly one of: fixed now,
an issue labelled `release-followup`, or `release-blocker` and the train
waits. The counts - found, fixed, deferred - go in the notes; a review nobody
can audit later is a review that happened once.

## Phase 5 - notes and version, one pull request

Dispatch `release-notes.yml` (version, name, previous tag). It opens a draft
pull request; take its branch over and finish it:

- Resolve every `TODO (human)` honestly. The figure is **cited** (§6 - an
  invented anecdote is the same class of defect as a water source in the
  wrong place); the §8d unvalidated section is never empty; the hiker-facing
  list is rewritten in plain language.
- Bump `client/package.json` to the version **in the same pull request** -
  it is the version gate's single source (§4), and the v1.1.1 precedent is
  the two landing together, because a tag that disagrees with that file
  refuses to deploy.
- `scripts/test.sh`, mark the pull request ready, hand it over - button 3.

## Phase 6 - draft, check the target, hand over

After the release pull request merges: dispatch `pages.yml` with
`draft_only: true` and the version. It runs the same two gates a tag runs -
the notes file exists, the version agrees - and drafts the GitHub release
without deploying (§12).

Then read the draft step's summary for **which commit publishing would tag**,
and confirm it is the merge commit just landed on `main`. That check exists
because v1.1.1 was drafted from a branch where publishing early would have
tagged unmerged work permanently.

Hand the maintainer the draft URL - button 4 - and say plainly: publishing
creates the tag, and the tag is the deploy.

## After the button

Watch the tag's `pages.yml` run to green (its `alert` job fires on failure).
If production is wrong, rollback is re-deploying the previous tag (§11b) -
say so rather than improvising. The standing monitors take it from there;
the only follow-up the train owns is confirming any `release-followup`
issues are milestoned to the next release.

## Hotfixes

§11a, shortened train: branch from the current production tag rather than
`main`, gates 1, 2, 4 and 8 stay hard, §8b applies in full, the notes still
get written, and the same four buttons remain the maintainer's.
