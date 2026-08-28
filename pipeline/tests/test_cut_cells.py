"""Tests for cut_cells.py - the 1-degree coverage cells (#1175).

Synthetic everything, in the shape the stretch cut's own suite used (#556,
removed with it): the
source archive is built in test code with each tile's payload encoding its
own address, the test_extract_package.py idiom that makes byte-identity
assertions meaningful. No centerline and no markers - the mile axis is the
machinery this cut deletes.

The fixture geography is chosen so the cell arithmetic can be checked by
hand. A source declaring bounds (-74.6, 40.2) to (-73.4, 40.8) covers
exactly two whole-degree cells - n40w075 spanning lon -75..-74 and n40w074
spanning -74..-73 - with the seam at lon -74.0.

Tiles are z15 (about 1.1 km across at this latitude) so that a tile is
comfortably smaller than the 3 km seam margin. At a low zoom a tile is wider
than the margin and every assertion about seams goes mushy.
"""

import json

import pytest
from pmtiles.reader import MmapSource, all_tiles
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write
from pyproj import Transformer

import cut_cells
from lib.corridor_grid import graticule_cells
from lib.tiling import tile_range_for_bounds

SOURCE_BOUNDS = (-74.6, 40.2, -73.4, 40.8)
SEAM_LON = -74.0


def _merc(lon, lat):
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    return transformer.transform(lon, lat)


def _tile_at(lon, lat, z=15):
    """The z/x/y tile containing a lon/lat point."""
    x_merc, y_merc = _merc(lon, lat)
    x0, _x1, y0, _y1 = tile_range_for_bounds((x_merc, y_merc, x_merc, y_merc), z)
    return z, x0, y0


def payload(z, x, y):
    return f"{z}/{x}/{y}".encode()


def _build_source(path, tiles, bounds=SOURCE_BOUNDS):
    west, south, east, north = bounds
    header = {
        "tile_type": TileType.MVT,
        "tile_compression": Compression.GZIP,
        "min_lon_e7": int(west * 1e7),
        "min_lat_e7": int(south * 1e7),
        "max_lon_e7": int(east * 1e7),
        "max_lat_e7": int(north * 1e7),
        "center_lon_e7": int((west + east) / 2 * 1e7),
        "center_lat_e7": int((south + north) / 2 * 1e7),
        "center_zoom": 0,
    }
    with write(str(path)) as writer:
        for z, x, y in sorted(set(tiles), key=lambda t: zxy_to_tileid(*t)):
            writer.write_tile(zxy_to_tileid(z, x, y), payload(z, x, y))
        writer.finalize(header, {"name": "source", "vector_layers": ["kept"]})
    return path


def read_all(path):
    with open(path, "rb") as f:
        return {zxy: data for zxy, data in all_tiles(MmapSource(f))}


def _cut(tmp_path, tiles, bounds=SOURCE_BOUNDS, **kwargs):
    source = _build_source(tmp_path / "source.pmtiles", tiles, bounds)
    out_dir = tmp_path / "out"
    manifest = cut_cells.cut_cells(
        source,
        "at_basemap",
        out_dir=out_dir,
        margin_km=kwargs.pop("margin_km", 3.0),
        **kwargs,
    )
    return out_dir, manifest


def _both_cells_tiles():
    """One tile well inside each of the two fixture cells, far enough from
    the seam that a 3 km margin does not reach it."""
    return [_tile_at(-74.5, 40.5), _tile_at(-73.5, 40.5)]


# ---------------------------------------------------------------- the grid


def test_graticule_cells_begin_on_whole_degrees():
    """The property the whole scheme rests on: two organizations whose
    sheets cover the same ground must get the same cells, which only holds
    if cells are anchored to the graticule rather than to a bounding box."""
    cells = graticule_cells(SOURCE_BOUNDS)
    assert cells == [(-75.0, 40.0, -74.0, 41.0), (-74.0, 40.0, -73.0, 41.0)]
    for west, south, east, north in cells:
        assert west == int(west) and south == int(south)
        assert east - west == 1.0 and north - south == 1.0


def test_a_second_sheet_over_the_same_ground_gets_the_same_cells():
    """The offset that would reintroduce #193's duplication. A different
    bounding box over overlapping ground must not produce a different grid."""
    at = graticule_cells((-74.6, 40.2, -73.4, 40.8))
    other_org = graticule_cells((-74.37, 40.11, -73.62, 40.93))
    assert set(other_org) <= set(at)


def test_cell_names_say_which_ground_they_hold():
    assert cut_cells.cell_name(-75.0, 40.0) == "n40w075"
    assert cut_cells.cell_name(-74.0, 40.0) == "n40w074"
    # Both hemispheres, because the naming is permanent once published.
    assert cut_cells.cell_name(7.0, -34.0) == "s34e007"


# ---------------------------------------------------------------- the cut


def test_every_tile_lands_in_the_cell_its_bounds_say(tmp_path):
    out_dir, _manifest = _cut(tmp_path, _both_cells_tiles(), margin_km=0.0)

    west_tile, east_tile = _both_cells_tiles()
    assert set(read_all(out_dir / "at_basemap_cell_n40w075.pmtiles")) == {west_tile}
    assert set(read_all(out_dir / "at_basemap_cell_n40w074.pmtiles")) == {east_tile}


def test_a_tile_near_the_seam_rides_in_both_neighbours(tmp_path):
    """The margin is the data-side share of #552's non-negotiable: a wrong
    answer must not cost a hiker map where they are walking."""
    near_seam = _tile_at(SEAM_LON - 0.01, 40.5)
    tiles = [*_both_cells_tiles(), near_seam]
    out_dir, _manifest = _cut(tmp_path, tiles, margin_km=3.0)

    assert near_seam in read_all(out_dir / "at_basemap_cell_n40w075.pmtiles")
    assert near_seam in read_all(out_dir / "at_basemap_cell_n40w074.pmtiles")


