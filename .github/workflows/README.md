# The workflows

29 files, 38 jobs. Each file's header comment is the design record for that
workflow and is the place to find out *why* it is the way it is — this file is
the level above: what exists, what makes each one run, and the three or four
facts that are dangerous to learn by discovering them.

`pipeline/`, `backend/` and `client/` each have a README for the same reason.
This directory went without one until [#680](https://github.com/OurHike/OurHike/issues/680).

## Three things to know before editing anything here

**There are no folders.** GitHub ignores anything nested under
`.github/workflows/` — a workflow in a subdirectory does not fail, it simply
never runs. The directory is flat by platform rule, not by preference, which is
why the only organising lever is naming, and why the families below are a
description rather than a directory layout.

**Renaming a job can hang the merge queue.** Branch protection requires a
*check*, and a check's name is a job's `name:` where it has one and its job id
otherwise — never the workflow's `name:` or its filename. So renaming a job, or
adding a `name:` to one that had none, silently stops the required check
reporting. That does not fail a queue entry; it **hangs** it until the queue
times out and ejects the pull request. The five names in the table below are
load-bearing strings. `.github/expected-protections.yml` is where they are
declared and `.github/tests/test_repository_protections.py` is what checks the
declaration still matches the files — but nothing can catch a rename that
updates both and leaves the GitHub ruleset behind, because no API this
repository reaches can read that ruleset without an optional PAT.

Renaming a *file* is safe by comparison: `expected-protections.yml` names
workflows by filename and the test fails on a stale one. It is still not cheap —
37 references from outside this directory, and 99 places where one workflow
header names another. [#681 — The workflow list sorts into no families, because two naming
conventions disagree about which end the word goes](https://github.com/OurHike/OurHike/issues/681)
holds that plan, and is deliberately not started.

**A `paths:` filter on a trigger is a trap.** A workflow skipped by a path
filter reports no status at all, and a required check that reports no status
leaves a pull request pending for ever rather than passing it. The three test
workflows scope themselves *inside* the job instead, through
`.github/actions/changed-paths`, so they always run and always finish green.
[TESTING.md](../../TESTING.md) has the full argument.

## The five required checks

These gate `main`. Every one of them triggers on `merge_group:`, which is what
lets it report against a merge queue entry; a required check without that
trigger is the hang described above.

| Check name | Workflow | What it is |
|---|---|---|
| `test` | `client-tests.yml` | the client suite, plus typecheck, lint, format and the build |
| `pytest` | `pipeline-tests.yml` | the pipeline suite — where the trail is drawn and how far along it a hiker is |
| `pytest-postgres` | `backend-tests.yml` | the backend suite against a real Postgres service container |
| `PR has a linked issue` | `pr-issue-link.yml` | CONTRIBUTING.md's tracker rule; the only one about process rather than correctness |
| `Manifest agrees with the workflows` | `settings-manifest.yml` | that `expected-settings.yml` still agrees with this directory |

`Settings are configured` (`settings-configured.yml`) looks like a sixth and
must stay out: it reads the live `secrets` context, which a fork's pull request
never receives, so requiring it would block every outside contributor's pull
request for a reason none of them could fix.
[BRANCHING.md](../../BRANCHING.md) holds the menu and the mechanism;
`.github/expected-protections.yml` holds the declaration and the reasons.

## The six families

Grouped by what makes a workflow run, which also predicts its permissions,
whether it holds credentials, and whether a failure reaches anyone.

### Runs because a pull request exists

| | |
|---|---|
| `client-tests.yml` | required check `test` |
| `pipeline-tests.yml` | required check `pytest` |
| `backend-tests.yml` | required check `pytest-postgres` |
| `pr-issue-link.yml` | required check `PR has a linked issue`; reports green on a queue entry without checking, deliberately |
| `settings-manifest.yml` | required check `Manifest agrees with the workflows` |
| `pr-preview.yml` | builds the pull request and deploys it to `pr-<n>.ourhike-preview.pages.dev` |

`shard-seam-spike.yml` also triggers on `pull_request`, filtered to its own
paths — it is a spike, and lives in the last family.

### Runs because something landed

| | |
|---|---|
| `ua.yml` | push to `main` → UA, the environment testers see |
| `pages.yml` | a `v*` tag → production, what hikers install. **Not** a push to `main` — [RELEASING.md](../../RELEASING.md) §2 |
| `migrate.yml` | push to `main` → applies the migration chain to UA, then production `needs: ua` |

The three test workflows also run on a push to `main`, unscoped, as post-merge
validation against the real merge commit. That is what caught the flaky
staleness boundary test in #32, green on the pull request and red on the merge.

### Builds or publishes data

All five publishing paths share `concurrency: publish-data`, so two of them can
never interleave. All are dispatch-only except `publish-conditions.yml`.

| | |
|---|---|
| `build-basemap.yml` | vector basemap → `build`, `publish` |
| `build-dem.yml` | DEM archive → `build`, `publish` |
| `build-raster.yml` | raster background → `compute-cells`, `render`, `assemble`, `publish` |
| `publish-vector-data.yml` | trails, POIs and the manifest hikers download |
| `publish-conditions.yml` | closures and warnings, on a daily schedule as well as dispatch |

`publish-vector-data.yml` and `migrate.yml`'s production job both run under the
`production` environment, which is what makes RELEASING.md §12 — only the
maintainer ships — a GitHub setting rather than a habit.

### Watches a live system

Scheduled. Four of them report by opening, updating and closing a **tracking
issue** rather than by failing the run, because GitHub emails on every failure
of a scheduled workflow and a week-long outage would send seven identical
emails before the eighth was filtered. Alert on transitions, not on runs.

| | reports by | |
|---|---|---|
| `check-deployment.yml` | tracking issue | sends a real `Origin` for every declared origin — the one check that would have caught #427 |
| `check-deployed-app.yml` | tracking issue | whether the deployed app draws a trail at all |
| `check-upstream-freshness.yml` | tracking issue | whether ATC and the other upstreams have moved |
| `smoke-published.yml` | tracking issue | the published artifacts, weekly |
| `schema-drift.yml` | failing the run | both databases against the models; being behind head is normal and never fails |
| `supabase-keepalive.yml` | failing the run | keeps a free-plan project from being paused; also reads all seven tables with the anon key |
| `protections-check.yml` | failing the run | branch protection, environments and labels |
| `settings-configured.yml` | failing the run | that the secrets and variables really exist |

**All four share one routine** — `.github/scripts/tracking-issue.js`, required
from each monitor's `github-script` step. It owns finding the issue by label
*and* title, opening, updating in place, commenting and closing, and the
"first seen" map. What stays with each caller is the verdict — whether this run
is green — and the rendered body.

That line is where it is because of #651, which corrected the all-clear
condition in two of these monitors and needed a *different* correction for
each: `check-deployment.yml` must not close on a run that never checked the
artifacts, `smoke-published.yml` must not let a total outage close the alarm
its own corruption opened. A shared "is it green" would have to be wrong for
one of them, so `healthy` is an input and a test asserts the two conditions
still differ.

First-seen dates live in an HTML-comment marker the module writes and reads.
Before #678 each copy parsed them back out of the markdown table it had just
written, with a regex fitted to that file's column count — so adding a column
would have silently reset that monitor's clock to today, for ever, with the
body still saying "first seen". `.github/tests/test_tracking_issue.py` drives
the real module under `node` and asserts the round trip.

Exactly one scheduled workflow may reach the Supabase project —
`supabase-keepalive.yml` — and `.github/tests/test_supabase_keepalive_workflow.py`
fails if a second appears. It asserts the longest gap the cron leaves rather
than the string it is written as, because `50 */20 * * *` reads like "every 20
hours" and actually fires 20 hours apart and then 4.

### Runs when someone is shipping

All dispatch-only. [RELEASING.md](../../RELEASING.md) is the process.

| | |
|---|---|
| `release-gate.yml` | asserts §8's gate table before a tag is cut, including that the labels it queries exist |
| `release-notes.yml` | drafts the notes — **never publishes**, per §12 |
| `verify-release.yml` | checks a release after it is out |

### Runs when someone is debugging or measuring

All dispatch-only, none of them gates anything.

| | |
|---|---|
| `r2-credentials-check.yml` | whether the R2 credentials still work |
| `supabase-config-check.yml` | the project's auth settings, and whether a sign-in can still come back. No schedule — see #488 |
| `package-overlap-spike.yml` | how many bytes a second overlapping package duplicates (#193) |
| `shard-seam-spike.yml` | whether a sharded continental basemap build is lossless (#194) |

## The schedule, in one place

UTC. Deliberately off the hour — GitHub queues everything submitted at `:00`
behind everyone else's — and deliberately spread, so two jobs never contend.
Each workflow's own header names its neighbours; this is that information
gathered rather than restated.

| When | | |
|---|---|---|
| `20 7 * * *` | daily | `check-upstream-freshness.yml` |
| `35 7 * * 1` | Mondays | `settings-configured.yml` |
| `45 7 * * 1` | Mondays | `protections-check.yml` |
| `10 8 * * *` | daily | `schema-drift.yml` |
| `40 8 * * *` | daily | `publish-conditions.yml` |
| `15 9 * * *` | daily | `check-deployment.yml` — after `publish-conditions`, so a publish that breaks something is noticed the same day |
| `30 9 * * *` | daily | `check-deployed-app.yml` |
| `40 9 * * 1` | Mondays | `smoke-published.yml` |
| `50 */20 * * *` | 00:50 and 20:50 | `supabase-keepalive.yml` |

## The shared actions

Composite actions, in `.github/actions/`, for logic that would otherwise be
copied. The bar is not "used twice" — it is that the interesting part is the
handful of ways the thing can be wrong, and those are worth fixing in one place.

| | |
|---|---|
| `changed-paths/` | does this run have anything to test? Every uncertain case answers "run" |
| `publish-to-pages/` | pushes a built directory to a path on `gh-pages` |
| `delete-pages-previews/` | tears a preview down when its pull request closes |

## What tests this directory

`.github/tests/` — run with `scripts/test.sh`, same as everything else.

- `test_repository_settings.py` — every `secrets.X`/`vars.X` a workflow reads is
  declared in `expected-settings.yml`, nothing declared has outlived its last
  reader, and nothing is read from the wrong context
- `test_repository_protections.py` — every required check exists as a job and
  can report on a queue entry
- `test_workflow_working_directory.py`, `test_pipe_to_tee_does_not_mask_failure.py` —
  two whole-directory rules, the second because a pipeline's exit status is
  `tee`'s under the default shell (#514)
- and named checks on individual workflows: `test_pages_publish.py`,
  `test_pages_preview_cleanup.py`, `test_publish_concurrency.py`,
  `test_pr_issue_link_duplicates.py`, `test_release_notes.py`,
  `test_supabase_keepalive_workflow.py`, `test_dependabot_labels.py`
