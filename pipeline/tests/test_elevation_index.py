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
   cuts the corridor to ~25 GB.

2. **3DEP tiles are Cloud-Optimized GeoTIFFs** - tiled 512x512, served with
   `Accept-Ranges: bytes`. rasterio reads them in place over HTTP, pulling
   only the blocks the trail actually crosses. Measured on real centerline
   points: 400 samples in 4.0 s (10 ms/point), which extrapolates to ~12
   minutes for the whole corridor with no bulk download and no local DEM
   storage at all.

So this step resolves tile URLs and footprints into a small index, and the
export samples them remotely. What ships to hikers is unchanged either way:
~70,000 {distance_mi, elevation_ft} records, about 3 MB of JSON.

And a third thing then made the DISCOVERY unnecessary too (#550): the 1/3
arc-second product is a uniform 1-degree grid with a deterministic URL per
cell, so the index is computed from the corridor's bounding box rather than
queried. `tests/test_fetch_elevation.py` covers the grid arithmetic; what is
left here is the shape of the index and the sampler that reads it.
"""

import json

import pytest

from export_elevation import ElevationSampler
from fetch_elevation import TILE_URL_TEMPLATE, build_tile_index, cell_url


class _FakeCorridorCheck:
    """Stands in for the DuckDB corridor-intersection query."""

    def __init__(self, accept=True):
        self.accept = accept
        self.checked = []

    def __call__(self, bounds):
        self.checked.append(bounds)
        return self.accept


# One cell's worth of bounding box, so the grid produces exactly n35w085.
ONE_CELL_BBOX = (-84.6, 34.2, -84.4, 34.4)


def test_dataset_is_the_ten_metre_product_not_one_metre():
    """A change back to 1 m is a ~40x download and should be a visible edit.

    Asserted against the URL rather than a DATASET string, which is what it
    used to be: the product is now named by the `13` in the path USGS serves
    it from, so the path IS the declaration.
    """
    assert "/Elevation/13/TIFF/" in TILE_URL_TEMPLATE


def test_index_records_a_url_and_its_footprint():
    index = build_tile_index(ONE_CELL_BBOX, corridor_hit=_FakeCorridorCheck())

    assert index == [{"url": cell_url("n35w085"), "bounds": [-85.0, 34.0, -84.0, 35.0]}]


def test_index_drops_a_tile_the_corridor_never_reaches():
    """Cell membership is not corridor membership - a 1-degree cell can sit in
    a corner of the bounding rectangle the actual (non-rectangular) corridor
    polygon never touches."""
    check = _FakeCorridorCheck(accept=False)

    assert build_tile_index(ONE_CELL_BBOX, corridor_hit=check) == []
    assert check.checked  # it was actually asked, rather than short-circuited


def test_index_asks_the_corridor_about_the_cell_it_would_publish():
    """The bounds handed to the polygon check are the bounds written to disk.
    Were they to differ, a tile could be admitted on one footprint and sampled
    on another - which reads as a plausible profile over the wrong ground."""
    check = _FakeCorridorCheck()

    [tile] = build_tile_index(ONE_CELL_BBOX, corridor_hit=check)

    assert [list(bounds) for bounds in check.checked] == [tile["bounds"]]


def test_index_is_json_serialisable():
    """It is written to disk and read back by the export step."""
    index = build_tile_index(ONE_CELL_BBOX, corridor_hit=_FakeCorridorCheck())

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
    export - a stretch with no DEM should leave a hole, not lose the run.

    This is also what a computed URL that 404s comes back as, which is why a
    coverage check up front is optional rather than required.
    """
    sampler = ElevationSampler([("/vsicurl/https://example.org/n35w084.tif", (-84, 34, -83, 35))])

    assert sampler.sample_many([(0.0, 0.0)]) == [None]


@pytest.mark.parametrize("point", [(-83.5, 34.5), (-84.0, 34.0)])
def test_sampler_treats_tile_bounds_as_inclusive(point):
    """Points exactly on a tile edge are common where two tiles abut, and
    must not fall through the gap between them."""
    sampler = ElevationSampler([("/vsicurl/https://example.org/n35w084.tif", (-84, 34, -83, 35))])

    assert list(sampler._covering_tiles(*point))


# --- One edition per footprint, and who guarantees it ----------------------
#
# Real-data gotcha, confirmed against the live catalog (2026-07-29): the TNM
# catalog carried MULTIPLE editions of the same 1-degree DEM cell, separated
# only by a date in the filename. The real corridor query returned 244 tiles
# covering just 110 distinct footprints - n35w084 alone had four
# (20220504, 20220512, 20220725, 20230215).
#
# It mattered because ElevationSampler takes the FIRST tile covering a point,
# so without deduplication the profile would be sampled from whichever edition
# came back first - silently mixing survey vintages along the trail, and often
# preferring an older one.
#
# The hazard is real and is no longer ours (#550). USGS splits the bucket:
# `current/` holds exactly one tif per cell, `historical/` holds the dated
# ones, and `current/`'s Last-Modified matched the newest dated edition on
# every cell checked. The catalogue returned both mixed together, which is why
# a newest-per-footprint dedup was needed at all. Asking `current/` asks a
# question that cannot have a wrong answer - so what is tested now is that the
# path stays on that side of the split.


def test_the_url_asks_for_the_current_edition():
    assert "/current/" in TILE_URL_TEMPLATE


def test_the_url_never_reaches_into_the_dated_editions():
    """`historical/` is where the four vintages of n35w084 live. A URL that
    drifted into it would reintroduce exactly the mixing the dedup existed to
    prevent, and would do it without any of the dedup left to catch it."""
    assert "historical" not in cell_url("n35w084")


def test_one_cell_yields_exactly_one_tile():
    """The dedup's guarantee, now structural rather than computed: a cell
    appears once in the grid, so there is no second edition to choose
    between."""
    index = build_tile_index(ONE_CELL_BBOX, corridor_hit=_FakeCorridorCheck())

    assert len(index) == 1


def test_neighbouring_cells_both_survive():
    """Deduplication was per footprint rather than global, and the property it
    protected still holds: two different cells are two different tiles."""
    index = build_tile_index((-84.6, 34.2, -83.4, 34.4), corridor_hit=_FakeCorridorCheck())

    assert len(index) == 2
    assert len({tile["url"] for tile in index}) == 2
