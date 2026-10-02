"""The suggested_hikes family's SQL answers what today's Python answers, on the same rows.

Stage 3 of #1793 — Rebuild the data platform as dlt → dbt: seven contracted
marts, a monthly refresh, published docs, and lighter phone downloads. The
Hike Finder hikes and the curated highlights moved to SQL (pipeline/ELT.md's
ledger, SH02 and SH04-SH14), and until stage 5 deletes the Python both are
live: parity.py compares the files the two write on the fixture warehouse in
CI. The fixture reaches few of the rules, because most of them are refusals,
so this holds the rest, model by model:

- the vars and the seed the models read are the Python's constants;
- each unit test's mocked seed is that seed file, row for row;
- the Python, run over each unit test's own rows, answers what the unit test
  expects: hike_problems() and difficulty_slug() for
  int_suggested_hikes__hike_finder, confirmed_photos() and photo_for() for
  int_suggested_hikes__photos, _grade() and published_route() for
  int_suggested_hikes__graded, build_document() for
  int_suggested_hikes__routed (the step's re-walk standing in for the snap
  and the search in track_ends(), which stay Python), resolve() and
  as_published() for int_suggested_hikes__highlights, and record_for() and
  split_record() for int_suggested_hikes__records, JSON text compared byte
  for byte;
- except where DELIBERATE says the SQL is stricter on purpose, each entry
  still a difference, so emptying the list turns this red.

dbt runs the other half: the unit tests hold the SQL to those expectations.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import export_highlights
import export_suggested_hikes as exporter
from lib import highlights as highlights_lib
from lib import hike_route_builder as builder
from lib import photo_store
from lib import trail_graph_route as router
from lib.hikefinder import SOURCE_KEY, hike_problems

DBT = Path(__file__).parent.parent / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "suggested_hikes" / "_suggested_hikes__unit_tests.yml"
SEED = DBT / "seeds" / "suggested_hikes" / "suggested_hike_difficulty_slugs.csv"

# The photographs the Python ships and int_suggested_hikes__photos refuses,
# by hike number, each for the reason that model's header gives. Each is a
# photograph whose attribution, the licence's condition, or whose key, the
# bucket's, would be wrong.
DELIBERATE_PHOTOS = {
    "58": "a credit of only whitespace: photo_for() prints 'Photo by ' with nobody after it",
    "64": "a credit of true: photo_for() prints 'Photo by True'",
    "65": "a digest with a trailing newline: re.match's $ matches before it, and the key carries the newline",
}


def compact(value) -> str:
    """JSON text as DuckDB's to_json() and json_object() write it: no spaces, and no ASCII escaping."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _unit_tests() -> list[dict]:
    return yaml.safe_load(UNIT_TESTS.read_text())["unit_tests"]


def _unit_test(name: str) -> dict:
    return next(test for test in _unit_tests() if test["name"] == name)


def _given(test: dict, model: str) -> list[dict]:
    return next(given for given in test["given"] if given["input"] == f"ref('{model}')")["rows"]


def _tests_of(model: str) -> list[dict]:
    tests = [test for test in _unit_tests() if test["model"] == model]
    assert tests, f"no unit test of {model}"
    return tests


def _seed() -> list[dict]:
    with SEED.open(newline="") as handle:
        return list(csv.DictReader(handle))


# --- the constants ----------------------------------------------------------------


