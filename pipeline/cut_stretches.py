"""Cut a sheet's 50-mile stretch units out of its corridor archive (#556).

The unit of offline coverage is the trail-derived stretch - the maintainer's
#552 decision (2026-08-18): ~50 miles, two to five days of hiking, chosen so
a hiker can take the piece of trail they are walking instead of a gigabyte.
This module is the pipeline half of that program; the client half waits on
new wireframes.

What a stretch IS: a mile interval on the calibrated NOBO axis (#652).
Stretch k covers miles [k*50, (k+1)*50), the last one short. That the axis
is ATC's own mile scale is what makes the definition sound: the planned
hike's start/end (lib/plannedHike.ts), every POI's published mile (#753),
and a closure's start_mile_marker all speak the same numbers a stretch's
bounds do.

How the cut works - by tile, not by polygon. The source archives
(at_basemap_package.pmtiles, dem.pmtiles) are already corridor-clipped, so
every tile in them belongs to the trail; the only question is WHICH MILES
each tile serves. Buffering per-stretch centerline substrings by the
corridor's 30-mile width was considered and rejected: adjacent buffers
overlap for tens of trail-miles around every seam, which at 44 units
re-buys the duplication #193 measured, multiplied. Instead each tile's
corners and center are projected onto the calibrated axis and the tile is
routed to every stretch whose mile interval it touches - a partition of the
corridor, not 44 overlapping corridors. Sampling five points (not one)
is what handles both the tiles that straddle a seam and the places the
corridor folds back on itself (a tile between two passes of the trail
belongs to both passes' stretches).

Two deliberate allowances on top of the partition:

- SEAM_MARGIN_MILES widens every tile's interval before routing, so a
  stretch's map does not end at the exact perpendicular of its boundary
  mile. #552's non-negotiable is that a wrong answer must not cost a hiker
  map where they are walking; the margin is the data-side share of that
  (the client-side share - offering the neighbouring stretch - is #558's).
- Everything through STRETCH_CONTEXT_ZOOM goes to ONE shared context
  artifact per sheet instead of riding in every stretch. #193 measured the
  context tiles at 6.3 MB duplicated per package BY CONSTRUCTION; at 44
  units that is ~280 MB of the same bytes, so the context becomes a single
  sibling download. This also gives the DEM the context mechanism #552
  notes it never had.

@unvalidated Both STRETCH_MILES=50 and SEAM_MARGIN_MILES=2 are starting
values, not findings - 50 is the maintainer's opening call ("2-5 days"),
2 is picked. What would settle them: real hikers' download behaviour once
#558 ships, and the duplication share this module prints per run.
"""

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import shapely
from pmtiles.reader import Reader, all_tiles
from pmtiles.tile import deserialize_header, zxy_to_tileid
from pmtiles.writer import write
from pyproj import Transformer
from shapely.strtree import STRtree

from export_elevation import MARKERS_PATH, calibrated_trail_axis, sha256_file
from lib.tiling import tile_bounds_merc

MERC_CRS = "EPSG:3857"
AXIS_CRS = "EPSG:5070"

PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
CENTERLINE_PATH = Path(__file__).parent / "data" / "raw" / "centerline.geojson"

STRETCH_MILES = 50.0
SEAM_MARGIN_MILES = 2.0
# The same boundary extract_package.DEFAULT_CONTEXT_ZOOM draws, for the same
# reason (z9 is the last zoom of coarse orientation). Kept as this module's
# own constant because here it decides which ARTIFACT a tile lands in, not
# merely how wide one package pans.
STRETCH_CONTEXT_ZOOM = 9


def stretch_span(stretch_id: int, stretch_miles: float, top_mile: float) -> tuple[float, float]:
    """The core mile interval stretch `stretch_id` covers, last one short."""
    lo = stretch_id * stretch_miles
    return lo, min(lo + stretch_miles, top_mile)


def miles_of_merc_points(calibrated, xs_merc: np.ndarray, ys_merc: np.ndarray) -> np.ndarray:
    """The calibrated NOBO mile of each EPSG:3857 point - nearest piece,
    then that piece's marker-interpolated scale (#652). Vectorised: one
    coordinate transform, one bulk STRtree query, one line_locate_point per
    piece that actually received points."""
    transformer = Transformer.from_crs(MERC_CRS, AXIS_CRS, always_xy=True)
    ax, ay = transformer.transform(xs_merc, ys_merc)
    points = shapely.points(ax, ay)
    tree = STRtree([cal.line for cal in calibrated])
    nearest = tree.nearest(points)
    miles = np.empty(len(points), dtype=float)
    for part_index in np.unique(nearest):
        mask = nearest == part_index
        alongs = shapely.line_locate_point(calibrated[part_index].line, points[mask])
        miles[mask] = calibrated[part_index].mile_at(alongs)
    return miles


