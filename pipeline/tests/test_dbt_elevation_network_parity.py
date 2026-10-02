"""The elevation family's network half answers what export_network_elevation.py and export_network_profile.py answer (#1793, stage 3).

trail_graph_elevation.json and trail_graph_profile.json moved to dbt
(pipeline/ELT.md's ledger rows EL10-EL13): each junction-graph edge's samples
to int_elevation__edge_sample_points, their DEM answers in whole feet to
int_elevation__edge_samples, the climb to int_elevation__edge_climbs over
macros/dead_band_gain.sql, the seam measurement to int_elevation__seam_nodes
and int_elevation__seam_measurement, and the two files to
pub_trail_graph_elevation and pub_trail_graph_profile. The DEM read stays the
Python step step_dem_sampling.py. Until stage 5 deletes the Python, today's
exporters still write the files publish.py uploads, so the two are held
together here:

- the vars the models read are the Python's constants;
- dead_band_gain is lib/elevation_gain.py's dead band, to the bit, on the
  shared vectors the TypeScript copy reads and on random profiles with gaps,
  and every model passes it a constant threshold (DuckDB 1.5.5's list_reduce
  reads a captured column from the wrong row; the macro's header has the
  measurement);
- today's own functions, run over each unit test's given rows, give every
  expected row: edge_sample_points, edge_climb, edge_profile's rounding,
  measure_seams and its _percentile, and write_artifact's json.dumps;
- SQL_ONLY names the unit test the Python has no counterpart for, and holds
  that a reader trusting the DEM rows would answer it differently;
- parity.py's two graph families pair the files' entries by their place.

parity.py's trail_graph_elevation and trail_graph_profile families compare the
whole files in CI's dbt job, on the build's own edges.
"""

import itertools
import json
import random
import re
from pathlib import Path

import duckdb
import pytest
import yaml

import export_network_elevation as network_elevation
import export_network_profile as network_profile
import parity
from lib import elevation_gain

DBT = Path(__file__).parent.parent / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "elevation" / "_elevation__network_unit_tests.yml"
MACROS = DBT / "macros" / "dead_band_gain.sql"
VECTORS = json.loads((Path(__file__).parent.parent / "reference" / "gain_vectors.json").read_text())
VARIABLES = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]

# The unit test the Python has nothing to hold it to, and why: today's
# exporters read the DEM at each sample's own point in the same run, so they
# have no table that could answer a sample from another point.
SQL_ONLY = {"int_elevation__edge_samples_refuses_an_elevation_read_at_another_point"}

HELD = (
    "int_elevation__edge_sample_points",
    "int_elevation__dem_points",
    "int_elevation__edge_samples",
    "int_elevation__edge_climbs",
    "int_elevation__seam_nodes",
    "int_elevation__seam_measurement",
    "pub_trail_graph_elevation",
    "pub_trail_graph_profile",
)


def _unit_tests() -> list[dict]:
    return yaml.safe_load(UNIT_TESTS.read_text())["unit_tests"]


def _on(model: str) -> list[dict]:
    return [test for test in _unit_tests() if test["model"] == model]


def _given(test: dict, model: str) -> list[dict]:
    return next(given for given in test["given"] if given["input"] == f"ref('{model}')")["rows"]


