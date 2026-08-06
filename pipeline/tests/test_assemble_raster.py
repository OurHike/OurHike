"""Tests for assemble_raster.py - the reconvergence gates and the merged
archives, driven end-to-end over synthetic cell outputs built with the same
helpers the real fan-out uses."""

import json

import numpy as np
import pytest
import rasterio
from pmtiles.reader import MmapSource, all_tiles
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write
from pyproj import Transformer
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds
from shapely.geometry import LineString, box, mapping
from shapely.ops import transform as shp_transform

import assemble_raster
from assemble_raster import assemble
from lib.raster_tiles import encode_webp
from render_cell_tiles import owned_tiles

GEO = "EPSG:4326"
MERC = "EPSG:3857"
to_merc = Transformer.from_crs(GEO, MERC, always_xy=True)

# A corridor straddling the -77 meridian, so BOTH 1-degree cells own tiles
# and the k-way merge is real. Sized like the real thing in the dimension
# that matters: ~55 km tall, so a z1 pixel (39 km) still lands ink - the
# completeness gate legitimately fails a corridor that vanishes at world
# zooms, and the real 30-mile ribbon does not (export_pmtiles.py measured
# 0.8 x 22 px at z0).
#
# The cell bboxes are CLIPPED to the corridor's bounding box, the way
# lib/corridor_grid.compute_cells actually cuts them - which puts edge
# tiles' centres outside every cell and leans on owner_index's nearest-cell
# fallback. Cells with room to spare would pass under the centre rule alone
# and miss the bug that refused the first real 51-cell assemble.
CORRIDOR_BOX = box(-77.9, 39.2, -76.1, 39.7)
CENTERLINE = LineString([(-77.85, 39.45), (-76.15, 39.45)])
CELLS = [
    {"index": 0, "bbox": [-77.9, 39.2, -77.0, 39.7], "quads": ["a.tif"]},
    {"index": 1, "bbox": [-77.0, 39.2, -76.1, 39.7], "quads": ["b.tif"]},
]


def solid_tile_bytes(value: int) -> bytes:
    arr = np.full((3, 8, 8), value, dtype="uint8")
    return encode_webp(arr)


def write_inputs(tmp_path):
    """corridor/centerline/cells.json plus a full set of synthetic cell
    outputs - returns (cells_dir, cells_json, corridor_path, centerline_path,
    per_cell_owned)."""
    corridor_path = tmp_path / "corridor.geojson"
    corridor_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {}, "geometry": mapping(CORRIDOR_BOX)}],
            }
        )
    )
    centerline_path = tmp_path / "centerline.geojson"
    centerline_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {}, "geometry": mapping(CENTERLINE)}],
            }
        )
    )
    cells_json = tmp_path / "cells.json"
    cells_json.write_text(json.dumps({"cells": CELLS}))

    corridor_merc = shp_transform(to_merc.transform, CORRIDOR_BOX)
    band_merc = shp_transform(to_merc.transform, CENTERLINE).buffer(assemble_raster.BAND_METERS)

    cells_dir = tmp_path / "raster_cells"
    cells_dir.mkdir()
    per_cell_owned = {}
    cell_bboxes = [tuple(c["bbox"]) for c in CELLS]
    for cell in CELLS:
        owned = owned_tiles(cell["index"], cell_bboxes, corridor_merc, band_merc)
        per_cell_owned[cell["index"]] = owned
        tiles_name = None
        if owned:
            tiles_name = f"cell_tiles_{cell['index']}.pmtiles"
            with write(str(cells_dir / tiles_name)) as writer:
                for z, x, y in sorted(owned, key=lambda t: zxy_to_tileid(*t)):
                    writer.write_tile(zxy_to_tileid(z, x, y), solid_tile_bytes(100 + cell["index"]))
                writer.finalize(
                    {
                        "tile_type": TileType.WEBP,
                        "tile_compression": Compression.NONE,
                        "min_lon_e7": 0,
                        "min_lat_e7": 0,
                        "max_lon_e7": 0,
                        "max_lat_e7": 0,
                        "center_lon_e7": 0,
                        "center_lat_e7": 0,
                        "center_zoom": 11,
                    },
                    {"name": "cell"},
                )
        receipt = {
            "cell": cell["index"],
            "owned": sorted(owned),
            "written": sorted(owned),
            "empty": [],
            "tiles": tiles_name,
            "overview": f"overview_{cell['index']}.tif",
        }
        (cells_dir / f"receipt_{cell['index']}.json").write_text(json.dumps(receipt))

        # A solid overview over the cell's slice of the corridor, in merc at
        # a coarse grid - enough for the low zooms to render non-empty.
        cell_box = box(*cell["bbox"]).intersection(CORRIDOR_BOX)
        west, south, east, north = transform_bounds(GEO, MERC, *cell_box.bounds)
        px = 64
        data = np.full((3, px, px), 90, dtype="uint8")
        with rasterio.open(
            cells_dir / f"overview_{cell['index']}.tif",
            "w",
            driver="GTiff",
            width=px,
            height=px,
            count=3,
            dtype="uint8",
            crs=MERC,
            transform=from_bounds(west, south, east, north, px, px),
            nodata=0,
        ) as dst:
            dst.write(data)

    return cells_dir, cells_json, corridor_path, centerline_path, per_cell_owned


