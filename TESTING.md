# Testing philosophy

This describes how OurHike tests its code, project-wide - not just the Python data pipeline, which is the only thing built so far. When the client (React/TypeScript PWA) or a backend (Python/FastAPI, Phase 2+) exist, they get their own section below following the same philosophy, not a separate one invented from scratch.

## Why this exists

Most of the pipeline was built through manual, ad hoc verification this session: one-off scripts, print statements, eyeballing results. That caught real bugs - an `ST_Transform` axis-order bug that silently produced garbage geometry, a band-count mismatch between fallback and bulk raster tiles, 3 genuinely corrupted USGS source files a shallow check missed - but none of those catches were permanent. Nothing stopped any of them from silently coming back the next time that code was touched.

**The core rule: every real gotcha becomes a regression test in the same change that fixes it - not just a comment.** A comment explains the bug to a human reading the code later; a test catches it automatically for a machine that isn't reading comments. This project has already paid for several of these lessons the hard way - the tests exist so nobody pays for them twice.

## What we test, project-wide

- **Pure functions** - zero setup, run in milliseconds. Every pure function should have one.
- **Small-synthetic-fixture tests** for anything spatial/numerical/binary (geometry, rasters, etc.) - tiny fixtures generated in test code, not committed as opaque binary files. A test that builds its own "corrupted" file byte-for-byte documents exactly what "corrupted" means; a checked-in blob doesn't.
- **HTTP-mocked tests** for any network-touching logic (especially change-detection/skip-logic, which is easy to silently break and expensive to notice - you'd only find out via a full re-fetch that should've been skipped). Real network calls are never allowed to fire during tests.

## What we deliberately don't test

- **Real network calls** to live third-party services (ArcGIS, opentrail.org, USGS, etc.) in the automated suite - slow, flaky, not reproducible, and impolite to hammer on every test run.
- **Real large datasets** (e.g. the full 1,654-quad USGS fetch/mosaic) - too slow/heavy for a test suite. Verifying the real pipeline end-to-end against real data stays a **documented manual procedure**, not a test - see each component's section below for what that looks like today.
- **Pixel-perfect "golden image" comparisons** for raster output - assert structural properties (band count, CRS, nodata boundary location, no unexpected NaNs) instead of byte-identical files, which are too fragile to maintain as inputs change.

## Adding a new gotcha as a regression test

Found a bug where the code did something surprising or silently wrong? Before moving on:
1. Fix it.
2. Write a test named for the behavior it guards against (e.g. `test_full_band_read_catches_late_strip_corruption`, not `test_bug_47`), in the same commit/PR as the fix.
3. If it's fast to check, verify the test actually fails against the pre-fix code (revert the fix locally, confirm red, restore it, confirm green) - proves the test has teeth instead of passing vacuously.

---

## Pipeline (Python)

**Framework:** pytest, with `requests-mock` for HTTP isolation (any unmocked request raises rather than silently hitting the network) and `pytest-cov` for a visibility-only coverage report (see below - not a merge gate).

