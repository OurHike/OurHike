"""The trail_network family's SQL answers what build_trail_graph.py answers, on the same rows (#1793, stage 3).

trail_graph.json and trail_graph_geometry.json moved to dbt (pipeline/ELT.md's
ledger rows TN01-TN08): the routable lines, the cuts, the node grid, the welds
and the edges to the int_trail_network__ models, and the cutting itself to the
Python step step_node_lines.py, which cuts with build_trail_graph's own
_split_all. Until stage 5 deletes the Python, build_trail_graph.py still writes
the files publish-vector-data.yml uploads, so the two are held together here:

- the trail_network_ vars the models read are build_trail_graph.py's
  constants;
- build_trail_graph's own functions, run over each unit test's given rows,
  give every expected row: routable_lines() and at_lines_of() for the
  routable lines, node_lines() for the cuts, _node_id() for the node grid,
  build_graph() for the edges' nodes and loops, _geographic_vertices() for an
  edge's geometry. Every unit test is held, so none is SQL-only;
- step_node_lines writes build_trail_graph's pieces and landings for the
  cuts it is handed, and refuses a cut shapely would not make.

parity.py's trail_graph families compare the two whole files in CI's dbt job,
on make_dbt_fixtures.py's lines.
"""

import json
from collections import Counter
from pathlib import Path

import pytest
import yaml
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString
from shapely.ops import transform

import build_trail_graph
import step_node_lines
from tests.conftest import spatial_connection

DBT = Path(__file__).parent.parent / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "trail_network" / "_trail_network__unit_tests.yml"
MODELS = (
    "int_trail_network__routable",
    "int_trail_network__cuts",
    "int_trail_network__node_lookups",
    "int_trail_network__raw_edges",
    "int_trail_network__edges",
)


def _unit_tests() -> list[dict]:
    return yaml.safe_load(UNIT_TESTS.read_text())["unit_tests"]


def _on(model: str) -> list[dict]:
    return [test for test in _unit_tests() if test["model"] == model]


def _given(test: dict, model: str) -> dict:
    return next(given for given in test["given"] if given["input"] == f"ref('{model}')")


def _vars() -> dict:
    return yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]


@pytest.fixture(scope="module")
def con():
    connection = spatial_connection()
    yield connection
    connection.close()


def test_the_trail_network_vars_are_build_trail_graphs_constants():
    variables = _vars()
    assert tuple(variables["trail_network_at_sources"]) == build_trail_graph.AT_GRAPH_SOURCES
    assert variables["trail_network_endpoint_snap_m"] == build_trail_graph.ENDPOINT_SNAP_M
    assert variables["trail_network_node_quant_m"] == build_trail_graph.NODE_QUANT_M


def test_every_unit_test_is_on_a_model_this_file_holds_to_the_python():
    tests = _unit_tests()
    assert {test["model"] for test in tests} == set(MODELS)
    assert len({test["name"] for test in tests}) == len(tests)


# ---------------------------------------------------------------- routable


def _features(rows: list[dict]) -> list[dict]:
    """The mart's rows as the features nearby_trails.geojson and trails.geojson carry, in feature order."""
    return [
        {
            "type": "Feature",
            "properties": {
                "id": row["trail_line_id"],
                "source": row["source_key"],
                "trail_status": row.get("trail_status"),
            },
            "geometry": json.loads(row["geom_geojson"]) if row.get("geom_geojson") else None,
        }
        for row in sorted(rows, key=lambda row: row["feature_order"])
    ]


