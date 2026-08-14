"""Tests for build_cells_manifest.py: corridor freshness (built via
lib/corridor.py rather than read from the stale data/spike/corridor.geojson)
and the completeness check this script now runs on its own cells.json output
before writing it - see the module docstring for why neither had a
regression test until now.
"""

import json

import pytest

import build_cells_manifest
from build_cells_manifest import check_manifest_is_complete
from tests.synthetic import write_centerline


def _write_metadata_csv(path, rows):
    """rows: list of (product_filename, west, east, north, south) - same
    column order as the real ustopo_current.csv."""
    lines = ["product_filename,westbc,eastbc,northbc,southbc"]
    lines += [f"{pf},{west},{east},{north},{south}" for pf, west, east, north, south in rows]
    path.write_text("\n".join(lines))


def _patch_paths(monkeypatch, tmp_path, *, centerline, corridor, metadata_csv, out):
    monkeypatch.setattr(build_cells_manifest, "CENTERLINE_PATH", centerline)
    monkeypatch.setattr(build_cells_manifest, "CORRIDOR_PATH", corridor)
    monkeypatch.setattr(build_cells_manifest, "METADATA_CSV_PATH", metadata_csv)
    monkeypatch.setattr(build_cells_manifest, "OUT_PATH", out)


def test_check_manifest_is_complete_is_a_noop_for_a_healthy_manifest():
    manifest = {
        "cells": [
            {"index": 0, "bbox": [0, 0, 1, 1], "quads": ["a.pdf"]},
            {"index": 1, "bbox": [1, 0, 2, 1], "quads": ["b.pdf", "c.pdf"]},
        ]
    }
    check_manifest_is_complete(manifest)  # should not raise/exit


def test_check_manifest_is_complete_fails_when_the_cells_list_is_empty(capsys):
    with pytest.raises(SystemExit):
        check_manifest_is_complete({"cells": []})

    out = capsys.readouterr().out
    assert "cells: 0, expected >= 1" in out


def test_check_manifest_is_complete_fails_when_any_cell_has_zero_quads(capsys):
    """The named case from the manifest-completeness gap: a cell present in
    the grid but with an empty quad list is treated as a hard failure, not
    just a warning - real data confirms the smallest legitimate cell still
    has 2 quads, so zero is never a legitimate edge-of-corridor result."""
    manifest = {
        "cells": [
            {"index": 0, "bbox": [0, 0, 1, 1], "quads": ["a.pdf"]},
            {"index": 1, "bbox": [1, 0, 2, 1], "quads": []},
        ]
    }

    with pytest.raises(SystemExit):
        check_manifest_is_complete(manifest)

    out = capsys.readouterr().out
    assert "cell 1 quads: 0, expected >= 1" in out
    # cell 0 (healthy) must not be reported as a problem alongside cell 1.
    assert "cell 0 quads" not in out


def test_main_builds_a_fresh_corridor_and_writes_cells_json(tmp_path, monkeypatch):
    """End-to-end: build_corridor() runs against a synthetic centerline -
    data/spike/corridor.geojson is never referenced at all - and the fresh
    corridor is written to CORRIDOR_PATH for lib/corridor_grid.py's file-
    based build_cells_manifest() to read, producing a complete manifest."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)

    metadata_csv = tmp_path / "ustopo_current.csv"
    # This fixture line's 30-mile-buffered corridor spans two 1-degree grid
    # cells (confirmed directly: bbox (-74.58, 40.57, -73.32, 41.53), tiled
    # into (-74.58..-73.58) and (-73.58..-73.32)) - so a single quad needs a
    # bbox wide enough to cover the corridor's *entire* extent, not just the
    # fixture line's own coordinates, or one of the two cells would come back
    # with zero quads and trip the completeness check below.
    _write_metadata_csv(metadata_csv, [("NY_Inside.pdf", -75.0, -73.0, 42.0, 40.0)])

    corridor_path = tmp_path / "corridor.geojson"
    out_path = tmp_path / "cells.json"
    _patch_paths(
        monkeypatch, tmp_path, centerline=centerline_path, corridor=corridor_path, metadata_csv=metadata_csv, out=out_path
    )

    result = build_cells_manifest.main()

    assert result == 0

    assert corridor_path.exists()
    corridor_geojson = json.loads(corridor_path.read_text())
    assert corridor_geojson["features"][0]["geometry"]["type"] in ("Polygon", "MultiPolygon")

    manifest = json.loads(out_path.read_text())
    assert len(manifest["cells"]) >= 1
    assert all(cell["quads"] for cell in manifest["cells"])


def test_main_fails_loudly_and_does_not_write_cells_json_when_a_cell_would_have_zero_quads(tmp_path, monkeypatch):
    """The completeness check runs before cells.json is written - a
    would-be manifest with a zero-quad cell must sys.exit(1) rather than
    silently writing a broken file downstream jobs would trust."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)

    metadata_csv = tmp_path / "ustopo_current.csv"
    # Nowhere near the corridor - compute_cells() still yields >= 1 cell (a
    # non-empty corridor always has at least one), but load_quad_bounds()
    # assigns it zero quads.
    _write_metadata_csv(metadata_csv, [("Elsewhere.pdf", -120.0, -119.5, 35.5, 35.0)])

    corridor_path = tmp_path / "corridor.geojson"
    out_path = tmp_path / "cells.json"
    _patch_paths(
        monkeypatch, tmp_path, centerline=centerline_path, corridor=corridor_path, metadata_csv=metadata_csv, out=out_path
    )

    with pytest.raises(SystemExit):
        build_cells_manifest.main()

    assert not out_path.exists()
