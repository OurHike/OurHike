"""Tests for the elevation tile INDEX - the replacement for downloading DEMs.

Why there is an index instead of a download
-------------------------------------------
The original design (and the MVP plan) called for USGS 3DEP **1 metre** DEM
tiles. Measured against the real TNM catalog before running it, that comes to
roughly **1 TB** for the AT corridor: ~190 tiles per 1-degree cell at a median
324 MB, across 51 cells. For an elevation profile that renders into a 100x40
SVG viewBox, that is wrong by about three orders of magnitude - 1 m DEM exists
to measure boulders and building footprints.

Two things then made the whole download unnecessary:

1. **1/3 arc-second (~10 m) is the right resolution** for a trail profile -
   ~1-2 m vertical accuracy, close enough that the "+640 ft ahead" callout
   (which feeds the Naismith estimate directly) is trustworthy. That alone
   cuts the corridor to ~24 GB.

2. **3DEP tiles are Cloud-Optimized GeoTIFFs** - tiled 512x512, served with
   `Accept-Ranges: bytes`. rasterio reads them in place over HTTP, pulling
   only the blocks the trail actually crosses. Measured on real centerline
   points: 400 samples in 4.0 s (10 ms/point), which extrapolates to ~12
   minutes for the whole corridor with no bulk download and no local DEM
   storage at all.

So this step resolves tile URLs and footprints into a small index, and the
export samples them remotely. What ships to hikers is unchanged either way:
~70,000 {distance_mi, elevation_ft} records, about 3 MB of JSON.
"""

import json

import pytest

from export_elevation import ElevationSampler
from fetch_elevation import DATASET, build_tile_index


class _FakeCorridorCheck:
    """Stands in for the DuckDB corridor-intersection query."""

    def __init__(self, accept=True):
        self.accept = accept
        self.checked = []

    def __call__(self, bbox):
        self.checked.append(bbox)
        return self.accept


def _item(name, minx, miny, maxx, maxy):
    return {
        "downloadURL": f"https://prd-tnm.s3.amazonaws.com/.../{name}.tif",
        "boundingBox": {"minX": minx, "minY": miny, "maxX": maxx, "maxY": maxy},
    }


def test_dataset_is_the_ten_metre_product_not_one_metre():
    """A change back to 1 m is a ~40x download and should be a visible edit."""
    assert "1/3 arc-second" in DATASET


def test_index_records_a_url_and_its_footprint():
    items = [_item("n35w084", -84, 34, -83, 35)]

    index = build_tile_index(items, corridor_hit=_FakeCorridorCheck())

    assert index == [
        {
            "url": "https://prd-tnm.s3.amazonaws.com/.../n35w084.tif",
            "bounds": [-84, 34, -83, 35],
        }
    ]


def test_index_deduplicates_a_tile_seen_from_two_cells():
    """Adjacent corridor cells overlap the same 1-degree DEM tile constantly."""
    same = _item("n35w084", -84, 34, -83, 35)

    index = build_tile_index([same, dict(same)], corridor_hit=_FakeCorridorCheck())

    assert len(index) == 1


def test_index_drops_a_tile_the_corridor_never_reaches():
    """Cell membership is not corridor membership - a tile can sit in a
    cell's corner the actual (non-rectangular) corridor polygon never
    touches."""
    index = build_tile_index([_item("far", -99, 20, -98, 21)], corridor_hit=_FakeCorridorCheck(accept=False))

    assert index == []


def test_index_skips_an_item_with_no_download_url():
    index = build_tile_index(
        [{"boundingBox": {"minX": -84, "minY": 34, "maxX": -83, "maxY": 35}}],
        corridor_hit=_FakeCorridorCheck(),
    )

    assert index == []


def test_index_skips_an_item_with_no_bounding_box():
    index = build_tile_index([{"downloadURL": "https://example.org/x.tif"}], corridor_hit=_FakeCorridorCheck())

    assert index == []


def test_index_is_json_serialisable():
    """It is written to disk and read back by the export step."""
    index = build_tile_index([_item("n35w084", -84, 34, -83, 35)], corridor_hit=_FakeCorridorCheck())

    assert json.loads(json.dumps(index)) == index