@pytest.mark.parametrize("test", _on("int_trail_network__routable"), ids=lambda test: test["name"])
def test_each_routable_unit_test_is_routable_lines(test):
    """build()'s merge of the network and at_lines_of(), then routable_lines(): the same parts in the same
    order, and the same refusals."""
    rows = _given(test, "trail_lines")["rows"]
    network = _features([row for row in rows if row["line_kind"] == "network"])
    at_lines = build_trail_graph.at_lines_of({"features": _features([row for row in rows if row["line_kind"] != "network"])})
    kept, refused = build_trail_graph.routable_lines({"features": [*network, *at_lines["features"]]})

    expected = test["expect"]["rows"]
    routable = sorted((row for row in expected if row.get("refused_because") is None), key=lambda row: row["part_order"])
    assert [row["part_order"] for row in routable] == list(range(len(routable)))
    assert [row["part_id"].split("#")[0] for row in routable] == [entry["properties"]["id"] for entry in kept]
    for row, entry in zip(routable, kept):
        if "geom_wkt" in row:
            assert list(shapely_wkt.loads(row["geom_wkt"]).coords) == list(entry["line"].coords), row["part_id"]
    assert Counter(row["refused_because"] for row in expected if row.get("refused_because")) == Counter(
        {reason: count for reason, count in refused.items() if count}
    )


# -------------------------------------------------------------------- cuts


def _projected_parts(test: dict) -> list[dict]:
    """The test's routable parts, in part order, projected as build() projects them."""
    to_projected, _ = build_trail_graph._transformers()
    rows = sorted(_given(test, "int_trail_network__routable")["rows"], key=lambda row: row["part_order"])
    return [
        {"properties": {"id": row["part_id"]}, "line": transform(to_projected.transform, shapely_wkt.loads(row["geom_wkt"]))}
        for row in rows
    ]


@pytest.mark.parametrize("test", _on("int_trail_network__cuts"), ids=lambda test: test["name"])
def test_each_cuts_unit_test_is_node_lines(test):
    """node_lines() at the test's tolerance: a crossing row for each pair whose intersection points it counts,
    and an endpoint_join row for each weld, at the weld's own end point to the bit."""
    snap_m = (
        (test.get("overrides") or {})
        .get("vars", {})
        .get("trail_network_endpoint_snap_m", _vars()["trail_network_endpoint_snap_m"])
    )
    parts = _projected_parts(test)
    by_id = {entry["properties"]["id"]: entry["line"] for entry in parts}
    _, stats, welds = build_trail_graph.node_lines(parts, snap_m)

    expected = test["expect"]["rows"]
    crossings = [row for row in expected if row["cut_kind"] == "crossing"]
    joins = [row for row in expected if row["cut_kind"] == "endpoint_join"]
    crossing_points = 0
    for row in crossings:
        line_id, other_id = row["cut_key"].removeprefix("crossing:").split("|")
        crossing_points += len(build_trail_graph._intersection_points(by_id[line_id].intersection(by_id[other_id])))
    assert crossing_points == stats["crossings"]
    assert len(joins) == stats["endpoint_joins"] == len(welds)
    sql_ends = sorted(shapely_wkt.loads(row["end_point_wkt"]).coords[0] for row in joins)
    assert sql_ends == sorted(end for end, _landing in welds)


# --------------------------------------------------------------- node grid


def _pieces(con, test: dict) -> list[dict]:
    """The test's graph_pieces rows, its `format: sql` run in DuckDB as dbt runs it, geometry as WKT."""
    sql = _given(test, "stg_derived__graph_pieces")["rows"]
    relation = con.sql(f"select row_kind, part_id, piece_index, piece_rank, cut_key, st_astext(geom) as geom_wkt from ({sql})")
    return [dict(zip(relation.columns, row)) for row in relation.fetchall()]


