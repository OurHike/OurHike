"""Tests for lib/raster_tiles.py - the warp-once tile renderer of #191.

Synthetic quads throughout: small solid-colour GeoTIFFs written in a real
UTM CRS, so every warp the tests exercise is the genuine article (per-quad
projected CRS onto the tile's mercator grid) rather than a same-CRS copy.
"""

import numpy as np
import pytest
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds
from shapely.geometry import box

from lib.raster_tiles import (
    NEAR_NATIVE_ZOOM,
    export_tiles,
    meters_per_pixel,
    owns_tile,
    render_tile_from_quads,
    resampling_for,
    tile_transform,
    tiles_intersecting_geom,
)
from lib.tiling import tile_bounds_merc, tile_range_for_bounds

UTM_18N = "EPSG:32618"  # covers the corridor's mid-Atlantic stretch
MERC = "EPSG:3857"
GEO = "EPSG:4326"


def write_quad(path, bounds_4326, color, px=64, crs=UTM_18N):
    """A solid-colour quad covering `bounds_4326`, stored in a projected CRS
    the way real US Topo quads are (per-quad UTM)."""
    west, south, east, north = transform_bounds(GEO, crs, *bounds_4326)
    data = np.full((3, px, px), 0, dtype="uint8")
    data[0], data[1], data[2] = color
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=px,
        height=px,
        count=3,
        dtype="uint8",
        crs=crs,
        transform=from_bounds(west, south, east, north, px, px),
        nodata=0,
    ) as dst:
        dst.write(data)
    return path


def center_tile(bounds_4326, zoom):
    """The XYZ tile containing the centre of a lon/lat box."""
    cx = (bounds_4326[0] + bounds_4326[2]) / 2
    cy = (bounds_4326[1] + bounds_4326[3]) / 2
    merc = transform_bounds(GEO, MERC, cx, cy, cx, cy)
    x0, x1, y0, y1 = tile_range_for_bounds((merc[0], merc[1], merc[0], merc[1]), zoom)
    return zoom, x0, y0

# A ~2km box near Harpers Ferry - inside UTM 18N and the corridor's latitudes.
QUAD_BOX = (-77.75, 39.30, -77.73, 39.32)


def test_resampling_decimates_with_average_and_keeps_ink_with_cubic():
    assert resampling_for(NEAR_NATIVE_ZOOM) == Resampling.cubic
    assert resampling_for(NEAR_NATIVE_ZOOM + 1) == Resampling.cubic
    assert resampling_for(NEAR_NATIVE_ZOOM - 1) == Resampling.average
    assert resampling_for(6) == Resampling.average


def test_near_native_threshold_is_argued_from_real_arithmetic():
    # z14 at the corridor's latitudes is 1.6-2.0x the 2.032 m native
    # resolution; z13 is over 3x. If either drifts out of that range the
    # constant's justification is gone and this fails.
    z14_mid = meters_per_pixel(14, 40.0)
    assert 2.032 * 1.5 < z14_mid < 2.032 * 2.1
    assert meters_per_pixel(13, 40.0) > 2.032 * 3


def test_renders_a_covered_tile_from_a_native_utm_quad(tmp_path):
    quad = write_quad(tmp_path / "quad.tif", QUAD_BOX, (200, 120, 40))
    z, x, y = center_tile(QUAD_BOX, 15)

    with rasterio.open(quad) as src:
        arr = render_tile_from_quads(z, x, y, [src], tile_px=64)

    assert arr is not None and arr.shape == (3, 64, 64)
    covered = arr.any(axis=0)
    assert covered.any()
    # The covered pixels carry the quad's colour, not a resampling smear.
    assert abs(int(arr[0][covered].mean()) - 200) < 12


def test_returns_none_for_a_tile_nothing_covers(tmp_path):
    quad = write_quad(tmp_path / "quad.tif", QUAD_BOX, (200, 120, 40))
    # A tile well north of the quad.
    far = (-77.75, 44.0, -77.73, 44.02)
    z, x, y = center_tile(far, 15)

    with rasterio.open(quad) as src:
        assert render_tile_from_quads(z, x, y, [src], tile_px=64) is None


def test_composites_first_wins_where_quads_overlap(tmp_path):
    # Two quads covering the same box in different colours: the first listed
    # paints, the second only fills what the first left empty - the same
    # rule rasterio.merge gave the cell mosaics.
    a = write_quad(tmp_path / "a.tif", QUAD_BOX, (250, 10, 10))
    b = write_quad(tmp_path / "b.tif", QUAD_BOX, (10, 250, 10))
    z, x, y = center_tile(QUAD_BOX, 15)

    with rasterio.open(a) as src_a, rasterio.open(b) as src_b:
        arr = render_tile_from_quads(z, x, y, [src_a, src_b], tile_px=64)

    covered = arr.any(axis=0)
    assert int(arr[0][covered].mean()) > 200, "first quad should win the overlap"


def test_a_border_tile_composites_both_neighbouring_quads(tmp_path):
    # Two adjacent quads; a tile spanning their shared edge gets pixels from
    # each side. This is the seam case the fetch-by-tile-footprint rule
    # exists for.
    west_box = (-77.76, 39.30, -77.74, 39.32)
    east_box = (-77.74, 39.30, -77.72, 39.32)
    a = write_quad(tmp_path / "a.tif", west_box, (250, 10, 10))
    b = write_quad(tmp_path / "b.tif", east_box, (10, 250, 10))
    # A tile centred on the shared -77.74 meridian.
    z, x, y = center_tile((-77.75, 39.30, -77.73, 39.32), 15)

    with rasterio.open(a) as src_a, rasterio.open(b) as src_b:
        arr = render_tile_from_quads(z, x, y, [src_a, src_b], tile_px=64)

    reds = (arr[0] > 200) & (arr[1] < 60)
    greens = (arr[1] > 200) & (arr[0] < 60)
    assert reds.any() and greens.any(), "both sides of the seam should be painted"


