import json
import sys

import pytest

import discover_sources
from discover_sources import extract_item_id, slugify


@pytest.mark.parametrize(
    "title, expected",
    [
        ("A.T. Trail Club Sections", "trail_club_sections"),
        ("A.T. Centerline", "centerline"),
        ("A.T. Half Mile Points From Springer", "half_mile_points_from_springer"),
        ("Bridges", "bridges"),
        ("", ""),
    ],
)
def test_slugify(title, expected):
    assert slugify(title) == expected


@pytest.mark.parametrize(
    "url_or_id, expected",
    [
        ("c218db84e3ec430db52249797f4cff43", "c218db84e3ec430db52249797f4cff43"),
        (
            "https://experience.arcgis.com/experience/c218db84e3ec430db52249797f4cff43",
            "c218db84e3ec430db52249797f4cff43",
        ),
        (
            "https://experience.arcgis.com/experience/c218db84e3ec430db52249797f4cff43?org=ATConservancy",
            "c218db84e3ec430db52249797f4cff43",
        ),
    ],
)
def test_extract_item_id(url_or_id, expected):
    assert extract_item_id(url_or_id) == expected


ITEM_ID = "expitem123"
WEBMAP_ID = "webmap456"
APP_CONFIG_URL = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}/data"
WEBMAP_DATA_URL = f"https://www.arcgis.com/sharing/rest/content/items/{WEBMAP_ID}/data"
BRIDGES_OLD_URL = "https://services1.arcgis.com/fake/arcgis/rest/services/BridgesOld/FeatureServer/0"
BRIDGES_NEW_URL = "https://services1.arcgis.com/fake/arcgis/rest/services/BridgesNew/FeatureServer/0"


def test_two_titles_slugifying_to_the_same_key_are_flagged_not_silently_duplicated(tmp_path, monkeypatch, requests_mock, capsys):
    """discover_layers() dedups discovered layers by URL only (seen_urls), so
    two distinct layers whose titles collide after slugify() - here "A.T.
    Bridges" and "Bridges" both -> "bridges", since slugify() strips the
    "A.T. " prefix - used to both get appended to new_sources under the same
    key. Since fetch_all.py derives its fetch output path purely from `key`
    (data/raw/<key>.geojson), a sources.json with two entries sharing one key
    would let the second one's fetch silently overwrite the first's file.
    This asserts the collision is now caught instead: a WARNING naming the
    key is printed, and sources.json ends up with exactly one "bridges"
    entry (the first one discovered), not two."""
    monkeypatch.setattr(discover_sources, "SOURCES_PATH", tmp_path / "sources.json")
    monkeypatch.setattr(sys, "argv", ["discover_sources.py", ITEM_ID])

    requests_mock.get(
        APP_CONFIG_URL,
        json={"dataSources": {"ds0": {"type": "WEB_MAP", "portalUrl": "https://www.arcgis.com", "itemId": WEBMAP_ID}}},
    )
    requests_mock.get(
        WEBMAP_DATA_URL,
        json={
            "operationalLayers": [
                {"title": "A.T. Bridges", "url": BRIDGES_OLD_URL},
                {"title": "Bridges", "url": BRIDGES_NEW_URL},
            ]
        },
    )

    discover_sources.main()

    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "bridges" in out

    registry = json.loads((tmp_path / "sources.json").read_text())
    bridges_entries = [s for s in registry["sources"] if s["key"] == "bridges"]
    assert len(bridges_entries) == 1  # not two entries silently sharing one key
    assert bridges_entries[0]["url"] == BRIDGES_OLD_URL  # first-discovered layer wins the key
