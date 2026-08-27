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

> **Since [#1116](https://github.com/OurHike/OurHike/issues/1116) the build
> emits that schema minus seven layers** — `export_basemap.py`'s
> `UNRENDERED_LAYERS` — and with `--languages=en` rather than Planetiler's
> ~80. The paragraph above still holds where it load-bears: every layer the
> style names is present, in the schema it expects, and nothing in
> `liveTopo.ts` changed. What is no longer true is that a downloaded tile and
> an OpenFreeMap tile carry the same *content*. See "What the exclusion
> costs" below.

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

### Published archives (2026-08-27)

What is in production's bucket right now — the exact artifacts `latest.json`
names, and the sizes `client/src/lib/hikingDetail.ts` advertises. Bytes read
back by `HEAD` on `https://data.ourhike.org` after the publish, tile counts
from each build's own Measure step, so no row here is copied from a projection:

| Artifact | Bytes | Tiles | Notes |
|---|---|---|---|
| `at_basemap_package.pmtiles` | **533,926,586** | 83,821 | z0–14; the hiking sheet's Fine level ([run 33074194236](https://github.com/OurHike/OurHike/actions/runs/33074194236)) |
| `at_basemap_package_z13.pmtiles` | **182,774,166** | 21,724 | z0–13, the package minus its z14 tiles; **Standard** (#276) |
| `at_basemap_package_z12.pmtiles` | **75,451,755** | 5,825 | z0–12; **Light** (#1107). Safe where the DEM's z12 cap was not — MapLibre overzooms z13 vector cleanly, and geometry and labels survive magnification where a hillshade computed from magnified elevation does not (`pipeline/LIGHT_DOWNLOAD.md`) |
| `dem.pmtiles` | **275,601,483** | 8,658 | z0–13, **0.5 m quantize**, corridor tapered 30/15/6 miles by zoom (#1088) ([run 33074191775](https://github.com/OurHike/OurHike/actions/runs/33074191775)) |
| `dem_light.pmtiles` | **182,205,873** | 5,553 | the same pyramid at a 20/6/3 taper, for Light (#1088/#1107) ([run 33074208491](https://github.com/OurHike/OurHike/actions/runs/33074208491)) |

Composed per level, which is the figure a hiker actually weighs against their
storage: **Light 257.7 MB**, **Standard 458.4 MB**, **Fine 809.5 MB**.

**The two DEMs reproduced UA's bytes exactly** — same size *and* same sha256,
from independent builds on different runners hours apart. That is the static
AWS Open Data source and a deterministic quantize-and-encode path, and it is
measured rather than assumed. The basemap carries no such guarantee: it rebuilds
from whatever OSM says that day.

**The previous table, and why the DEM row moved so far.** These replace the
first publish runs of 2026-08-06 — `at_basemap_package.pmtiles` 532,459,439,
`at_basemap_package_z13.pmtiles` 182,286,799, `dem.pmtiles` 607,265,661. The two
basemap cuts moved 0.3% (fresher OSM); the DEM fell 54.6% because #1088 stopped
buying corridor width at depths where it costs the most — 12.37 MB per mile of
buffer at z13 against 1.36 at z11.

### What the exclusion costs, and what it saves (#1116)

Every figure in the table above is a **pre-#1116 archive**, and stays correct
until the next build republishes. #1116 landed in `main` roughly 40 minutes
after the 2026-08-27 promotion, so the exclusion is in the build code and not
in the bucket. What that build will weigh was measured directly, by rebuilding
both published archives without the excluded layers and re-gzipping every tile:

| | published (whole schema) | `--exclude-layers` | + `--languages=en` |
|---|---|---|---|
| `at_basemap_package_z13.pmtiles` | 182,238,659 | 159,703,445 (−12.4%) | **158,348,907 (−13.1%)** |
| `at_basemap_package.pmtiles` | 532,287,514 | 347,947,790 (−34.6%) | **345,555,257 (−35.1%)** |

(Tile bytes, so the z13 row is 48,140 short of the file — header and
directories. The compressor is held constant and is not doing any of the work:
Planetiler's tiles re-compress to the byte at gzip level 6, verified on all
21,724 tiles of the z13 package, so these deltas are the exclusion's.)

**These were measured against the 2026-08-06 archives, not the ones now
published**, so carry the *ratios* forward and not the absolute right-hand
column: −12.4% and −34.6% applied to 182,774,166 and 533,926,586 land near
160.1 MB and 349.2 MB, and the honest figure is whatever `report_archive`
prints on the first build after this.

**Whoever runs that build moves `client/src/lib/hikingDetail.ts` in the same
change**, and this is the one consequence worth stating as an instruction
rather than an observation. A 12–35% drop against a release gate that fails
past 2% (`verify_release.py` check 18) is a hard block, so a rebuild that
republishes without refreshing those constants stops the next release rather
than shipping a wrong number — the safe direction, and still a surprise nobody
needs to rediscover from a red gate.

**The Light z12 cut is not measured here and is helped least**, which follows
from the same shape rather than from a separate finding: the exclusion's value
climbs with zoom because that is where the excluded layers live, so a cut that
stops at z12 keeps the smallest share of it. It is cut from the same build by
the same run, so it inherits the change with no extra step — the number it
lands on is whatever `report_archive` prints on the first build after this, and
that is the honest place to read it rather than an extrapolation from the two
rows above.

**The two tiers differ that much because z14 is where everything the sheet
does not draw arrives at once.** Of the Fine package: `transportation_name`
75.6 MB, `building` 56.7, `housenumber` 36.3, `poi` 33.5, and
`landuse`+`aeroway`+`aerodrome_label` 13.2 — 40% of the archive.
`housenumber` does not exist below z14 and `building`/`poi` barely do.

**`--languages=en` is worth 0.7%, and that is worth writing down** so nobody
re-derives it hoping for more. The ~80-language default is real and visible —
a `place` feature on the A.T. carries `name:ar`, `name:zh-Hant`, `name:tok` —
but the exotic variants are rare per feature, and the byte weight sits in
`name`, `name_en` and `name:latin`, which an English build keeps. It is kept
because it is free and because it stops being small the moment this pipeline
builds outside the United States.

**What is NOT reached from a flag.** The client reads six properties from this
source (`class`, `name`, `intermittent`, `admin_level`, `ele`, `ele_ft`) while
`transportation` ships `oneway`, `surface`, `network`, `brunnel`, `ramp`,
`bicycle`, `foot`, `horse` and `access` on 581,224 features. Stripping to
exactly those six measured **148,229,251 bytes** on the z13 package — another
6.3% — and needs a custom profile or a post-process that re-encodes every
tile. #1116 carries the measurement; it is not shipped because a hand-rolled
MVT re-encoder in the publish path is a poor trade against 6% of one tier, on
the archive a hiker navigates by.

**The cost.** A downloaded tile and an OpenFreeMap tile are no longer the same
bytes. Nothing renders differently — the style names none of the excluded
layers, and this was checked against every `['get', …]` in `liveTopo.ts`,
`PLACE_FILTER` and `PLACE_SORT_KEY_EXPRESSION`, with nothing outside
`liveTopo.ts` querying the source's features. What it forecloses is a *future*
style: adding road labels to the sheet used to be a stylesheet edit and is now
a rebuild and a republish. That is the trade, and it was made because 40% of
the tier a hiker picks when they want the good map is a large price for an
option nobody has asked for.

`planetiler_cmd` stays neutral and `main()` is what asks, so
`spike_shard_seam.py` keeps the whole schema by doing nothing: its recorded
drift rate above was measured across every layer, and a narrower build would
be a narrower question silently substituted for it. Defaulting the exclusion
on would have been tidier at one call site and wrong at the other — and it
would put the spike's three Planetiler builds (150-minute timeout each) on
every push that touched its file.

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
