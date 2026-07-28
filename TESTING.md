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

**What's intentionally manual-only:** fetching the real ~1,650-quad USGS corridor dataset and mosaicking it (`fetch_topo_quads.py` + `spike_raster_mosaic.py`) is a real multi-GB, multi-minute operation against live services - run it by hand to verify changes that touch fetch/mosaic logic, don't expect it in `pytest`.

## Client (React/TypeScript) - not yet built

Not scaffolded yet (see ROADMAP.md Phase 2). When it exists, the natural fit is Vitest or Jest + React Testing Library - same philosophy as above (pure-function/component unit tests, no real network in the suite, mock the pipeline's data API), not a from-scratch set of conventions.

## Backend (Python/FastAPI, Phase 2+) - not yet built

Not scaffolded yet (see TECHNICAL_ARCHITECTURE.md). When it exists, it would likely reuse pytest and much of the pipeline's approach (HTTP mocking, synthetic fixtures over real data/DB where possible).

## CI

`.github/workflows/pipeline-tests.yml` runs `ruff check`, `ruff format --check`, and `pytest` on every push and on PRs targeting `main`. It's not (yet) a required check via branch protection - a red run doesn't currently block merging, it's just visible on the PR.
