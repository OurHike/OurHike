"""Tests for export_pmtiles.py - packaging the corridor-clipped background
raster into a PMTiles archive. Synthetic fixtures throughout (tiny GeoTIFFs
and a tiny corridor polygon), not the real 1,654-quad dataset - see
TESTING.md for why."""
import io
import json

import numpy as np
import pytest
import rasterio
from PIL import Image
from pmtiles.reader import MmapSource, all_tiles
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds
from shapely.geometry import box

import export_pmtiles
from export_pmtiles import find_export_tiles, render_tile, tile_bounds_merc

# A small square fixture footprint, in the same lon/lat neighborhood other
# synthetic fixtures in this suite use (see test_spike_raster_mosaic.py) -
# far from any real quad, so it can't collide with anything.
FIXTURE_BOUNDS = (-74.1, 41.0, -73.9, 41.2)  # west, south, east, north
FIXTURE_VALUE = 200


def _tile_covering(bounds_4326, z=6):
    """A single (z, x, y) tile guaranteed to fully contain bounds_4326 - at
    zoom 6 a tile is ~625km on a side, far bigger than any fixture used here,
    so the whole fixture always lands in exactly one tile."""
    merc_bounds = transform_bounds("EPSG:4326", "EPSG:3857", *bounds_4326)
    x0, x1, y0, y1 = export_pmtiles.tile_range_for_bounds(merc_bounds, z)
    assert (x0, y0) == (x1, y1), "fixture bounds span more than one tile - shrink the fixture or lower z"
    return z, x0, y0


def _write_cell(path, bounds=FIXTURE_BOUNDS, value=FIXTURE_VALUE, size=200):
    west, south, east, north = bounds
    transform = from_bounds(west, south, east, north, size, size)
    profile = {
        "driver": "GTiff", "height": size, "width": size, "count": 3,
        "dtype": "uint8", "crs": "EPSG:4326", "transform": transform,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((3, size, size), value, dtype="uint8"))


def _write_partial_cell(path, bounds=FIXTURE_BOUNDS, value=FIXTURE_VALUE, size=200):
    """A single cell that's half real data, half nodata (0) - matching the
    actual shape of production cells, which are corridor-clipped (real data
    only inside the corridor polygon, 0 elsewhere in the same file) rather
    than uniformly filled like _write_cell's fixture."""
    west, south, east, north = bounds
    transform = from_bounds(west, south, east, north, size, size)
    profile = {
        "driver": "GTiff", "height": size, "width": size, "count": 3,
        "dtype": "uint8", "crs": "EPSG:4326", "transform": transform,
    }
    arr = np.zeros((3, size, size), dtype="uint8")
    arr[:, :, : size // 2] = value  # west half real, east half nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr)


def _write_corridor(path, bounds):
    west, south, east, north = bounds
    fc = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
            },
        }],
    }
    path.write_text(json.dumps(fc))


def test_find_export_tiles_returns_exactly_one_tile_for_a_corridor_confined_to_it(monkeypatch):
    monkeypatch.setattr(export_pmtiles, "MIN_ZOOM", 6)
    monkeypatch.setattr(export_pmtiles, "MAX_ZOOM", 6)
    corridor_merc = box(*tile_bounds_merc(6, 17, 24)).buffer(-1)  # shrunk well inside one tile, touching no neighbor
    assert find_export_tiles(corridor_merc) == [(6, 17, 24)]


def test_find_export_tiles_returns_both_tiles_for_a_corridor_spanning_two(monkeypatch):
    monkeypatch.setattr(export_pmtiles, "MIN_ZOOM", 6)
    monkeypatch.setattr(export_pmtiles, "MAX_ZOOM", 6)
    left = box(*tile_bounds_merc(6, 17, 24))
    right = box(*tile_bounds_merc(6, 18, 24))
    spanning_corridor = left.union(right).buffer(-1)
    assert sorted(find_export_tiles(spanning_corridor)) == [(6, 17, 24), (6, 18, 24)]


def test_render_tile_skips_a_cell_that_is_entirely_nodata(tmp_path):
    cell_path = tmp_path / "tile_000.tif"
    _write_cell(cell_path, value=0)
    with rasterio.open(cell_path) as src:
        cell_index = [(cell_path, src.bounds)]

    z, x, y = _tile_covering(FIXTURE_BOUNDS)
    arr, matching = render_tile(z, x, y, cell_index)

    assert arr is None
    assert matching == [cell_path]  # the cell was found (bbox overlap) - it's genuinely empty, not "missing"


