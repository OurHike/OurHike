"""Tests for build_nhd_streams.py - the nearest USGS-mapped stream per
shelter, behind the card's stream sentence (#529). Synthetic geometry and
canned service answers throughout, never the live NHDPlus HR service or the
checked-in reference file (TESTING.md).
"""

import json
import math

import build_nhd_streams
from build_nhd_streams import (
    FLOW_CLASSES,
    MAX_DISTANCE_M,
    NO_STREAM,
    STREAM_FCODES,
    build,
    nearest_distance_m,
    query_layer,
)


def test_every_stream_fcode_has_a_flow_class_and_nothing_else_does():
    """The WHERE clause and the classification are two spellings of one
    decision - a code queried but unclassified would KeyError mid-build, and
    a class for a code never queried is dead vocabulary."""
    assert set(FLOW_CLASSES) == set(STREAM_FCODES)


def test_the_where_clause_asks_for_streams_and_nothing_else(monkeypatch):
    """Artificial paths (55800) are how NHD threads lakes into the network -
    excluded by asking for what is wanted, and this pins that the ask stays
    narrow."""
    captured = {}

    class _Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"features": []}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["where"] = params["where"]
        return _Response()

    monkeypatch.setattr(build_nhd_streams.requests, "get", fake_get)
    query_layer(3, 41.0, -74.0)

    for fcode in STREAM_FCODES:
        assert str(fcode) in captured["where"]
    assert "55800" not in captured["where"]


def test_nearest_distance_is_point_to_segment_not_vertex_to_vertex():
    """A shelter beside the middle of a long straight reach is beside the
    stream. A vertex-only distance would report the far-off endpoints - the
    exact overstatement that would put 'no mapped stream' on a card 30 m
    from one."""
    lat, lon = 41.0, -74.0
    # One segment running north-south, passing ~30 m east of the shelter,
    # with endpoints ~1.1 km away in each direction.
    east = 30.0 / (111_132.0 * math.cos(math.radians(lat)))
    north = 1100.0 / 111_132.0
    paths = [[[lon + east, lat - north], [lon + east, lat + north]]]

    distance = nearest_distance_m(lat, lon, paths)

    assert 25.0 < distance < 35.0


def test_nearest_distance_past_an_endpoint_measures_to_the_endpoint():
    lat, lon = 41.0, -74.0
    north = 111_132.0  # metres per degree latitude
    paths = [[[lon, lat + 500.0 / north], [lon, lat + 900.0 / north]]]

    distance = nearest_distance_m(lat, lon, paths)

    assert 495.0 < distance < 505.0


def _shelter(global_id="glob-1", name="Test Shelter"):
    return {"global_id": global_id, "name": name, "lat": 41.0, "lon": -74.0}


def test_build_records_the_nearest_stream_with_its_facts(monkeypatch):
    monkeypatch.setattr(
        build_nhd_streams,
        "nearest_stream",
        lambda lat, lon: {"distance_m": 72, "flow": "perennial", "gnis_name": "Stony Brook"},
    )

    document = build([_shelter()])

    (record,) = document["shelters"]
    assert record["atc_global_id"] == "glob-1"
    assert record["distance_m"] == 72
    assert record["flow"] == "perennial"
    assert record["gnis_name"] == "Stony Brook"
    assert "unresolved" not in record
    assert document["counts"]["with_stream"] == 1
    assert document["counts"]["named"] == 1


def test_build_states_the_no_stream_case_rather_than_omitting_it(monkeypatch):
    """Blood Mountain's row: no stream within the radius is a fact the
    sentence prints, so the record states it instead of vanishing."""
    monkeypatch.setattr(build_nhd_streams, "nearest_stream", lambda lat, lon: None)

    document = build([_shelter()])

    (record,) = document["shelters"]
    assert record["distance_m"] is None
    assert record["unresolved"] == NO_STREAM
    assert str(int(MAX_DISTANCE_M / 1000)) in NO_STREAM  # the claim names its own radius
    assert document["counts"]["with_stream"] == 0


def test_check_mode_compares_without_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(build_nhd_streams, "OUT_PATH", tmp_path / "nhd_streams.json")
    monkeypatch.setattr(build_nhd_streams, "fetch_atc_features", lambda key: [_shelter()])
    monkeypatch.setattr(
        build_nhd_streams,
        "nearest_stream",
        lambda lat, lon: {"distance_m": 72, "flow": "perennial", "gnis_name": "Stony Brook"},
    )

    # Nothing on disk yet: --check reports the difference and writes nothing.
    assert build_nhd_streams.main(["--check"]) == 1
    assert not (tmp_path / "nhd_streams.json").exists()

    # A write, then the same derivation: --check agrees.
    assert build_nhd_streams.main([]) == 0
    assert build_nhd_streams.main(["--check"]) == 0

    # The file drifting from the derivation is the case --check exists for.
    drifted = json.loads((tmp_path / "nhd_streams.json").read_text())
    drifted["shelters"][0]["distance_m"] = 5
    (tmp_path / "nhd_streams.json").write_text(json.dumps(drifted))
    assert build_nhd_streams.main(["--check"]) == 1
