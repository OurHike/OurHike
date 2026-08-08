# Contributing to OurHike

OurHike is a map for hikers, built to be handed to the clubs that maintain the trails rather than owned by whoever wrote it. Contributions are welcome from anyone — club members, hikers, developers.

## Reporting something

**A trail condition** — a blowdown, flooding, a damaged shelter, a closure — goes through the **app's own "Report a problem" flow**, not GitHub. That reaches a moderator who can act on it. Nobody is watching this repository for washed-out bridges.

**A bug in the software**, or **a systematic data problem** (a shelter in the wrong place, a missing water source, a wrong blaze colour) belongs in [Issues](https://github.com/OurHike/OurHike/issues). There is a form for each.

If a bug could mislead someone about where they are, where water is, or a hazard, say so — there is a checkbox for it, and those get looked at first. This app gets used in places where being wrong is expensive.

## Where things are written down

This repository keeps two different kinds of writing, and the difference is worth knowing before you go looking.

**Docs describe what OurHike is and why.** They are canonical, reviewed in pull requests alongside the code, and meant to be read.

| | |
|---|---|
| [OurHikeValues.md](OurHikeValues.md) | The nine values everything else is argued against |
| [FEATURES.md](FEATURES.md) | What the product is, MVP and beyond |
| [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) | How it is built and why those choices |
| [WIREFRAMES.md](WIREFRAMES.md) | Screen-by-screen specification |
| [features/](features/) | Full design drafts, one per feature |
| [TESTING.md](TESTING.md) | Testing approach and standards |
| [BRANCHING.md](BRANCHING.md) | Branching and pull request strategy, and running several at once |
| [ROADMAP.md](ROADMAP.md) | Phase narrative — where the project is and what each phase means |
| [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) | Ordered runbook for getting v1 deployed |
| [RELEASING.md](RELEASING.md) | How a release is versioned, named, gated and shipped, and the three environments it moves through |
| [pipeline/DBT.md](pipeline/DBT.md), [pipeline/DATA_RELEASES.md](pipeline/DATA_RELEASES.md) | Data platform designs |
| [pipeline/R2_LAYOUT.md](pipeline/R2_LAYOUT.md) | Where an artifact goes in the bucket and what it may be called |

**Issues track the delta between that and reality** — anything with a state, an owner or a date. Open work, bugs, decisions still to make.

The rule that keeps these from rotting: **one home per item.** A task lives in an issue and links to its design doc. The design doc describes the intended state and does not enumerate the tasks. When both places listed the same work, one of them silently went stale — which is exactly how this repository ended up with a roadmap claiming the client was unbuilt while it was passing 601 tests.

If you are proposing something substantial, the design doc is usually the first contribution, not the code.

## Finding something to work on

- [`good first issue`](https://github.com/OurHike/OurHike/labels/good%20first%20issue) — settled design, existing patterns to follow
- [`v1-mvp`](https://github.com/OurHike/OurHike/labels/v1-mvp) — needed before launch
- [`post-mvp`](https://github.com/OurHike/OurHike/labels/post-mvp) — designed, deliberately not started
- [`needs-field-testing`](https://github.com/OurHike/OurHike/labels/needs-field-testing) — needs someone on an actual trail, which is a real contribution and does not require writing code
- [`blocked-external`](https://github.com/OurHike/OurHike/labels/blocked-external) — waiting on credentials or a third party; probably not a good starting point

Area labels: `client`, `backend`, `pipeline`, `data`, `ops`, `docs`.

## Working on the code

Three independent parts, each with its own tests, plus a small fourth suite covering the repository's own CI configuration. CI runs the same commands, so a green local run means a green CI run.

**Client** — React + TypeScript + Vite, MapLibre GL for the map.

```
cd client
npm ci
npm test          # vitest with coverage
npm run typecheck
npm run lint      # oxlint
npm run format:check
npm run dev
```

**Backend** — FastAPI + SQLAlchemy + Postgres. The suite talks to a real local
Postgres (the same engine Supabase runs), so start one first; the script is
idempotent and safe to re-run.

```
cd backend
pip install -r requirements-dev.txt
bash scripts/local-postgres.sh   # starts Postgres, creates ourhike_dev/ourhike_test
python -m pytest -v
python -m ruff check .
python -m ruff format --check .
```

**Pipeline** — Python + DuckDB, builds the map data.

```
cd pipeline
pip install -r requirements-dev.txt
python -m pytest -v
python -m ruff check .
python -m ruff format --check .
```

**Repository settings** — the workflows' own configuration.

```
cd .github/tests
pip install -r requirements-dev.txt
python -m pytest -v
python -m ruff check .
python -m ruff format --check .
```

Locally this checks that [`.github/expected-settings.yml`](.github/expected-settings.yml) still agrees with the workflows: every secret and variable a workflow reads is declared, and nothing declared has outlived its last reader. Whether those settings actually *exist* is a question no checkout can answer — a secret's value is write-only once set — so the **Settings check** workflow answers it from inside Actions, weekly and on every push to `main`. Adding a workflow that reads a new secret means adding it to the manifest in the same change.

### Changing a Python dependency

The `requirements.txt` and `requirements-dev.txt` files are **compiled output** — every package pinned to an exact version, transitive ones included. Do not edit them by hand. The hand-written files are the matching `.in`, which is where the comments explaining *why* a dependency exists live.

Add, remove or re-pin something in the `.in`, then regenerate. Each compiled file carries the exact command that produced it in its header; for `pipeline/` that is:

```
uv pip compile --universal --python-version 3.11 pipeline/requirements.in -o pipeline/requirements.txt
uv pip compile --universal --python-version 3.11 -c pipeline/requirements.txt pipeline/requirements-dev.in -o pipeline/requirements-dev.txt
```

Compile the runtime file first: the dev file takes it as a constraint, so the two cannot drift onto different versions of a shared package. `--universal` resolves across platforms rather than baking in whichever machine ran the command, and the 3.11 floor keeps one file installable on both CI's 3.14 and the web sandbox's 3.11.

Pinning is not tidiness. Four workflows — `build-basemap`, `build-dem`, `build-raster` and `publish-vector-data` — install these files in a job holding R2 write credentials, so an unpinned resolve means a compromised upstream release executes next to the keys for the bucket hikers download maps from. Dependabot proposes the bumps ([`.github/dependabot.yml`](.github/dependabot.yml)), grouped weekly so the queue stays readable.

The pipeline fetches large amounts of data from ATC, USGS and opentrail.org. Read [pipeline/README.md](pipeline/README.md) before running the fetch scripts — a full topo quad pull is on the order of 14 GB, and the scripts are built to skip work that has not changed upstream. Do not defeat that by clearing manifests.

## Pull requests

- Branch off `main`. Small and focused beats comprehensive.
- **Do not merge `main` back in to keep the branch current.** GitHub merges your pull request against `main` as it stands at that moment, so a branch that is behind produces exactly the same result as one freshly caught up — the catch-up run costs a CI round trip and buys nothing. Merge `main` in when it genuinely conflicts, or when your branch cannot pass its own tests without something that landed there. `scripts/threads.sh` answers which, for every branch at once, without touching your working tree. [BRANCHING.md](BRANCHING.md) has the reasoning and the rest of the strategy.
- Link the issue and let the merge close it — `Closes #42`. This is the mechanism that keeps the tracker honest, rather than someone remembering to tick a box. CI checks it: a PR that closes no issue fails **PR has a linked issue**. Attaching the issue through the sidebar's Development panel counts too, though that fires no event, so the check needs a manual re-run afterwards. A bare `#42` mention does not count — referring to an issue and resolving it are different claims.
- If a change genuinely has no issue behind it — a typo, a revert, a dependency bump — label it `no-issue` rather than opening an issue for the sole purpose of closing it. The exemption is there so the rule does not manufacture the paperwork it exists to prevent.
- New behaviour comes with tests. See [TESTING.md](TESTING.md) for what is expected; the short version is that tests describe behaviour rather than implementation.
- If a change contradicts something in a design doc, update the doc in the same PR. A doc that disagrees with the code is worse than no doc.
- Lint and format before pushing. CI checks both and will fail on formatting alone.

Money Man (cost) requirements

- The project maintains a strict $0 ongoing-cost policy for core features unless a documented coverage plan exists. Any PR that introduces a new external dependency, paid API, hosted dataset, or server-side background job must include a COSTS.md (see project root) documenting recurring cost estimates, mitigation options, and approval.
- The repository includes a lightweight GitHub Actions cost check that scans PR changes for common paid-provider indicators (e.g., Mapbox, Google Maps, AWS, Stripe, MapTiler). If a potential paid provider is detected and no COSTS.md is present in the PR or at the repository root, the check will fail and request a documented mitigation or funding plan.
- PR reviewers must explicitly consider cost implications: check whether the change needs a new secret, a hosted service, or long-running storage/compute. If the change introduces recurring costs, require a funding/coverage plan and a named approver before merge.
- Add `@money-man` (or request a cost reviewer) on PRs that touch map providers, external APIs, telemetry, server-side inference, or paid hosting.


## A note on data and licences

The app is AGPL-3.0. The data it ships is not all ours to relicense: USGS topo data is public domain, OpenStreetMap-derived basemap tiles are ODbL and require visible attribution (already rendered in `client/src/map/style.ts`), the bundled Noto Sans glyphs are SIL OFL 1.1 (provenance and licence text in `client/public/glyphs/`), opentrail.org's terms are [not yet formally confirmed](https://github.com/OurHike/OurHike/issues/98), and POI photos are Wikimedia Commons files licensed **per photo** (public domain, CC0, or CC BY / CC BY-SA at 4.0+ only — the pipeline rejects everything else, including pre-4.0 CC versions, whose terms a one-link credit cannot meet), each shipping with the author, licence and file-page link the waypoint card displays (`features/POI_PHOTOS.md`). If you add a data source, establish its licence first and record it — an unlicensed source is a problem inherited by every club that takes this project on later.