def render_macro(name: str, **arguments: str) -> str:
    """One macro of macros/dead_band_gain.sql as dbt renders it, without Jinja: its `set`s of string concatenations,
    its arguments and var() are all the Jinja it may use, and anything else fails here."""
    text = re.sub(r"\{#.*?#\}", "", MACROS.read_text(), flags=re.S)
    match = re.search(r"\{%-? macro " + name + r"\(([^)]*)\) -?%\}(.*?)\{%-? endmacro -?%\}", text, re.S)
    parameters = [parameter.strip() for parameter in match.group(1).split(",") if parameter.strip()]
    assert sorted(parameters) == sorted(arguments), (parameters, sorted(arguments))
    names = dict(arguments)

    def evaluate(expression: str) -> str:
        parts = []
        for part in expression.split("~"):
            part = part.strip()
            parts.append(part[1:-1] if len(part) >= 2 and part[0] == part[-1] and part[0] in "\"'" else names[part])
        return "".join(parts)

    def assign(found: re.Match) -> str:
        names[found.group(1)] = evaluate(found.group(2))
        return ""

    body = re.sub(r"\{%-?\s*set\s+(\w+)\s*=\s*(.*?)\s*-?%\}", assign, match.group(2), flags=re.S)
    body = re.sub(r"\{\{\s*var\(\"(\w+)\"\)\s*\}\}", lambda found: str(VARIABLES[found.group(1)]), body)
    body = re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda found: names[found.group(1)], body)
    assert "{{" not in body and "{%" not in body, f"{name} uses Jinja this renderer does not"
    return body


@pytest.fixture(scope="module")
def con():
    connection = duckdb.connect()
    yield connection
    connection.close()


def test_the_network_vars_are_the_pythons_constants():
    assert VARIABLES["elevation_gain_threshold_m"] == elevation_gain.DEFAULT_THRESHOLD_M
    assert VARIABLES["elevation_metres_per_foot"] == elevation_gain.METERS_PER_FOOT
    assert VARIABLES["elevation_sample_interval_m"] == network_elevation.SAMPLE_INTERVAL_METERS


def test_every_network_unit_test_is_on_a_model_this_file_holds_to_the_python():
    names = {test["name"] for test in _unit_tests()}
    assert names == {test["name"] for model in HELD for test in _on(model)}
    assert SQL_ONLY <= names


# --- macros/dead_band_gain.sql ---------------------------------------------------


def _gain_sql(values: str, threshold: str) -> str:
    return render_macro("dead_band_gain", values=values, threshold=threshold)


def test_the_threshold_macro_is_default_threshold_ft_to_the_bit(con):
    assert (
        con.execute("select " + render_macro("elevation_gain_threshold_ft")).fetchone()[0] == elevation_gain.DEFAULT_THRESHOLD_FT
    )


def _vector_values(case: dict) -> list:
    """A case's elevations, a shared boundary case's part_start as the null break the models put before a seam."""
    if "elevations" in case:
        return case["elevations"]
    values = []
    for record in case["samples"]:
        if record.get("part_start"):
            values.append(None)
        values.append(record.get("elevation_ft"))
    return values


@pytest.mark.parametrize(
    "case, python",
    [(case, elevation_gain.cumulative_gain) for case in VECTORS["cases"]]
    + [(case, elevation_gain.cumulative_gain_over_gaps) for case in VECTORS["gap_cases"]]
    + [(case, None) for case in VECTORS["boundary_cases"]],
    ids=lambda value: value["name"] if isinstance(value, dict) else "",
)
def test_dead_band_gain_is_the_librarys_on_every_shared_vector(con, case, python):
    """reference/gain_vectors.json, which tests/test_lib_elevation_gain.py and client/src/lib/elevationGain.ts read too."""
    want = (
        python(case["elevations"], case["threshold"])
        if python
        else elevation_gain.gain_over_profile(case["samples"], case["threshold"])
    )
    got = con.execute(
        "select " + _gain_sql("cast($v as double[])", "cast($t as double)"), {"v": _vector_values(case), "t": case["threshold"]}
    )
    assert got.fetchone()[0] == want