def test_without_a_margin_the_same_tile_rides_in_one(tmp_path):
    """Proves the previous test measures the margin rather than a tile that
    straddles the boundary on its own."""
    near_seam = _tile_at(SEAM_LON - 0.01, 40.5)
    tiles = [*_both_cells_tiles(), near_seam]
    out_dir, _manifest = _cut(tmp_path, tiles, margin_km=0.0)

    assert near_seam in read_all(out_dir / "at_basemap_cell_n40w075.pmtiles")
    assert near_seam not in read_all(out_dir / "at_basemap_cell_n40w074.pmtiles")


def test_context_tiles_publish_once_and_not_into_every_cell(tmp_path):
    """#193 measured context at 6.3 MB duplicated per package by
    construction. At 51 cells that is the saving the whole split exists for."""
    context = [(5, 9, 12), (9, 150, 192)]
    tiles = [*_both_cells_tiles(), *context]
    out_dir, manifest = _cut(tmp_path, tiles, context_zoom=9)

    assert set(read_all(out_dir / "at_basemap_context.pmtiles")) == set(context)
    for name in ("n40w075", "n40w074"):
        cut = read_all(out_dir / f"at_basemap_cell_{name}.pmtiles")
        assert not set(cut) & set(context)
    assert manifest["stats"]["context_tiles"] == len(context)


def test_a_cell_with_no_tiles_is_refused(tmp_path):
    """An empty cell means the archive's declared bounds and its actual
    tiles disagree. Publishing it would 404 nothing and cover nothing."""
    only_west = [_tile_at(-74.5, 40.5)]
    with pytest.raises(SystemExit, match="n40w074"):
        _cut(tmp_path, only_west, margin_km=0.0)


def test_tile_bytes_are_copied_verbatim(tmp_path):
    out_dir, _manifest = _cut(tmp_path, _both_cells_tiles(), margin_km=0.0)
    cut = read_all(out_dir / "at_basemap_cell_n40w075.pmtiles")
    for (z, x, y), data in cut.items():
        assert data == payload(z, x, y)


def test_every_cut_carries_the_sources_format_and_layer_catalogue(tmp_path):
    """MapLibre reads the layer catalogue out of the metadata, so a cell
    without one is an archive a style cannot draw from - and the bytes are
    copied rather than re-encoded, so the format facts must carry too."""
    out_dir, _manifest = _cut(tmp_path, _both_cells_tiles(), margin_km=0.0)

    for name in ("n40w075", "n40w074"):
        with open(out_dir / f"at_basemap_cell_{name}.pmtiles", "rb") as f:
            source = MmapSource(f)
            from pmtiles.reader import Reader

            reader = Reader(source)
            assert reader.metadata()["vector_layers"] == ["kept"]
            assert reader.header()["tile_type"] == TileType.MVT
            assert reader.header()["tile_compression"] == Compression.GZIP


# ------------------------------------------------------- index and manifest


def test_the_index_lists_the_cells_that_were_built(tmp_path):
    """Which cells the grid DEFINES is computable on the phone; which were
    built and published is not, and that difference is what the index is."""
    out_dir, _manifest = _cut(tmp_path, _both_cells_tiles(), margin_km=0.0)
    index = json.loads((out_dir / "at_basemap_cells.json").read_text())

    assert index["cell_degrees"] == 1.0
    assert [c["name"] for c in index["cells"]] == ["n40w075", "n40w074"]
    assert index["cells"][0]["key"] == "at_basemap_cell_n40w075.pmtiles"
    assert index["cells"][0]["bounds"] == [-75.0, 40.0, -74.0, 41.0]


def test_the_index_states_core_bounds_not_the_margin(tmp_path):
    """The margin is generosity in the bytes, never a promise in the
    metadata - or something downstream treats a margin as coverage."""
    out_dir, _manifest = _cut(tmp_path, _both_cells_tiles(), margin_km=25.0)
    index = json.loads((out_dir / "at_basemap_cells.json").read_text())

    assert index["seam_margin_km"] == 25.0
    assert index["cells"][0]["bounds"] == [-75.0, 40.0, -74.0, 41.0]


def test_the_manifest_prices_and_hashes_every_artifact(tmp_path):
    out_dir, manifest = _cut(tmp_path, _both_cells_tiles(), margin_km=0.0)

    expected = {
        "at_basemap_cells.json",
        "at_basemap_cell_n40w075.pmtiles",
        "at_basemap_cell_n40w074.pmtiles",
    }
    assert expected <= set(manifest["artifacts"])
    for name, entry in manifest["artifacts"].items():
        assert len(entry["sha256"]) == 64
        assert entry["size_bytes"] == (out_dir / name).stat().st_size


def test_the_manifest_reports_what_the_margin_cost(tmp_path):
    """#193's duplication figure gets its successor measured on every run
    rather than assumed away."""
    near_seam = _tile_at(SEAM_LON - 0.01, 40.5)
    tiles = [*_both_cells_tiles(), near_seam]
    _out_dir, manifest = _cut(tmp_path, tiles, margin_km=3.0)

    stats = manifest["stats"]
    assert stats["distinct_cell_tiles"] == 3
    assert stats["cell_tile_placements"] == 4
    assert stats["seam_duplication_pct"] == pytest.approx(33.33, abs=0.01)
    assert stats["cells"] == 2
