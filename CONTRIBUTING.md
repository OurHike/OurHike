# Contributing to OurHike

OurHike is a map for hikers, built to be handed to the clubs that maintain the trails rather than owned by whoever wrote it. Contributions are welcome from anyone — club members, hikers, developers.

## Reporting something

**A trail condition** — a blowdown, flooding, a damaged shelter, a closure — goes through the **app's own "Report a problem" flow**, not GitHub. That reaches a moderator who can act on it. Nobody is watching this repository for washed-out bridges.

**A bug in the software**, or **a systematic data problem** (a shelter in the wrong place, a missing water source, a wrong blaze colour) belongs in [Issues](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues). There is a form for each.

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
| [ROADMAP.md](ROADMAP.md) | Phase narrative — where the project is and what each phase means |
| [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) | Ordered runbook for getting v1 deployed |
| [pipeline/DBT.md](pipeline/DBT.md), [pipeline/DATA_RELEASES.md](pipeline/DATA_RELEASES.md) | Data platform designs |

**Issues track the delta between that and reality** — anything with a state, an owner or a date. Open work, bugs, decisions still to make.

The rule that keeps these from rotting: **one home per item.** A task lives in an issue and links to its design doc. The design doc describes the intended state and does not enumerate the tasks. When both places listed the same work, one of them silently went stale — which is exactly how this repository ended up with a roadmap claiming the client was unbuilt while it was passing 601 tests.

If you are proposing something substantial, the design doc is usually the first contribution, not the code.

## Finding something to work on

- [`good first issue`](https://github.com/jaimito-asuntos-gringuenos/OurHike/labels/good%20first%20issue) — settled design, existing patterns to follow
- [`v1-mvp`](https://github.com/jaimito-asuntos-gringuenos/OurHike/labels/v1-mvp) — needed before launch
- [`post-mvp`](https://github.com/jaimito-asuntos-gringuenos/OurHike/labels/post-mvp) — designed, deliberately not started
- [`needs-field-testing`](https://github.com/jaimito-asuntos-gringuenos/OurHike/labels/needs-field-testing) — needs someone on an actual trail, which is a real contribution and does not require writing code
- [`blocked-external`](https://github.com/jaimito-asuntos-gringuenos/OurHike/labels/blocked-external) — waiting on credentials or a third party; probably not a good starting point

Area labels: `client`, `backend`, `pipeline`, `data`, `ops`, `docs`.

## Working on the code

Three independent parts, each with its own tests. CI runs the same commands, so a green local run means a green CI run.

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

**Backend** — FastAPI + SQLAlchemy + Postgres.

```
cd backend
pip install -r requirements-dev.txt
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

The pipeline fetches large amounts of data from ATC, USGS and opentrail.org. Read [pipeline/README.md](pipeline/README.md) before running the fetch scripts — a full topo quad pull is on the order of 14 GB, and the scripts are built to skip work that has not changed upstream. Do not defeat that by clearing manifests.

## Pull requests

- Branch off `main`. Small and focused beats comprehensive.
- Link the issue and let the merge close it — `Closes #42`. This is the mechanism that keeps the tracker honest, rather than someone remembering to tick a box.
- New behaviour comes with tests. See [TESTING.md](TESTING.md) for what is expected; the short version is that tests describe behaviour rather than implementation.
- If a change contradicts something in a design doc, update the doc in the same PR. A doc that disagrees with the code is worse than no doc.
- Lint and format before pushing. CI checks both and will fail on formatting alone.

## A note on data and licences

The app is AGPL-3.0. The data it ships is not all ours to relicense: USGS topo data is public domain, OpenStreetMap-derived basemap tiles are ODbL and require visible attribution (already rendered in `client/src/map/style.ts`), and opentrail.org's terms are [not yet formally confirmed](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/98). If you add a data source, establish its licence first and record it — an unlicensed source is a problem inherited by every club that takes this project on later.
