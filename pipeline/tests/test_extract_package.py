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
from shapely.prepared import prep

import extract_package
from extract_package import choose_seam_winner, extract, load_region, tiles_intersecting, to_mercator

# Web Mercator covers lat ~[-85.05, 85.05]; this box sits safely inside the
# world's northeast quadrant, so its tile pyramid is known by hand: z0 (0,0),
# z1 (1,0), and downward through (1,0)'s children.
NE_QUADRANT_BOX = box(30.0, 30.0, 80.0, 70.0)

# Wide enough to intersect every z1 tile (all four quadrants), for the
# multi-source tests below where the point is that more than one source
# claims the SAME tile - the region driving the cut itself is not what is
# under test there.
WORLD_BOX = box(-179.0, -84.9, 179.0, 84.9)

# choose_seam_winner asks whether a tile's CENTRE sits inside a source's
# region - a stricter question than tiles_intersecting's bounding-box
# overlap, which NE_QUADRANT_BOX above answers (it overlaps z1 tile (1, 1,
# 0) without containing that tile's centre: z1 tile bounds span a whole
# hemisphere, (30, 30, 80, 70) does not reach the centre at lon 90). This
# box is built to actually contain it (z1 tile (1, 1, 0)'s centre sits at
# lon 90, lat ~66.5, computed via tile_center_merc and an inverse
# transform), and nowhere near the other three z1 tiles' centres (lon +-90,
# lat +-66.5) - so it can stand in for "this shard's own build region" in
# the seam-tile tests below.
TILE_1_1_0_CENTER_BOX = box(45.0, 40.0, 135.0, 80.0)


def payload(z, x, y):
    return f"{z}/{x}/{y}".encode()


def build_source(path, max_zoom=2, tile_type=TileType.MVT, compression=Compression.GZIP, payload_fn=payload, name="source"):
    """Every tile of every zoom up to max_zoom - a fully-populated little
    world, so what the extraction keeps and drops is decided only by the
    region geometry under test. `payload_fn` lets the multi-source tests
    build two archives whose tiles are distinguishable by content (#248)."""
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
                    writer.write_tile(zxy_to_tileid(z, x, y), payload_fn(z, x, y))
        writer.finalize(header, {"name": name, "vector_layers": ["kept-through-extraction"]})
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

    extract([source], region_path, out, min_zoom=None, max_zoom=None, name="AT package", context_zoom=None)

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

    extract([source], region_path, out, min_zoom=None, max_zoom=None, name="AT package", context_zoom=None)

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

    extract([source], region_path, out, min_zoom=1, max_zoom=1, name="AT package", context_zoom=None)

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
        extract([source], region_path, tmp_path / "package.pmtiles", min_zoom=1, max_zoom=1, name="empty", context_zoom=None)


def test_a_refused_extract_leaves_no_package_behind_and_spares_the_old_one(tmp_path):
    """#659: the wrong-region guard used to raise inside `with write(out_path)`,
    which had already truncated out_path - so a refused cut destroyed the
    existing good package AND left a 0-byte file at its name, looking real.
    The write now goes to a temp name and only renames over out_path after
    finalize; a refusal must leave the previous bytes untouched and no temp
    debris."""
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

    out_path = tmp_path / "package.pmtiles"
    good_bytes = b"the previous good package, which a refused cut must not destroy"
    out_path.write_bytes(good_bytes)

    with pytest.raises(SystemExit, match="no tiles"):
        extract([source], region_path, out_path, min_zoom=1, max_zoom=1, name="empty", context_zoom=None)

    assert out_path.read_bytes() == good_bytes
    assert not list(tmp_path.glob("*.tmp")), "the refused write must clean up its temp file"


def test_context_zoom_keeps_the_sources_whole_low_zoom_footprint(tmp_path):
    # Issue #189's beyond-the-package ground: through the context zoom the
    # package inherits every source tile, so panning out offline shows the
    # build's surroundings rather than blank paper. Above it, the region
    # still decides.
    source = build_source(tmp_path / "source.pmtiles")
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    out = tmp_path / "package.pmtiles"

    extract([source], region_path, out, min_zoom=None, max_zoom=None, name="AT package", context_zoom=1)

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

    extract([source], region_path, out, min_zoom=None, max_zoom=None, name="AT package")

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
        extract([source], region_path, tmp_path / "package.pmtiles", min_zoom=0, max_zoom=1, name="empty", context_zoom=0)


