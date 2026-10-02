"""The elevation family's SQL answers what export_elevation.py answers, on the same rows (#1793, stage 3).

elevation_profile.json moved to dbt (pipeline/ELT.md's ledger rows EL05-EL09):
the walk and its miles to int_elevation__sample_points, the clip, the seams
and the rounding to int_elevation__profile, and the DEM read to the Python
step step_dem_sampling.py, which reads through export_elevation's own
sampler. Until stage 5 deletes the Python, export_elevation.py still writes
the file publish.py uploads, so the two are held together here:

- the elevation_* vars the models read are export_elevation.py's constants;
- export_elevation's own functions, run over each unit test's given rows,
  give every expected row: sample_points_along_parts and CalibratedPart.
  mile_at for the walk, profile_records for the profile. A dbt 2.0.6 unit
  test compares a DOUBLE only to one decimal place, so the published numbers
  travel as text there and are compared exactly; along_m is held exactly here;
- SQL_ONLY names the one unit test the Python has no counterpart for, and
  holds that a reader trusting its DEM rows would answer it differently, so
  the name cannot hide a test that agrees;
- the fixture DEM make_dbt_fixtures.py writes reads the way a 3DEP cell
  reads, and gives the fixture profile both kinds of gap;
- step_dem_sampling writes the sampler's own answer at every sample point,
  in the walk's order, a gap as NULL and never as NaN, and refuses what it
  cannot write honestly.

parity.py's elevation family compares the two whole files in CI's dbt job.
"""

import json
import math
from pathlib import Path

import duckdb
import numpy as np
import pytest
import rasterio
import yaml
from shapely import wkt as shapely_wkt

import export_elevation
import make_dbt_fixtures
import parity
import step_dem_sampling
from tests.conftest import spatial_connection

DBT = Path(__file__).parent.parent / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "elevation" / "_elevation__unit_tests.yml"

# The unit test the Python has nothing to hold it to, and why: export_elevation.py
# reads the DEM at each sample's own point in the same run, so it has no table
# that could answer a sample from another point or leave one unanswered.
SQL_ONLY = {"int_elevation__profile_refuses_an_elevation_read_at_another_point"}

# The columns of int_elevation__profile a unit test can hold to profile_records.
PROFILE_COLUMNS = ("seq", "distance_mi_text", "elevation_ft_text", "part_start")


def _unit_tests() -> list[dict]:
    return yaml.safe_load(UNIT_TESTS.read_text())["unit_tests"]


def _on(model: str) -> list[dict]:
    return [test for test in _unit_tests() if test["model"] == model]


def _given(test: dict, model: str) -> dict:
    return next(given for given in test["given"] if given["input"] == f"ref('{model}')")


@pytest.fixture(scope="module")
def con():
    connection = spatial_connection()
    yield connection
    connection.close()


def test_the_elevation_vars_are_export_elevations_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["elevation_sample_interval_m"] == export_elevation.SAMPLE_INTERVAL_METERS
    assert variables["elevation_metres_per_foot"] == export_elevation.METERS_PER_FOOT
    assert variables["mile_axis_metres_per_mile"] == export_elevation.METERS_PER_MILE


def test_every_unit_test_is_on_a_model_this_file_holds_to_the_python():
    names = {test["name"] for test in _unit_tests()}
    assert names == {test["name"] for test in _on("int_elevation__sample_points") + _on("int_elevation__profile")}
    assert SQL_ONLY <= names


def _mile_axis(con, test: dict) -> list[dict]:
    """The test's mile-axis pieces, its `format: sql` run as dbt runs it, with the geometry as WKT for shapely."""
    sql = _given(test, "int_trail_lines__mile_axis")["rows"]
    relation = con.sql(f"select piece_id, st_astext(geom_5070) as geom_wkt, length_m, anchor_along_mi, anchor_mile from ({sql})")
    return sorted((dict(zip(relation.columns, row)) for row in relation.fetchall()), key=lambda row: row["piece_id"])


