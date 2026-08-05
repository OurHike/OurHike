"""Tests for extract_package.py - cutting a region-shaped package out of a
bigger PMTiles archive. Synthetic archives throughout, with each tile's
payload encoding its own address, so byte-identity assertions are meaningful
rather than vacuous."""

import argparse
import json

import pytest
from pmtiles.reader import MmapSource, all_tiles
from pmtiles.tile import Compression, TileType, deserialize_header, zxy_to_tileid
from pmtiles.writer import write
from shapely.geometry import box, mapping

import extract_package
from extract_package import extract, load_region, tiles_intersecting, to_mercator

# Web Mercator covers lat ~[-85.05, 85.05]; this box sits safely inside the
# world's northeast quadrant, so its tile pyramid is known by hand: z0 (0,0),
# z1 (1,0), and downward through (1,0)'s children.
NE_QUADRANT_BOX = box(30.0, 30.0, 80.0, 70.0)


def payload(z, x, y):
    return f"{z}/{x}/{y}".encode()


def build_source(path, max_zoom=2, tile_type=TileType.MVT, compression=Compression.GZIP):
    """Every tile of every zoom up to max_zoom - a fully-populated little
    world, so what the extraction keeps and drops is decided only by the
    region geometry under test."""
    header = {
        "tile_type": tile_type,
        "tile_compression": compression,
        "min_lon_e7": int(-180 * 1e7),
        "min_lat_e7": int(-85 * 1e7),
        "max_lon_e7": int(180 * 1e7),
        "max_lat_e7": int(85 * 1e7),
        "center_lon_e7": 0,
        "center_lat_e7": 0,
        "center_zoom": 0,
    }
    with write(str(path)) as writer:
        for z in range(max_zoom + 1):
            for x in range(2**z):
                for y in range(2**z):
                    writer.write_tile(zxy_to_tileid(z, x, y), payload(z, x, y))
        writer.finalize(header, {"name": "source", "vector_layers": ["kept-through-extraction"]})
    return path


def read_all(path):
    with open(path, "rb") as f:
        source = MmapSource(f)
        return {zxy: data for zxy, data in all_tiles(source)}


def test_tiles_intersecting_descends_the_quadtree():
    # A region strictly inside z2 tile (3, 0): each zoom names exactly the
    # ancestors and descendants of that tile, nothing else.
    z2_bounds = extract_package.tile_bounds_merc(2, 3, 0)
    minx, miny, maxx, maxy = z2_bounds
    pad_x, pad_y = (maxx - minx) * 0.25, (maxy - miny) * 0.25
    region = box(minx + pad_x, miny + pad_y, maxx - pad_x, maxy - pad_y)

    hits = tiles_intersecting(region, 0, 3)

    assert hits[0] == [(0, 0)]
    assert hits[1] == [(1, 0)]
    assert hits[2] == [(3, 0)]
    assert sorted(hits[3]) == [(6, 0), (6, 1), (7, 0), (7, 1)]


def test_load_region_accepts_geometry_feature_and_collection(tmp_path):
    geom = mapping(NE_QUADRANT_BOX)
    for i, doc in enumerate(
        [
            geom,
            {"type": "Feature", "properties": {}, "geometry": geom},
            {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": geom}]},
        ]
    ):
        path = tmp_path / f"region{i}.geojson"
        path.write_text(json.dumps(doc))
        assert load_region(path).equals(NE_QUADRANT_BOX)


def test_extract_keeps_exactly_the_region_tiles_byte_for_byte(tmp_path):
    # context_zoom=None throughout the region-walk tests: the synthetic world
    # tops out at z2, inside the default context window, so the default would
    # keep every tile and these tests would stop exercising the region cut.
    # Context behaviour has its own tests below.
    source = build_source(tmp_path / "source.pmtiles")
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    out = tmp_path / "package.pmtiles"

    extract(source, region_path, out, min_zoom=None, max_zoom=None, name="AT package", context_zoom=None)

    expected = tiles_intersecting(to_mercator(NE_QUADRANT_BOX), 0, 2)
    expected_zxy = {(z, x, y) for z, tiles in expected.items() for x, y in tiles}
    got = read_all(out)
    assert set(got) == expected_zxy
    # The northeast quadrant must be in and the southwest out - the by-hand
    # check that `expected` itself wasn't computed wrong.
    assert (1, 1, 0) in got and (1, 0, 1) not in got
    for (z, x, y), data in got.items():
        assert data == payload(z, x, y), "tile bytes must be copied verbatim"


def test_extract_carries_format_and_rewrites_bounds(tmp_path):
    source = build_source(tmp_path / "source.pmtiles", tile_type=TileType.WEBP, compression=Compression.NONE)
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    out = tmp_path / "package.pmtiles"

    extract(source, region_path, out, min_zoom=None, max_zoom=None, name="AT package", context_zoom=None)

    with open(out, "rb") as f:
        header = deserialize_header(f.read(127))
    assert header["tile_type"] == TileType.WEBP
    assert header["tile_compression"] == Compression.NONE
    assert header["min_lon_e7"] == int(30.0 * 1e7)
    assert header["max_lat_e7"] == int(70.0 * 1e7)


def test_extract_respects_an_explicit_zoom_window(tmp_path):
    source = build_source(tmp_path / "source.pmtiles")
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    out = tmp_path / "package.pmtiles"

    extract(source, region_path, out, min_zoom=1, max_zoom=1, name="AT package", context_zoom=None)

    assert set(read_all(out)) == {(1, 1, 0)}


def test_extract_refuses_an_empty_intersection(tmp_path):
    # A source holding only the world's northwest z1 tile, cut with a region
    # in the southeast: nothing matches, and shipping an empty package as if
    # it were a map is exactly what must not happen.
    source = tmp_path / "source.pmtiles"
    header = {
        "tile_type": TileType.MVT,
        "tile_compression": Compression.GZIP,
        "min_lon_e7": 0,
        "min_lat_e7": 0,
        "max_lon_e7": 0,
        "max_lat_e7": 0,
        "center_lon_e7": 0,
        "center_lat_e7": 0,
        "center_zoom": 1,
    }
    with write(str(source)) as writer:
        writer.write_tile(zxy_to_tileid(1, 0, 0), b"nw")
        writer.finalize(header, {"name": "source"})

    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(box(30.0, -70.0, 80.0, -30.0))))

    with pytest.raises(SystemExit, match="no tiles"):
        extract(source, region_path, tmp_path / "package.pmtiles", min_zoom=1, max_zoom=1, name="empty", context_zoom=None)