def test_main_extracts_and_reports(tmp_path, capsys):
    source = build_source(tmp_path / "source.pmtiles")
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    out = tmp_path / "package.pmtiles"

    extract_package.main(
        argparse.Namespace(
            source=[source],
            region=region_path,
            out=out,
            min_zoom=None,
            max_zoom=None,
            name="AT package",
            context_zoom=extract_package.DEFAULT_CONTEXT_ZOOM,
            source_region=[],
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
            source=[source],
            region=region_path,
            out=out,
            min_zoom=None,
            max_zoom=None,
            name="AT package",
            context_zoom=-1,
            source_region=[],
        )
    )

    # Region-only: the pure cut's own test proves this set, spot-check here.
    got = read_all(out)
    assert (1, 1, 0) in got and (1, 0, 1) not in got


def test_main_accepts_more_than_one_source(tmp_path):
    # The CLI-level proof that `source` is `nargs="+"`: a single positional
    # source still works (every test above), and a second one is accepted
    # without a second flag or a different entry point.
    source_a = build_source(tmp_path / "a.pmtiles", max_zoom=1, payload_fn=lambda z, x, y: f"A:{z}/{x}/{y}".encode())
    source_b = build_source(tmp_path / "b.pmtiles", max_zoom=1, payload_fn=lambda z, x, y: f"B:{z}/{x}/{y}".encode())
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(WORLD_BOX)))
    out = tmp_path / "package.pmtiles"

    extract_package.main(
        argparse.Namespace(
            source=[source_a, source_b],
            region=region_path,
            out=out,
            min_zoom=1,
            max_zoom=1,
            name="sharded package",
            context_zoom=-1,
            source_region=[],
        )
    )

    # No --source-region given, so every duplicate falls back to the first
    # source - proven fully below; this is only the CLI wiring smoke test.
    assert {data for data in read_all(out).values()} == {b"A:1/0/0", b"A:1/1/0", b"A:1/0/1", b"A:1/1/1"}


# --- #248: cutting from more than one source, and the seam-tile rule -----


def test_choose_seam_winner_is_a_no_op_for_a_single_candidate():
    # No second source produced this tile, so there is no seam question to
    # ask - the polygons dict is irrelevant and can be empty.
    assert choose_seam_winner((5, 3, 2), [(0, b"only")], {}) == b"only"


def test_choose_seam_winner_prefers_the_source_whose_polygon_contains_the_centre():
    polygon = prep(to_mercator(TILE_1_1_0_CENTER_BOX))
    candidates = [(0, b"first"), (1, b"second")]

    assert choose_seam_winner((1, 1, 0), candidates, {1: polygon}) == b"second"


def test_choose_seam_winner_falls_back_to_first_source_when_no_polygon_claims_the_tile():
    # TILE_1_1_0_CENTER_BOX claims only (1, 1, 0)'s centre - (1, 0, 1)'s is
    # nowhere near it, so source 1's polygon does not claim this tile, and
    # source 0 (the base) never has one by construction (#248).
    polygon = prep(to_mercator(TILE_1_1_0_CENTER_BOX))
    candidates = [(0, b"first"), (1, b"second")]

    assert choose_seam_winner((1, 0, 1), candidates, {1: polygon}) == b"first"


def test_extract_merges_two_sources_with_no_overlap(tmp_path):
    # A base source holding only z0, a shard holding only z1 - the ordinary
    # sharded-build shape (a national low-zoom archive plus a regional
    # high-zoom one) with no seam tile in the mix at all.
    base = tmp_path / "base.pmtiles"
    header = {
        "tile_type": TileType.MVT,
        "tile_compression": Compression.GZIP,
        "min_lon_e7": int(-180 * 1e7),
        "min_lat_e7": int(-85 * 1e7),
        "max_lon_e7": int(180 * 1e7),
        "max_lat_e7": int(85 * 1e7),
        "center_lon_e7": 0,
        "center_lat_e7": 0,
        "center_zoom": 0,
    }
    with write(str(base)) as writer:
        writer.write_tile(zxy_to_tileid(0, 0, 0), b"base:0/0/0")
        writer.finalize(header, {"name": "base"})
    shard = build_source(tmp_path / "shard.pmtiles", max_zoom=1, payload_fn=lambda z, x, y: f"shard:{z}/{x}/{y}".encode())

    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(WORLD_BOX)))
    out = tmp_path / "package.pmtiles"

    extract([base, shard], region_path, out, min_zoom=None, max_zoom=None, name="sharded package", context_zoom=None)

    got = read_all(out)
    assert got == {
        (0, 0, 0): b"base:0/0/0",
        (1, 0, 0): b"shard:1/0/0",
        (1, 1, 0): b"shard:1/1/0",
        (1, 0, 1): b"shard:1/0/1",
        (1, 1, 1): b"shard:1/1/1",
    }


