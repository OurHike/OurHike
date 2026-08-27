"""A dense sampled elevation profile per graph edge - the shape a chart draws
(#1045, features/HIKE_PLANNING.md "The day hike on a network").

export_network_elevation.py publishes `[gain_ft, loss_ft]` per edge and names
this file in its own header: "Dense samples are worth publishing only if a
chart is ever drawn for a network route, and then as a fourth artifact fetched
when that chart opens." #1045 is that chart. Two scalars say how much an edge
climbs and nothing about WHERE, and a cumulative-gain staircase drawn from them
would be a picture of terrain nobody measured - on the one band a hiker uses to
judge whether they beat the dark.

So this is the fourth file on `build_trail_graph.py`'s shelf, under the same
index-alignment invariant the other three carry: entry `i` here describes edge
`i` in `trail_graph.json`.

    trail_graph.json           launch      nodes, edges, lengths, attribution
    trail_graph_geometry.json  builder     each edge's vertices
    trail_graph_elevation.json builder     each edge's [gain_ft, loss_ft]
    trail_graph_profile.json   chart       each edge's dense samples  <- here

WHAT IS PUBLISHED PER EDGE

One array of whole feet per edge, first sample at 0 m and last at the edge's
full length, or `null`:

    [
      [1204,1211,1198,1187,1190],   edge 0: five samples, 0 m to length_m
      null,                         edge 1: the DEM covers none of this edge
      [980,null,1002],              edge 2: sample 1 is a hole in the DEM
      ...
    ]

**No distances are published, and none are needed.** Sample `j` of edge `i`
sits at `edges[i].length_m * j / (n - 1)` where `n` is that array's own length.
A consumer must take `n` FROM THE ARRAY and never recompute it from
`length_m`, and that is measured rather than defensive. The sampler walks the
edge's vertices re-projected to EPSG:5070; `length_m` is the projected length
of the same line before those vertices were rounded to 6 decimals for
publication. On the live artifacts (2026-08-27) the two differ by a median
0.035 m, p95 0.12 m, max 1.50 m - and `round(length/interval)` lands either
side of a half-step often enough that **63 of 40,596 edges (0.155%) would get a
different sample count** from a client that recomputed it. Those 63 would be
drawn with every sample after the first in the wrong place.

An array of length 1 is a degenerate edge with no length to draw across. None
exist on the live artifact - 0 of 40,596 - but `build_trail_graph.py` only
drops zero-length loops shorter than its node grid, so the shape stays
expressible and a consumer should skip it rather than divide by `n - 1`.

=============================================================================
THE SEAM RULE, WHICH THIS FILE MAKES MEASURABLE RATHER THAN ARGUABLE
=============================================================================

**Gain is summed WITHIN an edge and never across a node join.** That was
export_network_elevation.py's rule when the artifact was two scalars, where it
was free - there was no concatenated profile for a seam to hide in. A dense
profile hands the hazard back, because concatenating a route's edges into one
sample array is a `.flat()` call away, and #559 measured what summing across a
break in the ground costs: ~36,800 ft of climbing nobody did entering the
published A.T. total, the largest a single +2,588 ft "step" across 25 m.

The ground for it, measured on the live artifacts 2026-08-27 (see
`measure_seams` below, which re-measures it on every run rather than trusting
this paragraph): 21,149 of 31,545 nodes have more than one edge-end on them.
18,698 of those (88.41%) have every incident end at the SAME published
coordinate. The other 2,451 do not, because `ENDPOINT_SNAP_M = 8.0` joins ends
that stop short of each other: 1,067 nodes (5.05%) have their ends more than
1 m apart, 520 (2.46%) more than 4 m, and the widest is 19.06 m - wider than
the tolerance because a node can weld a chain of ends. Those metres are
horizontal; what they buy on a slope is a vertical step between two edge-ends
that a flat sum reads as climbing.

FOUR THINGS ENFORCE IT, none of which is "remember to":

1. **The file has no concatenated profile in it.** One array per edge, always,
   even for an edge whose samples are all holes. There is nothing to sum by
   accident; flattening is a thing a consumer has to decide to do.

2. **This artifact is for DRAWING. Route climb comes from
   `trail_graph_elevation.json`,** which is per-edge by construction and is
   what the card already prints. The manifest says so in a field
   (`route_gain_source`) rather than only here, so a consumer that cannot read
   this docstring still finds the answer. Two screens showing two totals for
   one walk is worse than either total on its own.

3. **The documented way to flatten, which the repository's own library already
   honours.** A consumer building route samples writes `part_start: true` on
   the FIRST sample of every edge. `lib/elevation_gain.py:profile_runs` and
   `client/src/lib/elevationGain.ts` both break a run there - the marker exists
   because export_elevation.py's 558 disconnected centerline pieces have the
   identical problem. So the correct behaviour is already implemented on both
   sides of the language boundary and needs no new mechanism.
   `tests/test_export_network_profile.py::TestTheSeamRule` is that rule as an
   executable specification: the same flattened records summed WITHOUT the
   markers read the phantom step, and with them do not.

4. **Every run measures its own seam** and puts it in the manifest - how many
   nodes have coincident ends, how large the steps are at the ones that do
   not, and how many exceed the dead band. A hazard with a number beside it,
   re-derived on every export, is one nobody can call theoretical.

WHAT THE PER-EDGE RULE COSTS, WHICH IS NOT NOTHING AND IS NOT HIDDEN HERE

Breaking a run at every junction under-counts climbing that spans one: a swing
that never reverses by the 3 m dead band WITHIN an edge is dropped, where a
continuous profile would have confirmed it across the join.

Measured, 2026-08-27: 300 six-mile shortest paths on the live graph cross a
median of 23 edges (p90 232). Cutting the real published A.T. 25 m profile at
those routes' own real edge boundaries and summing per edge understates the
continuous figure by a **median 6.9% (100 ft), p90 46.9%** - the terrain is the
A.T.'s and the cuts are the network's, so this isolates the chopping alone.

**The direction is the unsafe one and that is worth saying plainly.** An
understated climb is an understated Naismith time, on the question of whether
somebody beats the dark. export_network_elevation.py's header says "the
direction of the error is the safe one" - true of the dead band it is
describing, and this measurement is about the chopping instead, which pushes
the other way. Nobody has measured the net of the two on this ground.

The fix is NOT for this artifact to sum itself differently. 88.41% of nodes
have coincident ends, and at those the join is honest - a consumer holding
`trail_graph_geometry.json` (which a chart already has) can see that for itself
by comparing edge A's last vertex with edge B's first. That would recover most
of the shortfall. It is deliberately not done here: it is a second climb figure
disagreeing with the card's on the same walk, and it wants its own issue, its
own before-and-after, and a maintainer's decision. The measurement above is
this file's contribution to that decision.

=============================================================================
THE SAMPLING INTERVAL, MEASURED
=============================================================================

25 m, the same interval `export_elevation.py` walks the A.T. at - imported
from it rather than re-declared, so there is exactly one sampling interval in
this pipeline and no flag to make a file that disagrees with the scalars.

What each candidate weighs, against the live graph (40,596 edges, 16,213.2 km,
median edge 64.7 m, fetched 2026-08-27). **Sample counts are exact** - real
`length_m` through `sample_positions` - through `length_m` rather than through
the walked geometry the exporter itself measures, which is the same count to
within the 63 edges above (694,954 against 694,955 at 25 m).

**Bytes are modelled**: no DEM run produced them. The elevation values are the
real published A.T. profile (138,695 samples at 25 m) resampled to each spacing
and laid into the real edge shapes, so the digit distribution and the
sample-to-sample autocorrelation gzip feeds on are real terrain. gzip is level
6, mtime 0, which is what publish.py uploads with. The A.T. sits higher than
the NY sources that supply 92% of these edges (37,472 of 40,596), so every byte
figure is an over-estimate.

    interval    samples   /edge    raw MB   gzip MB
    -------------------------------------------------
        10 m  1,664,432    41.0      8.20      2.49
        15 m  1,124,983    27.7      5.57      1.82
        20 m    856,018    21.1      4.26      1.45
    ->  25 m    694,955    17.1      3.47      1.22
        30 m    587,943    14.5      2.95      1.06
        40 m    454,674    11.2      2.30      0.85
        50 m    375,314     9.2      1.92      0.72
        75 m    270,292     6.7      1.40      0.54
       100 m    218,476     5.4      1.15      0.45
       150 m    167,634     4.1      0.90      0.36
       200 m    142,764     3.5      0.78      0.31

For scale, from the live https://data.ourhike.org/latest.json the same day:
`trail_graph_geometry.json` is 17.29 MB raw / 4.70 MB transfer and the client
already fetches all of it one screen EARLIER (when the builder opens);
`trail_graph.json` is 7.48 MB / 1.20 MB and is fetched at launch. At 25 m this
file is a fifth of the geometry it sits beside, and is fetched later and less
often.

THE TRADE, STATED AS A TRADE. Coarser is cheap: 50 m halves the samples for
0.50 MB less over the wire. What buys the 25 m back is not resolution for its
own sake - it is that **the A.T. is in both artifacts**. 1,525 centerline and
1,599 side-trail edges of this graph are the same ground `elevation_profile.json`
samples at 25 m, and the dead band's answer depends on the spacing it is
applied at, so a second interval would print two different climbs for one ridge
depending on which plan the hiker had loaded. This codebase has measured "a
mile" two different ways before, which is why HIKE_PLANNING.md Finding 1 exists.
One interval is worth 0.50 MB.

Going finer is not free either and buys less than it looks: 3DEP's posting is
~10 m, so 10 m sampling is the finest that carries information rather than
interpolation, and it costs 2.4x this file. export_elevation.py's own note
gives the rest - below the DEM's resolution the errors compound into fake
climbing, and gain is the operation that integrates them.

The floor is worth knowing before anyone tries to shrink this by coarsening:
28.8% of edges are shorter than 25 m and get their two endpoints whatever the
interval is, so 40,596 edges can never cost less than 81,192 samples. At 200 m
the file is still 0.78 MB and the shape is gone.

WHAT A PHONE HOLDS, which is the cost that is not the download. 694,955
numbers in 40,596 arrays - about 5.6 MB at 8 bytes a number, plus one array
header each. The phone is already parsing `trail_graph_geometry.json`'s 755,326
vertices as 755,326 two-element arrays by the time anything asks for this, so
this is the smaller of the two structures on the same screen.

THE WHOLE-STATE DOWNLOAD IS NOT SOLVED HERE. A 6-mile loop is 0.1% of these
bytes. That is the same property `trail_graph_geometry.json` has and the same
answer applies - per-coverage-unit cuts are #552's to decide, and this artifact
will shard exactly as its siblings do when they do.

=============================================================================
PRECISION: WHOLE FEET
=============================================================================

Feet because that is what the ribbon draws in (`ElevationRibbon.tsx`: "the
samples stay in feet and miles whatever the hiker reads in") and what both
elevation artifacts already publish; `lib/units.ts` converts at display.

WHOLE feet, where `elevation_profile.json` publishes tenths, and the
divergence is deliberate. 3DEP's absolute vertical accuracy is ~1.55 m RMSE
(the figure `lib/elevation_gain.py:NOISE_FLOOR_M` cites), and its
sample-to-sample error as this pipeline resamples it is ~0.5 m. One foot is
0.3048 m. So integer feet already over-resolve the source, and a tenth of a
foot is 3 cm - a claim about the ground the DEM cannot support.

Measured cost of the extra decimal, on the modelled artifact above: 4.86 MB
raw / 1.78 MB gzip against 3.47 / 1.22 - 40% more bytes to record a quantity
16 times finer than the instrument's own sample-to-sample jitter.

Measured cost of the rounding, on the real published A.T. profile: recomputing
confirmed ascent from whole-foot values instead of tenths moves the 2,190-mile
total by +1,386.5 ft on 524,158.5 ft (+0.26%), and over 359 six-mile windows by
a median 1.1 ft (0.125% of a window's gain), p95 19.5 ft, max 30.5 ft. The
mechanism is not the 0.5 ft of quantisation itself - it is swings landing
either side of the 9.84 ft dead band after rounding.

That is the second reason `trail_graph_elevation.json` stays the sanctioned
total: **gain recomputed from these rounded feet does not reproduce the scalars
exactly**, and a hiker shown one total on the card and a different one under
the chart has been given two answers to one question.

=============================================================================
DEM NULLS
=============================================================================

Two different absences, published differently, and neither is ever a zero.

A **whole entry of `null`** means the DEM covers no part of that edge - the
same claim `trail_graph_elevation.json`'s null entry makes, and the same
reading: nobody measured this edge. It is not published as an array of nulls,
so the two artifacts answer "is this edge measured at all?" in the same shape.

A **`null` inside an array** is one sample the DEM has no value for. Its
position is kept rather than dropped, for export_elevation.py's reason: the
distance axis a chart draws from is derived from the array's length, so
dropping a hole would silently rescale everything after it - a shape that
misplaces a climb it did measure is worse than one with a gap in it.

**The recommended client rule is all-or-nothing per walk, and it should cover
both.** A route with an unmeasured EDGE already has no climb figure. A route
whose profile has a hole in it cannot be drawn as one continuous shape either:
an unmarked gap in a ribbon reads as terrain. #1041 draws no ribbon rather
than a wrong one, and a hole is the same decision arriving from the data
instead of from the shape of the artifact. The manifest carries the counts a
client needs to know how often this fires - on the live scalar artifact it
fires nowhere at all today (0 of 40,596 edges unmeasured, measured 2026-08-27),
which is a fact about the current DEM index and not a guarantee.

Output: `data/processed/trail_graph_profile.json`, an index-aligned JSON array,
plus `trail_graph_profile_manifest.json` carrying the hash, the edge count the
client checks alignment against, the sampling interval, per-source coverage,
the seam measurement, and the `sources` block copied from the graph manifest SO
THE LICENCE GATE TRAVELS WITH THE DERIVATION - a profile measured along a
steward's line is still that steward's data, and publish.py applies the same
`reaches_hikers` check it applies to the lines themselves.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from export_elevation import SAMPLE_INTERVAL_METERS, ElevationSampler, index_elevation_tiles

# Imported, including the underscored one, rather than re-implemented. Both are
# how the two-scalar artifact walks an edge, and this file has to walk it
# identically or the card and the chart become two measurements of one hike -
# see build(). The leading underscore says "not for outside this pipeline",
# which this is not.
from export_network_elevation import _transformers, edge_sample_points
from lib.elevation_gain import DEFAULT_THRESHOLD_FT, DEFAULT_THRESHOLD_M, METERS_PER_FOOT
from lib.hashing import sha256_file

ROOT = Path(__file__).resolve().parent
IN_DIR = ROOT / "data" / "processed"
OUT_DIR = ROOT / "data" / "processed"
GRAPH_NAME = "trail_graph.json"
GEOMETRY_NAME = "trail_graph_geometry.json"
GRAPH_MANIFEST_NAME = "trail_graph_manifest.json"
ARTIFACT_NAME = "trail_graph_profile.json"
MANIFEST_NAME = "trail_graph_profile_manifest.json"
ELEVATION_INDEX_PATH = ROOT / "data" / "raw" / "elevation" / "tile_index.json"

# Named here rather than spelled inline, because it is a claim this artifact
# makes ABOUT ANOTHER ARTIFACT and the manifest publishes it: route climb comes
# from the two-scalar file, never from summing this one. See the seam rule.
ROUTE_GAIN_SOURCE = "trail_graph_elevation.json"


def edge_profile(elevations_m: list[float | None]) -> list[int | None] | None:
    """One edge's samples in whole feet, or None when the DEM covers none of it.

    The two absences are different claims and are published differently: None
    for the whole edge says nobody measured this edge - the same thing
    `edge_climb` says with its own None, in the same place, so the two
    artifacts cannot disagree about which edges are known. A None INSIDE the
    list is one hole in the DEM, kept in place so the distance axis derived
    from the list's length stays true.

    Metres in (3DEP's own unit), feet out, rounded once here. See the module
    docstring for why whole feet and not tenths.
    """
    if not any(value is not None for value in elevations_m):
        return None
    return [None if value is None else round(value / METERS_PER_FOOT) for value in elevations_m]


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile, so every number reported is one that was
    actually measured rather than an interpolation between two that were."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def measure_seams(edges: list[dict], geometry: list[list[list[float]]], profiles: list[list[int | None] | None]) -> dict:
    """The vertical disagreement at every node two or more edge-ends meet at.

    THE HAZARD, RE-MEASURED ON EVERY RUN. `ENDPOINT_SNAP_M = 8.0` joins ends
    that stop short of each other, so two edges sharing a node can sit metres
    apart on the ground and an unmeasured distance apart vertically. A route
    profile concatenated across that join reads the step as climbing, which is
    #559 arriving in a new artifact.

    `coincident` is the count that decides whether a better join is even
    available: a node whose incident ends are all the SAME published
    coordinate has no step by construction, because the same lon/lat reads the
    same DEM pixel. Measured against the geometry artifact's own 6-decimal
    coordinates rather than against re-projected ones, so it is exactly the
    comparison a client holding that file can make for itself.

    Steps are in feet, from the published (rounded) profiles, because feet is
    what a consumer would be summing. A node where fewer than two incident
    ends have an elevation contributes no step - one measured end cannot
    disagree with anything.
    """
    ends: dict[int, list[tuple[tuple[float, float], int | None]]] = defaultdict(list)
    for edge, coordinates, profile in zip(edges, geometry, profiles):
        if not coordinates:
            continue
        first = profile[0] if profile else None
        last = profile[-1] if profile else None
        ends[edge["from"]].append((tuple(coordinates[0]), first))
        ends[edge["to"]].append((tuple(coordinates[-1]), last))

    shared = {node: incident for node, incident in ends.items() if len(incident) > 1}
    coincident = 0
    steps: list[float] = []
    for incident in shared.values():
        if len({coordinate for coordinate, _ in incident}) == 1:
            coincident += 1
        measured = [elevation for _coordinate, elevation in incident if elevation is not None]
        if len(measured) > 1:
            steps.append(float(max(measured) - min(measured)))

    over_band = [step for step in steps if step >= DEFAULT_THRESHOLD_FT]
    return {
        "shared_nodes": len(shared),
        "coincident_ends": coincident,
        "measured_nodes": len(steps),
        "nodes_with_a_step": sum(1 for step in steps if step > 0),
        "steps_over_dead_band": len(over_band),
        "step_ft_p50": round(_percentile(steps, 0.50), 1),
        "step_ft_p95": round(_percentile(steps, 0.95), 1),
        "step_ft_max": round(max(steps), 1) if steps else 0.0,
    }


def build(graph: dict, geometry: list[list[list[float]]], sampler: ElevationSampler) -> tuple[list, dict, dict]:
    """Every edge's dense profile, index-aligned with `graph["edges"]`, plus
    coverage stats per source and the seam measurement.

    SAMPLED BY export_network_elevation.edge_sample_points, IMPORTED RATHER
    THAN REIMPLEMENTED. The two artifacts have to describe the same points at
    the same spacing or the card and the chart are two measurements of one
    walk; sharing the function is what makes that structural instead of
    remembered.

    EVERY EDGE'S POINTS GO TO THE SAMPLER IN ONE CALL, for the reason that
    module's own `build` gives: `sample_many` groups points by covering tile
    and does one windowed read per tile, so batching across the whole graph
    turns thousands of remote range reads into a handful.
    """
    edges = graph["edges"]
    if len(geometry) != len(edges):
        # The alignment invariant build_trail_graph.py's manifest exists to
        # protect. A profile written under edge 41's name is a picture of the
        # wrong trail, and nothing downstream could tell.
        raise ValueError(f"geometry has {len(geometry)} entries against {len(edges)} edges - refusing to guess the pairing")

    to_projected, to_geographic = _transformers()
    per_edge_points = [edge_sample_points(edge_geometry, to_projected, to_geographic) for edge_geometry in geometry]

    flat = [point for points in per_edge_points for point in points]
    sampled = sampler.sample_many(flat) if flat else []

    profiles: list[list[int | None] | None] = []
    stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"edges": 0, "measured": 0, "partial": 0, "unmeasured": 0, "samples": 0, "null_samples": 0}
    )
    cursor = 0
    for edge, points in zip(edges, per_edge_points):
        window = sampled[cursor : cursor + len(points)]
        cursor += len(points)
        profile = edge_profile(window)
        profiles.append(profile)

        bucket = stats[edge.get("source") or "unknown"]
        bucket["edges"] += 1
        bucket["samples"] += len(window)
        bucket["null_samples"] += sum(1 for value in window if value is None)
        if profile is None:
            bucket["unmeasured"] += 1
        else:
            bucket["measured"] += 1
            if any(value is None for value in profile):
                bucket["partial"] += 1

    return profiles, dict(sorted(stats.items())), measure_seams(edges, geometry, profiles)


def coverage_summary(stats: dict[str, dict[str, int]]) -> dict:
    """The numbers a run should be judged on, across all sources.

    Counts rather than percentages alone, for the reason
    export_network_elevation.coverage_summary gives: "3 of 12,000 edges" and
    "3 of 4" are the same percentage rounded and completely different
    situations.
    """
    total = sum(bucket["edges"] for bucket in stats.values())
    measured = sum(bucket["measured"] for bucket in stats.values())
    samples = sum(bucket["samples"] for bucket in stats.values())
    null_samples = sum(bucket["null_samples"] for bucket in stats.values())
    return {
        "edges": total,
        "measured": measured,
        "unmeasured": total - measured,
        "partially_covered": sum(bucket["partial"] for bucket in stats.values()),
        "measured_pct": round(100.0 * measured / total, 2) if total else 0.0,
        "samples": samples,
        "null_samples": null_samples,
        "null_sample_pct": round(100.0 * null_samples / samples, 2) if samples else 0.0,
    }


def write_artifact(profiles: list, stats: dict, seam: dict, sources: dict | None = None) -> dict:
    """Write the artifact and its manifest.

    `edges` in the manifest is the alignment check the client applies before it
    draws anything: `lib/trailGraphData.ts` refuses a file whose entry count
    disagrees with the graph it already holds, the same way it already refuses
    a mismatched geometry or elevation file. Silent misalignment here draws one
    trail's terrain under another's name.

    `route_gain_source` is the seam rule as a field rather than as prose: a
    consumer that never reads this module still finds out where a route's climb
    is supposed to come from. `sample_interval_m` is next to it so the two
    artifacts can be checked for agreement without re-deriving anything.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / ARTIFACT_NAME
    path.write_text(json.dumps(profiles, separators=(",", ":")), encoding="utf-8")

    manifest = {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "sample_interval_m": SAMPLE_INTERVAL_METERS,
        "units": "feet",
        "decimals": 0,
        # Where a route's climb comes from, which is never this file. See the
        # module docstring's seam rule, and its measurement of what
        # recomputing from these rounded feet would cost even without a seam.
        "route_gain_source": ROUTE_GAIN_SOURCE,
        "threshold_m": DEFAULT_THRESHOLD_M,
        # The same flag its two-scalar sibling carries, for the same reason: no
        # published gain figure exists for any NYNJTC or OPRHP trail, so the
        # dead band that is checked on the A.T. arrives here unchecked. Every
        # surface that renders these numbers says so.
        "estimate": True,
        "seam": seam,
        "per_source": stats,
        **coverage_summary(stats),
        # AFTER the coverage spread, which carries an `edges` of its own. The
        # two are different questions - that one is "how many edges did the
        # sources account for", this one is "how many entries are in the file
        # the client is about to check its graph against" - and only the
        # second can be allowed to answer here, because it is the one a
        # misalignment would show up in. A run whose coverage total disagrees
        # with the array length has a bug; publishing the array's own length
        # means the client's check catches it rather than being told a number
        # that agrees with nothing.
        "edges": len(profiles),
        "sources": sources or {},
    }
    (OUT_DIR / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--graph", type=Path, default=IN_DIR / GRAPH_NAME)
    parser.add_argument("--geometry", type=Path, default=IN_DIR / GEOMETRY_NAME)
    parser.add_argument("--tile-index", type=Path, default=ELEVATION_INDEX_PATH)
    # Deliberately no --interval flag. The interval is export_elevation.py's
    # SAMPLE_INTERVAL_METERS and nothing else, because a file sampled at a
    # different spacing from trail_graph_elevation.json is a second answer to
    # one question - see the module docstring.
    args = parser.parse_args(argv)

    if not args.graph.exists():
        raise SystemExit(f"No junction graph at {args.graph} - run build_trail_graph.py first.")
    if not args.geometry.exists():
        raise SystemExit(f"No graph geometry at {args.geometry} - run build_trail_graph.py first.")
    if not args.tile_index.exists():
        raise SystemExit(f"No DEM tile index at {args.tile_index} - run fetch_elevation.py first.")

    graph = json.loads(args.graph.read_text())
    geometry = json.loads(args.geometry.read_text())
    sampler = ElevationSampler(index_elevation_tiles(args.tile_index))
    try:
        profiles, stats, seam = build(graph, geometry, sampler)
    finally:
        sampler.close()

    graph_manifest_path = IN_DIR / GRAPH_MANIFEST_NAME
    sources = json.loads(graph_manifest_path.read_text()).get("sources", {}) if graph_manifest_path.exists() else {}

    manifest = write_artifact(profiles, stats, seam, sources)

    print(f"{manifest['edges']:,} edge(s), {manifest['samples']:,} sample(s) at {SAMPLE_INTERVAL_METERS} m -> {manifest['path']}")
    print(f"  {manifest['bytes']:,} bytes")
    print(f"  measured   {manifest['measured']:,} edge(s) ({manifest['measured_pct']}%)")
    if manifest["partially_covered"]:
        print(
            f"  partial    {manifest['partially_covered']:,} edge(s) carry a null sample "
            f"({manifest['null_samples']:,} of {manifest['samples']:,}, {manifest['null_sample_pct']}%)"
        )
    if manifest["unmeasured"]:
        # Loud and per source, because a source no DEM tile covers is the
        # failure mode a newly registered trail system arrives with.
        print(f"  UNMEASURED {manifest['unmeasured']:,} edge(s) publish as null, never as flat ground:")
        for source, bucket in stats.items():
            if bucket["unmeasured"]:
                print(f"    {source}: {bucket['unmeasured']:,} of {bucket['edges']:,}")
    # The seam, every run. Not a warning - a graph is MADE of node joins and
    # these steps are a property of two surveys meeting, not a defect. What
    # would be a defect is summing across them, which is why the numbers are
    # printed next to the rule rather than buried in the manifest.
    print(
        f"  seam       {seam['coincident_ends']:,} of {seam['shared_nodes']:,} shared node(s) have every incident "
        f"edge-end at one coordinate; {seam['steps_over_dead_band']:,} carry a step over the "
        f"{DEFAULT_THRESHOLD_M} m dead band (p95 {seam['step_ft_p95']} ft, max {seam['step_ft_max']} ft)."
    )
    print(f"    Sum a route's climb from {ROUTE_GAIN_SOURCE}, never by concatenating these profiles (#559).")
    return manifest


if __name__ == "__main__":
    main()
