"""Tests for cut_trail_graph.py - the junction graph in 1-degree cells (#1257
stage 3).

Synthetic everything, in test_cut_cells.py's geography: a whole graph whose
nodes span the two fixture cells n40w075 (lon -75..-74) and n40w074 (lon
-74..-73), with the seam at lon -74.0. One edge sits well inside each cell,
and one CROSSES the seam - the edge every rule here is about. The companions
are tiny and deliberately distinguishable per edge, so a shard carrying the
wrong edge's climb is a visible failure rather than a plausible number.

The asymmetry this suite pins is the cutter's docstring's: an edge is never
cut, and duplicating it across the seam is the cheap failure where inventing
a junction at the seam is the expensive one.
"""

import json
import re
from pathlib import Path

import pytest

import cut_trail_graph

WEST_CELL = [(-74.5, 40.5), (-74.4, 40.5)]
EAST_CELL = [(-73.5, 40.5), (-73.4, 40.5)]
ACROSS_THE_SEAM = [(-74.1, 40.5), (-73.9, 40.5)]

NODES = [*WEST_CELL, *EAST_CELL, *ACROSS_THE_SEAM]
EDGES = [
    {"from": 0, "to": 1, "length_m": 8500.0, "trail_id": "west", "source": "oprhp_trails", "name": "West", "blaze_color": "Red"},
    {"from": 2, "to": 3, "length_m": 8500.0, "trail_id": "east", "source": "oprhp_trails", "name": "East", "blaze_color": "Blue"},
    {"from": 4, "to": 5, "length_m": 17000.0, "trail_id": "seam", "source": "centerline", "name": "A.T.", "blaze_color": "White"},
]
GEOMETRY = [
    [list(WEST_CELL[0]), [-74.45, 40.51], list(WEST_CELL[1])],
    [list(EAST_CELL[0]), list(EAST_CELL[1])],
    [list(ACROSS_THE_SEAM[0]), [-74.0, 40.52], list(ACROSS_THE_SEAM[1])],
]
ELEVATION = [[10, 5], [0, 0], [30, 30]]
PROFILE = [[100, 110, 105], [200, 200], [150, 180, 150]]
SOURCES = {"oprhp_trails": {"reaches_hikers": True}, "centerline": {"reaches_hikers": True}}


def _write_whole(in_dir, *, elevation=ELEVATION, profile=PROFILE, geometry=GEOMETRY):
    in_dir.mkdir(parents=True, exist_ok=True)
    (in_dir / cut_trail_graph.GRAPH_NAME).write_text(json.dumps({"nodes": NODES, "edges": EDGES}))
    (in_dir / cut_trail_graph.GEOMETRY_NAME).write_text(json.dumps(geometry))
    if elevation is not None:
        (in_dir / cut_trail_graph.ELEVATION_NAME).write_text(json.dumps(elevation))
    if profile is not None:
        (in_dir / cut_trail_graph.PROFILE_NAME).write_text(json.dumps(profile))
    (in_dir / cut_trail_graph.GRAPH_MANIFEST_NAME).write_text(json.dumps({"sources": SOURCES, "edges": len(EDGES)}))


def _cut(tmp_path, margin_km=0.0, **whole):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    _write_whole(in_dir, **whole)
    manifest = cut_trail_graph.cut_trail_graph(in_dir=in_dir, out_dir=out_dir, margin_km=margin_km)
    return out_dir, manifest


def _shard(out_dir, name, half="graph"):
    return json.loads((out_dir / cut_trail_graph.cell_key(name, half)).read_text())


