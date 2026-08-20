"""Tests for check_note_anchors.py.

The healthy path is one test; the rest are the ways this check must refuse
to say more than it knows, because its whole value is as a backstop whose
green means something: an unreachable notes artifact is not "no orphans",
a poi file whose features lost their id property is not "every note
orphaned", and every anchor orphaning at once is a broken join rather than
a per-anchor report (#446's class, applied here from the start).
"""

from __future__ import annotations

import json

from check_note_anchors import (
    FAILED,
    NOTES_KEY,
    RETIRED_KEY,
    SUSPICIOUS_ORPHAN_FLOOR,
    UNREACHABLE,
    anchor_rows,
    check_anchors,
    main,
)

BASE = "https://data.example.org"


def _poi_file(*ids: str) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"id": poi_id}, "geometry": None} for poi_id in ids],
    }


def _notes(*rows: dict) -> dict:
    return {"generated_at": "2026-08-20T09:00:00Z", "notes": list(rows)}


def _note(poi_id, observed="2026-08-19T12:00:00Z", lat=41.2, lon=-74.1, mile=1363.4) -> dict:
    return {
        "id": "note-1",
        "poi_id": poi_id,
        "lat": lat,
        "lon": lon,
        "mile": mile,
        "observed_at": observed,
    }


def _publish(mock, manifest_artifacts, objects=None):
    mock.get(f"{BASE}/latest.json", json={"artifacts": {key: {} for key in manifest_artifacts}})
    for key, payload in (objects or {}).items():
        mock.get(f"{BASE}/{key}", json=payload)


def test_every_anchor_publishing_is_healthy(requests_mock):
    _publish(
        requests_mock,
        ["poi_shelter.geojson"],
        {"poi_shelter.geojson": _poi_file("atc_shelters:abc")},
    )
    requests_mock.get(f"{BASE}/{NOTES_KEY}", json=_notes(_note("atc_shelters:abc")))

    verdict = check_anchors(BASE)

    assert verdict["healthy"]
    assert verdict["orphans"] == []
    assert verdict["anchored_pois"] == 1
    assert verdict["published_ids"] == 1


def test_an_unexplained_orphan_is_unhealthy_and_carries_its_reanchor_facts(requests_mock):
    _publish(requests_mock, ["poi_shelter.geojson"], {"poi_shelter.geojson": _poi_file("atc_shelters:abc")})
    requests_mock.get(
        f"{BASE}/{NOTES_KEY}",
        json=_notes(
            _note("atc_shelters:gone", observed="2026-08-01T00:00:00Z", lat=1.0, lon=2.0, mile=3.0),
            _note("atc_shelters:gone", observed="2026-08-15T00:00:00Z", lat=4.0, lon=5.0, mile=6.0),
        ),
    )

    verdict = check_anchors(BASE)

    assert not verdict["healthy"]
    (orphan,) = verdict["orphans"]
    assert orphan["disposition"] == "unknown"
    assert orphan["notes"] == 2
    # The MOST RECENT note's coordinates are the re-anchor point - the place
    # as last observed, not as first written down.
    assert (orphan["lat"], orphan["lon"], orphan["mile"]) == (4.0, 5.0, 6.0)
    assert orphan["latest_observed_at"] == "2026-08-15T00:00:00Z"


def test_a_tombstoned_orphan_is_the_ledger_working_not_an_alarm(requests_mock):
    _publish(
        requests_mock,
        ["poi_shelter.geojson", RETIRED_KEY],
        {"poi_shelter.geojson": _poi_file("atc_shelters:new")},
    )
    requests_mock.get(
        f"{BASE}/{RETIRED_KEY}",
        json={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": "atc_shelters:old", "superseded_by": "atc_shelters:new"},
                    "geometry": None,
                },
                {"type": "Feature", "properties": {"id": "atc_shelters:ended"}, "geometry": None},
            ],
        },
    )
    requests_mock.get(
        f"{BASE}/{NOTES_KEY}",
        json=_notes(_note("atc_shelters:old"), _note("atc_shelters:ended")),
    )

    verdict = check_anchors(BASE)

    assert verdict["healthy"], "a superseded or retired anchor is explained, not orphaned"
    dispositions = {o["poi_id"]: (o["disposition"], o["superseded_by"]) for o in verdict["orphans"]}
    assert dispositions == {
        "atc_shelters:old": ("superseded", "atc_shelters:new"),
        "atc_shelters:ended": ("retired", None),
    }
    assert verdict["unknown_orphans"] == 0


def test_an_unreachable_notes_artifact_is_not_anchor_health(requests_mock):
    _publish(requests_mock, ["poi_shelter.geojson"], {"poi_shelter.geojson": _poi_file("atc_shelters:abc")})
    requests_mock.get(f"{BASE}/{NOTES_KEY}", status_code=503)

    verdict = check_anchors(BASE)

    assert not verdict["healthy"]
    assert verdict["orphans"] == []
    assert [p["key"] for p in verdict["unreachable"]] == [NOTES_KEY]