def stretch_ids_for_samples(sample_miles: np.ndarray, margin_miles: float, stretch_miles: float, top_id: int) -> set[int]:
    """Every stretch whose interval the sampled miles (± margin) touch."""
    ids: set[int] = set()
    for mile in sample_miles:
        first = int((mile - margin_miles) // stretch_miles)
        last = int((mile + margin_miles) // stretch_miles)
        ids.update(range(max(0, first), min(top_id, last) + 1))
    return ids


def _bounds_header(source_header: dict, bounds_merc: tuple[float, float, float, float], min_zoom: int) -> dict:
    """A stretch's header: the source's format facts (bytes are copied
    verbatim, so tile_type/compression MUST carry over - same rule as
    extract_package.package_header) and its own tiles' bounds."""
    to_wgs84 = Transformer.from_crs(MERC_CRS, "EPSG:4326", always_xy=True)
    min_lon, min_lat = to_wgs84.transform(bounds_merc[0], bounds_merc[1])
    max_lon, max_lat = to_wgs84.transform(bounds_merc[2], bounds_merc[3])
    return {
        "tile_type": source_header["tile_type"],
        "tile_compression": source_header["tile_compression"],
        "min_lon_e7": int(min_lon * 1e7),
        "min_lat_e7": int(min_lat * 1e7),
        "max_lon_e7": int(max_lon * 1e7),
        "max_lat_e7": int(max_lat * 1e7),
        "center_lon_e7": int((min_lon + max_lon) / 2 * 1e7),
        "center_lat_e7": int((min_lat + max_lat) / 2 * 1e7),
        "center_zoom": min_zoom,
    }


def _tile_sample_points(z: int, x: int, y: int) -> list[tuple[float, float]]:
    """Four corners and the center, in mercator - see the module docstring
    for why one point is not enough at seams and corridor folds."""
    min_x, min_y, max_x, max_y = tile_bounds_merc(z, x, y)
    return [
        (min_x, min_y),
        (min_x, max_y),
        (max_x, min_y),
        (max_x, max_y),
        ((min_x + max_x) / 2, (min_y + max_y) / 2),
    ]


def cut_stretches(
    source_path: Path,
    family: str,
    centerline_path: Path = CENTERLINE_PATH,
    markers_path: Path = MARKERS_PATH,
    out_dir: Path = PROCESSED_DIR,
    stretch_miles: float = STRETCH_MILES,
    margin_miles: float = SEAM_MARGIN_MILES,
    context_zoom: int = STRETCH_CONTEXT_ZOOM,
) -> dict:
    """Cut `source_path` into one context archive plus per-stretch archives
    named `<family>_stretch_<id>.pmtiles`, write `<family>_stretches.json`
    (the published coverage index) and `<family>_stretches_manifest.json`
    (publish.py's input), and return the manifest dict.

    Two passes over the source: the first collects every above-context
    tile's address and routes it by projected mile, the second streams the
    bytes into the writers. Holding routing rather than bytes is what keeps
    a gigabyte archive cuttable on an ordinary runner.
    """
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    calibrated = calibrated_trail_axis(con, centerline_path, markers_path)
    top_mile = max(cal.mile_at(cal.line.length) for cal in calibrated)
    top_id = int(top_mile // stretch_miles)

    with open(source_path, "rb") as f:

        def get_bytes(offset, length):
            f.seek(offset)
            return f.read(length)

        source_header = deserialize_header(get_bytes(0, 127))
        # The source's own metadata (vector_layers above all) must reach
        # every cut - MapLibre reads the layer catalogue out of it, and a
        # stretch without one is an archive a style cannot draw from. Same
        # carry-over extract_package performs.
        source_metadata = Reader(get_bytes).metadata()

        # Pass 1: route every above-context tile by the miles it serves.
        addresses: list[tuple[int, int, int]] = []
        sample_xs: list[float] = []
        sample_ys: list[float] = []
        context_tile_count = 0
        for (z, x, y), _data in all_tiles(get_bytes):
            if z > context_zoom:
                addresses.append((z, x, y))
                for sx, sy in _tile_sample_points(z, x, y):
                    sample_xs.append(sx)
                    sample_ys.append(sy)
            else:
                context_tile_count += 1

        routing: dict[tuple[int, int, int], set[int]] = {}
        if addresses:
            miles = miles_of_merc_points(calibrated, np.array(sample_xs), np.array(sample_ys))
            for index, address in enumerate(addresses):
                samples = miles[index * 5 : index * 5 + 5]
                routing[address] = stretch_ids_for_samples(samples, margin_miles, stretch_miles, top_id)

        # Every stretch must be someone's map. An empty stretch means the
        # axis and the archive disagree about where the trail is - a cut
        # that quietly shipped it would 404 nothing and cover nothing.
        populated = set().union(*routing.values()) if routing else set()
        missing = [i for i in range(top_id + 1) if i not in populated]
        if missing:
            raise SystemExit(
                f"Stretches {missing} would contain no tiles. The archive and the "
                "calibrated axis disagree about where the trail runs - wrong source, "
                "or a centerline/markers fetch that does not match the build."
            )

        # Pass 2: stream bytes into one writer per artifact. No context
        # artifact when the source holds nothing at or under the context
        # zoom - an empty archive published as "the context" would read as
        # coverage that is actually nothing.
        out_dir.mkdir(parents=True, exist_ok=True)
        context_name = f"{family}_context.pmtiles" if context_tile_count else None
        stretch_name = {i: f"{family}_stretch_{i:02d}.pmtiles" for i in range(top_id + 1)}
        names = ([context_name] if context_name else []) + list(stretch_name.values())
        writers = {name: write(str(out_dir / name)) for name in names}
        handles = {name: writer.__enter__() for name, writer in writers.items()}
        counts = dict.fromkeys(writers, 0)
        bounds: dict[str, list[float]] = {}
        min_written_zoom = dict.fromkeys(writers, None)
        try:
            for (z, x, y), data in all_tiles(get_bytes):
                targets = [context_name] if z <= context_zoom else [stretch_name[i] for i in routing[(z, x, y)]]
                tile_id = zxy_to_tileid(z, x, y)
                tb = tile_bounds_merc(z, x, y)
                for name in targets:
                    handles[name].write_tile(tile_id, data)
                    counts[name] += 1
                    if name in bounds:
                        b = bounds[name]
                        b[0], b[1] = min(b[0], tb[0]), min(b[1], tb[1])
                        b[2], b[3] = max(b[2], tb[2]), max(b[3], tb[3])
                    else:
                        bounds[name] = list(tb)
                    if min_written_zoom[name] is None:
                        min_written_zoom[name] = z
            for name, handle in handles.items():
                written_min = min_written_zoom[name]
                handle.finalize(
                    _bounds_header(
                        source_header,
                        tuple(bounds[name]),
                        source_header["min_zoom"] if written_min is None else written_min,
                    ),
                    {**source_metadata, "name": name.removesuffix(".pmtiles")},
                )
        finally:
            for writer in writers.values():
                writer.__exit__(None, None, None)

    distinct = len(routing)
    routed = sum(len(ids) for ids in routing.values())
    duplication_pct = (routed - distinct) / distinct * 100 if distinct else 0.0
    print(
        f"{family}: {distinct} stretch tiles -> {routed} placements across {top_id + 1} stretches "
        f"({duplication_pct:.1f}% seam duplication at ±{margin_miles} mi), "
        f"{counts.get(context_name, 0)} context tiles through z{context_zoom} published once."
    )

    # The coverage index the client's picker will eventually read (#557/#558
    # - deferred until the new wireframes). Core intervals only: the margin
    # is generosity in the bytes, not a promise in the metadata, so nothing
    # downstream is tempted to treat a margin as coverage.
    index = {
        "stretch_miles": stretch_miles,
        "seam_margin_miles": margin_miles,
        "context_zoom": context_zoom,
        "axis_top_mile": round(top_mile, 3),
        "context": context_name,
        "stretches": [
            {
                "id": i,
                "key": stretch_name[i],
                "miles": [round(v, 3) for v in stretch_span(i, stretch_miles, top_mile)],
            }
            for i in range(top_id + 1)
        ],
    }
    index_name = f"{family}_stretches.json"
    (out_dir / index_name).write_text(json.dumps(index, indent=2))

    artifact_names = [index_name, *([context_name] if context_name else []), *stretch_name.values()]
    manifest = {
        "artifacts": {
            name: {
                "path": str(out_dir / name),
                "sha256": sha256_file(out_dir / name),
                "size_bytes": (out_dir / name).stat().st_size,
            }
            for name in artifact_names
        },
        # #193's duplication figure gets its successor here, measured on
        # every cut rather than assumed away: how many tile placements the
        # margin buys over a strict partition, and how many context tiles
        # now publish once instead of once per unit.
        "stats": {
            "distinct_stretch_tiles": distinct,
            "stretch_tile_placements": routed,
            "seam_duplication_pct": round(duplication_pct, 2),
            "context_tiles": context_tile_count,
        },
    }
    manifest_path = out_dir / f"{family}_stretches_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"{len(artifact_names)} artifacts -> {out_dir}, manifest -> {manifest_path}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="The corridor archive to cut (at_basemap_package.pmtiles or dem.pmtiles)")
    parser.add_argument("--family", required=True, choices=["at_basemap", "dem"], help="Key family for the cut artifacts")
    parser.add_argument("--stretch-miles", type=float, default=STRETCH_MILES)
    parser.add_argument("--margin-miles", type=float, default=SEAM_MARGIN_MILES)
    parser.add_argument("--context-zoom", type=int, default=STRETCH_CONTEXT_ZOOM)
    args = parser.parse_args()
    cut_stretches(
        args.source,
        args.family,
        stretch_miles=args.stretch_miles,
        margin_miles=args.margin_miles,
        context_zoom=args.context_zoom,
    )
