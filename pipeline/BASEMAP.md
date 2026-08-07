# The offline vector basemap — build once, extract many

Design for the pipeline half of making the hiking sheet work offline —
[#184](https://github.com/OurHike/OurHike/issues/184) holds the
full program and the client half. Written 2026-08-04 alongside the spike
([#185](https://github.com/OurHike/OurHike/issues/185)); the numbers
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
[#193](https://github.com/OurHike/OurHike/issues/193), not here.

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
| z10–14 | per sub-region, in parallel | Tile content at z10+ is *mostly* local — see the measured exceptions below. Give each shard a padded input and an exact `--polygon`, as `lib/poly.py` already does for the corridor. |

PMTiles orders tile IDs zoom-major, so a national z0–9 archive followed by a
regional z10–14 one is *already* in write order. Packages can be cut from the
pair without ever materialising a ~23 GB national file.

### Measured: sharding is not lossless

[#225](https://github.com/OurHike/OurHike/issues/225) built
a region three ways — whole as a control, then as two shards that saw *all*
the data and differed only in `--polygon` (arm A), then as two shards that saw
only their own state (arm B) — for a sparse pair (Vermont/New Hampshire) and a
dense one (New York/New Jersey), plus a control that builds one input twice to
establish what "no difference" looks like. This section previously said the
shards were disjoint and the ranking question was unproved. Both claims were
wrong, and in the same direction.

**The shards are not tile-disjoint.** 593 of 21,910 tiles were produced by
more than one shard — every zoom from z0 up through the seam. Low zooms cannot
be otherwise (a z4 tile spans both states), which the z0–9 split above already
handles. What it does not handle is that combining shards therefore needs a
rule for tiles two shards both wrote; "concatenation" is not one.

**Two builds of identical input are byte-identical.** New Jersey built twice
with identical flags: 15,239 tiles, zero layer-stat differences, zero byte
differences. Planetiler is deterministic, so every difference below is a real
difference and not the encoder disagreeing with itself. This control should
have been the first thing measured; without it none of the numbers here mean
anything, and a run that reports thousands of differing tiles cannot be told
apart from a tool that never repeats itself.

**Some differences are not the seam's fault.** Arm A is the decisive arm: no
data was missing from either shard, so nothing there can be a clipping
artifact. Vermont/New Hampshire produced 16 differing tiles that exactly one
shard built, 6 of them more than 8 tiles inside a shard. New York and New
Jersey — the same experiment across the Hudson, chosen because density is
where label ranking has the most to disagree about — produced 5,420, with
4,962 deeper than 8 tiles. Padding cannot fix a difference caused by the
extent of what a build was *asked to output*.

**But almost all of that is reordering, not content.** Of the dense arm's
5,442 differing tiles, only **136 differ in any layer statistic** — feature
count, geometry count, per-layer bytes, attribute bytes, attribute values.
The other ~5,300 carry identical values for all five metrics and differ only
in their serialised bytes. Planetiler sorts rendered features by tile ID and
the order within a tile follows the whole feature file, so a shard bounded to
a smaller polygon writes the same features in a different sequence.

That distinction is the difference between a fidelity question and a broken
map, and it is worth stating what is inference and what is measurement. The
measurement is that five independent metrics agree on ~5,300 tiles whose
bytes differ. The inference is that ordering explains it. Proving it needs a
semantic tile comparison — decode, sort, diff — which this spike does not
have. Note also that order is not purely cosmetic: MapLibre breaks label
collisions by feature order, so a reordered tile can place a label
differently, which lands in the same drift class rather than outside it.

**Content drift does not scale with density.** 136 tiles in 71,931 for dense
New York/New Jersey is 0.19%; 35 in 21,910 for sparse Vermont/New Hampshire
is 0.16%. The alarming raw counts grow with region size and tile count; the
rate does not. That is the number the decision below rests on.

Arm B, the realistic arrangement, shows the padding requirement on top: 299
of its single-shard differences sit exactly one tile from the cut — a tidy
padding signature — over a much larger reordering background.

**Decided (2026-08-06): the drift is accepted for v1.** A place name that
differs across a shard boundary is the same class of thing this file already
warns about under "freshness honesty" — a label disagreeing between a
downloaded tile and a live one — and hikers are already told that. Content
drift runs at roughly 0.2% of tiles and does not grow with density, which is
what makes the call safe to make on two regions rather than fifty.

The three alternatives each cost more than the defect does: wider padding
fixes the differences one tile from the cut and provably not the interior
ones, a seam-tile merge rule addresses the multi-shard population but not the
interior drift either, and building North America whole on a paid larger
runner spends the money #194 exists to avoid.

Revisit if a club reports it, or if the semantic tile comparison this spike
lacks shows the reordering inference to be wrong.

**Measured: the temp-disk multiplier is ~5×, as assumed.** Two builds sized
to dwarf Planetiler's fixed overhead: `us-northeast` (1.79 GB → 8.20 GB peak,
4.6×, 12 min) and `us-south` (4.10 GB → 20.34 GB peak, 5.0×, 34 min). Fitted
across both, peak temp is **5.3× the input with no meaningful fixed term**.
BASEMAP.md's 5× assumption holds; Planetiler's 10× planet guidance is
conservative for a regional build. Extrapolated against the 88 GB free:

| Input | Temp at 5.3× | + input + output | Verdict |
|---|---|---|---|
| `us-south` 4.1 GB | 20 GB | ~30 GB | fits easily |
| `canada` 6.0 GB | 30 GB | ~44 GB | fits |
| whole US 11.2 GB | 58 GB | ~84 GB | marginal |
| North America 17.9 GB | 93 GB | ~134 GB | **does not fit** |

So the sub-region table above is confirmed by measurement rather than
inherited from documentation, and the reason to shard is confirmed with it.

An earlier attempt to measure this at Vermont/New Hampshire scale reported
7.4× and 18.6× and both were artefacts: those inputs (0.05–0.12 GB) are
smaller than Planetiler's fixed overhead, so every ratio was one constant
over a small denominator. Apparent file size is worse still — Planetiler's
node map is a sparse file sized by the node-ID space, so `ls -l`,
`du --apparent-size` and any naive walk report ~2.25 GB regardless of input,
and the 19.5× that falls out of it is fiction. Measure allocated blocks, at a
size that dwarfs the overhead, or do not quote a multiplier.

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
Protomaps context extract measured in July (which was never built — see
TECHNICAL_ARCHITECTURE.md and #196) — nothing new to clear.

## Updates and publishing

Geofabrik state extracts refresh daily; trail data changes on the order of
seasons. A monthly or pre-season rebuild is the cadence, and an unchanged
build must not republish — the same skip-if-unchanged principle the fetch
scripts hold.

Publishing was wired on 2026-08-06 (#186 closed the loop): both build
workflows carry a `publish` input defaulting to false, only the publish job
holds R2 credentials, a non-canonical build (a states-subset shakedown, a
shallow pyramid, a spike quantization) is refused loudly rather than
skipped, and the DEM passes `check_dem_archive.py`'s coverage-and-decode
gate before anything uploads. This is today's flat-key mechanism
(`publish.py` + `latest.json`), the same one the raster tiers use;
[DATA_RELEASES.md](DATA_RELEASES.md)'s immutable dated releases remain the
destination for all of it once that machinery exists. One caveat the flat
keys inherit: a rebuild is not byte-identical, so republishing an unchanged
region still re-uploads and version-bumps — the dispatch-only cadence is
what keeps that honest until immutable releases land.

## Measured results

From `build-basemap.yml` run 2 (2026-08-04, all 14 states, free hosted
runner, [logs](https://github.com/OurHike/OurHike/actions/runs/30957719854)) —
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
are z0–13 ≈ **182 MB** (smaller than the 300.3 MB raster it improves on;
MapLibre overzooms z13 vector cleanly) and z0–14 ≈ **532 MB** for full
OpenMapTiles detail. Both cuts are published now: the z13 extract stopped
being a future decision when #276 made it the hiking sheet's Standard
level, cut by the same `extract_package.py` run with `--max-zoom 13`.

### Published archives (2026-08-06)

The first publish runs, from this repository's `build-basemap.yml` and
`build-dem.yml` with `publish` ticked — the exact artifacts `latest.json`
now names, and the sizes `client/src/lib/packages.ts` advertises:

| Artifact | Bytes | Notes |
|---|---|---|
| `at_basemap_package.pmtiles` | **532,459,439** | z0–14, 83,818 tiles; the rebuild reproduced run 2's package within 0.06 MB |
| `at_basemap_package_z13.pmtiles` | **182,286,799** | z0–13, 21,721 tiles (the package minus its 62,097 z14 tiles); the hiking sheet's Standard level (#276), published 2026-08-06 from a rebuild whose z14 package came out hash-identical to the row above |
| `dem.pmtiles` | **607,265,661** | z0–13, 21,758 tiles, 0 absent, **0.5 m quantize** |

The DEM's per-zoom table lives beside the raster tiers in
[README.md](README.md). The quantize step was settled at 0.5 m by
`spike_dem_banding.py` (2026-08-06): 1 m is clean at native z12–13 but
etches visible staircases once the client overzooms the z13 DEM toward z15,
where 0.5 m stays indistinguishable from unquantized at ~1.53× the bytes —
the measured 397.6 MB at 1 m became 607.3 MB.

Together the hiking sheet — the default background since #237 — is
**789,552,460 bytes ≈ 790 MB** on a phone at its Standard level (the z13
cut plus the DEM, #276) and **1,139,725,100 bytes ≈ 1.14 GB** at Fine,
plus ~6 MB of bundled glyphs (`client/public/glyphs/README.md`).
