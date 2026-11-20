"""fetch_atlas_outlines.py: one download per pinned version, and nothing kept
that is not the topology its row is read for (#1965)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import fetch_atlas_outlines as fetcher
from lib import atlas_sources
from lib.source_registry import atlas_files, load_registry

REAL_REGISTRY = Path(__file__).resolve().parents[1] / "sources.json"
TOPOLOGY = {"type": "Topology", "arcs": [], "objects": {"states": {"type": "GeometryCollection", "geometries": [{}]}}}


@pytest.fixture
def landing(tmp_path, monkeypatch):
    path = tmp_path / "atlas" / "us-atlas@3.0.1-states-10m.json"
    monkeypatch.setitem(atlas_sources.ATLAS_FILES, atlas_sources.US_ATLAS_KEY, (path, "states"))
    monkeypatch.setattr(fetcher, "ATLAS_FILES", atlas_sources.ATLAS_FILES)
    return path


ROW = {"key": atlas_sources.US_ATLAS_KEY, "url": "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json"}


def test_every_atlas_row_is_pinned_named_and_lands_under_its_own_version():
    rows = atlas_files(load_registry(REAL_REGISTRY))
    assert {row["key"] for row in rows} == atlas_sources.ATLAS_SOURCE_KEYS
    for row in rows:
        assert fetcher.PINNED.search(row["url"]), row["url"]
        version = re.search(r"/npm/([a-z0-9-]+@\d+\.\d+\.\d+)/", row["url"]).group(1)
        path, _ = atlas_sources.ATLAS_FILES[row["key"]]
        assert path.name.startswith(version + "-"), (
            f"{path.name} does not carry {version}, so a new edition would land on the old copy"
        )
        assert row["reaches_hikers"] is True


def test_a_copy_that_parses_is_kept_without_asking_the_network(landing):
    landing.parent.mkdir(parents=True)
    landing.write_text(json.dumps(TOPOLOGY))

    def never(*args, **kwargs):
        raise AssertionError("downloaded a pinned file that was already here")

    assert fetcher.fetch_one(ROW, download=never) == (landing, False)


def test_a_download_that_is_not_the_topology_is_refused_and_nothing_is_left_behind(landing):
    def error_page(url, dest, **kwargs):
        Path(dest).write_text("<html>Bad gateway</html>")

    with pytest.raises(fetcher.AtlasRefused, match="did not answer a TopoJSON topology carrying `states`"):
        fetcher.fetch_one(ROW, download=error_page)
    assert not landing.exists()
    assert list(landing.parent.iterdir()) == []


def test_a_good_download_lands_and_sends_the_pipelines_user_agent(landing):
    seen = {}

    def good(url, dest, **kwargs):
        seen.update(url=url, **kwargs)
        Path(dest).write_text(json.dumps(TOPOLOGY))

    assert fetcher.fetch_one(ROW, download=good) == (landing, True)
    assert seen["url"] == ROW["url"] and seen["headers"]["User-Agent"].startswith("OurHike")
    assert json.loads(landing.read_text())["type"] == "Topology"


@pytest.mark.parametrize(
    "url", ["https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json", "https://cdn.jsdelivr.net/npm/us-atlas/states-10m.json"]
)
def test_a_url_that_does_not_pin_an_exact_version_is_refused(landing, url):
    with pytest.raises(fetcher.AtlasRefused, match="does not pin an exact package version"):
        fetcher.fetch_one({**ROW, "url": url}, download=lambda *a, **k: None)