**Lint/format:** Ruff, pinned to a narrow rule set (pyflakes + core pycodestyle errors + import sorting - see the comment in `pyproject.toml`'s `[tool.ruff.lint]`) rather than its much larger default rule set, and matching this project's "boring, low-maintenance" preference over a maximalist lint config.

**Quick start:**
```
cd pipeline
.venv/Scripts/pip install -r requirements-dev.txt   # Windows; .venv/bin/pip on macOS/Linux
.venv/Scripts/python -m pytest                        # run everything (prints a coverage summary too)
.venv/Scripts/python -m pytest tests/test_x.py         # one file
.venv/Scripts/python -m pytest -k test_name            # one test
.venv/Scripts/python -m ruff check .                   # lint
.venv/Scripts/python -m ruff format .                  # auto-format
```

**On coverage:** the report is there to show what's untested, not to chase a percentage - CI doesn't fail on a coverage threshold. Padding coverage numbers pulls in the opposite direction from this file's actual rule (test real gotchas as regressions), so it's deliberately not gated.

**Layout:** `pipeline/tests/`, one file per source module, `conftest.py` for shared fixtures. `pipeline/pyproject.toml` sets `pythonpath = ["."]` so tests can `import fetch_all`, `from lib import arcgis`, etc. directly - these are standalone scripts, not an installed package.

**Network isolation caveat:** DuckDB's spatial extension (`INSTALL spatial`) fetches from DuckDB's own extension repository over the network on first use *per machine* - this is a one-time local setup step, not a per-test-run network call, but it's a real exception to "tests never touch the network" worth knowing about if a fresh environment's first test run looks like it's doing something unexpected.

**Blaze normalization, still to build (see `features/TRAIL_BLAZE_COLORS.md`):** decoding each trail-line source's raw color coding into one normalized `blaze_color` attribute happens here, during export - not on the client (see the Client section above, which only tests the client's *use* of the already-normalized value). Once built, this needs a regression test for exactly the gotcha `TRAIL_BLAZE_COLORS.md` already names from the real data: `side_trails`' `Blaze` field has 24 features with no value at all, 9 with the literal string `"Unknown"`, and 3 with `"Gold"`, none of which are in its actual 0-9 coded domain. The test should assert all three fall through to the neutral default with a warning logged - not a crash, and not a silently wrong color.

**What's intentionally manual-only:** fetching the real ~1,650-quad USGS corridor dataset and mosaicking it (`fetch_topo_quads.py` + `spike_raster_mosaic.py`) is a real multi-GB, multi-minute operation against live services - run it by hand to verify changes that touch fetch/mosaic logic, don't expect it in `pytest`.

## Client (React/TypeScript) - not yet built

Not scaffolded yet (see ROADMAP.md Phase 2). Framework: **Vitest + React Testing Library** - Vitest because it shares Vite's transform pipeline (the confirmed bundler per TECHNICAL_ARCHITECTURE.md) instead of adding a second one; same philosophy as the pipeline above (pure-function/component unit tests, no real network in the suite, mock any data/API calls), not a from-scratch set of conventions.

The test plan below is drawn from [WIREFRAMES.md](WIREFRAMES.md) - it names the behaviors those v1 MVP screens need covered, written before the client itself so the first pass at each area can be built test-first per this file's core rule. Written as behaviors, not implementations, so they survive refactors.