def test_the_vars_are_the_python_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["suggested_hikes_source_key"] == SOURCE_KEY
    assert variables["suggested_hikes_author_kind"] == exporter.AUTHOR_KIND
    assert variables["suggested_hikes_content_licence"] == exporter.CONTENT_LICENCE
    assert variables["suggested_hikes_photo_licence"] == exporter.PHOTO_LICENCE
    assert variables["suggested_hikes_photo_prefix"] == photo_store.PHOTO_PREFIX
    assert variables["suggested_hikes_photo_extension"] == photo_store.PHOTO_EXTENSION
    assert variables["suggested_hikes_same_tread_note"] == router.SAME_TREAD_NOTE
    assert variables["suggested_hikes_track_reproduction_tolerance"] == exporter.TRACK_REPRODUCTION_TOLERANCE
    assert variables["suggested_hikes_length_good"] == builder.LENGTH_GOOD
    assert variables["suggested_hikes_length_fair"] == builder.LENGTH_FAIR
    assert variables["suggested_hikes_retrace_min"] == builder.RETRACE_MIN
    assert variables["suggested_hikes_retrace_good"] == builder.RETRACE_GOOD
    assert variables["suggested_hikes_retrace_fair"] == builder.RETRACE_FAIR
    assert variables["suggested_hikes_trails_good"] == builder.TRAILS_GOOD
    assert variables["suggested_hikes_trails_fair"] == builder.TRAILS_FAIR
    assert variables["suggested_hikes_start_good_off_m"] == builder.START_GOOD_OFF_M
    assert set(variables["suggested_hikes_closed_route_types"]) == builder.CLOSED_ROUTE_TYPES
    assert variables["highlights_source"] == export_highlights.build_output([], [], [])[0]["source"]
    assert variables["highlights_basis"] == highlights_lib.NAMED_BASIS
    record = highlights_lib.as_published(
        highlights_lib.Highlight(id="x", name="X", legs=(highlights_lib.Leg("AT", 1.0, 2.0),), note="", reviewed="")
    )
    assert variables["highlights_cited_by"] == record["citations"][highlights_lib.NAMED_BASIS]["by"]


def test_the_difficulty_seed_is_difficulty_slugs():
    assert {row["difficulty_label"]: row["difficulty_slug"] for row in _seed()} == exporter.DIFFICULTY_SLUGS


def test_every_mocked_difficulty_seed_is_the_seed_file():
    mocked = [
        test
        for test in _unit_tests()
        if any(given["input"] == "ref('suggested_hike_difficulty_slugs')" for given in test["given"])
    ]
    assert mocked, "no unit test mocks the difficulty seed"
    for test in mocked:
        assert _given(test, "suggested_hike_difficulty_slugs") == _seed(), test["name"]


# --- int_suggested_hikes__hike_finder: SH02 and SH07 ------------------------------


def _parsed(row: dict) -> SimpleNamespace:
    """A base row as the ParsedHike hike_problems() reads, its JSON values loaded."""
    loaded = {
        name: json.loads(row[name]) if row.get(name) is not None else None
        for name in ("start_json", "description_json", "features_json")
    }
    return SimpleNamespace(
        start=loaded["start_json"],
        description=loaded["description_json"],
        stated_miles=row.get("stated_miles"),
        route_type=row.get("route_type"),
        features=loaded["features_json"],
        author=row.get("author"),
    )


def test_hike_finder_answers_what_hike_problems_and_difficulty_slug_answer():
    for test in _tests_of("int_suggested_hikes__hike_finder"):
        given = {row["hike_number"]: row for row in _given(test, "base_nynjtc__nynjtc_hike_finder")}
        expected = test["expect"]["rows"]
        assert {row["hike_number"] for row in expected} == set(given), test["name"]
        for row in expected:
            source = given[row["hike_number"]]
            if "problems_json" in row:
                assert row["problems_json"] == compact(hike_problems(_parsed(source))), (test["name"], row["hike_number"])
            if "difficulty_slug" in row:
                assert row["difficulty_slug"] == exporter.difficulty_slug(source.get("difficulty")), (
                    test["name"],
                    row["hike_number"],
                )


# --- int_suggested_hikes__photos: SH09 --------------------------------------------


def _python_photos(rows: list[dict], tmp_path: Path) -> dict[str, dict | str]:
    """confirmed_photos() over the unit test's rows as the reviewer's file, and photo_for() for each hike it confirms:
    the photo block, or the message photo_key() refuses its digest with."""
    path = tmp_path / "nynjtc_hike_photos.json"
    document = {"photos": [json.loads(row["photo"]) for row in sorted(rows, key=lambda row: row["file_row"])]}
    path.write_text(json.dumps(document), encoding="utf-8")
    confirmed = exporter.confirmed_photos(path)
    answers: dict[str, dict | str] = {}
    for key in confirmed:
        if not key.isdigit():
            # str() of a list or a float: photo_for() is only ever asked for a
            # record's number, so this key joins no hike, as in the SQL.
            continue
        try:
            answers[key] = exporter.photo_for(key, confirmed)
        except (TypeError, ValueError) as refused:
            answers[key] = str(refused)
    return answers


