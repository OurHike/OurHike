"""Tests for lib/corridor_grid.py - the corridor cell-grid logic shared
between spike_raster_mosaic.py's whole-corridor path and
fetch_and_mosaic_cell.py's per-cell CI path.

The highest-value tests here are for assign_quads_to_cells(): while
building the per-cell CI plan, running the real corridor-grid/quad-bbox
logic against the real AT corridor and USGS metadata inventory found that
378 of 1,654 corridor quads (22.9%) bbox-overlap more than one 1-degree
cell - not a rare edge case. A quad that gets assigned to only its "first"
matching cell would leave the other cell's mosaic missing real coverage at
that boundary, which is exactly the kind of gap TESTING.md's "every real
gotcha becomes a regression test" rule exists for.
"""

import json

import pytest

from lib.corridor_grid import assign_quads_to_cells, bounds_intersect, build_cells_manifest, compute_cells, load_quad_bounds


def _write_corridor(path, geometry):
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": geometry}]})
    )


def _write_metadata_csv(path, rows):
    """rows: list of (product_filename, west, east, north, south) - same
    column order as the real ustopo_current.csv and the existing
    load_neatlines test fixture."""
    lines = ["product_filename,westbc,eastbc,northbc,southbc"]
    lines += [f"{pf},{west},{east},{north},{south}" for pf, west, east, north, south in rows]
    path.write_text("\n".join(lines))


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ((-75.0, 40.0, -74.0, 41.0), (-74.5, 40.5, -73.5, 41.5), True),  # overlapping
        ((-75.0, 40.0, -74.0, 41.0), (-74.0, 41.0, -73.0, 42.0), False),  # touching at a corner only
        ((-75.0, 40.0, -74.0, 41.0), (-70.0, 35.0, -69.0, 36.0), False),  # far apart
    ],
)
def test_bounds_intersect(a, b, expected):
    assert bounds_intersect(a, b) is expected


def test_compute_cells_returns_the_corridors_own_bbox_when_smaller_than_one_cell(tmp_path):
    """The grid starts at the corridor's own bbox corner, not a fixed global
    grid aligned to whole-degree boundaries - a corridor smaller than 1
    degree in both directions produces exactly one cell, clipped to its own
    bbox rather than padded out to the next whole degree."""
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-74.8, 41.2], [-74.6, 41.2], [-74.6, 41.4], [-74.8, 41.4], [-74.8, 41.2]]],
    }
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, geometry)

    cells = compute_cells(corridor_path)

    assert cells == [(-74.8, 41.2, -74.6, 41.4)]


def test_compute_cells_tiles_a_corridor_wider_than_one_cell(tmp_path):
    """A corridor 2.5 degrees wide produces three 1-degree-wide cells (the
    last clipped to the corridor's actual xmax), not one giant cell -
    mirrors spike_raster_mosaic.py's own reasoning for why the whole
    corridor isn't mosaicked as a single rectangle."""
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-77.0, 41.0], [-74.5, 41.0], [-74.5, 41.3], [-77.0, 41.3], [-77.0, 41.0]]],
    }
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, geometry)

    cells = compute_cells(corridor_path)

    assert cells == [
        (-77.0, 41.0, -76.0, 41.3),
        (-76.0, 41.0, -75.0, 41.3),
        (-75.0, 41.0, -74.5, 41.3),
    ]


def test_load_quad_bounds_keeps_only_corridor_intersecting_quads(tmp_path):
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-75.0, 41.0], [-74.0, 41.0], [-74.0, 42.0], [-75.0, 42.0], [-75.0, 41.0]]],
    }
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, geometry)

    metadata_csv = tmp_path / "ustopo_current.csv"
    _write_metadata_csv(
        metadata_csv,
        [
            ("NY_Inside.pdf", -74.8, -74.6, 41.6, 41.4),  # inside the corridor
            ("NJ_FarAway.pdf", -70.0, -69.8, 35.6, 35.4),  # nowhere near it
        ],
    )

    quad_bounds = load_quad_bounds(corridor_path, metadata_csv)

    assert set(quad_bounds) == {"NY_Inside.pdf"}
    assert quad_bounds["NY_Inside.pdf"] == (-74.8, 41.4, -74.6, 41.6)


def test_assign_quads_to_cells_puts_a_straddling_quad_in_both_cells():
    """The named regression for the 22.9% finding: a quad whose bbox crosses
    a cell boundary must be fetched for BOTH owning cells, not just the
    first one encountered."""
    cells = [(-75.0, 41.0, -74.0, 42.0), (-74.0, 41.0, -73.0, 42.0)]
    quad_bounds = {"straddler.pdf": (-74.2, 41.3, -73.8, 41.7)}  # crosses x=-74.0

    assignment = assign_quads_to_cells(quad_bounds, cells)

    assert assignment[0] == ["straddler.pdf"]
    assert assignment[1] == ["straddler.pdf"]


def test_assign_quads_to_cells_puts_a_contained_quad_in_only_one_cell():
    cells = [(-75.0, 41.0, -74.0, 42.0), (-74.0, 41.0, -73.0, 42.0)]
    quad_bounds = {"contained.pdf": (-74.9, 41.3, -74.7, 41.7)}  # fully inside cell 0

    assignment = assign_quads_to_cells(quad_bounds, cells)

    assert assignment[0] == ["contained.pdf"]
    assert assignment[1] == []


def test_assign_quads_to_cells_drops_a_quad_that_matches_no_cell():
    cells = [(-75.0, 41.0, -74.0, 42.0)]
    quad_bounds = {"elsewhere.pdf": (-70.0, 35.0, -69.8, 35.2)}

    assignment = assign_quads_to_cells(quad_bounds, cells)

    assert assignment[0] == []


def test_build_cells_manifest_shape_and_straddling_quad(tmp_path):
    """Integration test tying compute_cells/load_quad_bounds/
    assign_quads_to_cells together into the actual cells.json shape
    fetch_and_mosaic_cell.py consumes."""
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-75.0, 41.0], [-73.0, 41.0], [-73.0, 41.5], [-75.0, 41.5], [-75.0, 41.0]]],
    }
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, geometry)

    metadata_csv = tmp_path / "ustopo_current.csv"
    _write_metadata_csv(
        metadata_csv,
        [
            ("A_Contained.pdf", -74.9, -74.7, 41.3, 41.1),  # fully inside cell 0 (-75..-74)
            ("B_Straddler.pdf", -74.2, -73.8, 41.3, 41.1),  # crosses the -74.0 cell boundary
        ],
    )

    manifest = build_cells_manifest(corridor_path, metadata_csv)

    assert [c["index"] for c in manifest["cells"]] == list(range(len(manifest["cells"])))
    by_index = {c["index"]: c["quads"] for c in manifest["cells"]}
    # cell 0 is (-75, 41, -74, 41.5): gets both quads (A is inside it, B straddles into it)
    assert set(by_index[0]) == {"A_Contained.pdf", "B_Straddler.pdf"}
    # cell 1 is (-74, 41, -73, 41.5): only the straddler reaches it
    assert by_index[1] == ["B_Straddler.pdf"]