def read_zooms(path):
    with open(path, "rb") as f:
        return sorted({z for (z, _x, _y), _data in all_tiles(MmapSource(f))})


def test_assembles_four_tiers_with_the_band_only_in_the_quad_sheet(tmp_path):
    cells_dir, cells_json, corridor, centerline, per_cell = write_inputs(tmp_path)
    out_dir = tmp_path / "out"

    assemble(cells_dir, cells_json, corridor, centerline, out_dir)

    for name, tier_max in assemble_raster.TIERS:
        zooms = read_zooms(out_dir / name)
        assert max(zooms) == tier_max
        assert min(zooms) == 0, "the #216 rule: tiles at the zoom the app opens at"
    # z14 exists only in the quad sheet.
    assert 14 not in read_zooms(out_dir / "background_z13.pmtiles")
    assert 14 in read_zooms(out_dir / "quad_sheet_z14.pmtiles")

    # Every owned tile from both cells made it into the top tier - the
    # k-way merge dropped nothing.
    with open(out_dir / "quad_sheet_z14.pmtiles", "rb") as f:
        native = {(z, x, y) for (z, x, y), _ in all_tiles(MmapSource(f)) if z >= 11}
    expected = {tuple(t) for owned in per_cell.values() for t in owned}
    assert native == expected


def test_refuses_a_missing_receipt(tmp_path):
    cells_dir, cells_json, corridor, centerline, _ = write_inputs(tmp_path)
    (cells_dir / "receipt_1.json").unlink()

    with pytest.raises(SystemExit, match="receipt"):
        assemble(cells_dir, cells_json, corridor, centerline, tmp_path / "out")


def test_refuses_overlapping_ownership(tmp_path):
    cells_dir, cells_json, corridor, centerline, per_cell = write_inputs(tmp_path)
    # Claim one of cell 0's tiles in cell 1's receipt too.
    receipt = json.loads((cells_dir / "receipt_1.json").read_text())
    receipt["owned"] = receipt["owned"] + [list(per_cell[0][0])]
    (cells_dir / "receipt_1.json").write_text(json.dumps(receipt))

    with pytest.raises(SystemExit, match="twice"):
        assemble(cells_dir, cells_json, corridor, centerline, tmp_path / "out")


def test_refuses_a_lost_cell_archive(tmp_path):
    cells_dir, cells_json, corridor, centerline, _ = write_inputs(tmp_path)
    (cells_dir / "cell_tiles_0.pmtiles").unlink()

    with pytest.raises(SystemExit, match="missing"):
        assemble(cells_dir, cells_json, corridor, centerline, tmp_path / "out")


def test_refuses_ownership_cut_against_a_different_corridor(tmp_path):
    cells_dir, cells_json, corridor, centerline, _ = write_inputs(tmp_path)
    # Shift the corridor after the cells rendered: the enumeration no longer
    # matches what the receipts own.
    moved = box(-79.2, 39.2, -78.1, 39.7)
    corridor.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {}, "geometry": mapping(moved)}],
            }
        )
    )

    with pytest.raises(SystemExit, match="different\\s+corridor|does not tile"):
        assemble(cells_dir, cells_json, corridor, centerline, tmp_path / "out")