@pytest.fixture(scope="module")
def random_profiles(con, tmp_path_factory):
    """4,000 seeded random walks of 0 to 60 samples, a twentieth of them gaps, as table `profiles` (i, v).

    Loaded through a JSON lines file, whose doubles json.dumps writes at the shortest length that reads back to
    each, because DuckDB takes a nested Python list as a parameter at about 70 s for these (measured 2026-10-02)."""
    rng = random.Random(559)
    profiles = []
    for _ in range(4000):
        level, values = rng.uniform(0, 3000), []
        for _ in range(rng.randint(0, 60)):
            level += rng.choice([rng.gauss(0, 2), rng.gauss(0, 15), rng.uniform(-40, 40)])
            values.append(None if rng.random() < 0.05 else level)
        profiles.append(values)
    path = tmp_path_factory.mktemp("gain") / "profiles.jsonl"
    path.write_text("".join(json.dumps({"i": i, "v": v}) + "\n" for i, v in enumerate(profiles)))
    con.execute(
        "create or replace temp table profiles as select * from read_json($path, columns = {'i': 'INTEGER', 'v': 'DOUBLE[]'})",
        {"path": str(path)},
    )
    assert [row[0] for row in con.execute("select v from profiles order by i").fetchall()] == profiles
    return profiles


@pytest.mark.parametrize("threshold_m", [0.0, 1.0, elevation_gain.DEFAULT_THRESHOLD_M, 10.0])
def test_dead_band_gain_and_its_loss_are_the_librarys_to_the_bit_on_random_profiles_with_gaps(con, random_profiles, threshold_m):
    """Many profiles in one query, as a model folds them: gain is cumulative_gain_over_gaps and loss loss_over_gaps,
    as the same doubles, at each threshold given as a constant."""
    threshold_ft = threshold_m / elevation_gain.METERS_PER_FOOT
    constant = f"cast('{threshold_ft!r}' as double)"
    rows = con.execute(
        f"select {_gain_sql('v', constant)}, {_gain_sql('list_transform(v, lambda x: -x)', constant)} from profiles order by i"
    ).fetchall()
    assert [gain for gain, _ in rows] == [elevation_gain.cumulative_gain_over_gaps(v, threshold_ft) for v in random_profiles]
    assert [loss for _, loss in rows] == [elevation_gain.loss_over_gaps(v, threshold_ft) for v in random_profiles]


def test_dead_band_gain_is_the_librarys_on_every_short_profile_whose_swings_tie_the_dead_band(con, tmp_path):
    """Every profile of up to five samples from {gap, 0, 1.5, 3, 4.5, 6} at a 3.0 dead band, exact in binary, so
    every swing that is exactly the band meets each comparison's tie: a `<` for a `<=` or a `>` for a `>=` anywhere in
    the fold changes some answer here, where random doubles almost never tie."""
    values = [None, 0.0, 1.5, 3.0, 4.5, 6.0]
    profiles = [list(combination) for length in range(6) for combination in itertools.product(values, repeat=length)]
    path = tmp_path / "ties.jsonl"
    path.write_text("".join(json.dumps({"i": i, "v": v}) + "\n" for i, v in enumerate(profiles)))
    con.execute(
        "create or replace temp table ties as select * from read_json($path, columns = {'i': 'INTEGER', 'v': 'DOUBLE[]'})",
        {"path": str(path)},
    )
    gains = [row[0] for row in con.execute(f"select {_gain_sql('v', 'cast(3.0 as double)')} from ties order by i").fetchall()]
    assert gains == [elevation_gain.cumulative_gain_over_gaps(profile, 3.0) for profile in profiles]


def test_every_model_passes_dead_band_gain_a_constant_threshold():
    """A column would be read from the wrong row (the macro's header), so each call's threshold is the vars' constant."""
    calls = []
    for path in (DBT / "models").rglob("*.sql"):
        calls += re.findall(r"dead_band_gain\((.*?)\)\s*\}\}", path.read_text(), flags=re.S)
    assert calls, "no model calls dead_band_gain, so this checked nothing"
    assert all(call.rstrip().endswith("elevation_gain_threshold_ft()") for call in calls), calls


# --- int_elevation__edge_sample_points and int_elevation__dem_points --------------


def _coordinates(edge: dict) -> list:
    return json.loads(edge["geom_geojson"])["coordinates"]


