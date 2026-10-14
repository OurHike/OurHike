"""step_closure_trail_lines.py lands the release's trail lines that may run inside an area closure, and never stops the
hourly build for want of them.

Decision 187 (S6, the maintainer's poll of 2026-10-11): int_closures__area_trail_cuts crosses out an area closure's trails
where they run inside it, from derived.closure_trail_lines, the A.T.'s own among them since decision 192. A failed step
stops build_marts.py's whole hourly build, every conditions file with it (its docstring, "ONE SOURCE OR ONE WRITER NEVER
STOPS THE REST"), so an hour with no lines, or lines that will not read, lands an empty table and says so instead; and
since decision 191 shades an area no trail runs inside, an hour that did read lines never lands an empty one.
"""

import json

import duckdb
import pytest

import prepare_closure_trail_lines as prepare
import step_closure_trail_lines as step

#: An area closure's box, as int_closures__trail_closure_areas carries it: NYS Parks' fixture "bridge washed out".
AREA = ("club_area:1", -73.975, 41.032, -73.965, 41.04)


def _warehouse(tmp_path, areas=(AREA,)):
    path = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute("create schema intermediate")
        con.execute(
            "create table intermediate.int_closures__trail_closure_areas "
            "(notice_id varchar, xmin double, ymin double, xmax double, ymax double)"
        )
        con.executemany("insert into intermediate.int_closures__trail_closure_areas values (?, ?, ?, ?, ?)", list(areas))
    return path


def _geojson(path, *lines):
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": line_id},
                        "geometry": {"type": "LineString", "coordinates": coordinates},
                    }
                    for line_id, coordinates in lines
                ],
            }
        )
    )
    return path


def _lines(tmp_path, *lines):
    source = _geojson(tmp_path / "nearby_trails.geojson", *lines)
    prepare.prepare(
        {prepare.NEARBY_KEY: source}, tmp_path / "prepared", release="2026-10-10-2", environment="ua", source_sha256s=None
    )
    return tmp_path / "prepared" / prepare.LINES_FILE


def _landed(warehouse):
    with duckdb.connect(str(warehouse)) as con:
        return con.execute("select release, line_id, geometry from derived.closure_trail_lines order by line_id").fetchall()


