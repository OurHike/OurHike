"""Tests for export_work_projects.py and lib/work_projects.py (#760).

The two claims that matter most, held mechanically: **no invented workday
reaches ANY environment's map** (the maintainer's 2026-09-09 decision, which
widened 2026-08-20's production-only rule from production to everywhere),
and **an unreviewed or broken file publishes nothing** rather than half a
list of events people might drive to.

The first claim is held from both ends: `rows` is the only list the bake
reads, and the retired `ua_sample_rows` key is REFUSED rather than ignored,
so a future re-add fails the bake instead of publishing quietly.
"""

from __future__ import annotations

import json

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


def test_the_retired_sample_list_is_refused_rather_than_ignored():
    """The 2026-09-09 decision, held where re-adding samples would land.

    Ignoring the key would make a re-add a silent no-op that reads like it
    worked; refusing it stops the bake and names the rule. An EMPTY list is
    refused too - the key itself is what is retired, and a file carrying it
    is a file somebody is about to fill in."""
    for samples in ([_row(id="sample:one")], []):
        document = {"reviewed_at": "2026-08-20", "rows": [], "ua_sample_rows": samples}

        assert any("ua_sample_rows is retired" in problem for problem in file_problems(document))


def test_duplicate_ids_are_refused():
    document = {"reviewed_at": "2026-08-20", "rows": [_row(id="one"), _row(id="one")]}

    assert any("duplicate id" in problem for problem in file_problems(document))


def test_an_unreviewed_file_is_not_reviewed():
    assert is_reviewed({"rows": []}) is False
    assert is_reviewed({"reviewed_at": "", "rows": []}) is False
    assert is_reviewed({"reviewed_at": "someday", "rows": []}) is False
    assert is_reviewed({"reviewed_at": "2026-08-20", "rows": []}) is True


def test_the_reviewed_rows_are_the_whole_published_set():
    """The decision this whole file exists to hold: an invented workday
    reaching anybody is the feature's own failure mode, self-inflicted. There
    is no environment argument left to get wrong."""
    document = {"reviewed_at": "2026-08-20", "rows": [_row()]}

    rows = published_rows(document)

    assert [row["id"] for row in rows] == ["nynjtc:2026-09-12-bear-mtn"]
    assert rows[0]["status"] == "upcoming"


def test_the_shipped_reference_file_is_valid_and_carries_nothing_invented():
    """The file in git, held to its own rules: valid, reviewed, EMPTY until a
    real club supplies real workdays, and with no sample list to publish from
    (the 2026-09-09 decision, checked against the shipped bytes rather than
    only against the validator)."""
    document = json.loads(export_work_projects.REVIEWED_PATH.read_text())

    assert is_reviewed(document)
    assert file_problems(document) == []
    assert document["rows"] == []
    assert "ua_sample_rows" not in document


def test_the_exporter_writes_artifact_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(export_work_projects, "OUT_DIR", tmp_path / "conditions")
    monkeypatch.setattr(export_work_projects, "OUT_PATH", tmp_path / "conditions" / "work_projects.json")
    monkeypatch.setattr(export_work_projects, "MANIFEST_PATH", tmp_path / "work_projects_manifest.json")

    assert export_work_projects.main() == 0

    document = json.loads((tmp_path / "conditions" / "work_projects.json").read_text())
    manifest = json.loads((tmp_path / "work_projects_manifest.json").read_text())
    # Empty today, and empty is the honest state rather than a failure: the
    # artifact still publishes so the client's read path stays live.
    assert document["work_projects"] == []
    assert document["generated_at"].endswith("Z")
    assert document["reviewed_at"]
    assert manifest["artifacts"]["work_projects"]["count"] == 0


def test_every_environment_gets_the_same_empty_list(tmp_path, monkeypatch):
    """$OURHIKE_DATA_ENV no longer selects anything here. Set to the value
    that used to add the samples, the artifact is the same one production
    gets - which is the 2026-09-09 decision stated as an outcome rather than
    as an absence of code."""
    written = {}
    for environment in ("ua", "dev", "production"):
        out = tmp_path / environment
        monkeypatch.setattr(export_work_projects, "OUT_DIR", out / "conditions")
        monkeypatch.setattr(export_work_projects, "OUT_PATH", out / "conditions" / "work_projects.json")
        monkeypatch.setattr(export_work_projects, "MANIFEST_PATH", out / "work_projects_manifest.json")
        monkeypatch.setenv("OURHIKE_DATA_ENV", environment)

        assert export_work_projects.main() == 0
        written[environment] = json.loads((out / "conditions" / "work_projects.json").read_text())["work_projects"]

    assert written == {"ua": [], "dev": [], "production": []}


def test_an_unreviewed_file_publishes_nothing_and_exits_zero(tmp_path, monkeypatch):
    unreviewed = tmp_path / "reference.json"
    unreviewed.write_text(json.dumps({"rows": []}))
    monkeypatch.setattr(export_work_projects, "REVIEWED_PATH", unreviewed)
    monkeypatch.setattr(export_work_projects, "OUT_PATH", tmp_path / "work_projects.json")
    monkeypatch.setattr(export_work_projects, "MANIFEST_PATH", tmp_path / "work_projects_manifest.json")

    assert export_work_projects.main() == 0
    assert not (tmp_path / "work_projects.json").exists()


def test_a_broken_row_publishes_nothing_and_exits_nonzero(tmp_path, monkeypatch):
    broken = tmp_path / "reference.json"
    broken.write_text(json.dumps({"reviewed_at": "2026-08-20", "rows": [_row(mile=9999.0)]}))
    monkeypatch.setattr(export_work_projects, "REVIEWED_PATH", broken)
    monkeypatch.setattr(export_work_projects, "OUT_PATH", tmp_path / "work_projects.json")
    monkeypatch.setattr(export_work_projects, "MANIFEST_PATH", tmp_path / "work_projects_manifest.json")

    assert export_work_projects.main() == 1
    assert not (tmp_path / "work_projects.json").exists()
