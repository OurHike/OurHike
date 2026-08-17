# Testing philosophy

This describes how OurHike tests its code, project-wide. All three parts now exist and carry suites - the pipeline, the client and the backend, plus a small fourth suite covering the repository's own settings - and each has its own section below following the same philosophy, not a separate one invented from scratch. The client and backend sections began as pre-build test plans; they are kept because they still name the behaviors those parts must not lose, and each now opens with what actually exists.

## Why this exists

Most of the pipeline was built through manual, ad hoc verification this session: one-off scripts, print statements, eyeballing results. That caught real bugs - an `ST_Transform` axis-order bug that silently produced garbage geometry, a band-count mismatch between fallback and bulk raster tiles, 3 genuinely corrupted USGS source files a shallow check missed - but none of those catches were permanent. Nothing stopped any of them from silently coming back the next time that code was touched.

**The core rule: every real gotcha becomes a regression test in the same change that fixes it - not just a comment.** A comment explains the bug to a human reading the code later; a test catches it automatically for a machine that isn't reading comments. This project has already paid for several of these lessons the hard way - the tests exist so nobody pays for them twice.

## What we test, project-wide

- **Pure functions** - zero setup, run in milliseconds. Every pure function should have one.
- **Small-synthetic-fixture tests** for anything spatial/numerical/binary (geometry, rasters, etc.) - tiny fixtures generated in test code, not committed as opaque binary files. A test that builds its own "corrupted" file byte-for-byte documents exactly what "corrupted" means; a checked-in blob doesn't.
- **HTTP-mocked tests** for any network-touching logic (especially change-detection/skip-logic, which is easy to silently break and expensive to notice - you'd only find out via a full re-fetch that should've been skipped). Real network calls are never allowed to fire during tests.

## A test proves the mechanism or proves the number, and says which

A passing test is read as evidence, so it has to be honest about what it is evidence
*of*. Two different things get asserted in this repository and they are worth very
different amounts:

- **The mechanism** - given this threshold, does the code do the right thing on each
  side of it. This is real coverage and it is most of the suite.
- **The number** - is the threshold itself right for a hiker on a trail. Almost nothing
  here proves this, and nothing in a test runner can: it needs field data.

