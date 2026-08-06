"""Tests for spike_package_overlap.py - the duplicated-bytes measurement
behind #193's packaging decision.

The spike's conclusions rest on three pieces of arithmetic: which archive
tiles count as shared (region intersection above the context zoom, all of
them at or below it), how their bytes are summed, and how the table reads
back. Each is pinned against a hand-built archive whose right answers are
countable by eye."""

import io

import numpy as np
from PIL import Image
from pmtiles.tile import zxy_to_tileid
from pmtiles.writer import write
from shapely.geometry import box

import spike_package_overlap as spike
from export_dem import build_header
from extract_package import to_mercator

# Package A's region: the north-east quadrant. Region B: the north-west, so
# at z1 they share nothing above context and everything within it.
NE_BOX = box(30.0, 30.0, 80.0, 70.0)
NW_BOX = box(-80.0, 30.0, -30.0, 70.0)


def tile_bytes() -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(buf, format="WEBP", lossless=True)
    return buf.getvalue()


def build_archive(tmp_path, tiles):
    out = tmp_path / "spike.pmtiles"
    with write(str(out)) as writer:
        for z, x, y in tiles:
            writer.write_tile(zxy_to_tileid(z, x, y), tile_bytes())
        writer.finalize(build_header(NE_BOX, 0), {"name": "spike"})
    return out


def test_region_tiles_shared_only_where_both_regions_reach(tmp_path):
    # z0's world tile plus z1's NE (1,0) and NW (0,0) quadrant tiles. With no
    # context zooms, region B (the NW box) shares the world tile and the NW
    # tile, never the NE one.
    archive = build_archive(tmp_path, [(0, 0, 0), (1, 0, 0), (1, 1, 0)])

    table = spike.shared_tiles(spike.archive_entries(archive), to_mercator(NW_BOX), max_zoom=1, context_zoom=None)

    assert table[0]["tiles"] == 1
    assert table[0]["shared_tiles"] == 1  # the world tile intersects any region
    assert table[1]["tiles"] == 2
    assert table[1]["shared_tiles"] == 1


def test_context_zooms_are_shared_by_construction(tmp_path):
    # The same archive with context through z1: every tile is shared, since
    # both packages would carry the whole build footprint at those zooms.
    archive = build_archive(tmp_path, [(0, 0, 0), (1, 0, 0), (1, 1, 0)])

    table = spike.shared_tiles(spike.archive_entries(archive), to_mercator(NW_BOX), max_zoom=1, context_zoom=1)

    assert table[1]["shared_tiles"] == 2


def test_bytes_are_the_archives_own_stored_lengths(tmp_path):
    archive = build_archive(tmp_path, [(1, 0, 0), (1, 1, 0)])
    size = len(tile_bytes())

    table = spike.shared_tiles(spike.archive_entries(archive), to_mercator(NW_BOX), max_zoom=1, context_zoom=None)

    assert table[1]["bytes"] == 2 * size
    assert table[1]["shared_bytes"] == size


def test_report_totals_and_share_of_bytes(tmp_path):
    archive = build_archive(tmp_path, [(1, 0, 0), (1, 1, 0)])
    table = spike.shared_tiles(spike.archive_entries(archive), to_mercator(NW_BOX), max_zoom=1, context_zoom=None)

    text = spike.report("example", table)

    assert "TOTAL" in text
    assert "(50.0% of the archive's bytes)" in text


def test_load_poly_reads_a_local_file(tmp_path):
    poly = tmp_path / "region.poly"
    poly.write_text("region\narea\n  -80.0 30.0\n  -30.0 30.0\n  -30.0 70.0\n  -80.0 70.0\n  -80.0 30.0\nEND\nEND\n")

    region = spike.load_poly(str(poly))

    assert region.equals(NW_BOX) or abs(region.area - NW_BOX.area) < 1e-6


def test_archive_entries_walks_every_tile(tmp_path):
    tiles = [(0, 0, 0), (1, 0, 0), (1, 1, 1), (2, 3, 2)]
    archive = build_archive(tmp_path, tiles)

    got = [(z, x, y) for z, x, y, _ in spike.archive_entries(archive)]

    assert sorted(got) == sorted(tiles)