def test_photos_confirms_what_confirmed_photos_and_photo_for_confirm(tmp_path):
    for test in _tests_of("int_suggested_hikes__photos"):
        python = _python_photos(_given(test, "base_nynjtc__nynjtc_hike_photos"), tmp_path)
        expected = {row["hike_key"]: row for row in test["expect"]["rows"]}
        for key, why in DELIBERATE_PHOTOS.items():
            assert isinstance(python.get(key), dict), f"hike {key} is no longer a deliberate difference: {why}"
            assert key not in expected or not expected[key]["digest_is_valid"], f"hike {key}: {why}"
            python.pop(key)
            expected.pop(key, None)
        assert set(expected) == set(python), test["name"]
        for key, row in expected.items():
            answer = python[key]
            if not row["digest_is_valid"]:
                # The SQL builds the key and fails the build on the mart's
                # test; photo_key() raises, which fails the export.
                assert isinstance(answer, str), (key, answer)
                continue
            assert answer == {"url": row["photo_url"], "credit": row["photo_credit"], "licence": row["photo_licence"]}, key


# --- int_suggested_hikes__graded: SH04 and published_route()'s checks -------------


def _python_grade(formed: dict, hike: dict, monkeypatch) -> tuple[str, list[str]]:
    """The grade and routeNotes today's code gives one measured route."""
    if formed.get("formed_problem") is not None:
        # form_route() and published_route() hand back a route that did not
        # form as measured: `rejected`, its one problem the reason.
        return builder.GRADE_REJECTED, [formed["formed_problem"]]
    if formed["provenance"] == builder.GENERATED:
        result = builder.FormedRoute(
            hike_id=formed["hike_number"],
            provenance=builder.GENERATED,
            grade=builder.GRADE_REJECTED,
            miles=formed["route_miles"],
            stated_miles=hike.get("stated_miles"),
            start_offset_m=formed.get("start_offset_m"),
            closed=bool(formed["route_closed"]),
            retrace_ratio=formed.get("retrace_ratio"),
            named_trails=json.loads(formed["named_trails"]),
            walked_trails=json.loads(formed["walked_trails"]),
        )
        return builder._grade(result, hike.get("route_type"))
    measured = builder.FormedRoute(
        hike_id=formed["hike_number"],
        provenance=builder.PUBLISHED,
        grade=builder.GRADE_STRONG,
        miles=formed["route_miles"],
        stated_miles=hike.get("stated_miles"),
        closed=bool(formed["route_closed"]),
        ends=[(0.0, 0.0), (0.0, 0.0)],
    )
    # published_route()'s checks over the step's measurements: the track's
    # length, whether its ends meet, and how far apart they sit.
    monkeypatch.setattr(builder, "measure_published", lambda _hike, _track: measured)
    monkeypatch.setattr(builder, "track_gap_m", lambda _result: formed["track_gap_m"])
    result = builder.published_route({"id": formed["hike_number"], **hike}, None)
    return result.grade, result.problems


def test_graded_grades_what_grade_and_published_route_grade(monkeypatch):
    for test in _tests_of("int_suggested_hikes__graded"):
        hikes = {row["hike_number"]: row for row in _given(test, "int_suggested_hikes__hike_finder")}
        formed = {row["hike_number"]: row for row in _given(test, "stg_derived__formed_routes")}
        expected = test["expect"]["rows"]
        assert {row["hike_number"] for row in expected} == set(formed), test["name"]
        for row in expected:
            grade, problems = _python_grade(formed[row["hike_number"]], hikes[row["hike_number"]], monkeypatch)
            assert (row["grade"], row["route_notes_json"]) == (grade, compact(problems)), (test["name"], row["hike_number"])


# --- int_suggested_hikes__routed: SH05, SH06's tolerance, SH08 ----------------------


