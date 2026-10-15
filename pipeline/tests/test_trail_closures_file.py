"""conditions/trail_closures.json is wired as conditions/hazard_areas.json is, and its cut can never stop the hourly build.

Decisions 184 and 187 (the maintainer's polls of 2026-10-11): build #1152 — Move OPRHP's temporary closures onto the conditions clock, where a
safety layer belongs — in its shape C for every club closure, drawn by S6. The file's rows and its cut are held
by dbt unit tests (models/publish/_publish__conditions.yml, models/intermediate/closures/_closures__intermediate.yml);
this holds what those cannot see: its exposure, the one home its rows come from, and where the step that hands the cut
its lines runs in each lane.
"""

import re
from pathlib import Path

import yaml

from build_marts import STEPS, Paths, plan

PIPELINE = Path(__file__).resolve().parent.parent
DBT = PIPELINE / "dbt"
PUBLISH = DBT / "models" / "publish"
WRITER = PUBLISH / "pub_conditions_trail_closures.sql"
CUT = DBT / "models" / "intermediate" / "closures" / "int_closures__area_trail_cuts.sql"
AREAS = DBT / "models" / "intermediate" / "closures" / "int_closures__trail_closure_areas.sql"
WORKFLOWS = PIPELINE.parent / ".github" / "workflows"
PATHS = Paths(warehouse=Path("/w/warehouse.duckdb"), processed_dir=Path("/w/processed"), raw_dir=Path("/w/raw"))
STEP = "step_closure_trail_lines"
REF = re.compile(r"ref\(\s*'([a-z0-9_]+)'")


def _exposures() -> dict[str, dict]:
    found = {}
    for path in sorted(PUBLISH.glob("*.yml")):
        for exposure in yaml.safe_load(path.read_text(encoding="utf-8")).get("exposures") or []:
            found[exposure["name"]] = exposure
    return found


def test_the_exposure_names_the_phones_key_on_the_hourly_clock():
    exposure = _exposures()["conditions_trail_closures_json"]

    assert exposure["config"]["meta"] == {"r2_keys": ["conditions/trail_closures.json"], "format": "json", "cadence": "hourly"}
    assert "ref('pub_conditions_trail_closures')" in exposure["depends_on"]


def test_the_writer_keeps_its_last_file_and_takes_its_rows_from_the_notices_writer_alone():
    """ONE HOME FOR EVERY RULE: which rows obstruct, the row shape and the dates are pub_conditions_notices'; the only
    other thing the writer reads is the cut, which also carries each drawn area's own outline for the same-closure rule
    (the review of 2026-10-15, thread 4279223668), and it reads no mart or source of its own. Reading
    int_closures__trail_closure_areas beside the cut, which already reads it, is the rejoin dbt_project_evaluator's
    fct_rejoining_of_upstream_concepts fails."""
    sql = WRITER.read_text(encoding="utf-8")

    assert "location='conditions_trail_closures.json'" in sql
    assert "meta={'when_empty': 'keep_last_file'}" in sql
    assert set(REF.findall(sql)) == {"pub_conditions_notices", "int_closures__area_trail_cuts"}
    assert "source(" not in sql


def test_every_geos_operation_on_the_hourly_path_before_the_writers_is_tried_rather_than_raised():
    """The areas build in stage A and the cut in what the step's table unblocks, where a failure stops every conditions
    file of the hour (build_marts.py's docstring, "ONE SOURCE OR ONE WRITER NEVER STOPS THE REST")."""
    areas = AREAS.read_text(encoding="utf-8")
    cut = CUT.read_text(encoding="utf-8")

    assert "try(st_makevalid(st_geomfromgeojson(marts.geom_geojson)))" in areas
    assert "try(st_collectionextract(geom, 3))" in areas
    assert "try(st_intersection(lines.geom, areas.geom))" in cut
    assert "try({{ notice_phone_geometry('geom') }})" in cut
    assert "try({{ notice_phone_geometry('areas.geom', grown=false) }})" in cut, "decision 191's shade"


def test_a_shade_is_the_area_as_its_source_drew_it_never_grown():
    """Decision 191: the hatch must not reach past the closure's edge onto an open trail, which the 100 m growth
    conditions/notices.json gives an area for a planned route would. The shade comes from the cut, which reads the
    source's own area (int_closures__trail_closure_areas), and the macro's ungrown branch grows nothing."""
    cut = CUT.read_text(encoding="utf-8")
    macro = (DBT / "macros" / "notice_phone_geometry.sql").read_text(encoding="utf-8")
    ungrown = macro.split("{%- else %}", 1)[1].split("{%- endif %}", 1)[0]

    assert "ref('int_closures__trail_closure_areas')" in cut
    assert "st_buffer" not in ungrown and "notice_area_m" not in ungrown
    assert "st_simplifypreservetopology({{ framed }}, 10)" in ungrown


def test_an_hour_with_no_lines_shades_no_area():
    """With no lines nothing says which areas have a trail inside, so the cut answers no row at all (its header), and
    the writer, which keeps an area only with a row of the cut, leaves every area out that hour."""
    cut = CUT.read_text(encoding="utf-8")
    writer = WRITER.read_text(encoding="utf-8")

    assert "having count(*) > 0" in cut and "cross join read_lines" in cut
    assert "or (closing.shape = 'area' and cuts.notice_id is not null)" in writer


def test_the_step_reads_the_restored_lines_in_the_hourly_lane_and_the_fixtures_geojson_in_a_fixture_build():
    def args(**options) -> tuple[str, ...] | None:
        found = [run for run in plan(STEPS, dbt="dbt", python="python", paths=PATHS, **options) if run.label == STEP]
        return found[0].argv[2:] if found else None

    assert args(fixtures=False, lane="hourly") == (
        "--warehouse",
        "/w/warehouse.duckdb",
        "--lines",
        "/w/raw/closure_trail_lines/lines.parquet",
    )
    assert args(fixtures=True) == (
        "--warehouse",
        "/w/warehouse.duckdb",
        "--geojson",
        "/w/raw/closure_trail_lines/nearby_trails.geojson",
        "--at-geojson",
        "/w/raw/closure_trail_lines/trails.geojson",
        "--release",
        "fixture",
    )
    assert args(fixtures=False, lane="monthly") is None, "the monthly lane builds nothing the step's table feeds"


def test_the_hourly_lane_cuts_after_stage_a_and_before_its_writers():
    labels = [run.label for run in plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly")]

    stage_a = next(position for position, label in enumerate(labels) if label.startswith("stage A"))
    assert stage_a < labels.index(STEP) < labels.index("what derived.closure_trail_lines unblocks")
    assert labels.index("what derived.closure_trail_lines unblocks") < labels.index("the hourly lane's pub_ writers")


def test_no_workflow_leaves_the_step_out():
    """--without-step would hold back its writer, and with it every line and point closure, which need no lines."""
    for path in sorted(WORKFLOWS.glob("*.yml")):
        assert f"--without-step {STEP}" not in path.read_text(encoding="utf-8"), path.name
