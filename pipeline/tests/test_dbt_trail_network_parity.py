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
import re
from collections import Counter
from pathlib import Path

import pytest
import yaml
from pyproj import Geod, Transformer
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString
from shapely.ops import transform

import build_trail_graph
import parity
import step_node_lines
from tests.conftest import spatial_connection

DBT = Path(__file__).parent.parent / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "trail_network" / "_trail_network__unit_tests.yml"
GEODESIC_MACRO = DBT / "macros" / "geodesic_length_m.sql"
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
    """A versioned mart's given names its version, `ref('trail_lines', v=1)` (check_contract_versions.py's rule 5)."""
    return next(given for given in test["given"] if re.fullmatch(rf"ref\('{model}'(, v=\d+)?\)", given["input"]))


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
    relation = con.sql(
        f"select row_kind, part_id, piece_index, piece_rank, weld_rank, cut_key, st_astext(geom) as geom_wkt from ({sql})"
    )
    return [dict(zip(relation.columns, row)) for row in relation.fetchall()]


def _grid_points(con, test: dict) -> list[tuple[float, float]]:
    """Every point build_graph() asks _node_id() about, in its order: each piece's two ends, then each weld's
    end and landing in the order node_lines() made the welds, which is each landing's weld_rank."""
    pieces = sorted((row for row in _pieces(con, test) if row["row_kind"] == "piece"), key=lambda row: row["piece_rank"])
    landings = {row["cut_key"]: row for row in _pieces(con, test) if row["row_kind"] == "landing"}
    points = []
    for row in pieces:
        line = shapely_wkt.loads(row["geom_wkt"])
        points += [line.coords[0], line.coords[-1]]
    joins = [cut for cut in _given(test, "int_trail_network__cuts")["rows"] if cut["cut_kind"] == "endpoint_join"]
    for cut in sorted(joins, key=lambda cut: landings[cut["cut_key"]]["weld_rank"]):
        landing = shapely_wkt.loads(landings[cut["cut_key"]]["geom_wkt"])
        points += [shapely_wkt.loads(cut["end_point_wkt"]).coords[0], landing.coords[0]]
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


def test_the_weld_order_unit_test_answers_otherwise_in_cut_order(con):
    """The unit test that holds the welds to weld_rank holds something: asked in cut_order instead, the east stub's
    landing finds the main line's piece end, and the west stub's makes a node no other point finds."""
    (test,) = [test for test in _on("int_trail_network__node_lookups") if "weld_rank_order_not_cut_order" in test["name"]]
    pieces = sorted((row for row in _pieces(con, test) if row["row_kind"] == "piece"), key=lambda row: row["piece_rank"])
    landings = {row["cut_key"]: shapely_wkt.loads(row["geom_wkt"]) for row in _pieces(con, test) if row["row_kind"] == "landing"}
    points = [
        end
        for row in pieces
        for end in (shapely_wkt.loads(row["geom_wkt"]).coords[0], shapely_wkt.loads(row["geom_wkt"]).coords[-1])
    ]
    for cut in sorted(_given(test, "int_trail_network__cuts")["rows"], key=lambda cut: cut["cut_order"]):
        points += [shapely_wkt.loads(cut["end_point_wkt"]).coords[0], landings[cut["cut_key"]].coords[0]]
    in_cut_order = _node_answers(points)
    assert in_cut_order[8:] == [(5, False), (2, False), (7, False), (8, True)]
    assert in_cut_order != _node_answers(_grid_points(con, test))