def test_render_tile_returns_real_data_for_a_covered_cell(tmp_path):
    cell_path = tmp_path / "tile_000.tif"
    _write_cell(cell_path, value=FIXTURE_VALUE)
    with rasterio.open(cell_path) as src:
        cell_index = [(cell_path, src.bounds)]

    z, x, y = _tile_covering(FIXTURE_BOUNDS)
    arr, matching = render_tile(z, x, y, cell_index)

    assert matching == [cell_path]
    assert arr is not None
    assert arr.shape == (3, export_pmtiles.TILE_PX, export_pmtiles.TILE_PX)
    # The source is a uniform-value raster, so bilinear resampling must
    # reproduce that exact value at every interior pixel - interpolating
    # between four identical source pixels is exact, not approximate. Only
    # pixels right at the fixture's edge blend with the surrounding empty
    # tile, so assert exactness where it's actually guaranteed rather than a
    # fuzzy average that would mask a systematic resampling bias.
    assert np.array_equal(arr[0], arr[1]) and np.array_equal(arr[1], arr[2])
    assert np.any(arr[0] == FIXTURE_VALUE)


def test_render_tile_combines_two_adjacent_cells_without_one_overwriting_the_other(tmp_path):
    # Two cells that exactly tile FIXTURE_BOUNDS side by side (west/east
    # halves, sharing the -74.0 meridian) - the common case at low zoom.
    # render_tile used to call reproject() once per matching cell into a
    # shared array; that silently let whichever cell ran last wipe out every
    # earlier cell's pixels (each reproject() call resets the whole
    # destination to nodata first), rather than each cell only filling its
    # own footprint. Fixed by switching to rasterio.merge.merge() (same as
    # spike_raster_mosaic.py) - this test guards against that regressing.
    west_bounds, east_bounds = (-74.1, 41.0, -74.0, 41.2), (-74.0, 41.0, -73.9, 41.2)
    assert (west_bounds[0], west_bounds[2], east_bounds[0], east_bounds[2]) == (
        FIXTURE_BOUNDS[0], -74.0, -74.0, FIXTURE_BOUNDS[2],
    )  # sanity: the two halves really do add up to FIXTURE_BOUNDS with no gap/overlap

    west_path, east_path = tmp_path / "tile_000.tif", tmp_path / "tile_001.tif"
    _write_cell(west_path, bounds=west_bounds, value=100)
    _write_cell(east_path, bounds=east_bounds, value=200)
    with rasterio.open(west_path) as src:
        west_rio_bounds = src.bounds
    with rasterio.open(east_path) as src:
        east_rio_bounds = src.bounds
    cell_index = [(west_path, west_rio_bounds), (east_path, east_rio_bounds)]

    z, x, y = _tile_covering(FIXTURE_BOUNDS)
    arr, matching = render_tile(z, x, y, cell_index)

    assert sorted(matching) == sorted([west_path, east_path])
    assert arr is not None

    band = arr[0]
    west_cols = np.where(band == 100)[1]  # exact - bilinear of a uniform source is exact away from edges
    east_cols = np.where(band == 200)[1]
    assert west_cols.size > 0, "the west cell's value never appears in the output - its data was lost"
    assert east_cols.size > 0, "the east cell's value never appears in the output - its data was lost"
    # The west cell is geographically west of the east cell, so its pixels
    # must land at lower column indices (column increases eastward). If
    # either cell's reproject() call had overwritten the other's pixels
    # instead of only writing its own footprint, this ordering would break
    # or one side would be missing entirely (caught by the asserts above).
    assert west_cols.mean() < east_cols.mean()


def test_render_tile_combines_a_four_cell_grid_without_losing_any_quadrant(tmp_path):
    # Four cells meeting at a single point (a "+" intersection) - the two-
    # cell test above only proves a left/right pair merges correctly; real
    # low-zoom corridor tiles can span cells in both x AND y simultaneously,
    # which a merge bug could get right for one axis and still wrong for
    # the other (e.g. if compositing happened row-by-row instead of over
    # the true 2D footprint).
    # Quadrants are derived from a known tile's own bounds (same z/x/y used
    # by the tests above), split at its exact center - not from hand-picked
    # lon/lat values. That sidesteps two failure modes hit while writing
    # this test: an arbitrary 0.4-degree box turned out to straddle a tile
    # boundary at both z=6 and z=3 (tile grid lines don't align with "nice"
    # lon/lat numbers), and z=0's whole-world tile was too coarse for a
    # small fixture to survive resampling at all (each pixel covers ~78km).
    # Using the entire real tile guarantees both containment and enough
    # resolution (each quadrant is ~256x256 destination pixels).
    z, x, y = 6, 17, 24
    tile_west, tile_south, tile_east, tile_north = transform_bounds("EPSG:3857", "EPSG:4326", *tile_bounds_merc(z, x, y))
    mid_lon, mid_lat = (tile_west + tile_east) / 2, (tile_south + tile_north) / 2
    quadrants = {
        "nw": ((tile_west, mid_lat, mid_lon, tile_north), 100),
        "ne": ((mid_lon, mid_lat, tile_east, tile_north), 150),
        "sw": ((tile_west, tile_south, mid_lon, mid_lat), 200),
        "se": ((mid_lon, tile_south, tile_east, mid_lat), 250),
    }
    cell_index = []
    for name, (bounds, value) in quadrants.items():
        path = tmp_path / f"tile_{name}.tif"
        _write_cell(path, bounds=bounds, value=value)
        with rasterio.open(path) as src:
            cell_index.append((path, src.bounds))

    arr, matching = render_tile(z, x, y, cell_index)

    assert sorted(matching) == sorted(p for p, _ in cell_index)
    assert arr is not None
    band = arr[0]

    rows, cols = {}, {}
    for name, (_, value) in quadrants.items():
        r, c = np.where(band == value)
        assert r.size > 0, f"the {name} quadrant's value never appears in the output - its data was lost"
        rows[name], cols[name] = r, c

    # Row increases southward, column increases eastward (standard raster
    # convention) - so the north pair must sit at lower rows than the south
    # pair, and the west pair at lower columns than the east pair, no matter
    # which order the four cells were merged in.
    north_rows = np.concatenate([rows["nw"], rows["ne"]])
    south_rows = np.concatenate([rows["sw"], rows["se"]])
    assert north_rows.mean() < south_rows.mean()

    west_cols = np.concatenate([cols["nw"], cols["sw"]])
    east_cols = np.concatenate([cols["ne"], cols["se"]])
    assert west_cols.mean() < east_cols.mean()