# --- The sampler reads remote tiles ---------------------------------------


def test_sampler_accepts_a_remote_url_as_a_tile_source():
    """The whole COG approach rests on this: rasterio.open() treats a
    /vsicurl/ URL exactly like a local path, so no separate remote code
    path is needed - only a widened type."""
    sampler = ElevationSampler([("/vsicurl/https://example.org/n35w084.tif", (-84, 34, -83, 35))])

    assert sampler is not None


def test_sampler_returns_none_outside_every_tile_it_knows_about():
    """A real coverage gap degrades the profile rather than crashing the
    export - a stretch with no DEM should leave a hole, not lose the run."""
    sampler = ElevationSampler([("/vsicurl/https://example.org/n35w084.tif", (-84, 34, -83, 35))])

    assert sampler.sample_many([(0.0, 0.0)]) == [None]


@pytest.mark.parametrize("point", [(-83.5, 34.5), (-84.0, 34.0)])
def test_sampler_treats_tile_bounds_as_inclusive(point):
    """Points exactly on a tile edge are common where two tiles abut, and
    must not fall through the gap between them."""
    sampler = ElevationSampler([("/vsicurl/https://example.org/n35w084.tif", (-84, 34, -83, 35))])

    assert list(sampler._covering_tiles(*point))


# --- One edition per footprint --------------------------------------------
#
# Real-data gotcha, confirmed against the live catalog (2026-07-29): the TNM
# catalog carries MULTIPLE editions of the same 1-degree DEM cell, separated
# only by a date in the filename. The real corridor query returned 244 tiles
# covering just 110 distinct footprints - n35w084 alone had four
# (20220504, 20220512, 20220725, 20230215).
#
# This directly contradicts what this module's own docstring used to claim
# ("one edition per tile, unlike the maps catalog"). It is the same problem
# fetch_topo_quads.py documents for the topo product, and it matters here for
# the same reason: with several tiles covering a point, ElevationSampler takes
# the FIRST that covers it, so without deduplication the profile would be
# sampled from whichever edition happened to come back first - silently
# mixing vintages along the trail, and often preferring an older survey.


def _dated(name, date, minx=-84, miny=34, maxx=-83, maxy=35):
    return {
        "downloadURL": f"https://prd-tnm.s3.amazonaws.com/.../USGS_13_{name}_{date}.tif",
        "boundingBox": {"minX": minx, "minY": miny, "maxX": maxx, "maxY": maxy},
    }


def test_index_keeps_only_one_edition_per_footprint():
    items = [_dated("n35w084", "20220504"), _dated("n35w084", "20230215")]

    index = build_tile_index(items, corridor_hit=_FakeCorridorCheck())

    assert len(index) == 1


def test_index_prefers_the_newest_edition():
    """An older survey is not wrong, but mixing vintages along one profile
    is - and the newest is the best available answer for each cell."""
    items = [
        _dated("n35w084", "20220725"),
        _dated("n35w084", "20230215"),
        _dated("n35w084", "20220504"),
    ]

    [tile] = build_tile_index(items, corridor_hit=_FakeCorridorCheck())

    assert "20230215" in tile["url"]


def test_index_keeps_genuinely_different_footprints():
    """Deduplication is per footprint, not global - neighbouring cells must
    both survive."""
    items = [
        _dated("n35w084", "20230215"),
        _dated("n36w084", "20230215", minx=-84, miny=35, maxx=-83, maxy=36),
    ]

    assert len(build_tile_index(items, corridor_hit=_FakeCorridorCheck())) == 2


def test_index_keeps_an_undated_tile_rather_than_discarding_it():
    """A filename that does not match the dated convention should still be
    usable - dropping coverage is worse than an unknown vintage."""
    items = [
        {"downloadURL": "https://example.org/odd_name.tif", "boundingBox": {"minX": -84, "minY": 34, "maxX": -83, "maxY": 35}}
    ]

    assert len(build_tile_index(items, corridor_hit=_FakeCorridorCheck())) == 1
