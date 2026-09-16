# What the sheet would cost if it covered every trail

Scoping for the question `lib/build_regions.py` raises and deliberately does not
answer: the trail lines are cut into 1-degree coverage cells nationwide, and the
sheet under them is not. Written 2026-09-16. Every number carries its grade
(measured / reasoned / `@unvalidated`) per [CLAUDE.md](../CLAUDE.md).

**The short version.** Closing the gap costs roughly **3.5–3.8 GB** of terrain
and **4–7 GB** of vector basemap, against a filled-continent ceiling of 16.9 GB
of terrain. Storing and serving that is **about thirty cents a month** and no
egress at all, so money is not the constraint and is not close to being one.
What binds is build capacity, which BASEMAP.md has already measured, and a
delivery path that is half-built. **And a hiker's download does not grow** —
that is what cells are for — which means every per-tile saving in
[LIGHT_DOWNLOAD.md](LIGHT_DOWNLOAD.md) is worth ~11× more at national scale
than it is today.

## The gap, measured rather than quoted

`lib/build_regions.py` says *"525 cells hold a tile. The sheet UNDER them was
not: 62 cells."* The second half is still right. The first is stale — the trail
network has grown since it was written.

**Measured** 2026-09-16 against `data.ourhike.org/latest.json` (release
2026-09-14), counting published cell artifacts by family:

| family | cells | total | mean per cell |
|---|---|---|---|
| `nearby_trails_cell_*` — trail lines | **681** | 204.8 MB | 0.30 MB |
| `at_basemap_cell_*` — the sheet | **62** | 419.5 MB | 6.77 MB |
| `dem_cell_*` — the terrain | **62** | 323.0 MB | 5.21 MB |

So **619 cells hold trail lines with no ground under them.** A phone can draw
another organization's trail over most of the country and has map to draw it on
over 9% of that.