def _grid_points(con, test: dict) -> list[tuple[float, float]]:
    """Every point build_graph() asks _node_id() about, in its order: each piece's two ends, then each weld's
    end and landing in cut order."""
    pieces = sorted((row for row in _pieces(con, test) if row["row_kind"] == "piece"), key=lambda row: row["piece_rank"])
    landings = {row["cut_key"]: shapely_wkt.loads(row["geom_wkt"]) for row in _pieces(con, test) if row["row_kind"] == "landing"}
    points = []
    for row in pieces:
        line = shapely_wkt.loads(row["geom_wkt"])
        points += [line.coords[0], line.coords[-1]]
    cuts = sorted(_given(test, "int_trail_network__cuts")["rows"], key=lambda row: row["cut_order"])
    for cut in cuts:
        if cut["cut_kind"] == "endpoint_join":
            points += [shapely_wkt.loads(cut["end_point_wkt"]).coords[0], landings[cut["cut_key"]].coords[0]]
    return points


def _node_answers(points: list[tuple[float, float]]) -> list[tuple[int, bool]]:
    """_node_id()'s answer for each point in turn, and whether that call made the node."""
    buckets: dict = {}
    nodes: list = []
    answers = []
    for x, y in points:
        before = len(nodes)
        answers.append((build_trail_graph._node_id(x, y, build_trail_graph.NODE_QUANT_M, buckets, nodes), len(nodes) > before))
    return answers


@pytest.mark.parametrize("test", _on("int_trail_network__node_lookups"), ids=lambda test: test["name"])
def test_each_node_lookups_unit_test_is_node_id(con, test):
    answers = _node_answers(_grid_points(con, test))
    expected = sorted(test["expect"]["rows"], key=lambda row: row["seq"])
    assert [row["seq"] for row in expected] == list(range(len(answers)))
    assert [(row["node_raw"], row["makes_node"]) for row in expected] == answers


# ------------------------------------------------------------------- edges


@pytest.mark.parametrize("test", _on("int_trail_network__raw_edges"), ids=lambda test: test["name"])
def test_each_raw_edges_unit_test_is_build_graph(con, test):
    """The given grid answers are _node_id()'s, and build_graph() over the same pieces and welds publishes
    exactly the edges the test keeps, in order, with their nodes and lengths."""
    lookups = sorted(_given(test, "int_trail_network__node_lookups")["rows"], key=lambda row: row["seq"])
    points = [(row["x"], row["y"]) for row in lookups]
    assert [(row["node_raw"], row["makes_node"]) for row in lookups] == _node_answers(points)

    pieces = sorted((row for row in _pieces(con, test) if row["row_kind"] == "piece"), key=lambda row: row["piece_rank"])
    for row in pieces:
        line = shapely_wkt.loads(row["geom_wkt"])
        start, end = (lookup for lookup in lookups if lookup.get("piece_rank") == row["piece_rank"])
        assert ((start["x"], start["y"]), (end["x"], end["y"])) == (line.coords[0], line.coords[-1])
    ends = [row for row in lookups if row["lookup_kind"] == "weld_end"]
    landings = {row["cut_key"]: row for row in lookups if row["lookup_kind"] == "weld_landing"}
    welds = [((row["x"], row["y"]), (landings[row["cut_key"]]["x"], landings[row["cut_key"]]["y"])) for row in ends]
    _, to_geographic = build_trail_graph._transformers()
    graph = build_trail_graph.build_graph(
        [{"properties": {"id": row["part_id"]}, "line": shapely_wkt.loads(row["geom_wkt"])} for row in pieces],
        welds,
        to_geographic,
    )

    published = [row for row in sorted(test["expect"]["rows"], key=lambda row: row["edge_rank"]) if not row["dropped_as_a_loop"]]
    assert [(row["part_id"], row["from_node"], row["to_node"]) for row in published] == [
        (edge["trail_id"], edge["from"], edge["to"]) for edge in graph["edges"]
    ]
    for row, edge in zip(published, graph["edges"]):
        if "length_m" in row:
            assert row["length_m"] == pytest.approx(edge["length_m"], abs=0.05), "dbt compares length_m to 0.1"


