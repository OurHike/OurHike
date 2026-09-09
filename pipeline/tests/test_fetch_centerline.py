"""fetch_centerline.py - the one-layer, geometry-only centerline fetch (#1295).

This script exists because `publish-conditions.yml` used to do the same job
in an inline python heredoc, which nothing could test. So the point of this
file is less "does the script work" than "the loop it now uses is the one
with the regression tests" - and the three behaviours below are exactly the
ones the heredoc got wrong or could not state.

No real network: requests_mock raises on any unmocked request, and
tests/conftest.py's socket guard raises under that (TESTING.md).
"""

from __future__ import annotations

import json

import pytest

import fetch_centerline

LAYER_URL = "https://services1.arcgis.com/fake/arcgis/rest/services/ANST_Centerline/FeatureServer/0"
QUERY_URL = LAYER_URL + "/query"


@pytest.fixture
def registered(tmp_path, monkeypatch):
    """A one-entry registry and a temp output path, so nothing touches data/."""
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"sources": [{"key": "centerline", "title": "A.T. Centerline", "url": LAYER_URL}]}))
    out = tmp_path / "raw" / "centerline.geojson"
    monkeypatch.setattr(fetch_centerline, "SOURCES_PATH", sources)
    monkeypatch.setattr(fetch_centerline, "OUT_PATH", out)
    return out


def features(start: int, stop: int) -> list[dict]:
    return [
        {"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": [[i, i]]}}
        for i in range(start, stop)
    ]


def test_a_short_page_does_not_end_the_fetch(registered, requests_mock):
    """The heredoc's bug, pinned against the script that replaced it.

    The inline version stopped on any page shorter than the requested size
    unless the response also carried `exceededTransferLimit`. This simulates
    a service whose own cap (1,200) sits below the 2,000 asked for and which
    says nothing about it - so every page is short, and the old rule would
    have written a partial trail and exited 0. The A.T. centerline is 3,025
    features; truncating it silently is a map missing trail.
    """
    pages = [
        {"json": {"type": "FeatureCollection", "features": features(0, 1200)}},
        {"json": {"type": "FeatureCollection", "features": features(1200, 2400)}},
        {"json": {"type": "FeatureCollection", "features": features(2400, 3025)}},
        {"json": {"type": "FeatureCollection", "features": []}},
    ]
    requests_mock.get(QUERY_URL, pages)

    assert fetch_centerline.main() == 0

    written = json.loads(registered.read_text())
    assert len(written["features"]) == 3025
    assert requests_mock.call_count == 4  # three short pages, then the empty one that ends it


def test_it_asks_for_geometry_only_at_reduced_precision(registered, requests_mock):
    """The query shape is the whole reason this is not `fetch_all.py`.

    Pinned because each field is a decision with a downstream reader:
    `outFields=''` because export_drought.py buffers the line and reads no
    attribute off it, and `geometryPrecision=5` because it simplifies by
    ~110 m before buffering anyway.
    """
    requests_mock.get(
        QUERY_URL,
        [
            {"json": {"type": "FeatureCollection", "features": features(0, 10)}},
            {"json": {"type": "FeatureCollection", "features": []}},
        ],
    )

    assert fetch_centerline.main() == 0

    asked = requests_mock.request_history[0].qs
    assert asked["outfields"] == [""]
    assert asked["geometryprecision"] == ["5"]
    assert asked["resultrecordcount"] == ["2000"]
    assert asked["f"] == ["geojson"]
    assert asked["outsr"] == ["4326"]


def test_an_empty_layer_is_refused_rather_than_written(registered, requests_mock):
    """ArcGIS answers a failed query with 200 and no features (fetch_all.py's
    docstring records it). Written through, that is a corridor clipped
    against nothing - drought bands drawn nowhere, which reads to a hiker
    exactly like a quiet week."""
    requests_mock.get(QUERY_URL, json={"type": "FeatureCollection", "features": []})

    assert fetch_centerline.main() == 1
    assert not registered.exists()


def test_an_unregistered_source_fails_rather_than_crashing(tmp_path, monkeypatch, requests_mock):
    """The heredoc did `find_source(...)['url']`, which is a TypeError on a
    registry that has no such key. A named exit code is the same outcome
    said out loud."""
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"sources": [{"key": "something_else", "url": LAYER_URL}]}))
    monkeypatch.setattr(fetch_centerline, "SOURCES_PATH", sources)
    monkeypatch.setattr(fetch_centerline, "OUT_PATH", tmp_path / "raw" / "centerline.geojson")

    assert fetch_centerline.main() == 1
    assert requests_mock.call_count == 0  # it never got as far as asking