> **Read the family prefix carefully.** `*_cell_*` is the 1-degree graticule unit
> `cut_cells.py` cuts today; `*_stretch_*` is the trail-derived cut it superseded
> (#1175), still in the bucket under its old keys — 44 of each. Counting the
> wrong one, or both, is an easy mistake with a 40% error in it, and this
> document made it once before `spike_national_scale.py` was written to read the
> prefixes by name.

## Why the corridor's own bytes cannot be multiplied out

The A.T. corridor is mountainous, and mountains compress worst. That is not an
aside — it is the reason LIGHT_DOWNLOAD.md calibrates rather than scales, and it
is the reason a national figure needs its own sample.

**Measured** 2026-09-16 (`spike_national_scale.py`), 24 areas across the kinds
of ground the United States is made of, 2×2 tiles each at z11/z12/z13, encoded
through `export_dem.encode_tile` itself at the shipping quantize step:

| zoom | low relief | high relief | sample mean | A.T. corridor | mean vs A.T. |
|---|---|---|---|---|---|
| z11 | 23.3K | 49.1K | 36.2K | 42.3K | 0.86 |
| z12 | 17.1K | 38.4K | 27.8K | 33.2K | 0.84 |
| z13 | **13.0K** | **27.5K** | 20.2K | 25.6K | 0.79 |

**Low relief is 2–4× cheaper per tile than high.** The Central Valley runs 2.6K
at z13 and the Smokies 34.4K — a 13× spread inside one country. Any national
figure that multiplies one corridor's mean is wrong by whatever that corridor
happened to sit on.

Note which way that cuts for a *trail-shaped* build: trails are where the
mountains are, so a national trail corridor skews toward the expensive column,
never toward the plains. The cheap tiles in this sample are mostly ground no
long trail crosses.

## The two numbers, and which one to use

### Realistic: scale the cells that exist

The honest estimate, because cells stay corridor-shaped *inside* — `cut_cells.py`
cuts the corridor archive, not the whole square — so a cell in the Rockies is a
ribbon through a square, exactly as an A.T. cell is.

**Reasoned** from the measured mean above:

| | GB |
|---|---|
| 681 cells at today's 5.21 MB mean | **3.5** |
| repriced at the sampled high-relief mean | **3.8** |

Against `dem.pmtiles`'s 275.6 MB for one trail, ~13× the terrain for ~11× the
cells — which is the sanity check that the two methods agree.

### Ceiling: fill the continent

**Reasoned** from the measured bytes/tile and web-mercator tile geometry at
CONUS's area-weighted mean latitude, over 8.08 M km² of land:

| zoom | tile side | tiles | GB |
|---|---|---|---|
| z11 | 15.21 km | 34,940 | 1.30 |
| z12 | 7.60 km | 139,759 | 3.98 |
| z13 | 3.80 km | 559,035 | 11.58 |
| | | **total** | **16.9** |

**This is an upper bound on any trail-shaped build and a poor estimate of one.**
A corridor is a ribbon; this is a filled continent. It is worth computing only
because it answers "does the worst case fit", and for storage it comfortably
does. The gap between 3.8 and 16.9 is the value of keeping the taper.

### The basemap half

Not measured here, and the two available estimates agree closely enough to act
on. Scaling the published cells: 681 × 6.77 MB = **4.6 GB**. From BASEMAP.md's
measured whole-US Geofabrik extract (11.2 GB PBF) against the A.T. build's own
input-to-output ratio: **~5–7 GB**.

The cell-scaled figure is the one that *understates*, and knowing why matters:
basemap bytes scale with feature density rather than area, and a national build
hits every city while the A.T. corridor deliberately threads between them.
Pulling the other way, #1116's layer exclusion drops exactly the city-dense
layers — `building`, `poi`, `housenumber`, `transportation_name`, `landuse`,
`aeroway`, `aerodrome_label` — so it is worth **more** nationally than the
34.6% it measured on the corridor. Those two do not obviously cancel and nobody
has separated them.

## Money is not the constraint, and it is not close

**Measured** 2026-09-16: the whole production bucket is 1,966 artifacts and
**3.94 GB**, which is **$0.059 a month** at R2's $0.015/GB-month after the 10 GB
free tier. At ~12 GB it is about **$0.20 a month**. R2 egress is **$0** however
many hikers download, which is why BASEMAP.md notes hiker downloads never enter
the cost math at all.

A build that costs single-digit gigabytes to store and nothing to serve is not
a budget decision. Treating it as one would be the wrong argument to have.

## What actually binds

1. **Build capacity, already measured.** BASEMAP.md puts whole-US Planetiler at
   ~84 GB of a free runner's 88 — *marginal* — and North America at ~134 GB,
   which **does not fit**. So the national basemap needs #194's sharded build
   before it can exist at all. The DEM has no disk problem, being fetch-and-
   repack rather than a Planetiler build, but ~700k tiles against today's 8,658
   would push a single run at the 6-hour job limit and wants sharding by cell
   for its own reasons.

2. **The delivery path is half-built, and this is the nearer blocker.**
   **[#1475 — A stretch download carries no terrain at all: the DEM cells are
   built and published, and no client code declares them](https://github.com/OurHike/OurHike/issues/1475)**:
   323.0 MB of DEM cells are in the bucket right now that the app cannot read.
   `client/src/lib/coverageCells.ts` declares `BASEMAP_CELLS`, `NETWORK_CELLS`
   and `GRAPH_CELLS`, and there is no fourth.
   **[#1485](https://github.com/OurHike/OurHike/pull/1485)** is the open fix.
   Nothing national is worth building until a cell can be read, and that is a
   correctness fix for today's hikers regardless.

3. **The unit a hiker chooses**, which is #552's question and the maintainer's
   to answer. 681 cells is not a list anybody picks from.

## The part worth carrying forward

**A hiker's download does not grow.** They take the cells they walk, so the
435.6 MB Standard sheet stays 435.6 MB whether the bucket holds one trail or
every trail. 3.8 GB is a storage number, never a phone number.

Which inverts the usual reading of [LIGHT_DOWNLOAD.md](LIGHT_DOWNLOAD.md)'s
per-tile levers. They look marginal against one corridor — #1506's encoder
setting is 1.1% — and they are **per-tile**, so they land on all 681 cells and
on every cell cut after. The taper, the quantize step and the encoder effort
are worth roughly eleven times more at national scale than the A.T. numbers
make them look, and they get cheaper to change the earlier they are changed.

## What would settle the open parts

- **The basemap figure needs a build, not an estimate.** One sharded region
  built and weighed would replace both estimates above with a measurement, and
  #194 has to build one anyway.
- **The high-relief repricing is `@unvalidated` as a method.** It assumes a
  national trail cell looks like this sample's mountainous half. What would
  settle it: cutting cells from one western region's real build and weighing
  them against this projection, the way the Light taper checked out at 2.0%.
- **Nobody has asked how many cells a hiker would actually take**, which decides
  whether 681 cells is a catalogue or a pile.