@pytest.mark.parametrize("test", _on("int_elevation__sample_points"), ids=lambda test: test["name"])
def test_each_sample_points_unit_test_is_export_elevations_walk(con, test):
    """sample_points_along_parts and CalibratedPart.mile_at over the test's pieces: every expected row, exactly."""
    pieces = _mile_axis(con, test)
    assert [row["piece_id"] for row in pieces] == list(range(len(pieces))), "the walk runs the pieces in piece_id order"
    lines = [shapely_wkt.loads(row["geom_wkt"]) for row in pieces]
    for row, line in zip(pieces, lines):
        assert row["length_m"] == line.length, f"piece {row['piece_id']}'s length_m is not its geometry's length"
    parts = [
        export_elevation.CalibratedPart(line, np.array(row["anchor_along_mi"]), np.array(row["anchor_mile"]))
        for row, line in zip(pieces, lines)
    ]
    offsets, cumulative = [], 0.0
    for line in lines:
        offsets.append(cumulative)
        cumulative += line.length

    samples = export_elevation.sample_points_along_parts(lines, export_elevation.SAMPLE_INTERVAL_METERS)
    python = [
        {
            "sample_index": index,
            "piece_id": part,
            "along_m": distance_m - offsets[part],
            "distance_mi_text": f"{round(parts[part].mile_at(distance_m - offsets[part]), 3):.3f}",
        }
        for index, (distance_m, _point, part) in enumerate(samples)
    ]
    assert python == test["expect"]["rows"]


def _dem_rows(con, test: dict) -> dict[tuple, dict]:
    """The test's DEM rows by (line_id, sample_index); a `format: sql` input is run in DuckDB, as dbt runs it."""
    given = _given(test, "stg_derived__dem_samples")
    rows = given["rows"]
    if given.get("format") == "sql":
        relation = con.sql(f"select line_id, sample_index, lon, lat, elevation_m from ({rows})")
        rows = [dict(zip(relation.columns, row)) for row in relation.fetchall()]
    return {(row["line_id"], row["sample_index"]): row for row in rows}


def _python_profile(con, test: dict, *, trust_every_row: bool = False) -> list[dict]:
    """profile_records over the test's sample points, each with the DEM's answer at its own point.

    `trust_every_row` takes a DEM row as the sample's answer wherever it was
    read, which is what a reader of that table would do without the SQL's
    point check."""
    points = sorted(_given(test, "int_elevation__sample_points")["rows"], key=lambda row: row["sample_index"])
    dem = _dem_rows(con, test)

    def elevation(point):
        row = dem.get((point["line_id"], point["sample_index"]))
        if row is None or not (trust_every_row or (row["lon"], row["lat"]) == (point["lon"], point["lat"])):
            return None
        return row["elevation_m"]

    records, _clipped = export_elevation.profile_records(
        (float(point["distance_mi_text"]), elevation(point), point["piece_id"]) for point in points
    )
    return [
        {
            "seq": seq,
            "distance_mi_text": f"{record['distance_mi']:.3f}",
            "elevation_ft_text": None if record["elevation_ft"] is None else f"{record['elevation_ft']:.1f}",
            "part_start": record.get("part_start", False),
        }
        for seq, record in enumerate(records)
    ]


def _restricted(rows: list[dict], like: list[dict]) -> list[dict]:
    """Each row cut to the profile columns its counterpart in `like` names."""
    return [{name: row[name] for name in PROFILE_COLUMNS if name in other} for row, other in zip(rows, like)]


@pytest.mark.parametrize(
    "test", [test for test in _on("int_elevation__profile") if test["name"] not in SQL_ONLY], ids=lambda test: test["name"]
)
def test_each_profile_unit_test_is_export_elevations_profile_records(con, test):
    """The clip, the seams and the rounding, by the Python's own loop: the same records in the same order."""
    expected = test["expect"]["rows"]
    python = _python_profile(con, test)
    assert len(python) == len(expected)
    assert _restricted(python, expected) == _restricted(expected, expected)
    assert all(row.get("dem_read", True) for row in expected), "every sample here was read at its own point"


@pytest.mark.parametrize("name", sorted(SQL_ONLY))
def test_each_sql_only_unit_test_is_one_a_trusting_reader_would_answer_differently(con, name):
    """The SQL lends no sample a DEM answer read elsewhere; a reader that trusted the table would publish one."""
    (test,) = [test for test in _unit_tests() if test["name"] == name]
    expected = test["expect"]["rows"]
    assert any(row["dem_read"] is False for row in expected)
    assert _restricted(_python_profile(con, test, trust_every_row=True), expected) != _restricted(expected, expected)


# --- The fixture DEM ------------------------------------------------------------


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    raw = tmp_path_factory.mktemp("raw")
    make_dbt_fixtures.write_fixtures(raw)
    return raw


