"""What NYNJTC's alerts look like once they are publishable, and the rails
that stay bolted on until the thing that would remove them exists.

`export_nynjtc_alerts.py` publishes without a reviewed file, which no other
notice source does, so the tests that matter here are the ones proving the
weakest-form guarantees rather than the happy path: nothing placed, nothing
obstructing, nothing claiming review, and no body text.
"""

from __future__ import annotations

import json

import export_nynjtc_alerts
from lib.nynjtc_alerts import PUBLISHED_FIELDS, SOURCE_KEY, UNREVIEWED, locality_of, published_rows


def cache(**overrides) -> dict:
    """Two cached alerts as `fetch_nynjtc_alerts.py` writes them."""
    entry = {
        "slug": "a-t-detour-at-harriman-state-park",
        "title": "A.T. Detour at Harriman State Park",
        "published_at": "2026-06-16T14:36:10",
        "modified_at": "2026-06-16T14:37:46",
        "source_url": "https://www.nynjtc.org/trail-alerts/a-t-detour-at-harriman-state-park/",
        "trails": [{"slug": "appalachian-trail", "name": "Appalachian Trail"}],
        "parks": [{"slug": "harriman", "name": "Harriman-Bear Mountain State Parks"}],
        "regions": [{"slug": "harriman-bear-mountain", "name": "Harriman-Bear Mountain"}],
        "states": [{"slug": "new-york", "name": "New York"}],
        "text": "The Appalachian Trail follows the detour shown on the map. Follow the yellow highlight.",
        "fetched_at": "2026-08-27T02:00:00+00:00",
        **overrides,
    }
    return {entry["slug"]: entry}


def test_a_published_row_carries_exactly_the_named_fields():
    """Projected rather than passed through, so a cache field nobody meant to
    publish cannot reach the bucket by being added upstream."""
    row = published_rows(cache())[0]

    assert tuple(row) == PUBLISHED_FIELDS


def test_nynjtcs_body_text_never_reaches_the_artifact():
    """The facts-and-a-link split. Their paragraphs are their writing, and
    sources.json's licence field on this source records why the artifact stops
    at the facts."""
    row = published_rows(cache())[0]

    assert "detour shown on the map" not in json.dumps(row)
    assert "text" not in row


def test_every_row_is_unplaced_until_a_join_table_exists():
    """features/ORG_NOTICES.md §3. No reference/notice_places.json means no
    placement, and unplaced is a first-class state rather than a gap - so this
    is the guarantee, not a stub waiting to be relaxed quietly."""
    row = published_rows(cache())[0]

    assert row["place"] == {"kind": "unplaced"}


def test_nothing_obstructs_the_trail_however_the_alert_is_worded():
    """`auto_row`'s rule for ATC, applied here: the one field that decides
    whether a barrier is drawn is forced false on a notice nobody has read."""
    row = published_rows(cache(title="Trail Closure: Lake Awosting Carriage Road"))[0]

    assert row["obstructs_trail"] is False


def test_every_row_says_it_is_unreviewed():
    assert published_rows(cache())[0]["review_state"] == UNREVIEWED


def test_the_category_is_absent_rather_than_borrowed_from_atc():
    """NYNJTC files every alert under one category and publishes no per-alert
    vocabulary, so there is nothing true to put here. Absent means unknown."""
    assert published_rows(cache())[0]["category"] is None


def test_the_notice_id_is_namespaced_by_the_registry_key():
    row = published_rows(cache())[0]

    assert row["notice_id"] == f"{SOURCE_KEY}:a-t-detour-at-harriman-state-park"
    assert row["source_key"] == SOURCE_KEY


def test_the_published_date_is_nynjtcs_modified_and_not_its_published():
    """The field that says whether an alert is current is the one they edit,
    because they maintain alerts in place."""
    row = published_rows(cache(published_at="2024-01-11T00:00:00", modified_at="2026-05-04T09:30:00"))[0]

    assert row["updated_at"] == "2026-05-04T09:30:00Z"