def test_a_poi_file_without_id_properties_is_a_broken_join_not_mass_orphaning(requests_mock):
    _publish(
        requests_mock,
        ["poi_shelter.geojson"],
        {
            "poi_shelter.geojson": {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {"name": "Fingerboard"}, "geometry": None}],
            }
        },
    )
    requests_mock.get(f"{BASE}/{NOTES_KEY}", json=_notes(_note("atc_shelters:abc")))

    verdict = check_anchors(BASE)

    assert not verdict["healthy"]
    assert any(p["state"] == FAILED and "properties.id" in p["detail"] for p in verdict["failed"])


def test_every_anchor_orphaning_at_once_reports_a_broken_join_not_a_list(requests_mock):
    anchors = [f"atc_shelters:{n}" for n in range(SUSPICIOUS_ORPHAN_FLOOR)]
    _publish(requests_mock, ["poi_shelter.geojson"], {"poi_shelter.geojson": _poi_file("atc_shelters:other")})
    requests_mock.get(f"{BASE}/{NOTES_KEY}", json=_notes(*[_note(a) for a in anchors]))

    verdict = check_anchors(BASE)

    assert not verdict["healthy"]
    assert verdict["orphans"] == [], "a per-anchor report over a broken join would be confidently wrong"
    assert any("renamed id scheme" in p["detail"] for p in verdict["failed"])


def test_one_fewer_than_the_floor_still_reports_each_orphan(requests_mock):
    anchors = [f"atc_shelters:{n}" for n in range(SUSPICIOUS_ORPHAN_FLOOR - 1)]
    _publish(requests_mock, ["poi_shelter.geojson"], {"poi_shelter.geojson": _poi_file("atc_shelters:other")})
    requests_mock.get(f"{BASE}/{NOTES_KEY}", json=_notes(*[_note(a) for a in anchors]))

    verdict = check_anchors(BASE)

    assert len(verdict["orphans"]) == SUSPICIOUS_ORPHAN_FLOOR - 1
    assert verdict["failed"] == []


def test_a_manifest_naming_no_poi_files_is_a_failure_not_an_empty_answer(requests_mock):
    _publish(requests_mock, ["trails.geojson"], {})
    requests_mock.get(f"{BASE}/{NOTES_KEY}", json=_notes(_note("atc_shelters:abc")))

    verdict = check_anchors(BASE)

    assert not verdict["healthy"]
    assert any("no poi_*.geojson" in p["detail"] for p in verdict["failed"])


def test_pin_drop_notes_have_nothing_to_orphan(requests_mock):
    _publish(requests_mock, ["poi_shelter.geojson"], {"poi_shelter.geojson": _poi_file("atc_shelters:abc")})
    requests_mock.get(
        f"{BASE}/{NOTES_KEY}",
        json=_notes({"id": "note-2", "poi_id": None, "lat": 1.0, "lon": 2.0, "mile": 3.0, "observed_at": "2026-08-19T00:00:00Z"}),
    )

    verdict = check_anchors(BASE)

    assert verdict["healthy"]
    assert verdict["anchored_pois"] == 0


def test_an_unreachable_poi_file_reports_itself_without_orphaning_its_ids(requests_mock):
    _publish(
        requests_mock,
        ["poi_shelter.geojson", "poi_water.geojson"],
        {"poi_shelter.geojson": _poi_file("atc_shelters:abc")},
    )
    requests_mock.get(f"{BASE}/poi_water.geojson", status_code=503)
    requests_mock.get(f"{BASE}/{NOTES_KEY}", json=_notes(_note("csi_water:xyz")))

    verdict = check_anchors(BASE)

    # The water anchor may well live in the file that did not answer, so
    # naming it an orphan would be the check saying more than it read. The
    # run is unhealthy for the unreachable file alone, and no anchor is
    # accused on a partial id set.
    assert not verdict["healthy"]
    assert [p["state"] for p in verdict["unreachable"]] == [UNREACHABLE]
    assert verdict["orphans"] == []


def test_no_manifest_exits_2(requests_mock, capsys):
    requests_mock.get(f"{BASE}/latest.json", status_code=404)

    assert main(["--base", BASE]) == 2
    assert "nothing is published" in capsys.readouterr().out.lower()


def test_exit_zero_holds_an_unhealthy_verdict_to_zero(requests_mock, tmp_path):
    _publish(requests_mock, ["poi_shelter.geojson"], {"poi_shelter.geojson": _poi_file("atc_shelters:abc")})
    requests_mock.get(f"{BASE}/{NOTES_KEY}", json=_notes(_note("atc_shelters:gone")))
    out = tmp_path / "anchors.json"

    assert main(["--base", BASE, "--json", str(out), "--exit-zero"]) == 0
    assert main(["--base", BASE, "--json", str(out)]) == 1

    verdict = json.loads(out.read_text())
    assert verdict["unknown_orphans"] == 1


def test_anchor_rows_keeps_the_latest_note_per_poi():
    rows = anchor_rows(
        _notes(
            _note("a", observed="2026-08-10T00:00:00Z", mile=1.0),
            _note("a", observed="2026-08-12T00:00:00Z", mile=2.0),
            _note("b", observed="2026-08-11T00:00:00Z", mile=9.0),
        )
    )

    assert rows["a"]["notes"] == 2
    assert rows["a"]["mile"] == 2.0
    assert rows["b"]["notes"] == 1