def test_build_graph_numbers_and_places_nodes_by_the_order_of_its_welds():
    """The same pieces and welds as that unit test, through build_graph() itself, in each order. West first, the two
    stubs' ends are one node, at the east stub's end (11.5, 7), and neither reaches the main line; east first, the
    east stub's end is the main line's node at (12, 0) and the west stub's is a node alone. So the welds' order moves
    a node, and every number after it, which is what monthly run 30's renumbering was."""
    pieces = [
        {"properties": {"id": part_id}, "line": LineString(coords)}
        for part_id, coords in (
            ("main#1", [(0, 0), (10, 0)]),
            ("main#1", [(12, 0), (100, 0)]),
            ("east#1", [(11.5, 30), (11.5, 7)]),
            ("west#1", [(11, -30), (11, -7)]),
        )
    ]
    west, east = ((11.0, -7.0), (11.0, 0.0)), ((11.5, 7.0), (11.5, 0.0))
    identity = Transformer.from_crs("EPSG:4326", "EPSG:4326", always_xy=True)
    in_tree_order = build_trail_graph.build_graph(pieces, [west, east], identity)
    in_cut_order = build_trail_graph.build_graph(pieces, [east, west], identity)
    assert [(edge["from"], edge["to"]) for edge in in_tree_order["edges"]] == [(0, 1), (2, 3), (4, 5), (6, 5)]
    assert [(edge["from"], edge["to"]) for edge in in_cut_order["edges"]] == [(0, 1), (2, 3), (4, 2), (5, 6)]
    assert (in_tree_order["nodes"][5], in_cut_order["nodes"][2]) == ([11.5, 7.0], [12.0, 0.0])


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
    # dbt compares a double to 0.1, so the expected length is held here to the
    # centimetre the file publishes: both sides measure the WGS84 geodesic and
    # round it to 2 decimals (decision 90).
    for row, edge in zip(published, graph["edges"]):
        if "length_m" in row:
            assert row["length_m"] == edge["length_m"], "length_m, at 2 decimals"


def _geodesic_length_sql(geom: str) -> str:
    """macros/geodesic_length_m.sql's macro as dbt renders it for `geom`: its one argument is all the Jinja it uses."""
    text = re.sub(r"\{#.*?#\}", "", GEODESIC_MACRO.read_text(), flags=re.S)
    (body,) = re.findall(r"\{%-? macro geodesic_length_m\(geom_5070\) -?%\}(.*?)\{%-? endmacro -?%\}", text, re.S)
    body = body.replace("{{ geom_5070 }}", geom)
    assert "{{" not in body and "{%" not in body, "geodesic_length_m uses Jinja this renderer does not"
    return body


# DBT2-2's places, each a kilometre on the WGS84 ellipsoid. EPSG:5070 reads the
# first four 887.7 m, 1,126.4 m, 775.9 m and 755.7 m, and the last 992.0 m
# (pyproj, 2026-10-06).
GEODESIC_KILOMETRES = {
    "north-south at Anchorage, Alaska": (-149.9, 61.2, 0),
    "east-west at Anchorage, Alaska": (-149.9, 61.2, 90),
    "north-south in the Brooks Range, Alaska": (-152.0, 68.0, 0),
    "north-south in American Samoa": (-170.7, -14.3, 0),
    "east-west at Harriman, New York": (-74.1, 41.25, 90),
}


@pytest.mark.parametrize(("lon", "lat", "azimuth"), GEODESIC_KILOMETRES.values(), ids=GEODESIC_KILOMETRES.keys())
def test_geodesic_length_m_reads_an_epsg5070_line_as_pyprojs_wgs84_geodesic(con, lon, lat, azimuth):
    """The macro int_trail_network__raw_edges measures length_m with, on a line handed to it in EPSG:5070 as the
    graph's pieces are: it reads pyproj's Geod(ellps='WGS84') length, and build_trail_graph's, to a micrometre
    (the two differed by at most 1e-8 m, measured 2026-10-06 on DuckDB 1.5.5). That proves the x-as-latitude trap
    handled: ST_Length_Spheroid without ST_FlipCoordinates reads NaN at Anchorage and 1,331.6 m at Harriman."""
    geod = Geod(ellps="WGS84")
    end_lon, end_lat, _ = geod.fwd(lon, lat, azimuth, 1000.0)
    to_projected, to_geographic = build_trail_graph._transformers()
    line = transform(to_projected.transform, LineString([(lon, lat), (end_lon, end_lat)]))

    (sql_m,) = con.execute(f"select {_geodesic_length_sql('st_geomfromwkb(?)')}", [line.wkb]).fetchone()
    (python_m,) = build_trail_graph._geodesic_lengths(*build_trail_graph._geographic_coordinates([line], to_geographic))

    assert sql_m == pytest.approx(geod.line_length([lon, end_lon], [lat, end_lat]), abs=1e-6)
    assert sql_m == pytest.approx(python_m, abs=1e-6)
    assert round(sql_m, 2) == 1000.0


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
# stub's north end stops 6.7 m short of the main line, the cross runs through it.
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
    assert [(stub_end, landing.coords[0]) for _key, landing, _rank in landings] == welds
    assert [rank for _key, _landing, rank in landings] == [0]