@pytest.mark.parametrize("test", _on("int_elevation__edge_sample_points"), ids=lambda test: test["name"])
def test_each_edge_sample_points_unit_test_is_edge_sample_points(test):
    """export_network_elevation.edge_sample_points over each given edge: the same count of samples, and the same
    point wherever the expectation names one."""
    to_projected, to_geographic = network_elevation._transformers()
    expected = test["expect"]["rows"]
    for edge in _given(test, "int_trail_network__edges"):
        points = network_elevation.edge_sample_points(_coordinates(edge), to_projected, to_geographic)
        rows = sorted((row for row in expected if row["edge_id"] == edge["edge_id"]), key=lambda row: row["sample_index"])
        assert [row["sample_index"] for row in rows] == list(range(len(points))), edge["edge_id"]
        for row, (lon, lat) in zip(rows, points):
            assert row.get("lon", lon) == lon and row.get("lat", lat) == lat, (edge["edge_id"], row)


@pytest.mark.parametrize("test", _on("int_elevation__dem_points"), ids=lambda test: test["name"])
def test_each_dem_points_unit_test_asks_in_publish_vector_datas_order(test):
    """export_elevation.py's walk first, then export_network_elevation.build's one call: edges by edge_index."""
    at = sorted(_given(test, "int_elevation__sample_points"), key=lambda row: row["sample_index"])
    edges = sorted(_given(test, "int_elevation__edge_sample_points"), key=lambda row: (row["edge_index"], row["sample_index"]))
    python = [(row["line_id"], row["sample_index"]) for row in at] + [(row["edge_id"], row["sample_index"]) for row in edges]
    expected = sorted(test["expect"]["rows"], key=lambda row: row["ask_order"])
    assert [(row["line_id"], row["sample_index"]) for row in expected] == python
    assert [row["ask_order"] for row in expected] == list(range(len(python)))


# --- int_elevation__edge_samples ---------------------------------------------------


def _read_at_own_point(test: dict) -> dict[tuple, float | None]:
    """Each sample's DEM answer as the Python has it, read at the sample's own point; a row at another point is none."""
    dem = {(row["line_id"], row["sample_index"]): row for row in _given(test, "stg_derived__dem_samples")}
    answers = {}
    for point in _given(test, "int_elevation__edge_sample_points"):
        row = dem.get((point["edge_id"], point["sample_index"]))
        read = row is not None and (row["lon"], row["lat"]) == (point["lon"], point["lat"])
        answers[(point["edge_id"], point["sample_index"])] = row["elevation_m"] if read else None
    return answers


def _whole_feet(metres: float | None) -> int | None:
    """export_network_profile.edge_profile's rounding of one sample."""
    return None if metres is None else round(metres / elevation_gain.METERS_PER_FOOT)


@pytest.mark.parametrize(
    "test", [test for test in _on("int_elevation__edge_samples") if test["name"] not in SQL_ONLY], ids=lambda test: test["name"]
)
def test_each_edge_samples_unit_test_is_edge_profiles_rounding(test):
    answers = _read_at_own_point(test)
    dem = {(row["line_id"], row["sample_index"]): row["elevation_m"] for row in _given(test, "stg_derived__dem_samples")}
    assert answers == dem, "the Python only ever has its own points' answers; name the test in SQL_ONLY"
    for row in test["expect"]["rows"]:
        assert row["elevation_ft"] == _whole_feet(answers[(row["edge_id"], row["sample_index"])]), row


@pytest.mark.parametrize("name", sorted(SQL_ONLY))
def test_each_sql_only_unit_test_is_one_a_trusting_reader_would_answer_differently(name):
    """The SQL lends no sample a DEM answer read elsewhere; a reader that trusted the table would publish one."""
    (test,) = [test for test in _unit_tests() if test["name"] == name]
    trusting = {(row["line_id"], row["sample_index"]): row["elevation_m"] for row in _given(test, "stg_derived__dem_samples")}
    own = _read_at_own_point(test)
    assert own != trusting
    for row in test["expect"]["rows"]:
        key = (row["edge_id"], row["sample_index"])
        assert row["elevation_ft"] == _whole_feet(own[key])
    assert any(
        row["elevation_ft"] != _whole_feet(trusting[(row["edge_id"], row["sample_index"])]) for row in test["expect"]["rows"]
    )