def test_the_fixture_dem_reads_as_a_3dep_cell_does(fixtures):
    """A float32 GeoTIFF in NAD83 with a declared nodata, whose index pins its edition, as fetch_elevation.py's do."""
    (entry,) = json.loads((fixtures / make_dbt_fixtures.ELEVATION_FIXTURE_INDEX).read_text())
    assert entry["url"] == (fixtures / make_dbt_fixtures.ELEVATION_FIXTURE_TILE).resolve().as_posix()
    with rasterio.open(entry["url"]) as tile:
        assert (tile.driver, tile.count, tile.dtypes[0], tile.crs.to_epsg()) == ("GTiff", 1, "float32", 4269)
        assert tile.nodata == make_dbt_fixtures.ELEVATION_FIXTURE_NODATA
        assert list(tile.bounds) == pytest.approx(entry["bounds"], abs=1e-12)
        values = tile.read(1)
    for row in make_dbt_fixtures.ELEVATION_FIXTURE_NODATA_ROWS:
        assert (values[row] == make_dbt_fixtures.ELEVATION_FIXTURE_NODATA).all()
    assert values[0, 0] == np.float32(make_dbt_fixtures._elevation_fixture_metres(0, 0))
    assert export_elevation._sources_with_no_pinned_edition(fixtures / make_dbt_fixtures.ELEVATION_FIXTURE_INDEX) == frozenset()


def test_the_fixture_dem_gives_the_fixture_profile_both_kinds_of_gap(fixtures, tmp_path):
    """build_profile on the fixtures: real elevations, nulls in the tile's nodata rows, nulls past its edge."""
    index = tmp_path / "tile_index.json"
    index.write_text((fixtures / make_dbt_fixtures.ELEVATION_FIXTURE_INDEX).read_text())
    records, _ = export_elevation.build_profile(
        fixtures / "centerline.geojson",
        fixtures / "half_mile_points_from_springer.geojson",
        index,
        export_elevation.SAMPLE_INTERVAL_METERS,
    )
    nulls = [index for index, record in enumerate(records) if record["elevation_ft"] is None]
    assert len(records) == 45
    # Two in the nodata rows on the first segment, six past the tile's north edge on the second.
    assert nulls == [12, 13, *range(39, 45)]
    assert [index for index, record in enumerate(records) if record.get("part_start")] == [0, 23]


def test_the_fixture_refuses_to_overwrite_a_real_dem_index(tmp_path):
    """A workspace that fetched the DEM index keeps it: export_elevation.py would read a fixture index as the real one."""
    (tmp_path / "elevation").mkdir()
    (tmp_path / make_dbt_fixtures.ELEVATION_FIXTURE_INDEX).write_text("[]")
    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        make_dbt_fixtures.write_fixtures(tmp_path)
    assert (tmp_path / make_dbt_fixtures.ELEVATION_FIXTURE_INDEX).read_text() == "[]"


# --- step_dem_sampling -------------------------------------------------------------

# Inside the fixture tile, in its nodata rows, past its north edge, and inside again.
STEP_POINTS = [("AT", 0, -74.0, 41.0), ("AT", 1, -74.0, 41.0029), ("AT", 2, -73.99, 41.0145), ("AT", 3, -73.99, 41.01)]


def _warehouse_with_points(path: Path, points: list[tuple[str, int, float, float]]) -> Path:
    with duckdb.connect(str(path)) as warehouse:
        warehouse.execute("create schema intermediate")
        warehouse.execute(
            "create table intermediate.int_elevation__sample_points (line_id varchar, sample_index integer, lon double, lat double)"
        )
        warehouse.executemany("insert into intermediate.int_elevation__sample_points values (?, ?, ?, ?)", points)
    return path


def test_step_dem_sampling_writes_the_samplers_own_answer_at_every_point(tmp_path, fixtures):
    warehouse = _warehouse_with_points(tmp_path / "warehouse.duckdb", list(reversed(STEP_POINTS)))
    index = tmp_path / "tile_index.json"
    index.write_text((fixtures / make_dbt_fixtures.ELEVATION_FIXTURE_INDEX).read_text())

    assert step_dem_sampling.main(["--warehouse", str(warehouse), "--index", str(index)]) == 0

    sampler = export_elevation.ElevationSampler.for_index(index, cache=False)
    try:
        answers = sampler.sample_many([(lon, lat) for _, _, lon, lat in STEP_POINTS])
    finally:
        sampler.close()
    assert [answer is None for answer in answers] == [False, True, True, False]
    with duckdb.connect(str(warehouse), read_only=True) as written:
        rows = written.execute(
            "select line_id, sample_index, geometry, elevation_m from derived.dem_samples order by sample_index"
        ).fetchall()
        nan_rows = written.execute("select count(*) from derived.dem_samples where isnan(elevation_m)").fetchone()[0]
        types = dict(
            written.execute(
                "select column_name, data_type from information_schema.columns where table_name = 'dem_samples'"
            ).fetchall()
        )
    assert [(line, sample, elevation) for line, sample, _geometry, elevation in rows] == [
        (line, sample, answer) for (line, sample, _lon, _lat), answer in zip(STEP_POINTS, answers)
    ]
    assert [tuple(json.loads(geometry)["coordinates"]) for *_, geometry, _elevation in rows] == [
        (lon, lat) for *_, lon, lat in STEP_POINTS
    ]
    assert nan_rows == 0, "a gap is NULL, never a NaN that a reader would take for a number"
    assert (types["_loaded_at"], types["elevation_m"]) == ("TIMESTAMP WITH TIME ZONE", "DOUBLE")


