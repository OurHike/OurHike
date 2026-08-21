"""Tests for route_disputes.py.

The happy path is one test. The rest are the two ways this job can be worse
than useless, both of which end with somebody at ATC reading something wrong
about their own data:

  - **Routing on incomplete evidence.** Every `to_file` line says "this is
    in your layer and it is not on the ground", and a poi file that did not
    answer is exactly the file that would have said otherwise.
  - **Closing a steward's issue on an outage.** An unreachable
    `disputes.json` is not an all-clear. Treating it as one closes the
    running list and loses it, which is the failure mode #431 named for the
    monitors this reuses.
"""

from __future__ import annotations

import json

from lib.source_registry import POI_SOURCE_KEYS
from route_disputes import DISPUTES_KEY, main, poi_source_of, published_places, route

BASE = "https://data.example.org"

REGISTRY = {
    "sources": [
        {"key": "shelters", "title": "A.T. Shelters", "provider": "ATC"},
        {"key": "osm_water", "title": "OSM water", "steward": "OpenStreetMap contributors"},
    ]
}


def _place(poi_id: str, name="Spring Shelter", mile=1363.4, lon=-74.1, lat=41.3) -> dict:
    return {
        "type": "Feature",
        "properties": {"id": poi_id, "name": name, "mile": mile, "poi_type": "shelter"},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def _poi_file(*features: dict) -> dict:
    return {"type": "FeatureCollection", "features": list(features)}


def _dispute(poi_id: str, accounts=2, latest="2026-08-19T12:00:00Z", maintainer=False) -> dict:
    return {
        "poi_id": poi_id,
        "accounts": accounts,
        "latest_at": latest,
        "maintainer_said": maintainer,
    }


def _publish(mock, artifacts, objects=None):
    mock.get(f"{BASE}/latest.json", json={"artifacts": {key: {} for key in artifacts}})
    for key, payload in (objects or {}).items():
        mock.get(f"{BASE}/{key}", json=payload)


def _source(verdict: dict, poi_source: str) -> dict:
    return next(source for source in verdict["sources"] if source["poi_source"] == poi_source)


def test_a_disputed_place_routes_to_the_organization_that_publishes_it(requests_mock):
    _publish(
        requests_mock,
        ["poi_shelter.geojson"],
        {
            "poi_shelter.geojson": _poi_file(_place("atc_shelters:abc")),
            DISPUTES_KEY: {"disputes": [_dispute("atc_shelters:abc")]},
        },
    )

    verdict = route(BASE, REGISTRY)
    shelters = _source(verdict, "atc_shelters")

    assert verdict["routable"]
    assert shelters["steward"] == "ATC"
    assert shelters["healthy"] is False
    assert shelters["to_file"][0]["poi_id"] == "atc_shelters:abc"


def test_the_report_carries_what_a_steward_needs_to_find_the_place(requests_mock):
    """The whole reason this reads the poi files at all. `atc_shelters:abc`
    is not something anybody can walk to."""
    _publish(
        requests_mock,
        ["poi_shelter.geojson"],
        {
            "poi_shelter.geojson": _poi_file(_place("atc_shelters:abc", name="Rocky Spring", mile=1101.2)),
            DISPUTES_KEY: {"disputes": [_dispute("atc_shelters:abc", accounts=3)]},
        },
    )

    record = _source(route(BASE, REGISTRY), "atc_shelters")["to_file"][0]

    assert record["name"] == "Rocky Spring"
    assert record["mile"] == 1101.2
    assert (record["lon"], record["lat"]) == (-74.1, 41.3)
    assert record["accounts"] == 3


def test_a_place_upstream_has_already_removed_is_not_an_ask(requests_mock):
    """The dispute was right and is answered. Filing it would be asking ATC
    to delete a feature they have already deleted, which is how a routing
    job teaches its recipient to ignore it."""
    _publish(
        requests_mock,
        ["poi_shelter.geojson"],
        {
            "poi_shelter.geojson": _poi_file(_place("atc_shelters:still-here")),
            DISPUTES_KEY: {"disputes": [_dispute("atc_shelters:gone")]},
        },
    )

    shelters = _source(route(BASE, REGISTRY), "atc_shelters")

    assert [record["poi_id"] for record in shelters["already_gone"]] == ["atc_shelters:gone"]
    assert shelters["to_file"] == []
    assert shelters["healthy"] is True


def test_a_source_with_nothing_disputed_is_healthy_so_its_issue_closes(requests_mock):
    """Enumerated even with nothing to say, because a steward whose last
    dispute was answered has an issue open that nothing else will close."""
    _publish(
        requests_mock,
        ["poi_shelter.geojson"],
        {"poi_shelter.geojson": _poi_file(_place("atc_shelters:abc")), DISPUTES_KEY: {"disputes": []}},
    )

    verdict = route(BASE, REGISTRY)

    assert {source["poi_source"] for source in verdict["sources"]} >= set(POI_SOURCE_KEYS)
    assert all(source["healthy"] for source in verdict["sources"])


def test_a_dispute_on_a_source_nobody_registered_says_so_rather_than_vanishing(requests_mock):
    """`nhd_crossing` is a derivation of ours, so there is no upstream row to
    correct - but a hiker who says there is no water there is still telling
    this project something, and a silent drop is how that gets lost."""
    _publish(
        requests_mock,
        ["poi_water.geojson"],
        {
            "poi_water.geojson": _poi_file(_place("nhd_crossing:12.5,-74.1", name=None)),
            DISPUTES_KEY: {"disputes": [_dispute("nhd_crossing:12.5,-74.1")]},
        },
    )

    crossings = _source(route(BASE, REGISTRY), "nhd_crossing")

    assert crossings["unregistered"] is True
    assert crossings["expected_unregistered"] is True
    assert crossings["steward"] is None
    assert len(crossings["to_file"]) == 1


def test_an_unreachable_poi_file_routes_nothing_at_all(requests_mock):
    """The refusal. A file that 503'd is exactly the file the disputed place
    might live in, so neither `to_file` nor `already_gone` can be claimed."""
    _publish(
        requests_mock,
        ["poi_shelter.geojson", "poi_water.geojson"],
        {
            "poi_shelter.geojson": _poi_file(_place("atc_shelters:abc")),
            DISPUTES_KEY: {"disputes": [_dispute("atc_shelters:abc")]},
        },
    )
    requests_mock.get(f"{BASE}/poi_water.geojson", status_code=503)

    verdict = route(BASE, REGISTRY)

    assert verdict["routable"] is False
    assert verdict["to_file"] == 0
    assert all(not source["to_file"] and not source["already_gone"] for source in verdict["sources"])


def test_an_unroutable_run_marks_no_source_healthy_either(requests_mock):
    """The half that is easy to get wrong: refusing to file is not the same
    as an all-clear, and `healthy` is what closes a steward's issue."""
    _publish(requests_mock, ["poi_shelter.geojson"], {DISPUTES_KEY: {"disputes": []}})
    requests_mock.get(f"{BASE}/poi_shelter.geojson", status_code=503)

    verdict = route(BASE, REGISTRY)

    assert verdict["routable"] is False
    assert not any(source["healthy"] for source in verdict["sources"])


def test_an_unreachable_disputes_artifact_is_not_an_all_clear(requests_mock):
    """A conditions-publish outage must not close every steward's running
    list. #431's lesson, in the direction that loses data rather than the
    direction that spams."""
    _publish(
        requests_mock,
        ["poi_shelter.geojson"],
        {"poi_shelter.geojson": _poi_file(_place("atc_shelters:abc"))},
    )
    requests_mock.get(f"{BASE}/{DISPUTES_KEY}", status_code=404)

    verdict = route(BASE, REGISTRY)

    assert verdict["routable"] is False
    assert [problem["key"] for problem in verdict["unreachable"]] == [DISPUTES_KEY]
    assert not any(source["healthy"] for source in verdict["sources"])


def test_a_poi_file_whose_features_lost_their_id_is_a_failure_not_an_emptying(requests_mock):
    """check_note_anchors.py's #446 guard, needed here for a sharper reason:
    without it every disputed place reads as `already_gone`, and this job
    would conclude that ATC had deleted their entire shelters layer."""
    _publish(
        requests_mock,
        ["poi_shelter.geojson"],
        {
            "poi_shelter.geojson": {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {"name": "Spring"}, "geometry": None}],
            },
            DISPUTES_KEY: {"disputes": [_dispute("atc_shelters:abc")]},
        },
    )

    verdict = route(BASE, REGISTRY)

    assert verdict["routable"] is False
    assert verdict["failed"][0]["key"] == "poi_shelter.geojson"