def test_every_edge_lands_whole_in_every_cell_its_box_touches(tmp_path):
    """The seam edge is in BOTH cells and cut in neither: its vertices are the
    whole graph's, on both sides. A route stepping across the seam finds it
    from either cell, which is the property the duplication buys."""
    out_dir, manifest = _cut(tmp_path)

    assert _shard(out_dir, "n40w075")["edge_ids"] == [0, 2]
    assert _shard(out_dir, "n40w074")["edge_ids"] == [1, 2]
    assert _shard(out_dir, "n40w075", "geometry")[1] == GEOMETRY[2]
    assert _shard(out_dir, "n40w074", "geometry")[1] == GEOMETRY[2]
    assert manifest["stats"]["edge_placements"] == 4
    assert manifest["stats"]["cells"] == 2


def test_a_shard_is_a_complete_graph_of_its_own_that_remembers_where_it_came_from(tmp_path):
    """`from`/`to` index the shard's own nodes, so buildGraphIndex reads a
    shard unchanged; `node_ids` and `edge_ids` carry the whole graph's
    positions, so two shards agree on which node is which without matching
    coordinates on the phone."""
    out_dir, _ = _cut(tmp_path)
    west = _shard(out_dir, "n40w075")

    assert west["node_ids"] == [0, 1, 4, 5]
    assert west["nodes"] == [list(NODES[i]) for i in west["node_ids"]]
    assert [(e["from"], e["to"]) for e in west["edges"]] == [(0, 1), (2, 3)]
    assert [e["trail_id"] for e in west["edges"]] == ["west", "seam"]
    # Every other field of the edge survives untouched, in the builder's order.
    assert list(west["edges"][0]) == list(EDGES[0])


def test_the_companions_are_cut_in_the_shards_own_edge_order(tmp_path):
    """The client's rule "refuse a companion whose length disagrees with the
    edges" holds per cell only if the cut keeps the two aligned - and the
    seam edge's climb rides into both cells with it."""
    out_dir, manifest = _cut(tmp_path)

    assert _shard(out_dir, "n40w075", "elevation") == [ELEVATION[0], ELEVATION[2]]
    assert _shard(out_dir, "n40w074", "elevation") == [ELEVATION[1], ELEVATION[2]]
    assert _shard(out_dir, "n40w074", "profile") == [PROFILE[1], PROFILE[2]]
    assert manifest["stats"]["companions_cut"] == ["elevation", "profile"]
    index = json.loads((out_dir / cut_trail_graph.INDEX_NAME).read_text())
    assert index["cells"][0]["companions"] == {
        "geometry": "trail_graph_geometry_cell_n40w075.json",
        "elevation": "trail_graph_elevation_cell_n40w075.json",
        "profile": "trail_graph_profile_cell_n40w075.json",
    }


def test_a_companion_written_for_another_graph_is_refused_not_cut(tmp_path, capsys):
    """2026-09-07's bucket held an elevation file of 42,103 entries beside a
    graph of 466,966 edges - the companions were not re-sampled when the
    graph grew. Cutting it by position would hand every cell the wrong edges'
    climb; the export refuses the same mismatch, and so does this."""
    out_dir, manifest = _cut(tmp_path, elevation=[[1, 1]])

    assert manifest["stats"]["companions_cut"] == ["profile"]
    assert not (out_dir / cut_trail_graph.cell_key("n40w075", "elevation")).exists()
    index = json.loads((out_dir / cut_trail_graph.INDEX_NAME).read_text())
    assert index["cells"][0]["companions"]["elevation"] is None
    assert index["cells"][0]["companions"]["profile"] == "trail_graph_profile_cell_n40w075.json"
    assert "NOT cut" in capsys.readouterr().out


def test_a_run_without_elevation_cuts_the_graph_and_its_geometry_alone(tmp_path):
    out_dir, manifest = _cut(tmp_path, elevation=None, profile=None)

    assert manifest["stats"]["companions_cut"] == []
    assert set(manifest["artifacts"]) == {
        cut_trail_graph.INDEX_NAME,
        "trail_graph_cell_n40w075.json",
        "trail_graph_geometry_cell_n40w075.json",
        "trail_graph_cell_n40w074.json",
        "trail_graph_geometry_cell_n40w074.json",
    }


