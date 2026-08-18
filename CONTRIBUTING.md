# Contributing to OurHike

OurHike is a map for hikers, built to be handed to the clubs that maintain the trails rather than owned by whoever wrote it. Contributions are welcome from anyone — club members, hikers, developers.

## Reporting something

**A trail condition** — a blowdown, flooding, a damaged shelter, a closure — goes through the **app's own "Report a problem" flow**, not GitHub. That reaches a moderator who can act on it. Nobody is watching this repository for washed-out bridges.

**A bug in the software**, or **a systematic data problem** (a shelter in the wrong place, a missing water source, a wrong blaze colour) belongs in [Issues](https://github.com/OurHike/OurHike/issues). There is a form for each, and the app links to both from **Settings → Report a bug** with the build details already filled in — so a report filed that way names the exact build it came from without anyone retyping a commit hash.

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
| [pipeline/SOURCE_SURVEY.md](pipeline/SOURCE_SURVEY.md) | Upstream A.T. data sources, surveyed and qualified (dated snapshot) |
| [pipeline/NYC_SOURCE_SURVEY.md](pipeline/NYC_SOURCE_SURVEY.md) | Trail sources within a day of NYC — DEC, NYNJTC, the NJ side — surveyed and qualified (dated snapshot) |
| [pipeline/WATER_SOURCES.md](pipeline/WATER_SOURCES.md) | Water near shelters — measurements against every candidate source, and the options (dated snapshot) |
| [pipeline/WATER_CONDITIONS.md](pipeline/WATER_CONDITIONS.md) | Whether the water is *flowing* — the hydrology and drought sources that carry a current low-water signal (dated snapshot) |

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

**`scripts/test.sh` runs the ones your change actually reaches**, which is usually one of the four. It reads each suite's scope list out of that suite's own workflow file, so it makes the same decision CI does rather than a second copy of it that can go stale; it runs the linters and formatters for everything selected before it runs any tests, so a formatting slip costs six seconds instead of a CI round trip; and it runs each suite across every core. Measured, four cores: 294s for the full sequence below, 174s for `scripts/test.sh --all`, 20 to 50 seconds for a change to one of the Python parts. `--list` shows what it picked and which changed file decided it. Anything it cannot work out — a stale `main` ref, an unreadable workflow — it resolves by running everything.

The per-part commands below are what it runs, and remain the reference.

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

### Units are the hiker's choice, everywhere

**Every height and distance the app displays is displayed in the system the hiker picked in Settings.** Feet and miles or metres and kilometres, one preference (`unit_system`), no screen exempt. This is a standard rather than a style: a component that formats its own feet looks right on its own and disagrees with the one beside it, and a hiker reading 800 m of climbing on the elevation ribbon and 2,600 ft in the callout underneath has to work out which one is lying.

Three rules, and the first two are most of it:

- **`client/src/lib/units.ts` is the only module that writes a unit.** Nothing else spells ` ft`, ` mi`, ` m` or ` km`, and nothing else converts. `client/src/test/unitDisplay.test.ts` fails the build over a new one, so this is checked rather than remembered.
- **Store canonical, convert at display.** The published data is imperial where the ATC's is (mile markers, `elevation_ft`) and metric where USGS 3DEP's is; both stay as they are. Every function in the units module takes a canonical number and returns a string, which is the one shape a caller cannot accidentally persist.
- **A component takes the preference; it does not read it.** `App.tsx` reads `unit_system` once and passes it down, the same road the resolved theme travels. Two independent reads is how the map ends up in kilometres under a banner in miles.

One exception, and it is deliberate: **mile markers stay in miles.** `mi 1,407.2` is where somebody *is* on the A.T. — the reference every guidebook, shelter register and shuttle driver shares — not a measurement of anything. The distance *between* two of them is an ordinary distance and converts, so a metric hiker's banner correctly reads "Trail closed 4.8 km ahead · mi 8.0 – 9.0". [features/UX_CUSTOMIZATION.md](features/UX_CUSTOMIZATION.md) holds the reasoning.

### Changing a Python dependency

The `requirements.txt` and `requirements-dev.txt` files are **compiled output** — every package pinned to an exact version, transitive ones included. Do not edit them by hand. The hand-written files are the matching `.in`, which is where the comments explaining *why* a dependency exists live.

Add, remove or re-pin something in the `.in`, then regenerate. Each compiled file carries the exact command that produced it in its header; for `pipeline/` that is:

```
uv pip compile --universal --python-version 3.11 pipeline/requirements.in -o pipeline/requirements.txt
uv pip compile --universal --python-version 3.11 -c pipeline/requirements.txt pipeline/requirements-dev.in -o pipeline/requirements-dev.txt
```

Compile the runtime file first: the dev file takes it as a constraint, so the two cannot drift onto different versions of a shared package. `--universal` resolves across platforms rather than baking in whichever machine ran the command, and the 3.11 floor keeps one file installable on both CI's 3.14 and the web sandbox's 3.11.

Pinning is not tidiness. Five workflows — `build-basemap`, `build-dem`, `build-raster`, `publish-vector-data` and `publish-conditions` — install these files in a job holding R2 write credentials, so an unpinned resolve means a compromised upstream release executes next to the keys for the bucket hikers download maps from. Dependabot proposes the bumps ([`.github/dependabot.yml`](.github/dependabot.yml)), grouped weekly so the queue stays readable.

The pipeline fetches large amounts of data from ATC, USGS and opentrail.org. Read [pipeline/README.md](pipeline/README.md) before running the fetch scripts — a full topo quad pull is on the order of 14 GB, and the scripts are built to skip work that has not changed upstream. Do not defeat that by clearing manifests.

## Pull requests

- Branch off `main`. Small and focused beats comprehensive.
- **Do not merge `main` back in to keep the branch current.** GitHub merges your pull request against `main` as it stands at that moment, so a branch that is behind produces exactly the same result as one freshly caught up — the catch-up run costs a CI round trip and buys nothing. Merge `main` in when it genuinely conflicts, or when your branch cannot pass its own tests without something that landed there. `scripts/threads.sh` answers which, for every branch at once, without touching your working tree. [BRANCHING.md](BRANCHING.md) has the reasoning and the rest of the strategy.
- Link the issue and let the merge close it — `Closes #42`. This is the mechanism that keeps the tracker honest, rather than someone remembering to tick a box. CI checks it: a PR that closes no issue fails **PR has a linked issue**. Attaching the issue through the sidebar's Development panel counts too, though that fires no event, so the check needs a manual re-run afterwards. A bare `#42` mention does not count — referring to an issue and resolving it are different claims.
- If a change genuinely has no issue behind it — a typo, a revert, a dependency bump — label it `no-issue` rather than opening an issue for the sole purpose of closing it. The exemption is there so the rule does not manufacture the paperwork it exists to prevent. Dependabot labels its own pull requests ([`.github/dependabot.yml`](.github/dependabot.yml)), so the weekly bumps are nobody's to label by hand.
- New behaviour comes with tests. See [TESTING.md](TESTING.md) for what is expected; the short version is that tests describe behaviour rather than implementation.
- If a change contradicts something in a design doc, update the doc in the same PR. A doc that disagrees with the code is worse than no doc.
- Lint and format before pushing. CI checks both and will fail on formatting alone.

## Data does not go in commits

**Anything a script fetched, derived or exported belongs in `pipeline/data/`, which is gitignored — never in a commit.** What hikers get is published to R2 by `publish.py`; what a build needs between runs is carried by the CI cache. Nothing derived is tracked.

This is a security rule rather than a tidiness one, and the reason is that **a commit is a publication that cannot be retracted.** This repository is public, every clone carries its whole history, and `git rm` in a later commit removes a file from the tree while leaving it in every fork, mirror and pack that already pulled it. A byte committed here is published permanently, before anyone has reviewed it — which is the wrong property for data whose terms are still being settled:

- **Licence.** The rule below is to establish a licence before the bytes are in the build, and several sources are still open ([opentrail.org](https://github.com/OurHike/OurHike/issues/98), the club PDFs whose registry entries read *review-only until the club answers*). Committing any of them redistributes them under this repository's licence, from every fork, irreversibly.
- **Safety.** [`pipeline/SOURCE_SURVEY.md`](pipeline/SOURCE_SURVEY.md) §3b describes 2,333 user-created campsites in ATC's own index — the ones land managers are often trying to close. Publishing their locations would put OurHike on the wrong side of every partner it depends on, and a file committed once cannot be unpublished.
- **People.** Reports, photos and hiker submissions carry personal data by construction ([features/IDENTITY_AND_PRIVACY.md](features/IDENTITY_AND_PRIVACY.md)). None of it belongs in a tree anybody can clone.

**The one exception is `pipeline/reference/`, and it is narrower than it looks.** Those files are *joins that encode judgement*: a row of `shelter_capacity.json` is somebody's decision that a hiker-list entry is a particular ATC shelter, and reviewing its diff reviews those decisions. That argument holds only while a human actually reads the rows — so the directory carries a line ceiling, and a file past it is either derived data on the wrong shelf or a file whose author says in review why anyone should read that many rows.

The rule is enforced by `.github/tests/test_no_committed_data.py` rather than remembered: it fails on a tracked `pipeline/data/` path, on a data-shaped file outside a stated allowlist, and on an oversized reference file. It exists because the gitignore alone is a convention that a `git add -f` walks past — and because the mistake that prompted it needed no force at all. A 20,099-line derivation was written to `reference/`, which is *not* ignored, and committed, because that directory held three small checked-in files and looked like where derived things go ([#529](https://github.com/OurHike/OurHike/issues/529)).

## A note on data and licences

The app is AGPL-3.0. The data it ships is not all ours to relicense: USGS topo data is public domain, OpenStreetMap-derived basemap tiles are ODbL and require visible attribution (already rendered in `client/src/map/style.ts`), the bundled Noto Sans glyphs are SIL OFL 1.1 (provenance and licence text in `client/public/glyphs/`), opentrail.org's terms are [not yet formally confirmed](https://github.com/OurHike/OurHike/issues/98), and POI photos are Wikimedia Commons files licensed **per photo** (public domain, CC0, or CC BY / CC BY-SA at 4.0+ only — the pipeline rejects everything else, including pre-4.0 CC versions, whose terms a one-link credit cannot meet), each shipping with the author, licence and file-page link the waypoint card displays (`features/POI_PHOTOS.md`). If you add a data source, establish its licence first and record it — an unlicensed source is a problem inherited by every club that takes this project on later.