**Pure logic (fast unit tests, zero rendering):**
1. **Blaze normalization (client's half)** - the pipeline decodes raw source data into a normalized `blaze_color` string during export (see the Pipeline section below); the client's job is just mapping that already-clean string to a MapLibre paint style via a `match` expression. Test the client's defensive fallback: any `blaze_color` value that isn't one of the expected strings renders as the neutral grey and **emits a warning**, rather than the client trusting the pipeline blindly or crashing on an unexpected value.
2. **Naismith** - 2.6 mi / 640 ft ⇒ `≈1h 10m`; rounds to 5-minute steps; descent never subtracts; output always carries `≈`; never formats an arrival time.
3. **Download detail levels** - each of Light/Standard/Fine maps to its correct zoom (z11/z12/z13) and its correct measured size (64 MB/314 MB/1.18 GB, from `pipeline/README.md`) as a table-driven test, guarding against one of the three drifting out of sync with the other two. No per-section math - see WIREFRAMES.md Known Deviations #1.
4. **Staleness tiers** - boundary tests at 14 and 60 days, `never confirmed` ⇒ stale, and staleness is independent of the verified/unverified flag (all four combinations produce the right pin treatment).
5. **Onboarding step counter** - total derived from the live step list; skipping a step does not change the total; adding a future step (trail name) yields "of 4" without touching call sites.
6. **Wrong-way detector** - table-driven against synthetic GPS traces: short backtrack to a spring ⇒ silent; standing still at a shelter ⇒ silent; sustained reversal past the persistence threshold ⇒ cue, then push; off-line distance under threshold ⇒ silent. False negatives are acceptable; **false positives are the failure**.

**Component tests:**
7. **Legend contents** - equals exactly what the viewport contains, with correct counts; recomputes on pan/zoom; closure and serious-warning rows render **without** a hide control.
8. **Map chrome** - compass + locate present and ≥44px effective target; zoom buttons absent on mobile, present on web; scale bar respects the unit preference; attribution always rendered.
9. **Report status rendering** - each of Waiting / Confirmed / Fixed / Not confirmed renders its own affordance; "Not confirmed" applies no penalty styling to the reporter.
10. **Closure sheet** - shows status, dates, marked-by, sync age; offers no detour computation; renders the barred-band line treatment distinctly from a red blaze.

**Integration / E2E:**
11. **First run** - three onboarding steps, each skippable; location asked only after the value-prop screen; **no notification prompt anywhere** in first run; a fresh install can reach a usable map with zero taps beyond the flow.
12. **Report -> sign-in -> submit** - the report survives the sign-in detour intact; the stored timestamp is the authoring time, not the send time; internal-only report types never appear in any public query result (mock the API here - see Backend below for the server-side half of the same invariant).
13. **Offline outbox** - write three items with the network off, restore network, all three sync with original timestamps and no duplicates; deleting a queued item deletes it for good.
14. **Download + detail** - choose each of Light/Standard/Fine for the single whole-corridor package; the size shown matches the measured figure.
15. **Closure freshness** - with a 3-day-old package, the closure sheet shows the sync age; after sync, newly-marked closures appear.

**Invariants worth asserting explicitly (regression guards):**
16. No route in the app exposes a closures toggle or a warnings toggle - assert on the settings schema, not the DOM.
17. Serious warnings never enqueue a push; the wrong-way alert is the only push publisher in the client codebase.
18. **Every POI category the app can name, it can draw.** The legend, search and the map all read one array, and the style's icon `match` resolves every published `POI_TYPES` entry to an image that was really registered - with an unknown type falling through to a neutral pin rather than to nothing. This is a regression guard for a real bug: POIs were fetched, stored, searchable and counted in the legend for months while the style had no layer that could put any of them on the map, so the legend's hide toggles were toggling layers that did not exist. Shape carries the category and colour only reinforces it (no two glyphs coincide, and none is a subset of another), since the accents sit within ~2:1 of each other and vanish as a channel in glare or greyscale - the same reasoning as the blaze dash rhythms in #1.

19. **A build that cannot draw a map does not ship.** Every test in `client/src` mocks `maplibre-gl` outright - it has to, since jsdom has no WebGL context and a real map cannot be constructed there at all - so the whole suite can pass while the shipped bundle draws nothing. That is not a hypothetical gap: maplibre-gl 6 stopped inlining its web worker and resolves one from its own module URL, which after bundling is the app chunk, so the built app fetched `assets/maplibre-gl-worker.mjs`, which no build ever emitted. MapLibre fires no error for that. The style still parsed, every layer was still in it, and the map was a blank sheet of paper on every platform, online and off - including the off-archive hatch that exists to say "no data here", which waits on a `load` event that a workerless map never fires. So the guard is on the artifact, not the source: `client/scripts/check-build-output.mjs` reads `dist/` and asserts that every asset the bundle references is really published, that the assets whose absence is *silent* are wired up rather than merely emitted, and that they are in the service worker's precache - a map that fetches part of itself on demand works in town and goes blank on a ridge. It runs as part of `npm run build`, so the check cannot be skipped by deploying. The source half is `client/src/map/mapWorker.test.ts` and one ordering test in `MapView.test.tsx`: MapLibre is pointed at a bundled worker URL, and pointed at it before any map is constructed (there is one worker pool per page, built for the first map, so a URL set afterwards is one nothing reads).

**Field testing (not automatable):** thresholds for off-trail distance and wrong-direction persistence need real GPS behaviour under tree canopy, ideally with NYNJTC/ATC volunteers, before the push path ships. Sunlight-glare readability and gloved one-handed use likewise (WIREFRAMES.md's `9d` is the greyscale pass to test against).

## Backend (Python/FastAPI, Phase 2+) - not yet built

Not scaffolded yet (see TECHNICAL_ARCHITECTURE.md). When it exists, it would likely reuse pytest and much of the pipeline's approach (HTTP mocking, synthetic fixtures over real data/DB where possible). Three invariants from the wireframe handoff belong here specifically, since they're only meaningfully enforceable server-side:

- `severity: serious` on a `Report` is only ever set by a user with a moderator role; a self-set attempt is rejected server-side, not just hidden client-side.
- Any report type intended to stay private (`bad_hikers` today - see [WIREFRAMES.md](WIREFRAMES.md) Known Deviations #2 for the still-open question of exactly what replaces it) has `visibility: internal-only` set on write, and public map/search API queries filter it out at the query level, not just in client rendering.
- Browsing endpoints (map, POIs, elevation, closures, warnings) require no auth token - a signed-out client can fetch all of them.

## CI

Three workflows, one per part: `.github/workflows/pipeline-tests.yml`, `backend-tests.yml` and `client-tests.yml`. Each runs that part's linter, formatter check and test suite - the same commands [CONTRIBUTING.md](CONTRIBUTING.md) gives for running them locally, so a green local run means a green CI run.

None of them is (yet) a required check via branch protection - a red run doesn't currently block merging, it's just visible on the PR.

### Why a PR only runs some of them

A pull request runs the suites for the parts it actually touches. Editing `ROADMAP.md` used to run all four jobs, including standing up a Postgres container, to prove that a paragraph of prose had not broken the trail exporter. Now it runs none of them, and each check still reports green with a summary saying why it had nothing to do.

The mapping is per-part and nothing finer: anything under `client/` runs the client suite, `backend/` the backend, `pipeline/` the pipeline. The three are genuinely independent - each carries its own dependency manifest, and none imports from another - so a per-part split is a fact about the repository rather than a guess about it. Each list also includes its own workflow file and `.github/actions/changed-paths/`, so a change to the gate re-runs the suite it gates.

Two deliberate limits:

- **`main` is never scoped.** A push to `main` runs everything, always. That trigger exists for post-merge validation against the real merge commit - it is what caught the flaky staleness boundary test in #32, green on the PR and red on the merge - and narrowing it would give back the thing it was kept for.
- **No test-level selection.** Nothing tries to work out that changing `export_trails.py` only needs `test_export_trails.py`. Tools for that exist and they infer the dependency graph, which means they can be wrong in the direction of not running a test that would have failed. At suites of about a minute there is nothing to win.

### How the scoping avoids blocking a PR

The obvious implementation is a `paths:` filter on the trigger, and it is a trap. A workflow skipped by a path filter reports no status at all, and a required status check that reports no status leaves the PR pending forever rather than passing it - so the day someone ticks "require Client tests", every docs-only PR becomes unmergeable for a reason that points nowhere near the cause. `pr-issue-link.yml` documents the same hazard for job-level `if:`.

So the triggers stay unfiltered and the decision moves inside the job, which always runs and always finishes green. `.github/actions/changed-paths` asks the API which files the PR touches and returns `run`; every step after it carries `if: steps.scope.outputs.run == 'true'`. The suites can be made required checks whenever the maintainer wants, with nothing else to change.

The action answers "run" for every case it is unsure about - a push, a PR too large for the files API to list, an API call that failed, an empty path list. Running a suite that did not need to run costs a minute; skipping one that did costs a merge, and does it quietly.
