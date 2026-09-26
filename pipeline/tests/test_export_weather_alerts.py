"""Tests for export_weather_alerts.py (#1056, the warnings slice).

The alerts here are shaped like api.weather.gov's, trimmed to what the export
reads. The trail squares are the three in the White Mountains that
tests/test_lib_nbm_grid.py pins to GDAL, and one on Springer Mountain."""

import json
from datetime import UTC, datetime

import pytest

import export_weather_alerts as alerts_mod
import publish
from lib.r2_keys import validate_key

WASHINGTON, PINKHAM, LAKES, SPRINGER = [562, 2074], [563, 2076], [563, 2073], [1053, 1683]

SQUARES = {
    "schema": 2,
    "release": "2026-09-25",
    "cells": {"n44w072": [WASHINGTON, PINKHAM, LAKES], "n34w085": [SPRINGER]},
    "zone_files": {"forecast": "z_16ap26.zip", "fire": "fz16ap26.zip", "county": "c_16ap26.zip"},
    "zones": {
        "forecast/NHZ002": [WASHINGTON, PINKHAM, LAKES],
        "county/NHC007": [WASHINGTON, PINKHAM, LAKES],
        "fire/NHZ021": [WASHINGTON, LAKES],
        "fire/NHZ022": [PINKHAM],
        "forecast/GAZ006": [SPRINGER],
    },
    "known_zones": {
        "forecast": ["GAZ006", "NHZ002", "NHZ004", "NHZ021", "NHZ022"],
        "fire": ["NHZ021", "NHZ022"],
        "county": ["NHC007", "MDC031"],
    },
}

ASKED = datetime(2026, 9, 26, 13, 39, 33, tzinfo=UTC)
BAKED = datetime(2026, 9, 26, 13, 39, 34, tzinfo=UTC)


def alert(n, event, zones, *, geometry=None, status="Actual", message_type="Alert", **extra):
    properties = {
        "id": f"urn:oid:test.{n}",
        "event": event,
        "headline": f"{event} issued by NWS Gray ME",
        "description": f"* WHAT...{event}.",
        "instruction": None,
        "severity": "Moderate",
        "urgency": "Expected",
        "certainty": "Likely",
        "response": "Execute",
        "messageType": message_type,
        "status": status,
        "sent": "2026-09-26T09:00:00-04:00",
        "effective": "2026-09-26T09:00:00-04:00",
        "onset": "2026-09-26T09:00:00-04:00",
        "expires": "2026-09-26T17:00:00-04:00",
        "ends": None,
        "senderName": "NWS Gray ME",
        "areaDesc": "Southern Coos",
        "affectedZones": [f"https://api.weather.gov/zones/{z}" for z in zones],
        **extra,
    }
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def response(*features):
    return {"type": "FeatureCollection", "updated": "2026-09-26T13:38:37+00:00", "features": list(features)}


def bake(*features):
    return alerts_mod.bake(SQUARES, response(*features), ASKED, BAKED)


def square_ring(west, south, east, north):
    return {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}


def test_a_zone_alert_reaches_exactly_the_squares_its_zones_overlap():
    document = bake(alert(1, "Wind Advisory", ["forecast/NHZ002"]))

    (published,) = document["alerts"]
    assert published["squares"] == sorted([WASHINGTON, PINKHAM, LAKES])
    assert published["placed_by"] == "zones"


def test_a_red_flag_warning_on_fire_zone_nhz022_does_not_land_on_forecast_zone_nhz022():
    # The same id names a fire weather zone and a forecast zone; only the kind
    # in the URL tells them apart. Forecast NHZ022 covers no trail square here.
    document = bake(alert(1, "Red Flag Warning", ["fire/NHZ022"]), alert(2, "Wind Advisory", ["forecast/NHZ022"]))

    assert [(a["event"], a["squares"]) for a in document["alerts"]] == [("Red Flag Warning", [PINKHAM])]


def test_a_drawn_warning_uses_its_polygon_and_not_the_counties_it_lists():
    # A severe thunderstorm warning drawn around Pinkham Notch only, listing
    # all of Coos County - which would otherwise reach every square here.
    drawn = square_ring(-71.2602, 44.2376, -71.2254, 44.2625)
    document = bake(alert(1, "Severe Thunderstorm Warning", ["county/NHC007"], geometry=drawn))

    (published,) = document["alerts"]
    assert published["squares"] == [PINKHAM]
    assert published["placed_by"] == "polygon"


def test_an_alert_reaching_no_trail_square_is_left_out():
    far = square_ring(-77.5, 39.0, -77.0, 39.3)
    document = bake(alert(1, "Flood Warning", ["county/MDC031"]), alert(2, "Flash Flood Warning", [], geometry=far))

    assert document["alerts"] == []


def test_test_messages_and_cancellations_are_not_relayed():
    document = bake(
        alert(1, "Test Message", ["forecast/NHZ002"], status="Test"),
        alert(2, "Wind Advisory", ["forecast/NHZ002"], message_type="Cancel"),
        alert(3, "Wind Advisory", ["forecast/NHZ002"], message_type="Update"),
    )

    assert [a["id"] for a in document["alerts"]] == ["urn:oid:test.3"]