def test_ownership_is_exclusive_across_adjacent_cells():
    # Every tile at a few zooms belongs to exactly one of two side-by-side
    # 1x1-degree cells - the fan-out's no-duplicate, no-orphan guarantee.
    west_cell = (-78.0, 39.0, -77.0, 40.0)
    east_cell = (-77.0, 39.0, -76.0, 40.0)
    both = box(*west_cell).union(box(*east_cell))
    from shapely.ops import transform as shp_transform
    from pyproj import Transformer

    to_merc = Transformer.from_crs(GEO, MERC, always_xy=True)
    both_merc = shp_transform(to_merc.transform, both)

    for zoom in (8, 10, 12):
        for x, y in tiles_intersecting_geom(both_merc, zoom):
            t_bounds = transform_bounds(MERC, GEO, *tile_bounds_merc(zoom, x, y))
            owners = sum(
                owns_tile(cell, t_bounds) for cell in (west_cell, east_cell)
            )
            cx = (t_bounds[0] + t_bounds[2]) / 2
            cy = (t_bounds[1] + t_bounds[3]) / 2
            inside = -78.0 <= cx < -76.0 and 39.0 <= cy < 40.0
            assert owners == (1 if inside else 0), (zoom, x, y)


def test_export_tiles_switches_to_the_near_trail_band_at_band_zoom():
    from shapely.ops import transform as shp_transform
    from pyproj import Transformer

    to_merc = Transformer.from_crs(GEO, MERC, always_xy=True)
    corridor = shp_transform(to_merc.transform, box(-78.0, 39.0, -77.0, 40.0))
    band = shp_transform(to_merc.transform, box(-77.6, 39.4, -77.4, 39.6))

    tiles = export_tiles(corridor, band, min_zoom=8, max_zoom=10, band_zoom=10)

    by_zoom = {z: [(x, y) for zz, x, y in tiles if zz == z] for z in (8, 9, 10)}
    # Below band_zoom the corridor decides; at band_zoom the band does, and
    # it is strictly smaller.
    assert set(by_zoom[9]) == set(tiles_intersecting_geom(corridor, 9))
    assert set(by_zoom[10]) == set(tiles_intersecting_geom(band, 10))
    assert len(by_zoom[10]) < len(tiles_intersecting_geom(corridor, 10))


def test_export_tiles_refuses_a_missing_band_rather_than_shipping_a_hole():
    from shapely.ops import transform as shp_transform
    from pyproj import Transformer

    to_merc = Transformer.from_crs(GEO, MERC, always_xy=True)
    corridor = shp_transform(to_merc.transform, box(-78.0, 39.0, -77.0, 40.0))

    with pytest.raises(ValueError, match="band"):
        export_tiles(corridor, None, min_zoom=8, max_zoom=10, band_zoom=10)


def test_tile_transform_spans_exactly_the_tile_bounds():
    z, x, y = 12, 1198, 1540
    west, south, east, north = tile_bounds_merc(z, x, y)
    t = tile_transform(z, x, y, tile_px=64)

    assert t.c == pytest.approx(west)
    assert t.f == pytest.approx(north)
    assert t.c + 64 * t.a == pytest.approx(east)
    assert t.f + 64 * t.e == pytest.approx(south)


def test_mask_outside_zeroes_ground_beyond_the_geometry(tmp_path):
    from pyproj import Transformer
    from shapely.ops import transform as shp_transform

    from lib.raster_tiles import mask_outside

    quad = write_quad(tmp_path / "quad.tif", QUAD_BOX, (200, 120, 40))
    z, x, y = center_tile(QUAD_BOX, 15)

    with rasterio.open(quad) as src:
        arr = render_tile_from_quads(z, x, y, [src], tile_px=64)
    before = int(arr.any(axis=0).sum())

    # A corridor covering only the western half of the quad box.
    to_merc = Transformer.from_crs(GEO, MERC, always_xy=True)
    west_half = shp_transform(
        to_merc.transform,
        box(QUAD_BOX[0], QUAD_BOX[1], (QUAD_BOX[0] + QUAD_BOX[2]) / 2, QUAD_BOX[3]),
    )
    masked = mask_outside(arr, west_half, z, x, y, tile_px=64)
    after = int(masked.any(axis=0).sum())

    assert 0 < after < before, "masking should remove some pixels and keep some"


def test_overview_resolution_serves_its_zooms_by_decimation_only():
    from lib.raster_tiles import NATIVE_MIN_ZOOM, OVERVIEW_MAX_ZOOM, OVERVIEW_RES_M

    # The coarsest overview-rendered zoom must still be at least 2x the
    # overview grid at the corridor's southernmost (finest-resolution)
    # latitude, or rendering from it upsamples.
    assert meters_per_pixel(OVERVIEW_MAX_ZOOM, 34.0) > 2 * OVERVIEW_RES_M
    assert NATIVE_MIN_ZOOM == OVERVIEW_MAX_ZOOM + 1