# --- int_elevation__edge_climbs ----------------------------------------------------


@pytest.mark.parametrize("test", _on("int_elevation__edge_climbs"), ids=lambda test: test["name"])
def test_each_edge_climbs_unit_test_is_edge_climb(test):
    """export_network_elevation.edge_climb over each edge's samples in order, and build()'s measured and partial."""
    samples = _given(test, "int_elevation__edge_samples")
    expected = {row["edge_id"]: row for row in test["expect"]["rows"]}
    assert set(expected) == {edge["edge_id"] for edge in _given(test, "int_trail_network__edges")}
    for edge_id, row in expected.items():
        window = [
            s["elevation_m"] for s in sorted((s for s in samples if s["edge_id"] == edge_id), key=lambda s: s["sample_index"])
        ]
        climb = network_elevation.edge_climb(window)
        python = {
            "sample_count": len(window),
            "measured_sample_count": sum(value is not None for value in window),
            "gain_ft": None if climb is None else climb[0],
            "loss_ft": None if climb is None else climb[1],
            "measured": climb is not None,
            "partially_covered": climb is not None and any(value is None for value in window),
        }
        assert {name: row[name] for name in row if name in python} == {name: python[name] for name in row if name in python}, (
            edge_id
        )


# --- the seam ----------------------------------------------------------------------


def _published_profiles(test: dict, edges: list[dict]) -> list[list | None]:
    """Each edge's published profile, as edge_profile publishes it: its samples in order, or None with no answer."""
    samples = _given(test, "int_elevation__edge_samples")
    profiles = []
    for edge in edges:
        values = [
            s["elevation_ft"]
            for s in sorted((s for s in samples if s["edge_id"] == edge["edge_id"]), key=lambda s: s["sample_index"])
        ]
        profiles.append(values if any(value is not None for value in values) else None)
    return profiles


def _summary(rows: list[dict]) -> dict:
    """measure_seams' summary of per-node rows, its percentiles by its own _percentile."""
    steps = [row["step_ft"] for row in rows if row.get("step_ft") is not None]
    return {
        "shared_nodes": len(rows),
        "coincident_ends": sum(1 for row in rows if row["coincident"]),
        "measured_nodes": len(steps),
        "nodes_with_a_step": sum(1 for step in steps if step > 0),
        "steps_over_dead_band": sum(1 for step in steps if step >= network_profile.DEFAULT_THRESHOLD_FT),
        "step_ft_p50": round(network_profile._percentile(steps, 0.50), 1),
        "step_ft_p95": round(network_profile._percentile(steps, 0.95), 1),
        "step_ft_max": round(max(steps), 1) if steps else 0.0,
    }


@pytest.mark.parametrize("test", _on("int_elevation__seam_nodes"), ids=lambda test: test["name"])
def test_each_seam_nodes_unit_test_sums_to_measure_seams(test):
    """measure_seams over the given edges, their published coordinates and profiles: the expected per-node rows,
    summed as it sums them, are its answer."""
    edges = _given(test, "int_trail_network__edges")
    graph = [{"from": edge["from_node"], "to": edge["to_node"]} for edge in edges]
    python = network_profile.measure_seams(graph, [_coordinates(edge) for edge in edges], _published_profiles(test, edges))
    assert _summary(test["expect"]["rows"]) == python


@pytest.mark.parametrize("test", _on("int_elevation__seam_measurement"), ids=lambda test: test["name"])
def test_each_seam_measurement_unit_test_is_measure_seams_summary(test):
    (expected,) = test["expect"]["rows"]
    assert expected == _summary(_given(test, "int_elevation__seam_nodes"))