# The main line again and two stubs stopping 6.7 m short of it: `east#1` is the second part and lies east of
# `west#1`, the third. node_lines() takes a part's partners in STRtree's order, west first; cut_order takes them in
# part order, east first.
WELD_ORDER_LINES = {
    "main#1": LineString([(-74.1, 41.25), (-74.08, 41.25)]),
    "east#1": LineString([(-74.083, 41.24), (-74.083, 41.24994)]),
    "west#1": LineString([(-74.097, 41.24), (-74.097, 41.24994)]),
}
WELD_ORDER_CUTS = [
    {
        "cut_key": f"endpoint_join:{stub}|main#1|end",
        "cut_kind": "endpoint_join",
        "line_part_id": stub,
        "other_part_id": "main#1",
        "end_side": "end",
    }
    for stub in ("east#1", "west#1")
]


def test_step_node_lines_ranks_the_welds_in_the_order_node_lines_makes_them_not_cut_order():
    """weld_rank is node_lines()' own order of welds, from the same STRtree: here the west stub's, the third part,
    before the east stub's, the second, where cut_order has the east stub's first."""
    to_projected, _ = build_trail_graph._transformers()
    projected = [
        {"properties": {"id": part_id}, "line": transform(to_projected.transform, line)}
        for part_id, line in WELD_ORDER_LINES.items()
    ]
    _, stats, welds = build_trail_graph.node_lines(projected, build_trail_graph.ENDPOINT_SNAP_M)
    parts = [
        {"part_id": part_id, "part_order": order, "line": line} for order, (part_id, line) in enumerate(WELD_ORDER_LINES.items())
    ]

    _, landings, _ = step_node_lines.cut_lines(parts, WELD_ORDER_CUTS, build_trail_graph.ENDPOINT_SNAP_M)

    assert stats["endpoint_joins"] == 2, "both stubs join, or this compares nothing"
    ranked = sorted(landings, key=lambda landing: landing[2])
    assert [key for key, _landing, _rank in ranked] == ["endpoint_join:west#1|main#1|end", "endpoint_join:east#1|main#1|end"]
    assert [landing.coords[0] for _key, landing, _rank in ranked] == [landing for _end, landing in welds]


def test_step_node_lines_refuses_a_join_whose_parts_strtree_does_not_hand_each_other():
    """A join of two parts whose envelopes do not meet is one node_lines() never makes."""
    far = {**WELD_ORDER_LINES, "far#1": LineString([(-74.0, 41.0), (-73.99, 41.001)])}
    parts = [{"part_id": part_id, "part_order": order, "line": line} for order, (part_id, line) in enumerate(far.items())]
    lines = [transform(build_trail_graph._transformers()[0].transform, part["line"]) for part in parts]
    index = {part["part_id"]: part["part_order"] for part in parts}
    cut = {**WELD_ORDER_CUTS[0], "cut_key": "endpoint_join:far#1|main#1|end", "line_part_id": "far#1"}
    with pytest.raises(SystemExit, match="STRtree.query does not hand node_lines"):
        step_node_lines.weld_ranks(lines, [cut], index)


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


# --- parity.py's trail_graph family: each end compared in place --------------------------------------------------

# Three places, and two edges along them. A node's number is only its place in its file's `nodes`.
WEST, MIDDLE, EAST = [-74.1, 41.1], [-74.0, 41.0], [-73.9, 40.9]
ATTRIBUTION = {"trail_id": "t", "source": "s", "name": "Long Path", "blaze_color": "Aqua"}


def _graph(nodes: list, ends: list[tuple[int, int]]) -> dict:
    return {"nodes": nodes, "edges": [{"from": a, "to": b, "length_m": 10.0, **ATTRIBUTION} for a, b in ends]}


def _compare(old: dict, new: dict) -> tuple[list, dict]:
    family = parity.FAMILIES["trail_graph"]
    old, new = parity._indexed_edges(old), family.new_shape(new, Path("trail_graph.json"))
    found = parity.differences(old, new, family)
    return found, family.kinds(old, new, found)


def test_the_same_graph_under_the_same_numbers_has_no_difference():
    graph = _graph([WEST, MIDDLE, EAST], [(0, 1), (1, 2)])
    assert _compare(graph, json.loads(json.dumps(graph))) == ([], {})


