"""Cut a sheet's 1-degree coverage cells out of its corridor archive (#1175).

The unit of offline coverage is the 1x1 degree cell - the maintainer's #552
decision (2026-08-25), superseding the trail-derived stretch cut #556 built
and this replaces. A cell is what gets built, versioned, downloaded and resumed; a
hiker never sees one, they tap a named PIECE that is a set of cells
(features/OFFLINE_COVERAGE.md). This module is the pipeline half.

WHAT A CELL IS: a whole graticule square from lib/corridor_grid.graticule_cells
- anchored on whole degrees, never on this archive's bounding box. That
anchoring is the whole point and the reason it is a separate function from
compute_cells: two organizations' sheets over the same ground must produce the
SAME cells, or the overlap that cells were chosen to eliminate comes straight
back. See that function for the measurement.

HOW THE CUT WORKS - by rectangle overlap, not by sampling. The stretch cut
projected five points per tile onto a calibrated mile axis, because "which
miles does this tile serve" is a question about a curve and one sample point
answers it wrongly at seams and where the corridor folds back. Cell
membership is not that question. A tile's bounds and a cell's bounds are both
axis-aligned rectangles in lon/lat, and web mercator is monotonic in both
axes, so the tile's mercator bounds convert to an exact lon/lat rectangle and
membership is an exact overlap test. No sampling, and therefore no false
negatives - a strict improvement the grid change buys rather than a corner
cut.

Two deliberate allowances on top of the partition, both carried over from
the stretch cut because the reasoning survives the change of unit:

- SEAM_MARGIN_KM widens every tile's rectangle before routing, so a cell's
  map does not end at the exact perpendicular of its boundary. #552's
  non-negotiable is that a wrong answer must not cost a hiker map where they
  are walking; the margin is the data-side share of that (the client-side
  share - offering the neighbouring piece - is #558's).
- Everything through CELL_CONTEXT_ZOOM goes to ONE shared context artifact
  per sheet instead of riding in every cell. #193 measured the context tiles
  at 6.3 MB duplicated per package BY CONSTRUCTION; at the A.T.'s 51 cells
  that would be ~321 MB of the same bytes, which would defeat the entire
  point of splitting.

@unvalidated SEAM_MARGIN_KM = 3.0 is picked, not found. What would settle it:
how far past a cell boundary a hiker actually pans and walks once #558 ships
and there is behaviour to measure, plus the duplication share this module
prints on every run. It is stated in kilometres rather than degrees on
purpose - a degree of longitude is 111 km at the equator and about 77 km in
Maine, so a degree margin would be a different amount of ground at each end
of the trail, while the thing being promised is ground.
"""

import argparse
import json
import math
from pathlib import Path

from pmtiles.reader import Reader, all_tiles
from pmtiles.tile import deserialize_header, zxy_to_tileid
from pmtiles.writer import write

from export_elevation import sha256_file
from lib.corridor_grid import CELL_DEGREES, graticule_cells
from lib.tiling import tile_bounds_merc

PROCESSED_DIR = Path(__file__).parent / "data" / "processed"

SEAM_MARGIN_KM = 3.0
# The same boundary extract_package.DEFAULT_CONTEXT_ZOOM draws, for the same
# reason (z9 is the last zoom of coarse orientation). Kept as this module's
# own constant because here it decides which ARTIFACT a tile lands in, not
# merely how wide one package pans.
CELL_CONTEXT_ZOOM = 9

# Mean meridional degree. Good to a few parts in a thousand over the
# latitudes any of these sheets cover, which is far inside a 3 km margin.
KM_PER_DEGREE_LAT = 111.0

MERC_MAX = 20037508.342789244


def cell_name(west: float, south: float) -> str:
    """A cell's name, from the ground it holds rather than an index.

    `n34w084` is the USGS quad convention: the south-west corner, latitude
    first. Graticule cells always have an integral corner, which is what
    makes this possible - and an index would renumber every artifact the
    moment a corridor's bounding box moved, which publish.py's additive-only
    manifest merge could never take back.
    """
    ns = "n" if south >= 0 else "s"
    ew = "e" if west >= 0 else "w"
    return f"{ns}{abs(int(round(south))):02d}{ew}{abs(int(round(west))):03d}"


