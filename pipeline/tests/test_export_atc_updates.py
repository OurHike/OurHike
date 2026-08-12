"""The ATC trail-updates bake: what it writes, and the two ways it writes nothing.

The distinction this file is mostly about is that those two ways are not the
same event. An unreviewed file is a true statement about where the feature has
got to and exits 0; a reviewed file with a bad row is a failure and exits
non-zero. Collapsing them either way costs something real - a red X on a
working job, or a silent skip past a broken one.
"""

from __future__ import annotations

import json

import pytest

import export_atc_updates


def row(**overrides) -> dict:
    return {
        "atc_id": "va-creeper-trail-closure-detour",
        "title": "SW Virginia: VA Creeper Trail Closure/Detour",
        "category": "Closure",
        "states": ["VA"],
        "start_mile_marker": 476.6,
        "end_mile_marker": 485.8,
        "obstructs_trail": True,
        "updated_at": "2026-07-17T00:00:00Z",
        "source_url": "https://appalachiantrail.org/trail-updates/va-creeper/",
        **overrides,
    }


@pytest.fixture
def bake(tmp_path, monkeypatch):
    """Point the script at a temp reviewed file and temp outputs."""

    def run(document: dict):
        reviewed = tmp_path / "atc_updates.json"
        reviewed.write_text(json.dumps(document))
        out_dir = tmp_path / "processed" / "conditions"
        monkeypatch.setattr(export_atc_updates, "REVIEWED_PATH", reviewed)
        monkeypatch.setattr(export_atc_updates, "OUT_DIR", out_dir)
        monkeypatch.setattr(export_atc_updates, "OUT_PATH", out_dir / "atc_updates.json")
        monkeypatch.setattr(export_atc_updates, "MANIFEST_PATH", tmp_path / "processed" / "atc_updates_manifest.json")
        return export_atc_updates.main()

    return run


def test_a_reviewed_file_bakes_its_rows(bake):
    manifest = bake({"reviewed_at": "2026-08-12", "updates": [row()]})

    document = json.loads(export_atc_updates.OUT_PATH.read_text())
    assert [update["atc_id"] for update in document["atc_updates"]] == ["va-creeper-trail-closure-detour"]
    assert manifest["artifacts"]["atc_updates"]["count"] == 1


def test_the_artifact_carries_all_three_ages(bake):
    """The bake's, the reviewer's, and ATC's - and the one a hiker cares
    about is the third. A daily `generated_at` on a three-month-old review
    would claim a freshness nobody has, which is why `reviewed_at` is on the
    document rather than inferred from it."""
    bake({"reviewed_at": "2026-08-12", "updates": [row()]})

    document = json.loads(export_atc_updates.OUT_PATH.read_text())
    assert document["generated_at"].endswith("Z")
    assert document["reviewed_at"] == "2026-08-12"
    assert document["atc_updates"][0]["updated_at"] == "2026-07-17T00:00:00Z"


def test_the_payload_is_named_so_the_client_can_check_it(bake):
    """lib/publishedConditions.ts refuses a document whose payload field is
    not the one it asked for, so a reports artifact served where ATC updates
    were expected reads as "no baseline" rather than as an empty trail."""
    bake({"reviewed_at": "2026-08-12", "updates": []})

    assert "atc_updates" in json.loads(export_atc_updates.OUT_PATH.read_text())


def test_an_empty_reviewed_file_still_publishes(bake):
    """ "We looked, and ATC has nothing placeable" is a real answer, and the
    `reviewed_at` on it is what makes it one."""
    manifest = bake({"reviewed_at": "2026-08-12", "updates": []})

    assert manifest["artifacts"]["atc_updates"]["count"] == 0
    assert json.loads(export_atc_updates.OUT_PATH.read_text())["atc_updates"] == []


# --- The two ways it writes nothing ----------------------------------------


def test_an_unreviewed_file_publishes_nothing_and_does_not_fail(bake, capsys):
    """No artifact and no manifest, so publish.py has nothing to upload and
    the client reads a 404 - which it renders as no ATC layer rather than as
    "ATC reports nothing". Exits normally: a red X on a job behaving
    correctly is how a real failure gets missed later."""
    assert bake({"reviewed_at": None, "updates": []}) is None

    assert not export_atc_updates.OUT_PATH.exists()
    assert not export_atc_updates.MANIFEST_PATH.exists()
    assert "reviewed_at" in capsys.readouterr().out


def test_a_reviewed_file_with_a_bad_row_publishes_nothing_and_fails(bake):
    """The other direction. One bad row fails the whole file: a dropped
    closure is invisible on the map, so a partial set is worse than none."""
    with pytest.raises(SystemExit) as exit_info:
        bake({"reviewed_at": "2026-08-12", "updates": [row(), row(start_mile_marker=99999.0)]})

    assert "outside the trail's own extent" in str(exit_info.value)
    assert not export_atc_updates.OUT_PATH.exists()


def test_a_bad_row_does_not_leave_a_stale_artifact_behind(bake, tmp_path):
    """A failed bake must not leave yesterday's bytes in a manifest that says
    they are today's. Nothing is written before the whole file has passed."""
    bake({"reviewed_at": "2026-08-12", "updates": [row()]})
    first = export_atc_updates.OUT_PATH.read_text()

    with pytest.raises(SystemExit):
        bake({"reviewed_at": "2026-08-13", "updates": [row(source_url="javascript:alert(1)")]})

    assert export_atc_updates.OUT_PATH.read_text() == first


# --- The manifest publish.py reads -----------------------------------------


def test_the_manifest_is_its_own_file_not_the_conditions_one(bake):
    """Two scripts, two manifests. export_conditions.py rewrites its manifest
    whole, so sharing one would make the published set depend on which ran
    last - and the loser would vanish from the upload with nothing said."""
    bake({"reviewed_at": "2026-08-12", "updates": [row()]})

    assert export_atc_updates.MANIFEST_PATH.name == "atc_updates_manifest.json"


def test_the_manifest_carries_the_review_date_for_the_job_log(bake):
    """publish-conditions.yml prints it. "0 rows, generated today" reads as a
    quiet trail; "0 rows, generated today, reviewed in May" reads as a review
    queue nobody is servicing, which is the thing worth noticing."""
    manifest = bake({"reviewed_at": "2026-08-12", "updates": []})

    assert manifest["artifacts"]["atc_updates"]["reviewed_at"] == "2026-08-12"


def test_the_manifest_hashes_the_bytes_that_were_written(bake):
    """publish.py diffs on this sha to decide whether to upload, so a hash of
    anything else is a daily upload of identical bytes or, worse, a changed
    artifact that never ships."""
    import hashlib

    manifest = bake({"reviewed_at": "2026-08-12", "updates": [row()]})

    expected = hashlib.sha256(export_atc_updates.OUT_PATH.read_bytes()).hexdigest()
    assert manifest["artifacts"]["atc_updates"]["sha256"] == expected
