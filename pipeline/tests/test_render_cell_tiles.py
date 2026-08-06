"""Tests for render_cell_tiles.py's geometry decisions - which tiles a cell
owns and which quads those tiles need. The fetch/fix/verify chain it drives
is fetch_topo_quads'/fix_corrupted_quads'/spike_raster_mosaic's, tested
where it lives."""

import json

from pyproj import Transformer
from rasterio.warp import transform_bounds
from shapely.geometry import box, mapping
from shapely.ops import transform as shp_transform

from lib.raster_tiles import NATIVE_MIN_ZOOM, owns_tile, tiles_intersecting_geom
from lib.tiling import tile_bounds_merc
from render_cell_tiles import (
    BAND_ZOOM,
    MAX_ZOOM,
    load_geom_merc,
    owned_tiles,
    quads_for_tiles,
)

GEO = "EPSG:4326"
MERC = "EPSG:3857"

to_merc = Transformer.from_crs(GEO, MERC, always_xy=True)


def merc(geom):
    return shp_transform(to_merc.transform, geom)


def test_owned_tiles_cover_native_zooms_with_the_band_only_at_fourteen():
    corridor = merc(box(-77.9, 39.1, -77.1, 39.9))
    band = merc(box(-77.6, 39.4, -77.4, 39.6))
    cell = (-78.0, 39.0, -77.0, 40.0)

    owned = owned_tiles(cell, corridor, band)
    zooms = {z for z, _x, _y in owned}

    assert zooms == set(range(NATIVE_MIN_ZOOM, MAX_ZOOM + 1))
    z14 = [(x, y) for z, x, y in owned if z == BAND_ZOOM]
    corridor_wide_z14 = tiles_intersecting_geom(corridor, BAND_ZOOM)
    assert 0 < len(z14) < len(corridor_wide_z14), "z14 must be the band, not the corridor"
    # Every owned tile really is this cell's by the centre rule.
    for z, x, y in owned:
        t = transform_bounds(MERC, GEO, *tile_bounds_merc(z, x, y))
        assert owns_tile(cell, t)


def test_border_tiles_pull_the_neighbouring_cells_quads():
    # A corridor spanning two cells; the west cell owns a z11 tile near the
    # shared edge, and that tile's footprint needs a quad that lives in the
    # east cell. The fetch set must include it - this is the no-seams rule.
    corridor = merc(box(-77.2, 39.4, -76.8, 39.6))
    band = corridor
    west_cell = (-78.0, 39.0, -77.0, 40.0)

    owned = owned_tiles(west_cell, corridor, band)
    quad_bounds = {
        "west_quad.tif": (-77.25, 39.35, -77.0, 39.65),
        "east_quad.tif": (-77.0, 39.35, -76.75, 39.65),
        "far_away.tif": (-70.0, 44.0, -69.8, 44.2),
    }

    wanted = quads_for_tiles(quad_bounds, owned)

    assert "west_quad.tif" in wanted
    assert "east_quad.tif" in wanted, "an owned border tile spans into the east quad"
    assert "far_away.tif" not in wanted


def test_load_geom_merc_accepts_feature_collections(tmp_path):
    geom = box(-77.5, 39.4, -77.3, 39.6)
    path = tmp_path / "corridor.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {}, "geometry": mapping(geom)}],
            }
        )
    )

    loaded = load_geom_merc(path)

    assert loaded.equals_exact(merc(geom), tolerance=1.0)