def merc_to_lonlat(x: float, y: float) -> tuple[float, float]:
    """EPSG:3857 metres to lon/lat degrees."""
    lon = x / MERC_MAX * 180.0
    lat = math.degrees(2 * math.atan(math.exp(math.radians(y / MERC_MAX * 180.0))) - math.pi / 2)
    return lon, lat


def tile_bounds_lonlat(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """A tile's bounds as an exact lon/lat rectangle (west, south, east,
    north). Exact rather than approximate because web mercator is monotonic
    and axis-aligned in both axes - the corners map to the corners."""
    min_x, min_y, max_x, max_y = tile_bounds_merc(z, x, y)
    west, south = merc_to_lonlat(min_x, min_y)
    east, north = merc_to_lonlat(max_x, max_y)
    return west, south, east, north


def margin_degrees(south: float, north: float, margin_km: float) -> tuple[float, float]:
    """The margin in degrees of longitude and latitude, at the latitude it is
    being applied. Longitude degrees shrink with cos(lat), so the widest
    (most generous) of the rectangle's own latitudes is used - erring toward
    more map, which is the only direction #552 allows erring in."""
    d_lat = margin_km / KM_PER_DEGREE_LAT
    worst = max(abs(south), abs(north))
    d_lon = margin_km / (KM_PER_DEGREE_LAT * max(math.cos(math.radians(worst)), 0.01))
    return d_lon, d_lat


def cells_for_tile(
    tile: tuple[float, float, float, float],
    cells: list[tuple],
    margin_km: float,
) -> list[int]:
    """Indices of every cell the tile touches once widened by the margin."""
    west, south, east, north = tile
    d_lon, d_lat = margin_degrees(south, north, margin_km)
    west, east = west - d_lon, east + d_lon
    south, north = south - d_lat, north + d_lat
    hits = []
    for index, (cw, cs, ce, cn) in enumerate(cells):
        if west < ce and east > cw and south < cn and north > cs:
            hits.append(index)
    return hits


def archive_bounds(header: dict) -> tuple[float, float, float, float]:
    """The lon/lat bounds a PMTiles header declares."""
    return (
        header["min_lon_e7"] / 1e7,
        header["min_lat_e7"] / 1e7,
        header["max_lon_e7"] / 1e7,
        header["max_lat_e7"] / 1e7,
    )


def _bounds_header(source_header: dict, bounds_merc: tuple[float, float, float, float], min_zoom: int) -> dict:
    """A cell's header: the source's format facts (bytes are copied verbatim,
    so tile_type/compression MUST carry over - the same rule
    extract_package.package_header follows) and its own
    tiles' bounds."""
    min_lon, min_lat = merc_to_lonlat(bounds_merc[0], bounds_merc[1])
    max_lon, max_lat = merc_to_lonlat(bounds_merc[2], bounds_merc[3])
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


def cut_cells(
    source_path: Path,
    family: str,
    out_dir: Path = PROCESSED_DIR,
    margin_km: float = SEAM_MARGIN_KM,
    context_zoom: int = CELL_CONTEXT_ZOOM,
) -> dict:
    """Cut `source_path` into one context archive plus per-cell archives named
    `<family>_cell_<name>.pmtiles`, write `<family>_cells.json` (the published
    coverage index) and `<family>_cells_manifest.json` (publish.py's input),
    and return the manifest dict.

    Two passes over the source: the first collects every above-context tile's
    address and routes it by rectangle overlap, the second streams the bytes
    into the writers. Holding routing rather than bytes is what keeps a
    gigabyte archive cuttable on an ordinary runner.
    """
    with open(source_path, "rb") as f:

        def get_bytes(offset, length):
            f.seek(offset)
            return f.read(length)

        source_header = deserialize_header(get_bytes(0, 127))
        # The source's own metadata (vector_layers above all) must reach every
        # cut - MapLibre reads the layer catalogue out of it, and a cell
        # without one is an archive a style cannot draw from.
        source_metadata = Reader(get_bytes).metadata()

        cells = graticule_cells(archive_bounds(source_header))
        if not cells:
            raise SystemExit(
                f"{source_path} declares bounds that cover no whole-degree cell. "
                "Either the header is wrong or this is not a sheet worth cutting."
            )

        # Pass 1: route every above-context tile by the cells it overlaps.
        routing: dict[tuple[int, int, int], list[int]] = {}
        context_tile_count = 0
        for (z, x, y), _data in all_tiles(get_bytes):
            if z > context_zoom:
                routing[(z, x, y)] = cells_for_tile(tile_bounds_lonlat(z, x, y), cells, margin_km)
            else:
                context_tile_count += 1

        # Every published cell must be someone's map. An empty one means the
        # grid and the archive disagree about where this sheet's ground is -
        # a cut that quietly shipped it would 404 nothing and cover nothing.
        populated = {index for indices in routing.values() for index in indices}
        missing = sorted(set(range(len(cells))) - populated)
        if missing:
            names = ", ".join(cell_name(cells[i][0], cells[i][1]) for i in missing)
            raise SystemExit(
                f"Cells {names} would contain no tiles. The archive's declared bounds and "
                "its actual tiles disagree - a wrong source, or a header that outran the cut."
            )

        # Pass 2: stream bytes into one writer per artifact. No context
        # artifact when the source holds nothing at or under the context zoom
        # - an empty archive published as "the context" would read as
        # coverage that is actually nothing.
        out_dir.mkdir(parents=True, exist_ok=True)
        context_name = f"{family}_context.pmtiles" if context_tile_count else None
        cell_key = {i: f"{family}_cell_{cell_name(c[0], c[1])}.pmtiles" for i, c in enumerate(cells)}
        names = ([context_name] if context_name else []) + list(cell_key.values())
        writers = {name: write(str(out_dir / name)) for name in names}
        handles = {name: writer.__enter__() for name, writer in writers.items()}
        counts = dict.fromkeys(writers, 0)
        bounds: dict[str, list[float]] = {}
        min_written_zoom = dict.fromkeys(writers, None)
        try:
            for (z, x, y), data in all_tiles(get_bytes):
                targets = [context_name] if z <= context_zoom else [cell_key[i] for i in routing[(z, x, y)]]
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
    routed = sum(len(indices) for indices in routing.values())
    duplication_pct = (routed - distinct) / distinct * 100 if distinct else 0.0
    print(
        f"{family}: {distinct} cell tiles -> {routed} placements across {len(cells)} cells "
        f"({duplication_pct:.1f}% seam duplication at {margin_km} km), "
        f"{counts.get(context_name, 0)} context tiles through z{context_zoom} published once."
    )

    # The coverage index the client resolves ground to cells with (#557/#558).
    # Core cell bounds only: the margin is generosity in the bytes, not a
    # promise in the metadata, so nothing downstream is tempted to treat a
    # margin as coverage. The list is what was BUILT, which is not the same
    # set as what the grid defines - and that difference is the one thing a
    # client cannot compute for itself.
    index = {
        "cell_degrees": CELL_DEGREES,
        "seam_margin_km": margin_km,
        "context_zoom": context_zoom,
        "context": context_name,
        "cells": [
            {
                "name": cell_name(c[0], c[1]),
                "key": cell_key[i],
                "bounds": [round(v, 6) for v in c],
            }
            for i, c in enumerate(cells)
        ],
    }
    index_name = f"{family}_cells.json"
    (out_dir / index_name).write_text(json.dumps(index, indent=2))

    artifact_names = [index_name, *([context_name] if context_name else []), *cell_key.values()]
    manifest = {
        "artifacts": {
            name: {
                "path": str(out_dir / name),
                "sha256": sha256_file(out_dir / name),
                "size_bytes": (out_dir / name).stat().st_size,
            }
            for name in artifact_names
        },
        # #193's duplication figure gets its successor here, measured on every
        # cut rather than assumed away: how many tile placements the margin
        # buys over a strict partition, and how many context tiles now publish
        # once instead of once per unit.
        "stats": {
            "distinct_cell_tiles": distinct,
            "cell_tile_placements": routed,
            "seam_duplication_pct": round(duplication_pct, 2),
            "context_tiles": context_tile_count,
            "cells": len(cells),
        },
    }
    manifest_path = out_dir / f"{family}_cells_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"{len(artifact_names)} artifacts -> {out_dir}, manifest -> {manifest_path}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="The corridor archive to cut (at_basemap_package.pmtiles or dem.pmtiles)")
    parser.add_argument("--family", required=True, choices=["at_basemap", "dem"], help="Key family for the cut artifacts")
    parser.add_argument("--margin-km", type=float, default=SEAM_MARGIN_KM)
    parser.add_argument("--context-zoom", type=int, default=CELL_CONTEXT_ZOOM)
    args = parser.parse_args()
    cut_cells(args.source, args.family, margin_km=args.margin_km, context_zoom=args.context_zoom)