def test_a_renumbered_graph_is_renumbered_on_every_difference_and_still_differs():
    """The same two edges along the same three places, with the nodes listed in another order: every edge's ends are
    in the same place, so each difference is `renumbered`, `nodes` too, and none is explained or `moved`."""
    found, kinds = _compare(_graph([WEST, MIDDLE, EAST], [(0, 1), (1, 2)]), _graph([MIDDLE, EAST, WEST], [(2, 0), (0, 1)]))
    assert [what for what, _, _ in found] == ["field nodes", "edge_index 0", "edge_index 1"]
    assert kinds == {"field nodes": "renumbered", "edge_index 0": "renumbered", "edge_index 1": "renumbered"}
    assert parity.FAMILIES["trail_graph"].explained is None


def test_a_moved_end_is_moved_never_renumbered():
    """The new side's second edge ends somewhere else: that edge is `moved`, the first is still only renumbered, and
    `nodes` holds another place, so it is of no kind."""
    elsewhere = [-73.8, 40.8]
    found, kinds = _compare(_graph([WEST, MIDDLE, EAST], [(0, 1), (1, 2)]), _graph([MIDDLE, elsewhere, WEST], [(2, 0), (0, 1)]))
    assert kinds == {"edge_index 0": "renumbered", "edge_index 1": "moved"}
    assert "field nodes" in [what for what, _, _ in found]


def test_an_end_that_moved_under_its_old_number_is_moved():
    """Both edges keep their numbers and the middle node moves: compared by number they would agree, and only `nodes`
    would differ. Compared in place, both edges are `moved`."""
    found, kinds = _compare(
        _graph([WEST, MIDDLE, EAST], [(0, 1), (1, 2)]), _graph([WEST, [-74.0, 41.01], EAST], [(0, 1), (1, 2)])
    )
    assert kinds == {"edge_index 0": "moved", "edge_index 1": "moved"}
    assert [what for what, _, _ in found] == ["field nodes", "edge_index 0", "edge_index 1"]


def test_a_renumbered_edge_whose_length_changed_is_of_no_kind():
    old = _graph([WEST, MIDDLE, EAST], [(0, 1), (1, 2)])
    new = _graph([MIDDLE, EAST, WEST], [(2, 0), (0, 1)])
    new["edges"][1]["length_m"] = 11.0
    _, kinds = _compare(old, new)
    assert "edge_index 1" not in kinds and kinds["edge_index 0"] == "renumbered"


def test_an_end_the_file_has_no_node_for_is_of_no_kind():
    _, kinds = _compare(_graph([WEST, MIDDLE, EAST], [(0, 1), (1, 2)]), _graph([WEST, MIDDLE], [(0, 1), (1, 2)]))
    assert "edge_index 1" not in kinds


def test_the_cli_prints_each_kind_under_its_heading_and_still_exits_1(tmp_path, monkeypatch, capsys):
    """A renumbered graph still fails the line: its kind is written beside each difference, never as a reason."""
    old = _graph([WEST, MIDDLE, EAST], [(0, 1), (1, 2)])
    monkeypatch.setitem(
        parity.FAMILIES,
        "fake_graph",
        parity.Family(
            old=lambda: parity._indexed_edges(old),
            records="edges",
            key="edge_index",
            ordered=True,
            new_shape=parity._indexed_edges,
            kinds=parity._trail_graph_kinds,
            kind_meanings=parity.TRAIL_GRAPH_KINDS,
        ),
    )
    new = tmp_path / "trail_graph.json"
    new.write_text(json.dumps(_graph([MIDDLE, EAST, WEST], [(2, 0), (0, 1)])))
    argv = ["fake_graph", "--new", str(new), "--json-dir", str(tmp_path / "results"), "--keys-only"]
    assert parity.main(argv) == 1
    printed = capsys.readouterr().out
    assert "  renumbered, 3: both ends in the same place" in printed
    assert "moved," not in printed and "of no kind above" not in printed
    result = json.loads((tmp_path / "results" / "fake_graph.json").read_text())
    assert (result["outcome"], result["explained"], result["kinds"]) == ("differences", [], {"renumbered": 3})
    assert {entry["what"]: entry["kind"] for entry in result["differences"]} == {
        "field nodes": "renumbered",
        "edge_index 0": "renumbered",
        "edge_index 1": "renumbered",
    }