def test_render_tile_preserves_internal_nodata_boundary_within_a_single_cell(tmp_path):
    # A single cell that's half real data, half nodata (0) - the actual
    # shape of production cells (corridor-clipped: real data only inside the
    # corridor polygon, 0 elsewhere in the same file), unlike every other
    # fixture in this file, which is uniformly one value or the other. This
    # exercises merge()/reproject on ONE source with an internal nodata
    # boundary, not multiple sources - a distinct code path from the
    # adjacent-cells tests above.
    full_path, partial_path = tmp_path / "full.tif", tmp_path / "partial.tif"
    _write_cell(full_path, value=FIXTURE_VALUE)  # entirely real, for comparison
    _write_partial_cell(partial_path, value=FIXTURE_VALUE)  # west half real, east half nodata

    z, x, y = _tile_covering(FIXTURE_BOUNDS)

    with rasterio.open(full_path) as src:
        full_arr, _ = render_tile(z, x, y, [(full_path, src.bounds)])
    with rasterio.open(partial_path) as src:
        partial_arr, matching = render_tile(z, x, y, [(partial_path, src.bounds)])

    assert matching == [partial_path]
    assert partial_arr is not None
    full_real_count = int(np.count_nonzero(full_arr[0] == FIXTURE_VALUE))
    partial_real_count = int(np.count_nonzero(partial_arr[0] == FIXTURE_VALUE))

    # The real half must still come through...
    assert partial_real_count > 0, "the cell's real half never appears in the output"
    # ...but strictly less of it than when the whole cell is real - if the
    # internal nodata half were incorrectly treated as real data (e.g. an
    # uninitialized nodata value, or nodata masking not surviving the warp),
    # this would equal full_real_count instead of being meaningfully smaller.
    assert partial_real_count < full_real_count


def test_end_to_end_export_round_trips_through_a_real_pmtiles_file(tmp_path, monkeypatch):
    cells_dir = tmp_path / "cells"
    cells_dir.mkdir()
    _write_cell(cells_dir / "tile_000.tif")
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, FIXTURE_BOUNDS)
    out_path = tmp_path / "background.pmtiles"

    monkeypatch.setattr(export_pmtiles, "CORRIDOR_PATH", corridor_path)
    monkeypatch.setattr(export_pmtiles, "CELLS_DIR", cells_dir)
    monkeypatch.setattr(export_pmtiles, "OUT_PATH", out_path)
    monkeypatch.setattr(export_pmtiles, "MIN_ZOOM", 6)
    monkeypatch.setattr(export_pmtiles, "MAX_ZOOM", 6)

    export_pmtiles.main()

    assert out_path.exists()
    with open(out_path, "rb") as f:
        tiles = list(all_tiles(MmapSource(f)))

    assert len(tiles) == 1
    (z, x, y), data = tiles[0]
    assert z == 6
    assert (z, x, y) == _tile_covering(FIXTURE_BOUNDS)

    img = np.array(Image.open(io.BytesIO(data)))
    assert img.shape[:2] == (export_pmtiles.TILE_PX, export_pmtiles.TILE_PX)
    # Same reasoning as test_render_tile_returns_real_data_for_a_covered_cell,
    # plus extra tolerance here for WebP's lossy quantization near the sharp
    # edge between the fixture's real data and the surrounding empty area.
    assert np.any(img > 10)
    assert img[img > 10].mean() == pytest.approx(FIXTURE_VALUE, abs=30)
