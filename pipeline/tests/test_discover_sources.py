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


def _discovering_one_layer(tmp_path, monkeypatch, requests_mock, prior_registry: dict):
    """Run discovery over a registry that already exists, and hand back what
    it wrote. One layer, rediscovered - the ordinary case, and the one where
    fields written by a person get thrown away."""
    (tmp_path / "sources.json").write_text(json.dumps(prior_registry))
    monkeypatch.setattr(discover_sources, "SOURCES_PATH", tmp_path / "sources.json")
    monkeypatch.setattr(sys, "argv", ["discover_sources.py", ITEM_ID])

    requests_mock.get(
        APP_CONFIG_URL,
        json={"dataSources": {"ds0": {"type": "WEB_MAP", "portalUrl": "https://www.arcgis.com", "itemId": WEBMAP_ID}}},
    )
    requests_mock.get(
        WEBMAP_DATA_URL,
        json={"operationalLayers": [{"title": "A.T. Bridges", "url": BRIDGES_NEW_URL}]},
    )

    discover_sources.main()
    return json.loads((tmp_path / "sources.json").read_text())


def test_rediscovery_keeps_fields_a_person_wrote_on_an_entry(tmp_path, monkeypatch, requests_mock):
    """features/SOURCE_REGISTRY.md asks for a steward, a licence and a
    contact on every source. This used to carry `notes` forward and nothing
    else, so any such field survived until the next discovery run and then
    vanished - on a run whose output nobody re-reads line by line, because it
    is supposed to be mechanical. #459 adds exactly those fields."""
    registry = _discovering_one_layer(
        tmp_path,
        monkeypatch,
        requests_mock,
        {
            "sources": [
                {
                    "key": "bridges",
                    "title": "A.T. Bridges",
                    "url": BRIDGES_OLD_URL,
                    "trust": "authoritative",
                    "steward": "Appalachian Trail Conservancy",
                    "licence": "unconfirmed - see #98",
                }
            ]
        },
    )

    bridges = next(s for s in registry["sources"] if s["key"] == "bridges")
    assert bridges["trust"] == "authoritative"
    assert bridges["steward"] == "Appalachian Trail Conservancy"
    assert bridges["licence"] == "unconfirmed - see #98"


def test_rediscovery_still_takes_the_url_from_the_layer(tmp_path, monkeypatch, requests_mock):
    """The other half of the same rule: discovery owns what it re-reads. A
    prior URL must not win, or a moved layer would be pinned to its old
    address forever."""
    registry = _discovering_one_layer(
        tmp_path,
        monkeypatch,
        requests_mock,
        {"sources": [{"key": "bridges", "title": "A.T. Bridges", "url": BRIDGES_OLD_URL}]},
    )

    assert next(s for s in registry["sources"] if s["key"] == "bridges")["url"] == BRIDGES_NEW_URL


def test_rediscovery_keeps_the_registry_s_other_top_level_blocks(tmp_path, monkeypatch, requests_mock):
    """`photo_licence` records the basis on which ATC's photos may be served
    at all - a question CONTRIBUTING.md says must be recorded rather than
    assumed. Rebuilding the document from `_comment` + `sources` deleted it
    on every discovery run."""
    registry = _discovering_one_layer(
        tmp_path,
        monkeypatch,
        requests_mock,
        {
            "photo_licence": {"license": "© ATC, used with permission"},
            "sources": [{"key": "bridges", "title": "A.T. Bridges", "url": BRIDGES_OLD_URL}],
        },
    )

    assert registry["photo_licence"]["license"] == "© ATC, used with permission"


def test_a_hand_registered_source_survives_a_discovery_run(tmp_path, monkeypatch, requests_mock, capsys):
    """ATC's Trail Updates are not in the Experience Builder app and never
    will be, so every discovery run finds them missing. Kept-not-deleted is
    what makes hand-registering a source viable at all (#459)."""
    registry = _discovering_one_layer(
        tmp_path,
        monkeypatch,
        requests_mock,
        {
            "sources": [
                {"key": "bridges", "title": "A.T. Bridges", "url": BRIDGES_OLD_URL},
                {"key": "atc_trail_updates", "title": "A.T. Trail Updates", "kind": "published_notices"},
            ]
        },
    )

    kept = next(s for s in registry["sources"] if s["key"] == "atc_trail_updates")
    assert kept["kind"] == "published_notices"
    assert "WARNING" in capsys.readouterr().out