def _python_routed(rows: list[dict], monkeypatch, tmp_path: Path) -> dict[int, dict]:
    """build_document() over the graded rows: each a routes-artifact row as to_dict() writes it, and, for a published
    track, the step's re-walk as the snap and the search track_ends() makes."""
    by_points: dict[tuple, dict] = {}
    current: dict = {}
    cache, routes = {}, {}
    for row in rows:
        ends = [tuple(end) for end in json.loads(row.get("route_ends") or "[]")]
        gain = row.get("climb_gain_ft")
        formed = builder.FormedRoute(
            hike_id=row["hike_number"],
            provenance=row["provenance"],
            grade=row["grade"],
            ends=ends,
            miles=row.get("route_miles"),
            closed=bool(row.get("route_closed")),
            climb=(gain, row["climb_loss_ft"]) if gain is not None else None,
            walked_trails=json.loads(row.get("walked_trails") or "[]"),
            problems=json.loads(row.get("route_notes_json") or "[]"),
        )
        key = str(row["hike_number"])
        routes[key] = json.loads(json.dumps(formed.to_dict()))
        cache[key] = {"id": row["hike_number"], "name": f"Hike {key}", "source_url": f"https://example.test/{key}"}
        by_points[tuple(tuple(end) for end in routes[key]["ends"])] = row

    def sample_track(points):
        current["row"] = by_points[tuple(tuple(point) for point in points)]
        if current["row"].get("rewalk_problem") is not None:
            return list(points)
        return [tuple(end) for end in json.loads(current["row"]["rewalk_ends"])]

    def nearest_point(_graph, lon, lat, max_off_m):
        assert max_off_m == router.MAX_OFF_NETWORK_M
        return None if current["row"].get("rewalk_problem") is not None else SimpleNamespace(at=(lon, lat))

    def route_through(_graph, _snapped):
        row = current["row"]
        gain = row.get("rewalk_climb_gain_ft")
        return SimpleNamespace(miles=row["rewalk_miles"], climb=(gain, row["rewalk_climb_loss_ft"]) if gain is not None else None)

    monkeypatch.setattr(exporter, "sample_track", sample_track)
    monkeypatch.setattr(exporter.router, "nearest_point", nearest_point)
    monkeypatch.setattr(exporter.router, "route_through", route_through)
    monkeypatch.setattr(exporter, "CONFIRMED_PHOTOS_PATH", tmp_path / "no_photos.json")
    document, _ = exporter.build_document(None, cache, routes, "Steward", datetime(2026, 10, 2, tzinfo=timezone.utc))
    return {int(record["id"].split(":")[-1]): record for record in document["hikes"]}


def test_routed_ships_what_build_document_ships(monkeypatch, tmp_path):
    for test in _tests_of("int_suggested_hikes__routed"):
        python = _python_routed(_given(test, "int_suggested_hikes__graded"), monkeypatch, tmp_path)
        expected = {row["hike_number"]: row for row in test["expect"]["rows"]}
        assert set(expected) == set(python), test["name"]
        for number, row in expected.items():
            record = python[number]
            climb = record.get("climb") or {}
            assert {
                "miles_json": compact(record["miles"]),
                "segments_json": compact(record["segments"]),
                "trails_json": compact(record["trails"]),
                "climb_gain_ft": climb.get("gainFt"),
                "climb_loss_ft": climb.get("lossFt"),
                "track_reproduction": record.get("trackReproduction"),
            } == {
                name: row[name]
                for name in ("miles_json", "segments_json", "trails_json", "climb_gain_ft", "climb_loss_ft", "track_reproduction")
            }, (
                test["name"],
                number,
            )


# --- int_suggested_hikes__highlights: SH12 and SH13 -------------------------------


def _club_runs(rows: list[dict]) -> list[dict]:
    """The club stretches as club_sections.json carries them: clubs in order, each its stretches in order."""
    clubs: dict[int, dict] = {}
    for row in sorted(rows, key=lambda row: (row["club_order"], row["stretch_order"])):
        club = clubs.setdefault(row["club_order"], {"acronym": row.get("acronym"), "stretches": []})
        club["stretches"].append({"start_mile": row["start_mile"], "end_mile": row["end_mile"]})
    return list(clubs.values())


def _python_highlights(test: dict) -> list[dict]:
    """resolve() over the unit test's rows, each row's outcome read off the run over the rows up to it."""
    rows = sorted(_given(test, "base_ourhike__highlights"), key=lambda row: row["file_row"])
    curated = [json.loads(row["highlight"]) for row in rows]
    pois = [{"id": row["poi_id"], "mile": row.get("mile")} for row in _given(test, "int_suggested_hikes__published_pois")]
    clubs = _club_runs(_given(test, "int_suggested_hikes__club_stretches"))
    answers = []
    before = highlights_lib.resolve([], pois, clubs)
    for upto, row in enumerate(rows, start=1):
        after = highlights_lib.resolve(curated[:upto], pois, clubs)
        if len(after.highlights) > len(before.highlights):
            published = highlights_lib.as_published(after.highlights[-1])
            answers.append(
                {
                    "file_row": row["file_row"],
                    "highlight_id": published["id"],
                    "problem": None,
                    "legs_json": compact(published["legs"]),
                    "club": published["club"],
                    "record_json": compact(published),
                }
            )
        else:
            highlight_id, why = after.dropped[-1]
            answers.append(
                {
                    "file_row": row["file_row"],
                    "highlight_id": highlight_id,
                    "problem": why,
                    "legs_json": None,
                    "club": None,
                    "record_json": None,
                }
            )
        before = after
    return answers


