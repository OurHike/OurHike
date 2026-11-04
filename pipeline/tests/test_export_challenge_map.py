"""export_challenge_map.py on a synthetic map small enough to read (#1965).

Two square "states" side by side - Georgia (FIPS 13) west of North Carolina
(37) - one far outside the frame, a square "Canada", and a trail of two
centerline chains crossing from one state into the other. Every number the
cases assert can be checked by eye against those shapes.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

import export_challenge_map as exporter
from lib import atlas_sources
from lib.source_registry import load_registry

REAL_REGISTRY = exporter.SOURCES_PATH

US = {
    "type": "Topology",
    "arcs": [
        [[-84.0, 34.0], [-84.0, 35.0]],
        [[-84.0, 35.0], [-85.0, 35.0], [-85.0, 34.0], [-84.0, 34.0]],
        [[-84.0, 34.0], [-83.0, 34.0], [-83.0, 35.0], [-84.0, 35.0]],
        [[-150.0, 60.0], [-149.0, 60.0], [-149.0, 61.0], [-150.0, 60.0]],
    ],
    "objects": {
        "states": {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Polygon", "id": "13", "properties": {"name": "Georgia"}, "arcs": [[1, 0]]},
                {"type": "Polygon", "id": "37", "properties": {"name": "North Carolina"}, "arcs": [[2, -1]]},
                {"type": "Polygon", "id": "02", "properties": {"name": "Alaska"}, "arcs": [[3]]},
            ],
        }
    },
}
WORLD = {
    "type": "Topology",
    "arcs": [[[-80.0, 45.0], [-70.0, 45.0], [-70.0, 50.0], [-80.0, 50.0], [-80.0, 45.0]]],
    "objects": {
        "countries": {
            "type": "GeometryCollection",
            "geometries": [{"type": "Polygon", "id": "124", "properties": {"name": "Canada"}, "arcs": [[0]]}],
        }
    },
}
#: Chain 0 runs west to east across Georgia at 34.5°N, miles 0-10; chain 1 is
#: published running SOUTH (its miles fall), from mile 20 back to 10.2, all in
#: North Carolina.
TRAILS = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"id": "c0", "source": "centerline"},
            "geometry": {"type": "LineString", "coordinates": [[-84.9, 34.5], [-84.5, 34.5], [-84.1, 34.5]]},
        },
        {
            "type": "Feature",
            "properties": {"id": "c1", "source": "centerline"},
            "geometry": {"type": "LineString", "coordinates": [[-83.2, 34.9], [-83.5, 34.7], [-83.9, 34.5]]},
        },
        {
            "type": "Feature",
            "properties": {"id": "side", "source": "spur"},
            "geometry": {"type": "LineString", "coordinates": [[-84.0, 34.0], [-84.0, 34.1]]},
        },
    ],
}
MILES = {"c0": [0.0, 5.0, 10.0], "c1": [20.0, 15.0, 10.2]}


def test_douglas_peucker_keeps_both_ends_drops_what_lies_on_the_line_and_keeps_a_real_bend():
    straight = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    assert exporter.simplify_indices(straight, 0.1) == [0, 3]
    bent = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 5.0], [3.0, 0.0], [4.0, 0.0]])
    assert exporter.simplify_indices(bent, 1.0) == [0, 2, 4]
    assert exporter.simplify_indices(bent[:2], 1.0) == [0, 1]


def test_a_chain_published_running_south_is_turned_north_by_its_own_miles():
    chains = exporter.load_chains(TRAILS, MILES)
    assert len(chains) == 2, "the spur is not the centerline"
    xy, m = chains[1]
    assert list(m) == [10.2, 15.0, 20.0]
    assert tuple(xy[0]) == (-83.9, 34.5)


def test_a_chain_without_miles_that_match_its_vertices_is_skipped_not_guessed(capsys):
    assert len(exporter.load_chains(TRAILS, {"c0": MILES["c0"], "c1": [1.0, 2.0]})) == 1
    assert "c1" in capsys.readouterr().err


def test_chains_join_into_one_run_across_a_gap_under_half_a_mile_and_not_over_it():
    chains = exporter.load_chains(TRAILS, MILES)
    assert len(exporter.stitch_runs(chains)) == 1
    apart = exporter.load_chains(TRAILS, {"c0": MILES["c0"], "c1": [20.0, 15.0, 10.6]})
    assert len(exporter.stitch_runs(apart)) == 2


def test_state_runs_follow_the_trail_across_a_line_and_leave_no_gap_between_them():
    chains = exporter.load_chains(TRAILS, MILES)
    states = {f.properties["name"][:2].upper(): f.geometry for f in exporter.topojson.features(US, "states")}
    runs = exporter.state_runs(chains, {"GA": states["GE"], "NC": states["NO"]})
    assert runs == [["GA", 0.0, 10.2], ["NC", 10.2, 20.0]]


def test_outlines_keep_the_states_in_frame_flag_the_trail_states_and_draw_each_shared_border_once():
    drawn = exporter.outlines(US, WORLD)
    assert [(s["code"], s["name"], s["trail"]) for s in drawn["states"]] == [
        ("GA", "Georgia", True),
        ("NC", "North Carolina", True),
    ]
    assert drawn["borders"] == [[[-84.0, 34.0], [-84.0, 35.0]]]
    assert drawn["canada"] and drawn["canada"][0][0][0] == [-80.0, 45.0]
    assert drawn["states"][0]["label"] == [-84.5, 34.5]


def test_credits_come_from_each_sources_own_registry_row():
    credits = exporter.credits(load_registry(REAL_REGISTRY))
    assert credits == [
        {"layer": "trail", "source": "centerline", "credit": "Appalachian Trail Conservancy"},
        {"layer": "states", "source": "us_atlas_states", "credit": "U.S. Census Bureau"},
        {"layer": "canada", "source": "world_atlas_countries", "credit": "Natural Earth"},
    ]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    us_path, world_path = tmp_path / "us.json", tmp_path / "world.json"
    monkeypatch.setitem(atlas_sources.ATLAS_FILES, atlas_sources.US_ATLAS_KEY, (us_path, "states"))
    monkeypatch.setitem(atlas_sources.ATLAS_FILES, atlas_sources.WORLD_ATLAS_KEY, (world_path, "countries"))
    for name in ("TRAILS_PATH", "TRAIL_MILES_PATH", "OUT_PATH", "MANIFEST_PATH"):
        monkeypatch.setattr(exporter, name, processed / getattr(exporter, name).name)
    return processed, us_path, world_path


def write_inputs(processed, us_path, world_path):
    (processed / "trails.geojson").write_text(json.dumps(TRAILS))
    (processed / "trail_miles.json").write_text(json.dumps({"format": 1, "miles": MILES}))
    us_path.write_text(json.dumps(US))
    world_path.write_text(json.dumps(WORLD))


def test_the_file_carries_the_trail_states_credits_and_the_isc_notice_and_is_the_same_bytes_twice(workspace):
    processed, us_path, world_path = workspace
    write_inputs(processed, us_path, world_path)

    output = exporter.main()
    first = exporter.OUT_PATH.read_bytes()
    exporter.main()

    assert exporter.OUT_PATH.read_bytes() == first, "a run that changes nothing must write the same bytes"
    assert "generated_at" not in output
    assert output["trail"][0]["miles"][0] == 0.0 and output["trail"][0]["miles"][-1] == 20.0
    assert output["state_runs"] == [["GA", 0.0, 10.2], ["NC", 10.2, 20.0]]
    assert "Copyright 2013-2019 Michael Bostock" in output["notices"][0]
    manifest = json.loads(exporter.MANIFEST_PATH.read_text())
    assert manifest["path"].endswith("challenge_map.json")
    assert len(manifest["sha256"]) == 64


def test_a_missing_input_writes_nothing_and_takes_away_an_earlier_runs_manifest(workspace, capsys):
    processed, us_path, world_path = workspace
    exporter.MANIFEST_PATH.write_text('{"path": "stale", "sha256": "0"}')

    assert exporter.main() is None

    assert not exporter.MANIFEST_PATH.exists()
    assert not exporter.OUT_PATH.exists()
    assert "::warning::challenge_map.json not written" in capsys.readouterr().out