@pytest.mark.parametrize("test", _on("int_trail_network__edges"), ids=lambda test: test["name"])
def test_each_edges_unit_test_is_geographic_vertices(test):
    """_geographic_vertices() over each kept edge's piece: the coordinates the GeoJSON text carries, exactly,
    and the edges numbered without the dropped ones."""
    given = sorted(_given(test, "int_trail_network__raw_edges")["rows"], key=lambda row: row["edge_rank"])
    kept = [row for row in given if not row["dropped_as_a_loop"]]
    _, to_geographic = build_trail_graph._transformers()
    vertices = build_trail_graph._geographic_vertices([shapely_wkt.loads(row["geom_m_wkt"]) for row in kept], to_geographic)

    expected = sorted(test["expect"]["rows"], key=lambda row: row["edge_index"])
    assert [row["edge_index"] for row in expected] == list(range(len(kept)))
    assert [row["edge_id"] for row in expected] == [f"{row['part_id']}.{row['piece_index']}" for row in kept]
    assert [json.loads(row["geom_geojson"])["coordinates"] for row in expected] == vertices


# ------------------------------------------------------- step_node_lines

# One crossing and one join at test_build_trail_graph.py's ring point: the
# stub's north end stops 6.8 m short of the main line, the cross runs through it.
STEP_LINES = {
    "main#1": LineString([(-74.1, 41.25), (-74.08, 41.25)]),
    "cross#1": LineString([(-74.09, 41.24), (-74.09, 41.26)]),
    "stub#1": LineString([(-74.085, 41.24), (-74.085, 41.24994)]),
}
STEP_CUTS = [
    {
        "cut_key": "crossing:main#1|cross#1",
        "cut_kind": "crossing",
        "line_part_id": "main#1",
        "other_part_id": "cross#1",
        "end_side": None,
    },
    {
        "cut_key": "endpoint_join:stub#1|main#1|end",
        "cut_kind": "endpoint_join",
        "line_part_id": "stub#1",
        "other_part_id": "main#1",
        "end_side": "end",
    },
]


def _step_parts() -> list[dict]:
    return [{"part_id": part_id, "part_order": order, "line": line} for order, (part_id, line) in enumerate(STEP_LINES.items())]


def test_step_node_lines_cuts_as_node_lines_cuts():
    """The step's pieces and landings for the SQL's cuts are node_lines()' own on the same parts, to the bit."""
    to_projected, _ = build_trail_graph._transformers()
    projected = [
        {"properties": {"id": part_id}, "line": transform(to_projected.transform, line)} for part_id, line in STEP_LINES.items()
    ]
    pieces, stats, welds = build_trail_graph.node_lines(projected, build_trail_graph.ENDPOINT_SNAP_M)

    step_pieces, landings, crossings = step_node_lines.cut_lines(_step_parts(), STEP_CUTS, build_trail_graph.ENDPOINT_SNAP_M)

    assert stats["endpoint_joins"] == 1, "the fixture is one join, or this compares nothing"
    assert [list(piece.coords) for part in step_pieces for piece in part] == [list(piece["line"].coords) for piece in pieces]
    assert crossings == stats["crossings"]
    stub_end = transform(to_projected.transform, STEP_LINES["stub#1"]).coords[-1]
    assert [(stub_end, landing.coords[0]) for _key, landing in landings] == welds


@pytest.mark.parametrize(
    ("cut", "refusal"),
    [
        ({**STEP_CUTS[0], "other_part_id": "stub#1"}, "the SQL says these parts cross and shapely says they do not"),
        ({**STEP_CUTS[1], "end_side": "start"}, "the SQL joins this end and shapely would not"),
        ({**STEP_CUTS[1], "cut_kind": "proximity"}, "which this step does not make"),
    ],
    ids=["a crossing that does not cross", "an end beyond the tolerance", "a kind it does not know"],
)
def test_step_node_lines_refuses_a_cut_shapely_would_not_make(cut, refusal):
    with pytest.raises(SystemExit, match=refusal):
        step_node_lines.cut_lines(_step_parts(), [cut], build_trail_graph.ENDPOINT_SNAP_M)