def test_step_dem_sampling_asks_in_the_walks_order(tmp_path, fixtures, monkeypatch):
    """The cache answers a second point within 0.11 m of a first with the first's pixel, so the order is build_profile's."""
    warehouse = _warehouse_with_points(tmp_path / "warehouse.duckdb", list(reversed(STEP_POINTS)))
    asked = []

    def sample_many(self, points):
        asked.extend(points)
        return [None] * len(points)

    monkeypatch.setattr(export_elevation.ElevationSampler, "sample_many", sample_many)
    step_dem_sampling.main(["--warehouse", str(warehouse), "--index", str(fixtures / make_dbt_fixtures.ELEVATION_FIXTURE_INDEX)])
    assert asked == [(lon, lat) for *_, lon, lat in STEP_POINTS]


def test_step_dem_sampling_refuses_a_warehouse_without_its_input(tmp_path, fixtures):
    warehouse = tmp_path / "warehouse.duckdb"
    duckdb.connect(str(warehouse)).close()
    with pytest.raises(SystemExit, match="int_elevation__sample_points is not in the warehouse"):
        step_dem_sampling.main(
            ["--warehouse", str(warehouse), "--index", str(fixtures / make_dbt_fixtures.ELEVATION_FIXTURE_INDEX)]
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, True], ids=["nan", "infinity", "bool"])
def test_step_dem_sampling_refuses_an_answer_that_is_not_an_elevation(tmp_path, fixtures, monkeypatch, value):
    warehouse = _warehouse_with_points(tmp_path / "warehouse.duckdb", STEP_POINTS[:1])
    monkeypatch.setattr(export_elevation.ElevationSampler, "sample_many", lambda self, points: [value] * len(points))
    with pytest.raises(SystemExit, match="an elevation is a finite number or None"):
        step_dem_sampling.main(
            ["--warehouse", str(warehouse), "--index", str(fixtures / make_dbt_fixtures.ELEVATION_FIXTURE_INDEX)]
        )
    with duckdb.connect(str(warehouse), read_only=True) as written:
        assert written.execute("select count(*) from information_schema.tables where table_schema = 'derived'").fetchone()[0] == 0


# --- parity.py's elevation family ------------------------------------------------


def test_parity_pairs_elevation_records_by_their_mile_and_reports_the_one_that_moved():
    family = parity.FAMILIES["elevation"]
    old = {
        "samples": [{"distance_mi": 0.0, "elevation_ft": 900.1, "part_start": True}, {"distance_mi": 0.016, "elevation_ft": None}]
    }
    new = {
        "samples": [{"distance_mi": 0.0, "elevation_ft": 900.1, "part_start": True}, {"distance_mi": 0.016, "elevation_ft": 0.0}]
    }
    assert parity.differences(old, old, family) == []
    ((what, before, after),) = parity.differences(old, new, family)
    assert what == "distance_mi 0.016"
    assert (json.loads(before)["elevation_ft"], json.loads(after)["elevation_ft"]) == (None, 0.0)


def test_parity_reads_elevation_profile_json_as_the_bare_array_it_is(tmp_path, monkeypatch):
    profile = [{"distance_mi": 0.0, "elevation_ft": 900.1, "part_start": True}]
    written = tmp_path / "elevation_profile.json"
    written.write_text(json.dumps(profile) + "\n")
    asked_for = []

    def old(raw_dir):
        asked_for.append(raw_dir)
        return {"samples": profile}

    family = parity.FAMILIES["elevation"]
    monkeypatch.setitem(parity.FAMILIES, "elevation", parity.Family(**{**vars(family), "old": old}))
    assert parity.main(["elevation", "--new", str(written), "--raw-dir", str(tmp_path)]) == 0
    assert asked_for == [tmp_path]