def test_locality_prefers_the_region_then_the_state_then_the_park():
    assert locality_of({"regions": [{"name": "Catskill"}], "states": [{"name": "New York"}]}) == "Catskill"
    assert locality_of({"regions": [], "states": [{"name": "New Jersey"}]}) == "New Jersey"
    assert locality_of({"regions": [], "states": [], "parks": [{"name": "Norvin Green State Forest"}]}) == (
        "Norvin Green State Forest"
    )


def test_an_alert_tagged_with_nothing_gets_an_empty_locality_rather_than_a_guess():
    assert locality_of({"regions": [], "states": [], "parks": []}) == ""


def test_rows_come_out_in_a_stable_order():
    """Keyed on the slug, so two bakes of an unchanged cache produce an
    identical file - which is what lets publish.py's sha256 mean 'the notices
    changed' rather than 'the dict iterated differently'."""
    entries = {**cache(), **cache(slug="zzz-last", modified_at="2026-01-01T00:00:00")}

    assert [row["notice_id"].split(":")[1] for row in published_rows(entries)] == [
        "a-t-detour-at-harriman-state-park",
        "zzz-last",
    ]


def test_an_empty_cache_publishes_nothing_at_all(tmp_path, monkeypatch, capsys):
    """An absent cache means the fetch has not run, which is a different claim
    from NYNJTC reporting nothing - and publishing an empty artifact would
    render as the second."""
    monkeypatch.setattr(export_nynjtc_alerts, "CACHE_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(export_nynjtc_alerts, "OUT_PATH", tmp_path / "out.json")
    monkeypatch.setattr(export_nynjtc_alerts, "MANIFEST_PATH", tmp_path / "manifest.json")

    assert export_nynjtc_alerts.main() is None
    assert not (tmp_path / "out.json").exists()
    # Read once - capsys drains on read, so asking twice loses the output.
    said = capsys.readouterr().out
    assert "nothing was published" in said
    assert "NYNJTC reports nothing" in said


def test_a_full_bake_writes_the_artifact_and_a_manifest_that_counts_it(tmp_path, monkeypatch):
    cache_path = tmp_path / "nynjtc_alerts.json"
    cache_path.write_text(json.dumps({"fetched_at": "2026-08-27T02:00:00+00:00", "listed": 1, "alerts": cache()}))
    monkeypatch.setattr(export_nynjtc_alerts, "CACHE_PATH", cache_path)
    monkeypatch.setattr(export_nynjtc_alerts, "OUT_DIR", tmp_path)
    monkeypatch.setattr(export_nynjtc_alerts, "OUT_PATH", tmp_path / "nynjtc_alerts_out.json")
    monkeypatch.setattr(export_nynjtc_alerts, "MANIFEST_PATH", tmp_path / "manifest.json")

    manifest = export_nynjtc_alerts.main()

    document = json.loads((tmp_path / "nynjtc_alerts_out.json").read_text())
    assert document["generated_at"].endswith("Z")
    assert len(document["nynjtc_alerts"]) == 1
    # No `reviewed_at`: nobody has reviewed NYNJTC's page, and carrying the
    # bake's own clock as a review date would claim a review that never
    # happened. See export_nynjtc_alerts.build_document.
    assert "reviewed_at" not in document

    entry = manifest["artifacts"]["nynjtc_alerts"]
    assert entry["count"] == 1
    assert entry["reviewed_count"] == 0
    assert entry["automatic_count"] == 1


def test_the_artifact_publishes_under_conditions():
    """A key in the bucket is a URL deployed clients request and can never be
    renamed, so the payload name is pinned here as well as spelled once in the
    exporter."""
    import publish

    assert "nynjtc_alerts_manifest.json" in publish.CONDITIONS_MANIFESTS
    assert export_nynjtc_alerts.PAYLOAD == "nynjtc_alerts"
