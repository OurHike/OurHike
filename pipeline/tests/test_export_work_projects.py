"""Tests for export_work_projects.py and lib/work_projects.py (#760).

The two claims that matter most, held mechanically: **no invented workday
can reach production** (the maintainer's 2026-08-20 decision - sample rows
publish to UA and dev only, and an unset environment reads as production),
and **an unreviewed or broken file publishes nothing** rather than half a
list of events people might drive to.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import export_work_projects
from lib.work_projects import file_problems, is_reviewed, published_rows, row_problems


def _row(**overrides) -> dict:
    return {
        "id": "nynjtc:2026-09-12-bear-mtn",
        "club_name": "NY-NJ Trail Conference",
        "title": "Bear Mountain steps",
        "lat": 41.31,
        "lon": -73.99,
        "mile": 1407.6,
        "starts_on": "2026-09-12",
        "ends_on": "2026-09-12",
        "signup_mode": "contact",
        "signup_contact": "mailto:volunteer@example.org",
        **overrides,
    }


def _sample(**overrides) -> dict:
    return {
        "id": "sample:one",
        "club_name": "[Sample] UA Test Crew",
        "title": "[Sample] Rehearsal workday",
        "lat": 41.31,
        "lon": -73.99,
        "starts_in_days": 4,
        "ends_in_days": 4,
        "signup_mode": "contact",
        "signup_contact": "mailto:ua@example.invalid",
        **overrides,
    }


def test_a_complete_row_has_no_problems():
    assert row_problems(_row()) == []


def test_a_row_needs_a_place():
    problems = row_problems(_row(lat=None, lon=None, mile=None))

    assert any("sends nobody anywhere" in problem for problem in problems)


def test_a_mile_off_the_trail_is_refused():
    assert any("extent" in problem for problem in row_problems(_row(mile=2400.0)))


def test_a_backwards_date_range_is_refused():
    assert any("before starts_on" in p for p in row_problems(_row(ends_on="2026-09-11")))


def test_in_app_signup_is_refused_until_its_backend_exists():
    """Phase B is read-only (#760): a row claiming in_app would render a
    button that files nothing. #762 widens SIGNUP_MODES when the endpoint
    lands."""
    problems = row_problems(_row(signup_mode="in_app"))

    assert any("#762" in problem for problem in problems)


def test_a_contact_row_needs_its_contact():
    problems = row_problems({**_row(), "signup_contact": None})

    assert any("signup_contact" in problem for problem in problems)


def test_a_sample_row_must_say_it_is_one():
    document = {"reviewed_at": "2026-08-20", "rows": [], "ua_sample_rows": [_sample(title="Rehearsal workday")]}

    assert any("[Sample]" in problem for problem in file_problems(document))


def test_duplicate_ids_are_refused_across_both_lists():
    document = {
        "reviewed_at": "2026-08-20",
        "rows": [_row(id="one")],
        "ua_sample_rows": [_sample(id="one")],
    }

    assert any("duplicate id" in problem for problem in file_problems(document))


def test_an_unreviewed_file_is_not_reviewed():
    assert is_reviewed({"rows": []}) is False
    assert is_reviewed({"reviewed_at": "", "rows": []}) is False
    assert is_reviewed({"reviewed_at": "someday", "rows": []}) is False
    assert is_reviewed({"reviewed_at": "2026-08-20", "rows": []}) is True


def test_production_never_sees_a_sample_row():
    """The decision this whole file exists to hold: an invented workday
    reaching a hiker is the feature's own failure mode, self-inflicted."""
    document = {"reviewed_at": "2026-08-20", "rows": [_row()], "ua_sample_rows": [_sample()]}

    production = published_rows(document, environment="production", today=date(2026, 8, 20))
    unset = published_rows(document, environment=None, today=date(2026, 8, 20))

    assert [row["id"] for row in production] == ["nynjtc:2026-09-12-bear-mtn"]
    # Unset reads as production - "nobody said" publishes LESS, never more.
    assert [row["id"] for row in unset] == ["nynjtc:2026-09-12-bear-mtn"]


def test_ua_gets_the_samples_with_their_dates_resolved_from_bake_time():
    document = {"reviewed_at": "2026-08-20", "rows": [], "ua_sample_rows": [_sample()]}
    today = date(2026, 8, 20)

    [row] = published_rows(document, environment="ua", today=today)

    # Relative dates are what keep UA's fourteen-day window populated
    # however long ago the file was edited.
    assert row["starts_on"] == (today + timedelta(days=4)).isoformat()
    assert row["ends_on"] == row["starts_on"]
    assert "starts_in_days" not in row
    assert row["status"] == "upcoming"


def test_the_shipped_reference_file_is_valid_and_production_empty():
    """The file in git, held to its own rules: valid, reviewed, and with an
    EMPTY production list until a real club supplies real workdays."""
    document = json.loads(export_work_projects.REVIEWED_PATH.read_text())

    assert is_reviewed(document)
    assert file_problems(document) == []
    assert document["rows"] == []
    assert len(document["ua_sample_rows"]) > 0


def test_the_exporter_writes_artifact_and_manifest_for_ua(tmp_path, monkeypatch):
    monkeypatch.setattr(export_work_projects, "OUT_DIR", tmp_path / "conditions")
    monkeypatch.setattr(export_work_projects, "OUT_PATH", tmp_path / "conditions" / "work_projects.json")
    monkeypatch.setattr(export_work_projects, "MANIFEST_PATH", tmp_path / "work_projects_manifest.json")
    monkeypatch.setenv("OURHIKE_DATA_ENV", "ua")

    assert export_work_projects.main() == 0

    document = json.loads((tmp_path / "conditions" / "work_projects.json").read_text())
    manifest = json.loads((tmp_path / "work_projects_manifest.json").read_text())
    assert document["work_projects"], "UA should carry the sample rows"
    assert all(row["title"].startswith("[Sample]") for row in document["work_projects"])
    assert document["generated_at"].endswith("Z")
    assert document["reviewed_at"]
    assert manifest["artifacts"]["work_projects"]["count"] == len(document["work_projects"])


def test_the_exporter_keeps_production_empty_today(tmp_path, monkeypatch):
    monkeypatch.setattr(export_work_projects, "OUT_DIR", tmp_path / "conditions")
    monkeypatch.setattr(export_work_projects, "OUT_PATH", tmp_path / "conditions" / "work_projects.json")
    monkeypatch.setattr(export_work_projects, "MANIFEST_PATH", tmp_path / "work_projects_manifest.json")
    monkeypatch.setenv("OURHIKE_DATA_ENV", "production")

    assert export_work_projects.main() == 0

    document = json.loads((tmp_path / "conditions" / "work_projects.json").read_text())
    assert document["work_projects"] == []


def test_an_unreviewed_file_publishes_nothing_and_exits_zero(tmp_path, monkeypatch):
    unreviewed = tmp_path / "reference.json"
    unreviewed.write_text(json.dumps({"rows": [], "ua_sample_rows": []}))
    monkeypatch.setattr(export_work_projects, "REVIEWED_PATH", unreviewed)
    monkeypatch.setattr(export_work_projects, "OUT_PATH", tmp_path / "work_projects.json")
    monkeypatch.setattr(export_work_projects, "MANIFEST_PATH", tmp_path / "work_projects_manifest.json")

    assert export_work_projects.main() == 0
    assert not (tmp_path / "work_projects.json").exists()


def test_a_broken_row_publishes_nothing_and_exits_nonzero(tmp_path, monkeypatch):
    broken = tmp_path / "reference.json"
    broken.write_text(json.dumps({"reviewed_at": "2026-08-20", "rows": [_row(mile=9999.0)], "ua_sample_rows": []}))
    monkeypatch.setattr(export_work_projects, "REVIEWED_PATH", broken)
    monkeypatch.setattr(export_work_projects, "OUT_PATH", tmp_path / "work_projects.json")
    monkeypatch.setattr(export_work_projects, "MANIFEST_PATH", tmp_path / "work_projects_manifest.json")

    assert export_work_projects.main() == 1
    assert not (tmp_path / "work_projects.json").exists()