def test_every_kind_of_alert_is_relayed_including_beach_and_marine_kinds():
    # "Relay all", the maintainer, 2026-09-26: OurHike does not pick which
    # NWS alerts matter.
    kinds = ["Rip Current Statement", "High Surf Advisory", "Air Quality Alert", "Hydrologic Outlook"]
    document = bake(*[alert(n, kind, ["forecast/GAZ006"]) for n, kind in enumerate(kinds)])

    assert sorted(a["event"] for a in document["alerts"]) == sorted(kinds)


def test_nws_text_is_relayed_verbatim_and_a_missing_field_stays_null():
    words = "* WHAT...Northeast winds 15 to 25 mph with gusts up to 45 mph.\n\n* WHERE...Southern Coos."
    document = bake(alert(1, "Wind Advisory", ["forecast/NHZ002"], description=words))

    (published,) = document["alerts"]
    assert published["description"] == words
    assert published["ends"] is None and published["instruction"] is None
    assert published["sender_name"] == "NWS Gray ME"
    assert "status" not in published and "affectedZones" not in published


def test_the_document_carries_when_nws_was_asked():
    document = bake()

    assert document["fetched_at"] == "2026-09-26T13:39:33Z"
    assert document["nws_updated"] == "2026-09-26T13:38:37+00:00"
    assert document["alerts"] == []  # asked, and none reach a trail - not "could not ask"
    assert document["zone_files"]["county"] == "c_16ap26.zip"


def test_a_zone_the_pinned_outlines_have_never_heard_of_is_reported():
    document = bake(alert(1, "Wind Advisory", ["forecast/NHZ099", "forecast/NHZ002"]))

    assert document["unknown_zones"] == ["forecast/NHZ099"]
    assert len(document["alerts"]) == 1  # still placed by the zone it does know


def test_a_marine_zone_is_not_reported_as_unknown():
    # ANZ335 is a stretch of sea; no state is "AN", so the zone files never
    # held it and never will.
    document = bake(alert(1, "Small Craft Advisory", ["forecast/ANZ335"]))

    assert document["unknown_zones"] == [] and document["alerts"] == []


@pytest.mark.parametrize("body", [{"type": "Feature"}, {"type": "FeatureCollection"}, [], None])
def test_an_answer_that_is_not_a_feature_collection_is_refused_rather_than_read_as_none(body):
    with pytest.raises(RuntimeError, match="FeatureCollection"):
        alerts_mod.bake(SQUARES, body, ASKED, BAKED)


def test_a_failed_request_writes_nothing_so_the_last_good_copy_is_carried(tmp_path, monkeypatch):
    squares = tmp_path / "squares.json"
    squares.write_text(json.dumps(SQUARES))
    monkeypatch.setattr(alerts_mod, "SQUARES_PATH", squares)
    monkeypatch.setattr(alerts_mod, "CONDITIONS_DIR", tmp_path / "conditions")
    monkeypatch.setattr(alerts_mod, "ALERTS_PATH", tmp_path / "conditions" / "weather_alerts.json")
    monkeypatch.setattr(alerts_mod, "MANIFEST_PATH", tmp_path / "weather_alerts_manifest.json")

    def refuse():
        raise ConnectionError("api.weather.gov did not answer")

    monkeypatch.setattr(alerts_mod, "fetch", refuse)

    with pytest.raises(ConnectionError):
        alerts_mod.main()
    assert not (tmp_path / "weather_alerts_manifest.json").exists()
    assert not (tmp_path / "conditions").exists()


def test_publish_collects_the_alerts_under_a_legal_conditions_key(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    squares = tmp_path / "squares.json"
    squares.write_text(json.dumps(SQUARES))
    monkeypatch.setattr(alerts_mod, "SQUARES_PATH", squares)
    monkeypatch.setattr(alerts_mod, "CONDITIONS_DIR", processed / "conditions")
    monkeypatch.setattr(alerts_mod, "ALERTS_PATH", processed / "conditions" / "weather_alerts.json")
    monkeypatch.setattr(alerts_mod, "MANIFEST_PATH", processed / "weather_alerts_manifest.json")
    monkeypatch.setattr(alerts_mod, "to_manifest_path", str)
    monkeypatch.setattr(alerts_mod, "fetch", lambda: (response(alert(1, "Wind Advisory", ["forecast/NHZ002"])), ASKED))
    monkeypatch.setattr(publish, "PROCESSED_DIR", processed)
    monkeypatch.setattr(publish, "from_manifest_path", lambda p: __import__("pathlib").Path(p))

    manifest = alerts_mod.main()
    artifacts = publish.collect_artifacts()

    assert manifest["artifacts"]["weather_alerts"]["count"] == 1
    assert "conditions/weather_alerts.json" in artifacts
    assert validate_key("conditions/weather_alerts.json") is None


def test_a_squares_file_from_before_zones_is_refused(tmp_path, monkeypatch):
    old = {k: v for k, v in SQUARES.items() if k not in ("zones", "known_zones")}
    squares = tmp_path / "squares.json"
    squares.write_text(json.dumps(old))
    monkeypatch.setattr(alerts_mod, "SQUARES_PATH", squares)
    monkeypatch.setattr(alerts_mod, "fetch", lambda: pytest.fail("asked NWS before checking squares.json"))

    with pytest.raises(SystemExit, match="zones"):
        alerts_mod.main()