def test_extract_breaks_a_seam_tie_by_source_region_centre_containment(tmp_path):
    # Two shards, both covering the whole z0-1 world, standing in for two
    # regional builds that overlap at the seam (#225's measured finding).
    # Only (1, 1, 0) is claimed by shard B's own build region (its centre,
    # not merely its bounds - see TILE_1_1_0_CENTER_BOX); every other
    # duplicate has no claimant and falls back to shard A, the first one
    # named on the command line.
    shard_a = build_source(tmp_path / "a.pmtiles", max_zoom=1, payload_fn=lambda z, x, y: f"A:{z}/{x}/{y}".encode())
    shard_b = build_source(tmp_path / "b.pmtiles", max_zoom=1, payload_fn=lambda z, x, y: f"B:{z}/{x}/{y}".encode())
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(WORLD_BOX)))
    shard_b_region = tmp_path / "b_region.geojson"
    shard_b_region.write_text(json.dumps(mapping(TILE_1_1_0_CENTER_BOX)))
    out = tmp_path / "package.pmtiles"

    extract(
        [shard_a, shard_b],
        region_path,
        out,
        min_zoom=1,
        max_zoom=1,
        name="sharded package",
        context_zoom=None,
        source_regions=[shard_b_region],
    )

    got = read_all(out)
    assert got[(1, 1, 0)] == b"B:1/1/0", "the tile shard B's own region claims must come from shard B"
    assert got[(1, 0, 0)] == b"A:1/0/0"
    assert got[(1, 0, 1)] == b"A:1/0/1"
    assert got[(1, 1, 1)] == b"A:1/1/1"
    assert len(got) == 4, "each seam tile must be written exactly once, not once per source"


def test_extract_without_source_regions_falls_back_to_first_source_wins(tmp_path):
    shard_a = build_source(tmp_path / "a.pmtiles", max_zoom=1, payload_fn=lambda z, x, y: f"A:{z}/{x}/{y}".encode())
    shard_b = build_source(tmp_path / "b.pmtiles", max_zoom=1, payload_fn=lambda z, x, y: f"B:{z}/{x}/{y}".encode())
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(WORLD_BOX)))
    out = tmp_path / "package.pmtiles"

    extract([shard_a, shard_b], region_path, out, min_zoom=1, max_zoom=1, name="sharded package", context_zoom=None)

    got = read_all(out)
    assert all(data.startswith(b"A:") for data in got.values()), "with no --source-region, every tie goes to the first source"


def test_extract_refuses_sources_with_different_tile_type(tmp_path):
    mvt_source = build_source(tmp_path / "mvt.pmtiles", tile_type=TileType.MVT)
    webp_source = build_source(tmp_path / "webp.pmtiles", tile_type=TileType.WEBP)
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(WORLD_BOX)))

    with pytest.raises(SystemExit, match="tile_type"):
        extract(
            [mvt_source, webp_source],
            region_path,
            tmp_path / "package.pmtiles",
            min_zoom=None,
            max_zoom=None,
            name="mixed",
            context_zoom=None,
        )


def test_extract_refuses_more_source_regions_than_shards(tmp_path):
    source = build_source(tmp_path / "a.pmtiles")
    region_path = tmp_path / "region.geojson"
    region_path.write_text(json.dumps(mapping(WORLD_BOX)))

    with pytest.raises(SystemExit, match="source-region"):
        extract(
            [source],
            region_path,
            tmp_path / "package.pmtiles",
            min_zoom=None,
            max_zoom=None,
            name="single",
            context_zoom=None,
            # A single source is the base and never takes a --source-region -
            # any given here has nothing left to pair with.
            source_regions=[tmp_path / "unused_region.geojson"],
        )