def test_context_zoom_keeps_the_sources_whole_low_zoom_footprint(tmp_path):
    # Issue #189's beyond-the-package ground: through the context zoom the
    # package inherits every source tile, so panning out offline shows the
    # build's surroundings rather than blank paper. Above it, the region
    # still decides.
    source = build_source(tmp_path / "source.pmtiles")
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    out = tmp_path / "package.pmtiles"

    extract(source, region_path, out, min_zoom=None, max_zoom=None, name="AT package", context_zoom=1)

    got = read_all(out)
    # All of z0-z1, the region-misses included - this is the southwest tile
    # the pure region cut proves it drops.
    assert (1, 0, 1) in got
    assert {(z, x, y) for (z, x, y) in got if z <= 1} == {(0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 0, 1), (1, 1, 1)}
    # z2 is still the region's: the northeast stays, the southwest is out.
    assert (2, 2, 0) in got and (2, 0, 3) not in got
    for (z, x, y), data in got.items():
        assert data == payload(z, x, y), "context tiles are copied verbatim too"


def test_context_zoom_is_clamped_to_the_archives_own_ceiling(tmp_path):
    # The default (9) against a z2 source must not error or over-reach - the
    # region walk simply has nothing left to answer for.
    source = build_source(tmp_path / "source.pmtiles")
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    out = tmp_path / "package.pmtiles"

    extract(source, region_path, out, min_zoom=None, max_zoom=None, name="AT package")

    assert len(read_all(out)) == 1 + 4 + 16  # the whole synthetic world


def test_context_tiles_do_not_mask_an_empty_region_intersection(tmp_path):
    # Context tiles arrive for ANY region, so the wrong-region guard has to
    # ask about region tiles specifically - otherwise a typo'd region file
    # ships a low-zoom-only package that looks like a map until you zoom in.
    # A sparse source: the world tile plus the northwest z1 tile, cut with a
    # southeast region - context (z0) is served, the region (z1) matches
    # nothing the source holds.
    region_path = tmp_path / "region.geojson"
    source = tmp_path / "sparse.pmtiles"
    header = {
        "tile_type": TileType.MVT,
        "tile_compression": Compression.GZIP,
        "min_lon_e7": 0,
        "min_lat_e7": 0,
        "max_lon_e7": 0,
        "max_lat_e7": 0,
        "center_lon_e7": 0,
        "center_lat_e7": 0,
        "center_zoom": 0,
    }
    with write(str(source)) as writer:
        writer.write_tile(zxy_to_tileid(0, 0, 0), b"world")
        writer.write_tile(zxy_to_tileid(1, 0, 0), b"nw")
        writer.finalize(header, {"name": "source"})
    region_path.write_text(json.dumps(mapping(box(30.0, -70.0, 80.0, -30.0))))

    with pytest.raises(SystemExit, match="no tiles"):
        extract(source, region_path, tmp_path / "package.pmtiles", min_zoom=0, max_zoom=1, name="empty", context_zoom=0)


def test_main_extracts_and_reports(tmp_path, capsys):
    source = build_source(tmp_path / "source.pmtiles")
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    out = tmp_path / "package.pmtiles"

    extract_package.main(
        argparse.Namespace(
            source=source,
            region=region_path,
            out=out,
            min_zoom=None,
            max_zoom=None,
            name="AT package",
            context_zoom=extract_package.DEFAULT_CONTEXT_ZOOM,
        )
    )

    assert out.exists()
    assert "package.pmtiles" in capsys.readouterr().out


def test_main_treats_a_negative_context_zoom_as_disabled(tmp_path):
    source = build_source(tmp_path / "source.pmtiles")
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    out = tmp_path / "package.pmtiles"

    extract_package.main(
        argparse.Namespace(
            source=source, region=region_path, out=out, min_zoom=None, max_zoom=None, name="AT package", context_zoom=-1
        )
    )

    # Region-only: the pure cut's own test proves this set, spot-check here.
    got = read_all(out)
    assert (1, 1, 0) in got and (1, 0, 1) not in got