def test_only_the_lines_whose_box_meets_an_areas_box_are_landed(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    warehouse = _warehouse(tmp_path)
    lines = _lines(
        tmp_path,
        ("across", [[-73.97, 41.03], [-73.97, 41.035]]),
        ("on_its_edge", [[-73.98, 41.04], [-73.975, 41.045]]),
        ("beside_it", [[-73.98, 41.03], [-73.98, 41.035]]),
        ("far_away", [[-120.0, 45.0], [-120.0, 45.01]]),
    )

    assert step.main(["--warehouse", str(warehouse), "--lines", str(lines)]) == 0

    landed = _landed(warehouse)
    assert [line_id for _, line_id, _ in landed] == ["across", "on_its_edge"], (
        "a box that only touches the area's box may still touch the area, so it lands; the cut decides"
    )
    assert {release for release, _, _ in landed} == {"2026-10-10-2"}
    assert json.loads(landed[0][2]) == {"type": "LineString", "coordinates": [[-73.97, 41.03], [-73.97, 41.035]]}


def test_lines_read_with_none_near_an_area_land_the_files_first_line_so_the_table_says_they_were_read(
    tmp_path, monkeypatch, capsys
):
    """Decision 191 shades an area no trail runs inside, and an empty table is how the cut knows an hour had no lines
    to look with; so lines that were read never leave it empty, and every area is shaded rather than left out."""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    warehouse = _warehouse(tmp_path)
    lines = _lines(
        tmp_path,
        ("far_west", [[-120.0, 45.0], [-120.0, 45.01]]),
        ("far_east", [[-70.0, 44.0], [-70.0, 44.01]]),
    )

    assert step.main(["--warehouse", str(warehouse), "--lines", str(lines)]) == 0

    assert [line_id for _, line_id, _ in _landed(warehouse)] == ["far_east"], "the first by line id, and no other"
    out = capsys.readouterr().out
    assert "0 of release 2026-10-10-2's 2 trail lines" in out
    assert "to say the lines were read" in out
    assert "::warning" not in out


def test_no_lines_file_lands_an_empty_table_and_warns_on_the_runs_summary(tmp_path, monkeypatch, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    warehouse = _warehouse(tmp_path)

    assert step.main(["--warehouse", str(warehouse), "--lines", str(tmp_path / "absent.parquet")]) == 0

    assert _landed(warehouse) == []
    out = capsys.readouterr().out
    assert f"::warning title={step.NO_LINES_TITLE}::" in out
    assert "no area closure was cut or shaded this run" in out
    assert "none of the 1 reaches conditions/trail_closures.json, and every line and point closure still does" in out
    assert step.NO_LINES_TITLE in summary.read_text()


def test_a_lines_file_that_will_not_read_is_no_lines_and_never_a_failed_build(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    warehouse = _warehouse(tmp_path)
    broken = tmp_path / "lines.parquet"
    broken.write_bytes(b"not a parquet file")

    assert step.main(["--warehouse", str(warehouse), "--lines", str(broken)]) == 0

    assert _landed(warehouse) == []
    assert "could not be read" in capsys.readouterr().out


def test_a_lines_file_with_no_line_lands_none_and_says_so(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    warehouse = _warehouse(tmp_path)
    empty = tmp_path / "lines.parquet"
    with duckdb.connect() as con:
        con.execute(
            "copy (select 'r' as release, 'x' as line_id, 0.0 as xmin, 0.0 as ymin, 0.0 as xmax, 0.0 as ymax, "
            f"'{{}}' as geometry where false) to '{empty}' (format parquet)"
        )

    assert step.main(["--warehouse", str(warehouse), "--lines", str(empty)]) == 0

    assert _landed(warehouse) == []
    assert f"{empty} holds no line" in capsys.readouterr().out


def test_a_second_run_replaces_the_table(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    warehouse = _warehouse(tmp_path)
    lines = _lines(tmp_path, ("across", [[-73.97, 41.03], [-73.97, 41.035]]))
    step.main(["--warehouse", str(warehouse), "--lines", str(lines)])

    step.main(["--warehouse", str(warehouse), "--lines", str(tmp_path / "absent.parquet")])

    assert _landed(warehouse) == []


def test_the_fixture_build_prepares_a_geojson_first(tmp_path, monkeypatch):
    """Under --fixtures build_marts.py hands make_dbt_fixtures.py's nearby_trails.geojson, prepared by the same code the
    weather job runs."""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    warehouse = _warehouse(tmp_path)
    source = tmp_path / "fixture.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": "across"},
                        "geometry": {"type": "LineString", "coordinates": [[-73.97, 41.03], [-73.97, 41.035]]},
                    }
                ],
            }
        )
    )

    assert step.main(["--warehouse", str(warehouse), "--geojson", str(source), "--release", "fixture"]) == 0

    assert [(release, line_id) for release, line_id, _ in _landed(warehouse)] == [("fixture", "across")]


def test_the_fixture_build_prepares_the_ats_own_lines_beside_the_nearby_ones(tmp_path, monkeypatch):
    """Decision 192: the fixture's trails.geojson goes through the same preparation, so an A.T. line inside an area
    lands like any trail, and one far from every area does not."""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    warehouse = _warehouse(tmp_path)
    nearby = _geojson(tmp_path / "nearby.geojson", ("across", [[-73.97, 41.03], [-73.97, 41.035]]))
    at = _geojson(
        tmp_path / "at.geojson",
        ("centerline:chain:0", [[-73.967, 41.028], [-73.967, 41.045]]),
        ("side_trails:far", [[-121.0, 46.0], [-121.0, 46.01]]),
    )

    argv = ["--warehouse", str(warehouse), "--geojson", str(nearby), "--at-geojson", str(at), "--release", "fixture"]
    assert step.main(argv) == 0

    assert [line_id for _, line_id, _ in _landed(warehouse)] == ["across", "centerline:chain:0"]


def test_the_ats_file_is_refused_without_the_nearby_one(tmp_path):
    with pytest.raises(SystemExit):
        step.main(["--warehouse", str(_warehouse(tmp_path)), "--at-geojson", str(tmp_path / "at.geojson")])