def test_a_geometry_from_another_graph_refuses_the_whole_cut(tmp_path):
    with pytest.raises(SystemExit):
        _cut(tmp_path, geometry=GEOMETRY[:2])


def test_the_margin_files_an_edge_near_the_seam_into_the_neighbour_too(tmp_path):
    """cut_cells.py's rule, with the edge's box for the tile's: the west
    edge ends 44 km from the seam and stays west at 3 km, and rides east at
    a margin that reaches it - over-filed, never under-filed."""
    out_dir_near, _ = _cut(tmp_path / "near", margin_km=3.0)
    assert _shard(out_dir_near, "n40w074")["edge_ids"] == [1, 2]

    out_dir_wide, _ = _cut(tmp_path / "wide", margin_km=50.0)
    assert _shard(out_dir_wide, "n40w074")["edge_ids"] == [0, 1, 2]


def test_the_index_is_the_other_families_shape(tmp_path):
    """One parser on the phone (lib/coverageCells.ts's parseCellIndex) and one
    walk in the gate (check 20) read every family, so this index carries the
    fields they read, and the two it has no use for say so honestly."""
    out_dir, _ = _cut(tmp_path)
    index = json.loads((out_dir / cut_trail_graph.INDEX_NAME).read_text())

    assert index["cell_degrees"] == 1.0
    assert index["seam_margin_km"] == 0.0
    assert index["context"] is None
    assert index["context_zoom"] == 0
    assert [c["name"] for c in index["cells"]] == ["n40w075", "n40w074"]
    assert index["cells"][0]["key"] == "trail_graph_cell_n40w075.json"
    assert index["cells"][0]["bounds"] == [-75.0, 40.0, -74.0, 41.0]
    assert index["cells"][0]["edges"] == 2


def test_the_manifest_prices_hashes_and_carries_the_sources(tmp_path):
    out_dir, manifest = _cut(tmp_path)

    for name, entry in manifest["artifacts"].items():
        assert len(entry["sha256"]) == 64
        assert entry["size_bytes"] == (out_dir / name).stat().st_size
    assert manifest["sources"] == SOURCES
    assert manifest["stats"]["seam_duplication_pct"] == pytest.approx(33.33, abs=0.01)
    assert (out_dir / cut_trail_graph.MANIFEST_NAME).exists()


def test_every_cell_key_passes_the_bucket_rules():
    from lib import r2_keys

    for half in cut_trail_graph.HALVES:
        assert r2_keys.validate_key(cut_trail_graph.cell_key("s34e007", half)) is None
    assert r2_keys.validate_key(cut_trail_graph.INDEX_NAME) is None


CONFIG_TS = Path(__file__).resolve().parents[2] / "client" / "src" / "lib" / "config.ts"


def test_the_client_spells_a_cell_key_the_way_this_cutter_does():
    """lib/config.ts's `trailGraphCellKey` against `cell_key`, every half.

    The two ends build the same name from the same two template literals,
    and nothing else holds them equal: a cell the client asks for under a
    respelt name is a 404 the loader reads as "this release has no such
    cell", on a mountain. Read from the TypeScript as text rather than
    restated, for test_published_key_contract.py's reason - a third copy of
    the spelling is the thing being guarded against.
    """
    source = CONFIG_TS.read_text()
    match = re.search(r"export function trailGraphCellKey\([^)]*\)[^{]*\{(.*?)\n\}", source, re.DOTALL)
    assert match, "config.ts no longer defines trailGraphCellKey where this test can read it"
    graph_template, companion_template = re.findall(r"`([^`]+)`", match.group(1))
    for half in cut_trail_graph.HALVES:
        template = graph_template if half == "graph" else companion_template
        client = template.replace("${half}", half).replace("${name}", "n41w075")
        assert client == cut_trail_graph.cell_key("n41w075", half), half
