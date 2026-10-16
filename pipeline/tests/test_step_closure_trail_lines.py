"""step_closure_trail_lines.py lands the release's trail lines that may run inside an area closure, and never stops the
hourly build for want of them.

int_closures__area_trail_cuts crosses out an area closure's trails where they run inside it, from
derived.closure_trail_lines, the A.T.'s own among them. A failed step
stops build_marts.py's whole hourly build, every conditions file with it (its docstring, "ONE SOURCE OR ONE WRITER NEVER
STOPS THE REST"), so an hour with no lines, or lines that will not read, lands an empty table and says so instead; and
since an area no trail runs inside is shaded whole, an hour that did read lines never lands an empty one.
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
    """An area no trail runs inside is shaded whole, and an empty table is how the cut knows an hour had no lines
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
    """The fixture's trails.geojson goes through the same preparation, so an A.T. line inside an area
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


# --- the lines' release against the leg's current one: publish-conditions.yml restores the newest entry its branch can see, which need not be the leg's
# current release, so the step says when it is not, and never refuses the lines for it.

BASE = "https://data.example.org"
LATEST = f"{BASE}/environments/ua/latest.json"


def _latest(release):
    return {"release": release, "artifacts": {key: {"sha256": "0" * 64} for key in prepare.SOURCE_KEYS}}


def _across(tmp_path):
    return _lines(tmp_path, ("across", [[-73.97, 41.03], [-73.97, 41.035]]))


def test_lines_of_the_legs_current_release_say_so_and_warn_of_nothing(tmp_path, monkeypatch, capsys, requests_mock):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    requests_mock.get(LATEST, json=_latest("2026-10-10-2"))
    argv = ["--warehouse", str(_warehouse(tmp_path)), "--lines", str(_across(tmp_path)), "--leg", "ua", "--base", BASE]

    assert step.main(argv) == 0

    out = capsys.readouterr().out
    assert "::warning" not in out
    assert "area closures, the ua leg's current release" in summary.read_text()
    assert requests_mock.call_count == 1, "one read, never retried"
    assert requests_mock.last_request.headers["User-Agent"] == step.USER_AGENT


def test_lines_of_another_release_are_still_cut_against_and_warned_of_with_both_ids(tmp_path, monkeypatch, capsys, requests_mock):
    """An older release's lines differ from the current one's only where a release moved a trail, while refusing them
    would leave every area closure out of conditions/trail_closures.json for the hour: so they land, and it is said."""
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    requests_mock.get(LATEST, json=_latest("2026-10-16"))
    warehouse = _warehouse(tmp_path)
    argv = ["--warehouse", str(warehouse), "--lines", str(_across(tmp_path)), "--leg", "ua", "--base", BASE]

    assert step.main(argv) == 0

    assert [(release, line_id) for release, line_id, _ in _landed(warehouse)] == [("2026-10-10-2", "across")]
    out = capsys.readouterr().out
    assert f"::warning title={step.OTHER_RELEASE_TITLE}::" in out
    assert f"holds release 2026-10-10-2's trail lines, and {LATEST} names release 2026-10-16" in out
    assert "Every closure still publishes" in out
    page = summary.read_text()
    assert f"**{step.OTHER_RELEASE_TITLE}.**" in page
    assert "area closures, not the ua leg's current release, 2026-10-16" in page


@pytest.mark.parametrize(
    ("answer", "says"),
    [
        ({"status_code": 503}, "could not be read (HTTPError)"),
        ({"exc": __import__("requests").exceptions.ConnectTimeout}, "could not be read (ConnectTimeout)"),
        ({"text": "not json"}, "could not be read (JSONDecodeError)"),
        ({"json": {"release": None, "artifacts": {}}}, "names no release carrying nearby_trails.geojson and trails.geojson"),
        ({"json": _latest("../../etc")}, "could not be read (SystemExit)"),
    ],
)
def test_a_current_release_that_cannot_be_known_is_said_as_not_checked_and_never_fails_the_build(
    tmp_path, monkeypatch, capsys, requests_mock, answer, says
):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    requests_mock.get(LATEST, **answer)
    warehouse = _warehouse(tmp_path)
    argv = ["--warehouse", str(warehouse), "--lines", str(_across(tmp_path)), "--leg", "ua", "--base", BASE]

    assert step.main(argv) == 0

    assert [line_id for _, line_id, _ in _landed(warehouse)] == ["across"]
    assert "::warning" not in capsys.readouterr().out
    assert "whether it is the ua leg's current release was not checked: " in summary.read_text()
    assert says in summary.read_text()


def test_the_leg_and_the_base_come_from_the_build_steps_environment(tmp_path, monkeypatch, capsys, requests_mock):
    """publish-conditions.yml sets CLOSURE_LINES_LEG and DATA_BASE_URL on the build step, which build_marts.py's steps
    inherit."""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv(step.LEG_VARIABLE, "ua")
    monkeypatch.setenv("DATA_BASE_URL", BASE)
    requests_mock.get(LATEST, json=_latest("2026-10-16"))

    assert step.main(["--warehouse", str(_warehouse(tmp_path)), "--lines", str(_across(tmp_path))]) == 0

    assert f"::warning title={step.OTHER_RELEASE_TITLE}::" in capsys.readouterr().out


def test_nothing_is_asked_without_a_leg_nor_for_the_fixture_build(tmp_path, monkeypatch, requests_mock):
    """Every other test in this file, and build_marts.py --fixtures, which names release `fixture`."""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv(step.LEG_VARIABLE, raising=False)
    monkeypatch.setenv("DATA_BASE_URL", BASE)
    step.main(["--warehouse", str(_warehouse(tmp_path)), "--lines", str(_across(tmp_path))])
    source = _geojson(tmp_path / "fixture.geojson", ("across", [[-73.97, 41.03], [-73.97, 41.035]]))
    (tmp_path / "fixtures").mkdir()
    fixture = ["--warehouse", str(_warehouse(tmp_path / "fixtures")), "--geojson", str(source), "--release", "fixture"]
    step.main([*fixture, "--leg", "ua", "--base", BASE])

    assert requests_mock.call_count == 0


def test_a_leg_with_no_base_url_is_said_as_not_checked(tmp_path, monkeypatch, requests_mock):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.delenv("DATA_BASE_URL", raising=False)

    assert step.main(["--warehouse", str(_warehouse(tmp_path)), "--lines", str(_across(tmp_path)), "--leg", "ua"]) == 0

    assert requests_mock.call_count == 0
    assert "was not checked, as no DATA_BASE_URL was given" in summary.read_text()
