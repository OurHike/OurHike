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


def cached(**overrides) -> dict:
    """One entry as `fetch_atc_updates.py` writes it into the raw cache."""
    return {
        "slug": "central-va-war-spur-bridge-closed",
        "title": "Central VA: War Spur Bridge Closed",
        "category": "Closure",
        "states": ["VA"],
        "date_modified": "2026-08-19T16:22:50-04:00",
        "date_published": "2026-08-19T16:22:50-04:00",
        "miles": [{"direction": "NOBO", "start": 670.2, "end": None, "raw": "NOBO mile 670.2"}],
        "text": "The War Spur Branch Bridge at the War Spur Shelter is closed (NOBO mile 670.2).",
        "fetched_at": "2026-08-24T00:00:00+00:00",
        "listed": True,
        **overrides,
    }


@pytest.fixture
def bake(tmp_path, monkeypatch):
    """Point the script at a temp reviewed file, temp outputs and a temp cache.

    THE CACHE HAS TO BE POINTED SOMEWHERE EVEN WHEN A TEST DOES NOT USE ONE.
    `data/raw/atc_updates.json` is a real path on any machine where
    `fetch_atc_updates.py` has run, and two tests in this file read it and
    failed the moment it first existed. A bake whose row count depends on
    whether somebody has run the fetcher is not a test - it passes here and
    fails in CI, or the other way round, for a reason nothing in the test says.
    """

    def run(document: dict, cache: dict | None = None):
        reviewed = tmp_path / "atc_updates.json"
        reviewed.write_text(json.dumps(document))
        out_dir = tmp_path / "processed" / "conditions"
        cache_path = tmp_path / "raw" / "atc_updates.json"
        if cache is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache))
        monkeypatch.setattr(export_atc_updates, "REVIEWED_PATH", reviewed)
        monkeypatch.setattr(export_atc_updates, "OUT_DIR", out_dir)
        monkeypatch.setattr(export_atc_updates, "OUT_PATH", out_dir / "atc_updates.json")
        monkeypatch.setattr(export_atc_updates, "MANIFEST_PATH", tmp_path / "processed" / "atc_updates_manifest.json")
        monkeypatch.setattr(export_atc_updates, "CACHE_PATH", cache_path)
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


# --- Publishing what ATC posted since the review (#963) ----------------------


def test_an_update_posted_since_the_review_reaches_the_artifact(bake):
    """The gap this feature closes, end to end.

    `reference/atc_updates.json` only moves when a pull request merges, so
    before this an ATC notice waited for a person. Here one posted after the
    review rides out on the next hourly bake, beside the reviewed rows.
    """
    bake(
        {"reviewed_at": "2026-08-12", "updates": [row()]},
        cache={"updates": {"central-va-war-spur-bridge-closed": cached()}},
    )

    document = json.loads(export_atc_updates.OUT_PATH.read_text())
    by_id = {update["atc_id"]: update for update in document["atc_updates"]}

    assert by_id["va-creeper-trail-closure-detour"]["review_state"] == "reviewed"
    assert by_id["central-va-war-spur-bridge-closed"]["review_state"] == "unreviewed"
    # And the rail: nothing unread can put a barrier across the treadway.
    assert by_id["central-va-war-spur-bridge-closed"]["obstructs_trail"] is False


def test_the_reviewed_rows_survive_a_cache_that_cannot_be_read(bake):
    """The asymmetry that decides the failure mode.

    The reviewed rows are what a person stood behind; the automatic ones are a
    convenience. Losing the second to a broken cache is a bad hour. Losing the
    first would be a hiker's map going blank because a scrape failed, and
    export_conditions.py's stance is that a missing closure is invisible.
    """
    cache_path = export_atc_updates.CACHE_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{ this is not json")

    bake({"reviewed_at": "2026-08-12", "updates": [row()]})

    document = json.loads(export_atc_updates.OUT_PATH.read_text())
    assert [u["atc_id"] for u in document["atc_updates"]] == ["va-creeper-trail-closure-detour"]


def test_an_update_atc_has_taken_down_is_not_republished(bake):
    """`listed: false` means the slug was in the cache but is no longer on
    ATC's site. The copy is kept - discover_sources.py's posture for a
    vanished source, and #463's open question answered the same way - but we
    stop asserting it, because not being able to see a notice is not the same
    as knowing it is over."""
    bake(
        {"reviewed_at": "2026-08-12", "updates": [row()]},
        cache={"updates": {"central-va-war-spur-bridge-closed": cached(listed=False)}},
    )

    document = json.loads(export_atc_updates.OUT_PATH.read_text())
    assert [u["atc_id"] for u in document["atc_updates"]] == ["va-creeper-trail-closure-detour"]


def test_the_manifest_separates_what_a_person_checked_from_what_nobody_did(bake):
    """One count would hide the ratio, and the ratio is the thing worth
    watching: a bake that is mostly unreviewed rows means nobody has read
    ATC's page in a while."""
    manifest = bake(
        {"reviewed_at": "2026-08-12", "updates": [row()]},
        cache={"updates": {"central-va-war-spur-bridge-closed": cached()}},
    )

    entry = manifest["artifacts"]["atc_updates"]
    assert (entry["count"], entry["reviewed_count"], entry["automatic_count"]) == (2, 1, 1)