def test_highlights_resolves_what_resolve_resolves():
    for test in _tests_of("int_suggested_hikes__highlights"):
        expected = sorted(test["expect"]["rows"], key=lambda row: row["file_row"])
        if any(row["problem"] == "not an object" for row in expected):
            # resolve() does not survive a row that is not an object, and the
            # build does not either: the model's error test fails on it.
            with pytest.raises(AttributeError):
                _python_highlights(test)
            continue
        python = _python_highlights(test)
        columns = ("file_row", "highlight_id", "problem", "legs_json", "club", "record_json")
        assert [{name: row.get(name) for name in columns} for row in expected] == python, test["name"]


# --- int_suggested_hikes__records: SH10 and SH11 ----------------------------------


def _hike(row: dict) -> dict:
    """An int_suggested_hikes__hike_finder row as the cache entry record_for() reads."""
    return {
        "id": row["hike_number"],
        "name": row["name"],
        "source_url": row.get("source_url"),
        "summary": row.get("summary"),
        "stated_miles": row.get("stated_miles"),
        "difficulty": row.get("difficulty"),
        "estimated_hours": row.get("estimated_hours"),
        "route_type": row.get("route_type"),
        "dogs": row.get("dogs"),
        "park": row.get("park"),
        "region": row.get("region"),
        "author": row.get("author"),
        "start": {"lat": row["start_lat"], "lon": row["start_lon"], "label": row.get("start_label")}
        if row.get("has_start")
        else None,
        "features": json.loads(row.get("features_json") or "[]"),
        "published_on": row.get("published_on"),
        "updated_on": row.get("updated_on"),
        "directions": json.loads(row.get("directions_json") or "[]"),
        "description": json.loads(row.get("description_json") or "[]"),
        "public_transport": json.loads(row.get("public_transport_json") or "[]"),
    }


def _python_records(test: dict) -> dict[int, tuple[str, str]]:
    """record_for() and split_record() over the unit test's rows, as JSON text."""
    source = next(row for row in _given(test, "stg_registry__sources") if row["source_key"] == SOURCE_KEY)
    steward = source.get("steward") or source.get("attribution")
    confirmed = {
        row["hike_key"]: {"digest": row["digest"], "credit": row["photo_credit"]}
        for row in _given(test, "int_suggested_hikes__photos")
    }
    routed = {row["hike_number"]: row for row in _given(test, "int_suggested_hikes__routed")}
    answers = {}
    for row in _given(test, "int_suggested_hikes__hike_finder"):
        assert row.get("difficulty_slug") == exporter.difficulty_slug(row.get("difficulty")), row["hike_number"]
        walk = routed.get(row["hike_number"])
        if walk is None:
            continue
        gain = walk.get("climb_gain_ft")
        route = {
            "miles": json.loads(walk["miles_json"]),
            "closed": walk["route_closed"],
            "provenance": walk["provenance"],
            "grade": walk["grade"],
            "problems": json.loads(walk["route_notes_json"]),
            "walked_trails": json.loads(walk["trails_json"]),
            "climb": [gain, walk["climb_loss_ft"]] if gain is not None else None,
        }
        coords = [point["coord"] for point in json.loads(walk["segments_json"])[0]]
        record = exporter.record_for(_hike(row), route, coords, steward, walk.get("track_reproduction"), confirmed)
        shelf, detail = exporter.split_record(record)
        answers[row["hike_number"]] = (compact(shelf), compact(detail))
    return answers


def test_records_write_what_record_for_and_split_record_write():
    for test in _tests_of("int_suggested_hikes__records"):
        python = _python_records(test)
        expected = {row["hike_number"]: (row["shelf_json"], row["detail_json"]) for row in test["expect"]["rows"]}
        assert expected == python, test["name"]