def test_nothing_published_is_reported_as_no_verdict_rather_than_a_clean_one(requests_mock):
    requests_mock.get(f"{BASE}/latest.json", status_code=404)

    assert route(BASE, REGISTRY) is None


def test_the_manifest_naming_no_poi_files_is_a_failure(requests_mock):
    _publish(requests_mock, ["conditions/notes.json"], {DISPUTES_KEY: {"disputes": []}})

    verdict = route(BASE, REGISTRY)

    assert verdict["routable"] is False
    assert verdict["failed"][0]["key"] == "latest.json"


def test_published_places_keeps_every_poi_file_the_manifest_names(requests_mock):
    keys = ["poi_shelter.geojson", "poi_water.geojson", "trails.geojson"]
    _publish(
        requests_mock,
        keys,
        {
            "poi_shelter.geojson": _poi_file(_place("atc_shelters:abc")),
            "poi_water.geojson": _poi_file(_place("osm_water:9", name="Spring")),
        },
    )

    places, problems = published_places(BASE, {"artifacts": {key: {} for key in keys}})

    assert problems == []
    assert set(places) == {"atc_shelters:abc", "osm_water:9"}


def test_an_id_whose_feature_id_contains_a_colon_still_names_its_source():
    """`nhd_crossing` composes its feature id from coordinates, and
    `lib/feature_id.py`'s fallback can produce ids with punctuation in them.
    Splitting from the right would attribute those to nobody."""
    assert poi_source_of("nhd_crossing:12.5:-74.1") == "nhd_crossing"


def test_the_cli_reserves_two_for_nothing_published(requests_mock, tmp_path, capsys):
    """The workflow branches on this: exit 2 is "no verdict", which must not
    look like an unhealthy run and must not look like a crash."""
    requests_mock.get(f"{BASE}/latest.json", status_code=404)
    registry = tmp_path / "sources.json"
    registry.write_text('{"sources": []}')

    assert main(["--base", BASE, "--registry", str(registry)]) == 2
    assert "nothing is published" in capsys.readouterr().out


def test_the_cli_writes_the_verdict_the_workflow_reads(requests_mock, tmp_path):
    _publish(
        requests_mock,
        ["poi_shelter.geojson"],
        {
            "poi_shelter.geojson": _poi_file(_place("atc_shelters:abc")),
            DISPUTES_KEY: {"disputes": [_dispute("atc_shelters:abc")]},
        },
    )
    registry = tmp_path / "sources.json"
    registry.write_text('{"sources": [{"key": "shelters", "title": "A.T. Shelters", "provider": "ATC"}]}')
    out = tmp_path / "disputes-routed.json"

    assert main(["--base", BASE, "--registry", str(registry), "--json", str(out), "--exit-zero"]) == 0
    assert json.loads(out.read_text())["to_file"] == 1
