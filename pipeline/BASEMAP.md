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

**Low-zoom context rides in every package** (decided with #189): through z9,
`extract_package.py` keeps the source build's *entire* footprint rather than
only region-intersecting tiles, so panning out offline shows the ground
around the trail instead of blank paper. How wide that context is stays the
build's decision — corridor-shaped today (where this changes nothing, since
the build's own `--polygon` bounds it to the same shape), statewide NY under
#184's 2026-08-04 scope call, national under #194 — and every package's
offline pan-out widens with it, with no extract-side change. This supersedes
the never-wired Protomaps context extract noted in TECHNICAL_ARCHITECTURE.md:
context travels inside each package, not as a second artifact.

**Freshness honesty, for the client's framing:** the package is built on our
cadence; OpenFreeMap (the live sheet's per-tile network fallthrough,
`client/src/map/basemap.ts`) rebuilds weekly. Same schema, both OpenStreetMap
— but a label edited upstream can differ between a downloaded tile and the
live tile one screen over until the next package release. That is data
freshness, not disagreement about where things are, and the Downloads
screen's release date is where a hiker reads it.

Overlapping trails (the AT and NYNJTC systems share ground) mean packages cut
this way duplicate tiles on a phone holding both — measured and decided in
[#193](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/193), not here.

## Where the build runs, and what it costs

The runner capacity all of this turns on is **measured, not assumed** —
`build-basemap.yml` prints it every run, which is the entire reason that step
exists. On this public repository a free hosted runner is **4 vCPU, 16 GB
RAM, and 88 GB free** of a 145 GB volume (run 2, 2026-08-04). Earlier drafts
here and in #194 assumed ~22–29 GB free, needing a cleanup action to reach
~50–60 GB. That has not been true for some time, and the gap is what makes
the plan below work without paying anyone.

- **AT scale (now):** `build-basemap.yml`, free hosted runner, manual
  dispatch. State PBFs 3.44 GB, clipped to a 690 MB build input, 12.5 minutes
  end to end with 80 GB still free — measured below.
- **Continental scale (#194):** North America's Geofabrik extract is
  **17.9 GB**, not the ~14–15 GB first estimated. Planetiler wants temp disk
  on top: its own preflight asked ~5× the input on the AT run, while its
  planet guidance says 10×, so 5× is a floor rather than a promise. A single
  whole-NA build therefore needs ~130 GB at 5× and ~220 GB at 10×, against
  88 GB free. **Disk is the only thing that fails** — the compute is ~8
  CPU-hours, about 2.5 h wall clock at the 3.3× parallelism this runner
  actually achieves, inside the 6 h job limit.

**So the continental build shards instead of buying a bigger machine.** Every
Geofabrik sub-region fits a free runner under *either* disk multiplier — the
largest, `canada` at 6.0 GB, needs ~44 GB of the 88 at 5× and ~74 GB at 10× —
and a matrix of them runs in parallel for $0, because standard runners have
unlimited free minutes on a public repository. Larger runners are always
billed, public repos included, so the sharded free build is not a compromise
against the paid one; it is cheaper *and* faster in wall clock.

The split that lets shards be cut apart is the one `extract_package.py`
already draws at z9 — low zooms are shared context, high zooms are local:

| | Built | Why it splits there |
|---|---|---|
| z0–9 | once, whole-NA, from the full 17.9 GB PBF | Cross-shard by nature: a z4 tile spans regions, so no shard can produce it alone. Cheap regardless — tile counts quadruple per zoom, so everything through z9 is a rounding error against z14 (31 MB of the AT build's 532). Reads the big PBF, writes almost nothing, fits. |
| z10–14 | per sub-region, in parallel | Tile content at z10+ is local. Give each shard a padded input and an exact `--polygon` — what `lib/poly.py` already does for the corridor — and the shards are disjoint, so combining them is concatenation, not reconciliation. |

PMTiles orders tile IDs zoom-major, so a national z0–9 archive followed by a
regional z10–14 one is *already* in write order. Packages can be cut from the
pair without ever materialising a ~23 GB national file.

What this has not proved: whether any OpenMapTiles layer ranks features from
a global view rather than a local one. If one does, it shows at shard seams,
and that — not the disk arithmetic — is the thing to check on the first real
sharded run.

R2 keeps the rest flat: tens of GB stored ≈ $1–2/month at $0.015/GB-month
after a 10 GB free tier, and **egress is $0** no matter how many hikers
download — which is why hiker downloads never enter the cost math at all.

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

From `build-basemap.yml` run 2 (2026-08-04, all 14 states, free hosted
runner, [logs](https://github.com/jaimito-asuntos-gringuenos/OurHike/actions/runs/30957719854)) —
these supersede the estimates above:

| Stage | Measured |
|---|---|
| 14 Geofabrik state PBFs | 3.44 GB fetched |
| After osmium pre-clip | **690 MB** build input |
| Planetiler z0–14 build | ~11 min → 535.1 MB |
| AT package (`extract_package.py`) | 83,818 tiles in ~5 s → **532.4 MB** |
| Whole run | **12.5 minutes**, 80 GB disk still free |

Per-zoom (AT package): z14 = 62,097 tiles / 350.0 MB, z13 = 15,899 / 107.0,
z12 = 4,172 / 44.1, z0–11 ≈ 31 MB. Tile counts land within 0.5% of the
independent corridor enumeration from #184's research pass.

Tier consequence: **z14 is 66% of the bytes**, so the natural download tiers
are z0–13 ≈ **182 MB** (smaller than the 314 MB raster it improves on;
MapLibre overzooms z13 vector cleanly) and z0–14 ≈ **532 MB** for full
OpenMapTiles detail. The DEM archive (#186) prices separately, on top.