**A test that locks in an unvalidated number, without saying so, converts a guess into a
rule** - the next contributor reads a red suite as "you broke it" rather than "you
changed a placeholder nobody has checked", and the number outlives everyone who knew it
was arbitrary. So a suite exercising a value tagged `@unvalidated` (see
[CLAUDE.md](CLAUDE.md)'s evidence rule) opens with a comment saying the numbers are
placeholders, asserts against the imported constants rather than literals, and names
what would validate them.

`client/src/lib/wrongWay.test.ts` is the worked example. Its header states that the
90 ft / 12 min / 25 min figures are WIREFRAMES.md mock-up placeholders pending
field-testing under canopy, that "these tests assert the MECHANISM behaves correctly
against the placeholder constants, never that the numbers themselves are correct", and
which direction of error the module exists to avoid. Every case then reads
`OFF_TRAIL_THRESHOLD_FT - 10` rather than `80`, so re-tuning the threshold moves the
tests with it and only a genuine behaviour change goes red.

Where a number *is* backed, cite the backing in the test rather than only at the
definition - the test is where the next person arrives when it fails.

## What we deliberately don't test

- **Real network calls** to live third-party services (ArcGIS, opentrail.org, USGS, etc.) in the automated suite - slow, flaky, not reproducible, and impolite to hammer on every test run.
- **Real large datasets** (e.g. the full 1,654-quad USGS fetch/mosaic) - too slow/heavy for a test suite. Verifying the real pipeline end-to-end against real data stays a **documented manual procedure**, not a test - see each component's section below for what that looks like today.
- **Pixel-perfect "golden image" comparisons** for raster output - assert structural properties (band count, CRS, nodata boundary location, no unexpected NaNs) instead of byte-identical files, which are too fragile to maintain as inputs change.

## Adding a new gotcha as a regression test

Found a bug where the code did something surprising or silently wrong? Before moving on:
1. Fix it.
2. Write a test named for the behavior it guards against (e.g. `test_full_band_read_catches_late_strip_corruption`, not `test_bug_47`), in the same commit/PR as the fix.
3. If it's fast to check, verify the test actually fails against the pre-fix code (revert the fix locally, confirm red, restore it, confirm green) - proves the test has teeth instead of passing vacuously.

## What has actually failed, and what it teaches

An audit of every CI run to date (2,538 runs, 2026-07-25 through 2026-08-06) puts numbers on where the risk really sits. Half of all suite failures were one infrastructure incident - the 2026-08-06 Actions outage - and a quarter were formatting-only, overwhelmingly `ruff format` in `pipeline/`, the exact round-trip CONTRIBUTING.md's "run what CI runs" exists to prevent. Real regressions caught by CI were about one failure in ten. Excluding the outage, the suites run ~98-99% green.

The failures that *mattered* - the only ones that broke `main` - were neither. Both were timing races in client tests that passed on their own PR and failed at the merge, where the machine was loaded differently:

- A staleness boundary test took two separate `Date.now()` readings and flaked when a millisecond elapsed between them (~1-in-6,000; broke `main` at #31, fixed in #32 with `vi.setSystemTime`).
- Map-readiness races, fixed twice: asserting on `MockMap.live[0]` after `findByRole` resolved but before the effect constructing the map had run, and later, firing `moveend` before an offline-background rebuild finished - the state was gone, not late. CLAUDE.md canonizes that incident.

Three rules fall out of this, and they are rules rather than tastes because each one has already cost a red `main`:

1. **A time boundary is tested with a set clock** (`vi.setSystemTime`), never with two reads of the real one.
2. **Wait on an observable that proves the sequence completed** - a map that reports itself live, a promise the code under test exposes - never on a sleep. A real-clock sleep followed by an assertion of *absence* is the worst shape: it passes on a broken implementation exactly as readily as on a correct one, and it is the next flake waiting for a loaded runner.
3. **A test that cannot fail is worse than no test** - it spends its credibility everywhere else. #175 tracks the known ones (listener-leak tests asserting on an event production no longer uses, progress tests that assert nothing). The gotcha rule above already says to confirm red once; that applies to audit findings too - a vacuous test gets teeth or gets deleted.

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

**Blaze normalization, still to build (see `features/TRAIL_BLAZE_COLORS.md`):** decoding each trail-line source's raw color coding into one normalized `blaze_color` attribute happens here, during export - not on the client (see the Client section below, which only tests the client's *use* of the already-normalized value). Once built, this needs a regression test for exactly the gotcha `TRAIL_BLAZE_COLORS.md` already names from the real data: `side_trails`' `Blaze` field has 24 features with no value at all, 9 with the literal string `"Unknown"`, and 3 with `"Gold"`, none of which are in its actual 0-9 coded domain. The test should assert all three fall through to the neutral default with a warning logged - not a crash, and not a silently wrong color.

**What's intentionally manual-only:** fetching the real ~1,650-quad USGS corridor dataset and mosaicking it (`fetch_topo_quads.py` + `spike_raster_mosaic.py`) is a real multi-GB, multi-minute operation against live services - run it by hand to verify changes that touch fetch/mosaic logic, don't expect it in `pytest`.

## Client (React/TypeScript)

Built, and now the largest suite in the repository: 1,735 tests across 119 files (measured 2026-08-06), ~98% statement coverage - visibility-only, not a gate, same stance as the pipeline. Framework: **Vitest + React Testing Library** in jsdom - Vitest because it shares Vite's transform pipeline (the confirmed bundler per TECHNICAL_ARCHITECTURE.md) instead of adding a second one; same philosophy as the pipeline (pure-function/component unit tests, no real network in the suite, mock any data/API calls), not a from-scratch set of conventions. MapLibre is a hand-written double in `src/test/mocks/maplibre-gl.ts` that models the real library's throwing and lifecycle behavior, wired per-file - jsdom has no WebGL, so this is necessity, and item 19 below is what keeps the necessity honest.

The test plan below is drawn from [WIREFRAMES.md](WIREFRAMES.md) - it named the behaviors the v1 MVP screens needed covered, written before the client itself so the first pass at each area could be built test-first per this file's core rule. Written as behaviors, not implementations, so they survive refactors - which is why it stays now that the client exists: it is the list of behaviors the suite must keep asserting, not a to-do list that finished.

One boundary worth stating plainly: everything in this suite runs in jsdom against mocked MapLibre and mocked storage. It attests to the *logic* of the client, on web semantics. What it cannot attest to - real IndexedDB under quota pressure, real map rendering, real touch, real platforms - is covered by the layers in "Redundancy" below, and the gaps that remain are named there rather than papered over here.

**Pure logic (fast unit tests, zero rendering):**
1. **Blaze normalization (client's half)** - the pipeline decodes raw source data into a normalized `blaze_color` string during export (see the Pipeline section above); the client's job is just mapping that already-clean string to a MapLibre paint style via a `match` expression. Test the client's defensive fallback: any `blaze_color` value that isn't one of the expected strings renders as the neutral grey and **emits a warning**, rather than the client trusting the pipeline blindly or crashing on an unexpected value. Line **width** is a second `match`, on the `source` attribute rather than on the blaze, and carries the hue-independent channel: the AT centerline is the widest line on the map, and a source this build has never heard of is drawn at the side-trail width rather than at nothing at all.
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
18. **Every POI category the app can name, it can draw.** The legend, search and the map all read one array, and the style's icon `match` resolves every published `POI_TYPES` entry to an image that was really registered - with an unknown type falling through to a neutral pin rather than to nothing. This is a regression guard for a real bug: POIs were fetched, stored, searchable and counted in the legend for months while the style had no layer that could put any of them on the map, so the legend's hide toggles were toggling layers that did not exist. Shape carries the category and colour only reinforces it (no two glyphs coincide, and none is a subset of another), since the accents sit within ~2:1 of each other and vanish as a channel in glare or greyscale - the same reasoning as the blaze line widths in #1.

19. **A build that cannot draw a map does not ship.** Every test in `client/src` mocks `maplibre-gl` outright - it has to, since jsdom has no WebGL context and a real map cannot be constructed there at all - so the whole suite can pass while the shipped bundle draws nothing. That is not a hypothetical gap: maplibre-gl 6 stopped inlining its web worker and resolves one from its own module URL, which after bundling is the app chunk, so the built app fetched `assets/maplibre-gl-worker.mjs`, which no build ever emitted. MapLibre fires no error for that. The style still parsed, every layer was still in it, and the map was a blank sheet of paper on every platform, online and off - including the off-archive hatch that exists to say "no data here", which waits on a `load` event that a workerless map never fires. So the guard is on the artifact, not the source: `client/scripts/check-build-output.mjs` reads `dist/` and asserts that every asset the bundle references is really published, that the assets whose absence is *silent* are wired up rather than merely emitted, and that they are in the service worker's precache - a map that fetches part of itself on demand works in town and goes blank on a ridge. It runs as part of `npm run build`, so the check cannot be skipped by deploying. The source half is `client/src/map/mapWorker.test.ts` and one ordering test in `MapView.test.tsx`: MapLibre is pointed at a bundled worker URL, and pointed at it before any map is constructed (there is one worker pool per page, built for the first map, so a URL set afterwards is one nothing reads).

20. **No screen keeps its own units.** Every height and distance a hiker reads goes through `client/src/lib/units.ts` and comes out in the system they chose (CONTRIBUTING.md states the standard; `features/UX_CUSTOMIZATION.md` holds the reasoning). Asserted as a property of the source rather than screen by screen - `client/src/test/unitDisplay.test.ts` scans every shipped `.ts`/`.tsx` for a unit written into a string literal and fails on one, the same shape and for the same reason as `themeTokens.test.ts`'s palette rule. Both catch a mistake that is invisible under the default and wrong for everyone else, and that no component test can fail on because it is not a mistake in the component: `unit_system` sat in the model, the backend's schema and the sync payload for months while eleven display sites printed feet and miles regardless, each of them locally correct. The rule matches on order - a unit *after* a figure (`${gain} ft`) is a measurement, a unit *before* one (`mi ${start}`) is the mile marker, which is a position on the A.T. and the one thing that does not convert - so the exception needs no exemption list and stays legible in the code that relies on it. The guard's own test asserts both halves, because a regex this quiet stops earning its place the day it silently matches nothing.

**Field testing (not automatable):** thresholds for off-trail distance and wrong-direction persistence need real GPS behaviour under tree canopy, ideally with NYNJTC/ATC volunteers, before the push path ships. Sunlight-glare readability and gloved one-handed use likewise (WIREFRAMES.md's `9d` is the greyscale pass to test against).

## Backend (Python/FastAPI)

Built. pytest, 167 tests (measured 2026-08-06), reusing the pipeline's approach - synthetic fixtures, no network (every JWT is minted locally; the JWKS fetch is a monkeypatched seam, never called). The one deliberate departure from "mock the heavy thing": the suite runs against a **real local Postgres 16** - the same engine Supabase runs in production - never a stand-in dialect, because RLS statements, Alembic migrations up *and* down, and `pg_class` readbacks are exactly the things a stand-in would vouch for wrongly. `scripts/local-postgres.sh` makes that a one-command setup, and CI runs a service container of the same version.

The isolation model is worth knowing before pointing `DATABASE_URL` anywhere: each test drops every table in whatever database that URL names and recreates the schema. That is what makes the suite recover from a run killed mid-test, and it is also why the URL must never name a database anyone cares about. Since #320 the harness enforces that rather than trusting it: `conftest.py` refuses to run unless the database `DATABASE_URL` names ends in `_test`, with a message saying what to set instead — the test database differs from the dev default by four characters, and one stray export used to be the whole distance between running the suite and emptying `ourhike_dev`.

That model is also why this suite is the one place in the repository where parallelism had to be bought rather than switched on. "Drop every table between tests" is safe exactly as long as one process is doing it; four `pytest -n` workers sharing one database do not merely fail, they wedge, each blocking on locks held by tables another worker is partway through dropping — measured at 1785s before it was killed, against 60s for the same suite serially. So `tests/conftest.py` gives each worker its own database, created on demand, and the per-test drop is unchanged inside it. Every worker still runs its own tests serially against its own schema, which is the model that was already there; `gw0` simply cannot see `gw1`'s tables to drop them. `tests/test_worker_database.py` is what keeps that true, including one test asserting the rewrite actually took effect in the process running it — a rewrite that silently became a no-op would put every worker back on one database and buy the deadlock back.

Three invariants from the wireframe handoff live here specifically, since they're only meaningfully enforceable server-side:

- `severity: serious` on a `Report` is only ever set by a user with a moderator role; a self-set attempt is rejected server-side, not just hidden client-side.
- Any report type intended to stay private (`bad_hikers` today - see [WIREFRAMES.md](WIREFRAMES.md) Known Deviations #2 for the still-open question of exactly what replaces it) has `visibility: internal-only` set on write, and public map/search API queries filter it out at the query level, not just in client rendering.
- Browsing endpoints (map, POIs, elevation, closures, warnings) require no auth token - a signed-out client can fetch all of them.

## Repository settings

The one thing in this repository that its own test suites structurally cannot see. A GitHub Actions secret is write-only once set: the API will not read one back, and neither will the maintainer who set it. So nothing in a checkout - no pytest run, no vitest run, no reviewer reading the diff - can tell you whether `R2_SECRET_ACCESS_KEY` is configured. The failure that produces is the expensive kind: it surfaces at the moment some workflow needs the value, which for the R2 credentials is partway through a publish, and which for `DATA_BASE_URL` was an app that built, installed and then could not download a map.

**Framework:** pytest in `.github/tests/`, with `.github/expected-settings.yml` as the manifest of what is supposed to be configured. Same ruff config as the pipeline and backend suites.

Split by what can see what, not by taste:

- **From a checkout** - the manifest and `.github/workflows/` still agree. Every `secrets.X`/`vars.X` a workflow reads is declared; nothing declared has outlived its last reader; nothing is read from the context it wasn't declared for (GitHub resolves the wrong one to an empty string rather than an error, so that surfaces as missing configuration somewhere far away). Runs anywhere, including on a fork's PR. This is the half with teeth on an ordinary change, because drift is what actually happens.

- **From inside Actions** - the settings really exist. `settings-configured.yml` resolves the `secrets` and `vars` contexts, reduces them to the *names* that came back non-empty, and passes only those to pytest. Values never enter the test process, which is what lets the failure messages be written for a human to read. It runs weekly, because a revoked R2 token is a change nobody makes to this repository, and there is otherwise nothing to notice it before the next publish does.

Which workflows use a setting is derived, never written down - a hand-kept copy is the half that goes stale (CONTRIBUTING.md's one home per item). `LAUNCH_CHECKLIST.md` steps 1.3 and 2 stay the prose instructions; the manifest is the same statement in a form a test can read.

Two of these guard the checker rather than the settings, and both earn their place: one asserts the live inputs are names and never values, so a change that stopped reducing the contexts fails loudly instead of quietly putting credentials in an assertion message; the other fails the live job if its environment didn't arrive, since every live test skipping is otherwise indistinguishable from all of them passing.

**The suite also holds claims about the *set* of workflows,** which is the other thing no checkout of one file can answer. `test_supabase_keepalive_workflow.py` is the current example: it fails if a second scheduled workflow starts reaching the Supabase project, because one sweep is all a free-plan project needs and a second is only another thing to keep in sync — and it fails on a schedule that has quietly stopped running often enough, which is the one part of that job with no feedback loop of its own. It asserts the **longest gap the cron leaves**, not the string it is written as: `50 */20 * * *` reads like "every 20 hours" and actually fires 20 hours apart and then 4, so a test pinning the text would have said nothing about the thing that decides whether the job works.

**Warning, not failure:** a setting declared for the Variables tab that is *also* kept as a secret still works, which is exactly why it survives. What it costs is the readability the Variables tab existed to provide - GitHub masks a registered secret value everywhere it appears, so the variable's own value prints as `***` too. `pages.yml` cannot see this: it takes the variable and never looks at the secret.

## Platforms - web now, iOS and Android at Phase 3

The client is one codebase for all three platforms: a PWA, wrapped with Capacitor for the app-store builds (TECHNICAL_ARCHITECTURE.md). The wrapper does not exist yet - that is Phase 3 - so "will the tests work on Android and iOS" has a precise answer today: the suite runs anywhere Node runs and will keep passing unchanged after wrapping, but it *attests* to web semantics only. jsdom is one idealized browser; nothing in a green run speaks for WKWebView on iOS or the Android System WebView. And those are where this app's riskiest behaviors genuinely differ:

- **Storage.** WebKit can evict an origin's storage - Safari applies a seven-day cap to sites that aren't installed, and every platform evicts under pressure unless `navigator.storage.persist()` is granted. The suite's storage layer is mocked (`idb-keyval`), so eviction and quota exhaustion are precisely the failure modes it cannot see, on the platform where a hiker's 1.18 GB archive matters most. Quota exhaustion is now reachable by hand in Chromium (`client/scripts/storage-probe/`, and #544 is what it found); eviction, WebKit's allowance and the seven-day cap are still nothing but this paragraph.
- **Service worker and offline.** Registration, precache and update semantics inside a Capacitor shell (which serves from a local origin) differ from a browser tab's. The build-output check guards the artifact; nothing yet exercises it inside a WebView.
- **Geolocation and permissions.** Prompt flows and background behavior are platform policy, not web spec.
- **Touch.** No test on either side simulates a touch; gestures are delegated to MapLibre, which every test mocks. Tap-target sizes are asserted as CSS text only.
- **Image decoding and canvas.** jsdom has neither, so `client/src/lib/reportPhoto.ts` - the shrink and EXIF strip a report photo goes through (#234) - is tested against a doubled `createImageBitmap` and a doubled canvas. That proves the arithmetic and the decisions (scale factor, quality ladder, what is refused, what is released) and proves nothing about whether a real JPEG from a real phone survives the round trip. This is the same shape of gap as item 19's blank map, on a path whose failure is quieter: a wrong answer here is a sideways photo, an oversized upload, or EXIF that was never actually dropped. HEIC in particular is decided entirely by the browser, and a phone that cannot decode its own camera format is a real case this cannot see.

When Capacitor lands, the posture is: the unit suite stays platform-agnostic and does not fork. What gets added is a thin per-platform smoke layer, not a parallel suite - Playwright's WebKit and Chromium builds are the same rendering engines the two WebViews embed, which makes an engine-level smoke check cheap and runnable in CI. The truly device-bound behaviors - storage eviction, permission prompts, background GPS under canopy - belong to Phase 3 acceptance runs on real devices and to field testing: a documented manual procedure, same category as the full USGS fetch.

## Redundancy - what double-checks what

Coverage says how much code the tests touch. Redundancy is the different question of how many *independent* layers have to fail before a hiker sees the bug. Where it exists here, it has already earned its keep:

- **The build-output check backs up the mocked-map suite.** Every source test mocks MapLibre, so `client/scripts/check-build-output.mjs` in `npm run build` is the second layer - it exists because of the one class of bug (item 19's worker URL) that a fully green suite structurally could not see.
- **The settings manifest backs up the live check.** Drift is caught from any checkout on every PR; existence is confirmed from inside Actions weekly. Different failure modes, different vantage points.
- **The post-merge full run on `main` backs up PR path-scoping.** It caught the staleness flake that was green on its own PR (#32), and it is what makes scoping PRs safe at all.
- **The live project backs up the RLS migration.** `backend/tests/test_migration_rls.py` proves a revision turns RLS on and that no model escaped one; the Supabase keepalive (LAUNCH_CHECKLIST.md 4.6) reads all seven tables with the anon key against the deployed project, twice a day, and fails on a row. Different claims - "the migration says so" and "the database still does" - and the second one is asked through the front door an attacker would use.
- **The elevation-gain vectors are asserted from both languages.** `pipeline/reference/gain_vectors.json` is read by a pytest suite and a Vitest suite, with a guard test against the file silently emptying - the model for every cross-part contract.
- **The vocabularies both ends speak are compared, by reading the other end's source as text.** Four models are written twice in two languages, and each copy's comments claim to mirror the other. These are what check it: `backend/tests/test_preferences_contract.py` (the `UserPreferences` field names, and since the v1 review the enum *values* under them), `backend/tests/test_client_report_contract.py` (report types, reporter types, moderation statuses, and the photo cap `lib/reportPhoto.ts` is told to duplicate), and `pipeline/tests/test_published_key_contract.py` (every published R2 key the app fetches, against what `publish.collect_artifacts()` actually writes). Reading the source rather than restating the list is the whole mechanism: a third copy in Python would be one more thing to drift. Each file carries a guard-the-guard test, because a regex that matches nothing compares two empty sets and stays green for ever.

And where it is missing (audited 2026-08-06, revised during the v1 review), which is where a bug can ship green today:

- ~~**The backend↔client seam is checked at its edges, not down the middle.**~~ Closed by #316. `backend/tests/test_client_response_contract.py` asserts the five response shapes the client declares (`ReportSummary`, `ClosureSummary`, `ProfileSummary`, `QueuedReport`, `QueuedClosure`) against `app.openapi()` — presence, nullability and scalar type, plus the closure vocabulary and the request direction the outbox writes. Two things about it are worth keeping if it is ever rewritten. It runs against the **document** rather than the response models, so it is reached through the route table: a route rewired to serve a different schema fails it while `ReportOut` sits unchanged, which a model-level check cannot see. And the rule is **subset, in one direction** — the client declaring fewer fields than the server sends is the intended design (`ClosureSummary`'s own comment: "limited to the fields this app reads"), while a field the client declares and the server does not send is `undefined` behind a type that says `string`, because `response.json() as ReportSummary[]` is an assertion and not a parse.

  What is still not checked, and is a smaller thing than the bullet it replaces: type narrowing beyond scalars and nullability, for the reason `check_openapi_compat.py` gives about its own four rules — detecting those well means implementing JSON Schema subtyping, and detecting them badly means a check people learn to override.
- ~~**The one existing contract test is one-sided in CI.**~~ Fixed in the v1 review (#317). The rule it left behind is the one that matters, and it now has three files depending on it: **a suite's scope list includes every file its tests read.** The client suite reads `pipeline/reference/gain_vectors.json` and `site/index.html`; the backend and pipeline suites each read four modules under `client/src/lib/`. All three scope lists say so, and each says why - because the drift a cross-language guard exists to catch usually arrives in a pull request that touches only the *other* language, which is exactly the run a same-directory scope would skip.

  **The Python suites name those files individually rather than listing `client/src/lib/`**, and that is a deliberate second decision rather than fussiness. The directory is touched by most client work, so the broad prefix stood up a Postgres container and ran two Python suites on nearly every client pull request in order to check eight modules that change a few times a year. A tax that size on the commonest kind of change here is how a rule ends up quietly relaxed later.

  What makes the narrow list safe is that it is checked: `backend/tests/test_ci_scope.py` and `pipeline/tests/test_ci_scope.py` parse their own workflow and compare its scope list against the paths the contract tests declare (`CLIENT_FILES_READ`), so a contract test that starts reading a fifth client file fails there rather than silently ceasing to run in CI. This is the general shape worth copying: **narrow the scope list as far as you like, provided something fails when it goes stale.** The client suite keeps directory prefixes and has no equivalent guard - `pipeline/reference/` and `site/` are whole directories rather than named files, so there is much less to go stale, and finding the out-of-tree reads in a Vitest suite would mean parsing them out of test source. That is the remaining soft spot in this rule, and it is the one #317 was originally about.
- **The guard has no guard.** `check-build-output.mjs` has no tests of its own. If its assertions rot, every layer past the unit suite is gone and nothing says so.
- **Storage has one layer in CI and it is simulated.** Between `vi.mock('idb-keyval')` and a full phone, CI has nothing - no real-IndexedDB run, no quota-pressure test, for the app's headline feature. What now exists off to the side is `client/scripts/storage-probe/`, which drives the real download into a real Chromium at a real size, by hand. It is what found #544 - the Fine tier transferring all 1.18 GB before failing to store it, because the Blob being accumulated is not charged against the origin's quota, so nothing refuses until the final `set()`. No jsdom test can see that, and this one saw it in a minute. It is deliberately not a gate: it moves gigabytes and its numbers depend on the machine's free disk. **The gap that remains is that nothing runs it on a schedule**, so a regression in the download path is caught by whoever thinks to look.

## CI

Three workflows, one per part: `.github/workflows/pipeline-tests.yml`, `backend-tests.yml` and `client-tests.yml`. Each runs that part's linter, formatter check and test suite - the same commands [CONTRIBUTING.md](CONTRIBUTING.md) gives for running them locally, so a green local run means a green CI run.

None of them is (yet) a required check via branch protection - a red run doesn't currently block merging, it's just visible on the PR. All three do now trigger on `merge_group` as well, so they report against a merge queue entry the day one is switched on; [BRANCHING.md](BRANCHING.md) is the home for that, including which checks are safe to require and which would wedge the queue.

**Two workflows run the settings suite, split by what each half can see** (#679). `settings-manifest.yml` runs the from-a-checkout half on every PR, including from a fork, and carries `merge_group:` so it can be - and now is - a required check. `settings-configured.yml` runs the live half weekly and deliberately never on a pull request, because GitHub passes no secrets to a fork's PR run and the job would fail for every outside contributor for a reason none of them could fix.

They were one file until #679, and the split bought something specific. The combined file was the only workflow here that both ran on `pull_request` and read the secrets context, and any pull request that proposed *any* change to it - a comment was enough - got `action_required` with zero jobs instead of a status. Measured by restoring the file byte-for-byte, which turned it green again. `settings-manifest.yml` reads no secrets context anywhere, so it sits under no such gate. BRANCHING.md holds the table, the mechanism, and the full history.

### Why a PR only runs some of them

A pull request runs the suites for the parts it actually touches. Editing `ROADMAP.md` used to run all four jobs, including standing up a Postgres container, to prove that a paragraph of prose had not broken the trail exporter. Now it runs none of them, and each check still reports green with a summary saying why it had nothing to do.

The mapping is per-part and nothing finer: anything under `client/` runs the client suite, `backend/` the backend, `pipeline/` the pipeline. The three are genuinely independent - each carries its own dependency manifest, and none imports from another - so a per-part split is a fact about the repository rather than a guess about it. Each list also includes its own workflow file and `.github/actions/changed-paths/`, so a change to the gate re-runs the suite it gates.

Two deliberate limits:

- **`main` is never scoped.** A push to `main` runs everything, always. That trigger exists for post-merge validation against the real merge commit - it is what caught the flaky staleness boundary test in #32, green on the PR and red on the merge - and narrowing it would give back the thing it was kept for.
- **No test-level selection.** Nothing tries to work out that changing `export_trails.py` only needs `test_export_trails.py`. Tools for that exist and they infer the dependency graph, which means they can be wrong in the direction of not running a test that would have failed. At suites of about a minute there is nothing to win.

### How the scoping avoids blocking a PR

The obvious implementation is a `paths:` filter on the trigger, and it is a trap. A workflow skipped by a path filter reports no status at all, and a required status check that reports no status leaves the PR pending forever rather than passing it - so the day someone ticks "require Client tests", every docs-only PR becomes unmergeable for a reason that points nowhere near the cause. `pr-issue-link.yml` records the same hazard for job-level `if:`.

So the triggers stay unfiltered and the decision moves inside the job, which always runs and always finishes green. `.github/actions/changed-paths` asks the API which files the PR touches and returns `run`; every step after it carries `if: steps.scope.outputs.run == 'true'`. The suites can be made required checks whenever the maintainer wants, with nothing else to change.

The scoping is a pull-request optimisation and deliberately stops there: on a merge queue entry the action answers "run" for everything, the same as it does for a push. A queue entry is a commit combining several pull requests, so the union of their file lists is the most any filter could compute - and the failure a queue exists to catch is the one that belongs to the combination rather than to either diff, which no file list shows.

The distinction is which half of the check you want. `settings-configured.yml` has no `pull_request` trigger on purpose, and is right not to: that check *should* be absent on a pull request, because it cannot pass on one. Until #679 it expressed the same intent as a job-level `if:` on a trigger it did not want, which is the weaker form - a workflow that simply does not trigger says so in one place rather than two. A test suite is the opposite - it is a check a reviewer expects to see reporting, so it has to report even when the answer is "nothing to do".

The action answers "run" for every case it is unsure about - a push, a PR too large for the files API to list, an API call that failed, an empty path list. Running a suite that did not need to run costs a minute; skipping one that did costs a merge, and does it quietly.

### The same decision, locally

`scripts/test.sh` makes that decision before the push instead of after it. CONTRIBUTING.md asks for every suite before every push and is right to - the round trip it prevents is real, and a quarter of this repository's CI failures were formatting alone. What it costs is the whole four-suite run for a change that could only have broken one part, which is most changes here.

Measured on a four-core machine: the full sequence CONTRIBUTING.md lists takes **294s**. `scripts/test.sh --all` is the same four suites in **174s**, and a change to one of the Python parts is **20 to 50 seconds** because the other three suites do not run at all. A client-only change is about **two minutes**, nearly all of it the client suite itself - that one is large enough that scoping is what helps every *other* change, rather than something that helps it. Three things get those numbers, and only the first is a judgement call:

- **Only the affected suites run.** The scope lists are *read out of the workflow YAML at run time*, not copied into the script - the same parse `test_ci_scope.py` already does, so local and CI cannot disagree by being forgotten. Adding a path to a workflow changes what runs locally in the same edit. Every uncertain case runs everything, for the reason the action gives: a stale `main` ref, no upstream, an unreadable workflow, a detached head.
- **The suites run across cores.** `pytest-xdist` for the three Python suites; vitest already did. Pipeline 45s to 22s, settings 24s to 12s, backend 60s to 16s.
- **Coverage is off unless asked for.** It is visibility-only in all four suites by deliberate decision, so leaving it out cannot turn a green run red or the reverse - and it is not free: 148s against 100s for the client. `--coverage` puts it back, and CI measures it on every run regardless, which is where the report is actually read.

The linters and formatters for every selected suite run **before any suite does**, which is the ordering CLAUDE.md asks for and the reason it asks. Ruff and prettier answer in about six seconds against three minutes of tests, and the CI job that catches formatting runs the formatter first - so a formatting-only failure there never ran the tests at all and the log said nothing about the change being made.

What this does *not* do is select individual tests, for the reason the section above gives. Per part is still the whole of the mapping.

## The long-term strategy

Where this is going, given what the audit measured. Five commitments, in the order they pay off; the concrete deltas live in issues, per CONTRIBUTING.md's one-home rule.

1. **Contracts are asserted, not remembered.** Every surface two parts share gets the `gain_vectors.json` treatment: one fixture or schema, read from both sides, with a guard against the shared file going silently empty - the publish manifest's shape, the POI category ids, the download-tier sizes, and above all the backend's API, asserted from its OpenAPI document rather than from a hand-kept TypeScript copy. And every shared file sits in the scope list of every suite that reads it, so the guard fires on the PR, not after the merge.

2. **Flake classes die structurally, not case-by-case.** Both incidents that broke `main` were the same class passing review twice. The rules in "What has actually failed" become mechanical where a config can hold them: a network guard in the client's test setup (the pipeline's "any unmocked request raises" posture, which the client currently trusts to convention), `TZ` pinned in CI so a formatter without an explicit zone cannot pass by fixture luck, and waits on observables rather than sleeps - with the real-clock-sleep-then-assert-absence shape treated as a defect in review, not a style preference.

3. **A real-browser layer lands between jsdom and the trail.** Not a broad E2E suite - a smoke: the built app boots in real Chromium and WebKit, constructs a real map with its real worker, completes one small archive download against real IndexedDB, and comes back up offline. Its job is to catch the classes of bug the mocks structurally cannot - item 19's blank map is the acceptance test for it - and it doubles as the platform smoke layer Phase 3 needs anyway. Until it exists, `check-build-output.mjs` is the only non-jsdom layer, which is why it gets tests of its own.

4. **Platform coverage arrives with Phase 3, not before.** Per the Platforms section: the unit suite never forks per platform; engine-level smoke runs in CI; device-bound behavior is Phase 3 acceptance plus field testing, documented as manual procedure.

5. **Red means code.** Half of all historical failures were one outage and a quarter were formatting - noise that teaches people to re-run instead of read. The controllable half: dependencies pinned or locked in both Python suites (the client already has a lockfile) so an upstream release cannot redden an unrelated PR, and the DuckDB spatial extension cached in CI the way the session hook already seeds it locally, closing the one standing network dependency in "tests never touch the network."

None of this moves the core rule. Every real gotcha still becomes a regression test in the same change that fixes it. The strategy is about the suite those tests land in - making sure its green is worth trusting, on every platform a hiker will actually stand on.