# --- the writers -------------------------------------------------------------------


def _dumps(entries: list) -> str:
    """write_artifact's json.dumps, both exporters'."""
    return json.dumps(entries, separators=(",", ":"))


@pytest.mark.parametrize("test", _on("pub_trail_graph_elevation"), ids=lambda test: test["name"])
def test_each_trail_graph_elevation_unit_test_is_write_artifacts_array(test):
    """The climbs in edge order, a missing or unmeasured one None; and None where the edge's source may not publish,
    the marts' rule (pipeline/ELT.md, "The eleven marts"), which no graph edge is expected to meet."""
    climbs = {row["edge_id"]: row for row in _given(test, "int_elevation__edge_climbs")}
    may = {row["source_key"]: row["may_publish"] for row in _given(test, "int_sources__publication")}
    entries = []
    for edge in sorted(_given(test, "int_trail_network__edges"), key=lambda edge: edge["edge_index"]):
        climb = climbs.get(edge["edge_id"])
        published = climb is not None and climb["gain_ft"] is not None and may.get(edge["source_key"]) is True
        entries.append([climb["gain_ft"], climb["loss_ft"]] if published else None)
    assert test["expect"]["rows"] == [{"climbs_json": _dumps(entries)}]


@pytest.mark.parametrize("test", _on("pub_trail_graph_profile"), ids=lambda test: test["name"])
def test_each_trail_graph_profile_unit_test_is_write_artifacts_array(test):
    rows = _given(test, "elevation")
    entries = []
    for edge in sorted(_given(test, "int_trail_network__edges"), key=lambda edge: edge["edge_index"]):
        values = [
            row["elevation_ft"] for row in sorted((r for r in rows if r["line_id"] == edge["edge_id"]), key=lambda r: r["seq"])
        ]
        values = [None if value is None else int(value) for value in values]
        entries.append(values if any(value is not None for value in values) else None)
    assert test["expect"]["rows"] == [{"profiles_json": _dumps(entries)}]


# --- parity.py's graph families ----------------------------------------------------


def test_parity_pairs_a_companion_arrays_entries_by_their_place_and_reports_the_one_that_moved():
    family = parity.FAMILIES["trail_graph_elevation"]
    old = parity._by_edge([[12, 3], None, [0, 0]])
    assert parity.differences(old, family.new_shape([[12, 3], None, [0, 0]], Path("x")), family) == []
    ((what, before, after),) = parity.differences(old, family.new_shape([[12, 3], [0, 0], [0, 0]], Path("x")), family)
    assert what == "edge_index 1"
    assert (json.loads(before)["entry"], json.loads(after)["entry"]) == (None, [0, 0])


def test_parity_reads_the_graph_the_build_made_from_its_edges(tmp_path):
    """The old side's trail_graph.json and trail_graph_geometry.json are int_trail_network__edges' rows, in edge order."""
    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema intermediate")
        con.execute(
            "create table intermediate.int_trail_network__edges"
            " (edge_index integer, source_key varchar, from_node integer, to_node integer, geom_geojson varchar)"
        )
        con.execute(
            "insert into intermediate.int_trail_network__edges values"
            ' (1, \'b\', 1, 2, \'{"type": "LineString", "coordinates": [[-74.1, 41.1], [-74.2, 41.2]]}\'),'
            ' (0, \'a\', 0, 1, \'{"type": "LineString", "coordinates": [[-74.0, 41.0], [-74.1, 41.1]]}\')'
        )
    graph, geometry = parity._graph_edges(warehouse)
    assert graph == {"edges": [{"source": "a", "from": 0, "to": 1}, {"source": "b", "from": 1, "to": 2}]}
    assert geometry == [[[-74.0, 41.0], [-74.1, 41.1]], [[-74.1, 41.1], [-74.2, 41.2]]]
