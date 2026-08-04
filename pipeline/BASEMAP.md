# The offline vector basemap — build once, extract many

Design for the pipeline half of making the hiking sheet work offline —
[#184](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/184) holds the
full program and the client half. Written 2026-08-04 alongside the spike
([#185](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/185)); the numbers
marked *estimate* below are replaced by measured ones the first time
`build-basemap.yml` runs.

## Why this exists

The client already renders two backgrounds: the downloaded USGS raster archive
(offline, structurally blurry — [features/MAP_OPTIONS.md](../features/MAP_OPTIONS.md) §1)
and the live topographic sheet (`client/src/map/liveTopo.ts` — vector, sharp,
restylable, and online-only). The 2026-08-04 decision in #184 is that the live
sheet becomes the offline map too. That needs its vector tiles on the phone,
which needs a tileset we build and host ourselves.

**Schema is the load-bearing choice.** Planetiler's default profile emits the
OpenMapTiles schema — the same one OpenFreeMap serves — so `liveTopo.ts`
renders our archive **unchanged**, and the offline map is behaviorally
identical to the live map a hiker already judged by. Every alternative
costs a full restyle for no quality gain:

| Considered | Why not |
|---|---|
| Protomaps daily planet + `pmtiles extract` | Zero build infrastructure — but a Tilezen-derived schema; all 17 style layers rewritten, re-done on their major schema bumps. The documented escape hatch if owning a build ever becomes a burden, not the plan. |
| Geofabrik Shortbread tile packages | Pre-built per region, free — but explicitly experimental, a third schema, more minimal content. Watch it. |
| OpenFreeMap's published weekly planet | Byte-identical to the live source — but ~90 GB download plus a disk-heavy convert per refresh. Strictly worse than building the region ourselves. |

## The shape: one build, many packages

Trails beyond the AT are coming (NYNJTC's statewide network, other club
systems, national scenic trails — see #100, #109). A basemap built
corridor-shaped is the right optimization for exactly one trail and the wrong
one for two, so the shape is:

1. **Build** (`export_basemap.py`) — periodic, the heavy step. Fetch Geofabrik
   state extracts, clip each to a padded corridor shape with osmium
   (`lib/poly.py` — the padding is a guaranteed superset, see its docstring),
   merge, and run Planetiler over the result: an OpenMapTiles-schema PMTiles,
   z0–14. The pre-clip is what makes the AT-scale build fit a **free** GitHub
   runner; without it Planetiler's temp-disk need (5–10× input) outgrows one.
2. **Extract** (`extract_package.py`) — per trail, minutes, free-runner-sized
   forever. Cut a trail-corridor-shaped package out of the build. Adding a
   trail is one run of this against the same build — near-zero marginal cost,
   which is the property "any trail you can hike" needs.

The corridor polygon is a *parameter* end to end. Nothing in either script
assumes the AT; today's defaults point at it.

Overlapping trails (the AT and NYNJTC systems share ground) mean packages cut
this way duplicate tiles on a phone holding both — measured and decided in
[#193](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/193), not here.

## Where the build runs, and what it costs

- **AT scale (now):** `build-basemap.yml`, free hosted runner, manual
  dispatch. State PBFs ~3–4 GB, clipped input a fraction of that, well inside
  the ~22–29 GB a runner has free. Output *estimate*: 100–380 MB at z14.
- **Regional/continental scale (#194):** North America's extract is
  ~14–15 GB → ~8 GB RAM, 70–150 GB temp disk, 1–2 h on 8–16 cores. Options,
  ranked by boringness-per-dollar: GitHub larger runners (needs Team plan —
  check GitHub for Nonprofits; ≈ $2–6/month at a monthly cadence), an
  ephemeral self-hosted VM (≈ $1–3/build), or a volunteer's machine with a
  runbook. R2 keeps the rest flat: tens of GB stored ≈ $1–2/month, and
  **egress is $0** no matter how many hikers download — which is why hiker
  downloads never enter the cost math at all.

## External tools

Deliberately not Python dependencies — both are pinned/installed where the
build runs, and the scripts only construct their command lines (tested) and
invoke them:

- **osmium-tool** — OS package (`apt-get install osmium-tool`).
- **Planetiler** — a release jar from
  [onthegomap/planetiler](https://github.com/onthegomap/planetiler/releases)
  (Java 21+). Not on Maven Central; the workflow takes the jar URL as a
  dispatch input so a bad pin is fixable without a commit.

## Licensing

The output is an ODbL **Produced Work** of OpenStreetMap data: visible
"© OpenStreetMap" attribution is required wherever it renders, and the client
already renders it (`client/src/map/style.ts` — do not remove). The
OpenMapTiles schema itself is CC-BY, satisfied by the "© OpenMapTiles" credit
already shipped. This repository's open pipeline satisfies ODbL's
share-alike-or-method obligation with no extra work. Same terms as the
already-shipped Protomaps context extract — nothing new to clear.

## Updates and publishing

Geofabrik state extracts refresh daily; trail data changes on the order of
seasons. A monthly or pre-season rebuild is the cadence, and an unchanged
build must not republish — the same skip-if-unchanged principle the fetch
scripts hold. Publishing (not wired yet, on purpose — the spike measures, it
does not ship) goes through [DATA_RELEASES.md](DATA_RELEASES.md)'s immutable
dated releases exactly like every other artifact; the packages join the
per-artifact hash manifest so the client's "only re-download what changed"
promise carries over.

## Measured results

*(Filled in from `build-basemap.yml`'s first runs — per-zoom tile counts and
bytes for the build and the AT package, from `report_archive()`. Until then
the honest numbers are the estimates above, whose provenance is #184.)*
