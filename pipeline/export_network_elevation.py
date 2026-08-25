"""Per-edge climb and drop for the junction graph a day hike routes over
(#1011, features/HIKE_PLANNING.md "The day hike on a network").

export_elevation.py answers "how high is the A.T. at mile 1,804?" - one trail,
one axis, one dense profile. A park has no such axis (#928), so the question
here is a different one: **how much does THIS edge climb?** An edge is a piece
of a maintained trail between two junctions, and a route is a list of them, so
a per-edge answer is the one a builder can add up.

WHY THIS IS A THIRD ARTIFACT AND NOT TWO MORE COLUMNS ON THE EDGE

build_trail_graph.py already splits its output on when a phone needs it: the
routing half (`trail_graph.json` - nodes, lengths, attribution) at launch, the
geometry half (`trail_graph_geometry.json` - every edge's vertices) only once
the builder opens. This is the third file on that shelf, under the same
index-alignment invariant: entry `i` here describes edge `i` there.

The maintainer's call, 2026-08-25. What it buys is that a phone deciding
whether to OFFER a day hike never downloads elevation to answer, and the
routing search never reads it: `client/src/lib/trailGraph.ts` paths over
`length_m` alone, so climb is not an input to the search and cannot slow it
down. Gain is read once per resolved hike - tens of edges - not once per edge
relaxation.

WHAT IS PUBLISHED PER EDGE, AND WHY IT IS TWO SCALARS RATHER THAN A PROFILE

`[gain_ft, loss_ft]`, rounded to whole feet, or `null`.

Two scalars because the alternative is the one shape that would cost a hiker
battery. If the client had to walk a dense sampled profile to sum a route's
climb, a per-open cost of tens of additions becomes thousands of sample reads
plus a dead-band pass - on the screen `dayHikeCard.ts` re-resolves EVERY time
it opens. Dense samples are worth publishing only if a chart is ever drawn for
a network route, and then as a fourth artifact fetched when that chart opens.

`null` means nobody knows, and it is never 0. An edge the DEM does not cover
has no climb figure, and FEATURES.md's rule applies unchanged: absent means
unknown. A route containing one such edge must say its climb is unknown rather
than summing the edges it does have - a partial total is exactly the
confidently-wrong answer that is more dangerous than an honest gap.

THE SEAM HAZARD, WHICH THIS SHAPE MAKES UNREPRESENTABLE

#559 measured what happens when elevation is summed across a break in the
ground: ~36,800 ft of climbing nobody did entered the published A.T. total,
the largest a single +2,588 ft "step" across 25 m. A junction graph is made of
that hazard - every edge is a separate piece, and `ENDPOINT_SNAP_M = 8.0`
means two edges meeting at one node can be 8 m apart on the ground and some
unmeasured distance apart vertically.

So gain is summed WITHIN an edge and never across a node join. That is not a
rule this module remembers to follow; it is the only thing the artifact can
express, because each edge is measured from its own vertices and the sum
happens on the phone, over edges, in feet. There is no concatenated profile for
a seam to hide in.

HOW PRECISE THIS IS, STATED RATHER THAN IMPLIED

The dead band is `lib/elevation_gain.py`'s, unchanged - 3 m, derived from the
DEM's own sample-to-sample error and checked on the A.T. against three
published sections by check_elevation_gain.py. It is NOT re-derived here and
must not be: one threshold working on the Whites and in Virginia is the whole
evidence that it is a measurement rather than a knob.

What is honest to say about applying it here: **no published gain figure
exists for any NYNJTC or OPRHP trail**, so the threshold arrives on this ground
unchecked. `reference/published_gain.json`'s three rows say where the risk is -
the two sustained ascents land within +/-4%, while the rolling,
descent-dominated Roan Highlands section reads +18.8% and needed a documented
25% tolerance. Harriman is rolling and descent-dominated (a junction every 1.2
trail-miles, #771), so it matches the section where the A.T.'s own gate had to
be loosened, not the ones where it was tight.

The maintainer's decision, 2026-08-25, taken with that in front of them: ship
the figure and frame it as an estimate rather than withhold it - *"Elevation
gain is not precise."* The client says so in the hiker's own words; this module
publishes `estimate: true` in its manifest so no consumer has to infer it. The
direction of the error is the safe one - a dead band that over-reads on rolling
terrain over-states climb, and therefore over-states Naismith time.

Output: `data/processed/trail_graph_elevation.json`, an index-aligned JSON
array, plus `trail_graph_elevation_manifest.json` carrying the hash, the edge
count the client checks alignment against, per-source coverage counts, and the
`sources` block copied from the graph manifest SO THE LICENCE GATE TRAVELS
WITH THE DERIVATION - climb measured along a steward's line is still that
steward's data (publish.py applies the same `reaches_hikers` check it applies
to the lines themselves).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString

from export_elevation import SAMPLE_INTERVAL_METERS, ElevationSampler, index_elevation_tiles
from lib.elevation_gain import (
    DEFAULT_THRESHOLD_FT,
    DEFAULT_THRESHOLD_M,
    METERS_PER_FOOT,
    cumulative_gain_over_gaps,
    loss_over_gaps,
)
from lib.hashing import sha256_file

ROOT = Path(__file__).resolve().parent
IN_DIR = ROOT / "data" / "processed"
OUT_DIR = ROOT / "data" / "processed"
GRAPH_NAME = "trail_graph.json"
GEOMETRY_NAME = "trail_graph_geometry.json"
GRAPH_MANIFEST_NAME = "trail_graph_manifest.json"
ARTIFACT_NAME = "trail_graph_elevation.json"
MANIFEST_NAME = "trail_graph_elevation_manifest.json"
ELEVATION_INDEX_PATH = ROOT / "data" / "raw" / "elevation" / "tile_index.json"

# The same CRS pair build_trail_graph.py measures its `length_m` in, and the
# same one export_elevation.py walks the A.T. profile in. HIKE_PLANNING.md
# Finding 1 exists because this codebase has measured "a mile" two different
# ways before; a third would be this module's own invention.
GEOGRAPHIC_CRS = "EPSG:4326"
PROJECTED_CRS = "EPSG:5070"


def _transformers() -> tuple[Transformer, Transformer]:
    """to-projected and back. always_xy because every coordinate here is
    (lon, lat) and pyproj's authority-order default would swap them - the same
    note build_trail_graph.py carries."""
    return (
        Transformer.from_crs(GEOGRAPHIC_CRS, PROJECTED_CRS, always_xy=True),
        Transformer.from_crs(PROJECTED_CRS, GEOGRAPHIC_CRS, always_xy=True),
    )


def sample_positions(length_m: float, interval_m: float = SAMPLE_INTERVAL_METERS) -> list[float]:
    """Distances along an edge to sample at, always including both ends.

    Both ends matter more here than they do on a continuous profile. An edge is
    the whole of what gets measured - there is no neighbouring piece to pick up
    a climb this one truncated - so an edge sampled from 0 m to 20 m of its
    23 m length would silently lose the last 3 m of drop into a junction.

    The count is `round(length / interval)` rather than `ceil`, so spacing
    lands NEAR the interval rather than always under it: a 30 m edge gets one
    interval (0 m, 30 m) instead of two 15 m ones. The dead band is a property
    of the DEM's resolution, not of how finely this walks, so oversampling buys
    nothing and costs a point lookup each.

    An edge shorter than half an interval still gets its two endpoints, which
    is the minimum `cumulative_gain` needs to see any ground at all.
    """
    if length_m <= 0 or interval_m <= 0:
        return [0.0]
    steps = max(1, round(length_m / interval_m))
    return [length_m * i / steps for i in range(steps + 1)]


def edge_sample_points(
    geometry: list[list[float]], to_projected: Transformer, to_geographic: Transformer
) -> list[tuple[float, float]]:
    """One edge's vertices, resampled at a real-distance interval, back in
    lon/lat ready for ElevationSampler.

    Projected first so `.interpolate()` walks metres rather than degrees -
    export_elevation.py's step 3, for the same reason and into the same CRS. A
    degenerate edge (fewer than two distinct vertices) yields a single point
    rather than raising: build_trail_graph.py already drops zero-length loops,
    so one reaching here is a shape this module should measure as "no climb"
    rather than crash the whole export over.
    """
    if len(geometry) < 2:
        return [(geometry[0][0], geometry[0][1])] if geometry else []
    projected = LineString([to_projected.transform(lon, lat) for lon, lat in geometry])
    if projected.length <= 0:
        lon, lat = geometry[0]
        return [(lon, lat)]
    points = [projected.interpolate(distance) for distance in sample_positions(projected.length)]
    return [to_geographic.transform(point.x, point.y) for point in points]


def edge_climb(elevations_m: list[float | None], threshold_ft: float = DEFAULT_THRESHOLD_FT) -> list[int] | None:
    """One edge's `[gain_ft, loss_ft]`, or None when nothing was measured.

    The elevations arrive in METRES (3DEP's own unit) and the dead band is in
    feet, so the conversion happens here, once, before either sum - not after,
    because a threshold applied in the wrong unit is a different threshold.

    None rather than [0, 0] when every sample is a DEM null. The two are
    completely different claims - "this edge is flat" against "nobody has
    measured this edge" - and the second is the one a hiker deciding whether to
    push on is owed. A PARTIALLY covered edge is measured over the runs it has
    (`cumulative_gain_over_gaps`), which under-counts by whatever happened
    inside the gap: the honest direction, and visible in the manifest's
    coverage counts rather than only described here.
    """
    if not any(value is not None for value in elevations_m):
        return None
    feet = [None if value is None else value / METERS_PER_FOOT for value in elevations_m]
    gain = cumulative_gain_over_gaps(feet, threshold_ft)
    loss = loss_over_gaps(feet, threshold_ft)
    return [round(gain), round(loss)]


def build(graph: dict, geometry: list[list[list[float]]], sampler: ElevationSampler) -> tuple[list, dict]:
    """Every edge's climb, index-aligned with `graph["edges"]`, plus coverage
    stats per source.

    EVERY EDGE'S POINTS GO TO THE SAMPLER IN ONE CALL. `sample_many` groups
    points by the tile that covers them and does one windowed read per tile, so
    batching across the whole graph is what turns thousands of remote range
    reads into a handful. Sampling edge-by-edge would re-open the same
    WarpedVRT for every edge that crosses the same cell, which on a graph whose
    edges are ~200 m long is nearly all of them.
    """
    edges = graph["edges"]
    if len(geometry) != len(edges):
        # The alignment invariant build_trail_graph.py's manifest exists to
        # protect, checked again at the one place that would otherwise write a
        # file quietly attributing edge 40's climb to edge 41.
        raise ValueError(f"geometry has {len(geometry)} entries against {len(edges)} edges - refusing to guess the pairing")

    to_projected, to_geographic = _transformers()
    per_edge_points: list[list[tuple[float, float]]] = [
        edge_sample_points(edge_geometry, to_projected, to_geographic) for edge_geometry in geometry
    ]

    flat = [point for points in per_edge_points for point in points]
    sampled = sampler.sample_many(flat) if flat else []

    climbs: list[list[int] | None] = []
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"edges": 0, "measured": 0, "partial": 0, "unmeasured": 0})
    cursor = 0
    for edge, points in zip(edges, per_edge_points):
        window = sampled[cursor : cursor + len(points)]
        cursor += len(points)
        climb = edge_climb(window)
        climbs.append(climb)

        source = edge.get("source") or "unknown"
        bucket = stats[source]
        bucket["edges"] += 1
        if climb is None:
            bucket["unmeasured"] += 1
        elif any(value is None for value in window):
            bucket["partial"] += 1
            bucket["measured"] += 1
        else:
            bucket["measured"] += 1

    return climbs, dict(sorted(stats.items()))


def coverage_summary(stats: dict[str, dict[str, int]]) -> dict:
    """The three numbers a run should be judged on, across all sources.

    Reported as counts rather than only as a percentage because "3 of 12,000
    edges" and "3 of 4" are the same percentage rounded and completely
    different situations.
    """
    total = sum(bucket["edges"] for bucket in stats.values())
    measured = sum(bucket["measured"] for bucket in stats.values())
    partial = sum(bucket["partial"] for bucket in stats.values())
    return {
        "edges": total,
        "measured": measured,
        "unmeasured": total - measured,
        "partially_covered": partial,
        "measured_pct": round(100.0 * measured / total, 2) if total else 0.0,
    }


def write_artifact(climbs: list, stats: dict, sources: dict | None = None) -> dict:
    """Write the artifact and its manifest.

    `edges` in the manifest is the alignment check: the client refuses an
    elevation file whose entry count disagrees with the graph it holds, the
    same way it already refuses a mismatched geometry file. Silent misalignment
    here would print one trail's climb against another's name.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / ARTIFACT_NAME
    path.write_text(json.dumps(climbs, separators=(",", ":")), encoding="utf-8")

    manifest = {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "edges": len(climbs),
        "threshold_m": DEFAULT_THRESHOLD_M,
        "sample_interval_m": SAMPLE_INTERVAL_METERS,
        # Flagged in the data rather than left for a reader to infer from this
        # docstring: no published gain figure exists for any trail in this
        # graph, so the dead band that is checked on the A.T. is unchecked
        # here. Every surface that renders these numbers says so.
        "estimate": True,
        "per_source": stats,
        **coverage_summary(stats),
        "sources": sources or {},
    }
    (OUT_DIR / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--graph", type=Path, default=IN_DIR / GRAPH_NAME)
    parser.add_argument("--geometry", type=Path, default=IN_DIR / GEOMETRY_NAME)
    parser.add_argument("--tile-index", type=Path, default=ELEVATION_INDEX_PATH)
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
        climbs, stats = build(graph, geometry, sampler)
    finally:
        sampler.close()

    graph_manifest_path = IN_DIR / GRAPH_MANIFEST_NAME
    sources = json.loads(graph_manifest_path.read_text()).get("sources", {}) if graph_manifest_path.exists() else {}

    manifest = write_artifact(climbs, stats, sources)

    print(f"{manifest['edges']:,} edge(s) -> {manifest['path']}")
    print(f"  measured   {manifest['measured']:,} ({manifest['measured_pct']}%)")
    if manifest["partially_covered"]:
        print(f"  partial    {manifest['partially_covered']:,} edge(s) span a DEM gap and are measured over the runs they have")
    if manifest["unmeasured"]:
        # Loud, and per source, because a source no DEM tile covers is the
        # failure mode a newly registered trail system arrives with - see
        # fetch_elevation.py's network extent.
        print(f"  UNMEASURED {manifest['unmeasured']:,} edge(s) have no elevation at all:")
        for source, bucket in stats.items():
            if bucket["unmeasured"]:
                print(f"    {source}: {bucket['unmeasured']:,} of {bucket['edges']:,}")
        print("    These publish as null, not as zero. Check the DEM tile index covers this ground.")
    return manifest


if __name__ == "__main__":
    main()
