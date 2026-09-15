"""fetch_hikefinder.py - the registry-driven Hike Finder fetch (#1427).

Every request is stubbed; nothing here touches the network or the real cache
(TESTING.md). The parse itself is tested in test_lib_hikefinder.py, so what is
pinned here is the FETCHER'S judgement: which failures leave the previous
cache alone and exit non-zero, which ones are a line in the log and a hike
recorded as incomplete, and that a track is downloaded once.
"""

from __future__ import annotations

import json

import pytest

import fetch_hikefinder as fetcher
from tests.test_lib_hikefinder import GPX, page

LISTING = 'Results (2 hikes found) <a href="hike.php?id=1">a</a><a href="hike.php?id=2">b</a>'


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """The fetcher pointed at a temp tree, with a registry of one source."""
    raw = tmp_path / "raw"
    raw.mkdir()
    sources = tmp_path / "sources.json"
    sources.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "key": fetcher.SOURCE_KEY,
                        "kind": "published_hikes",
                        "url": "https://example.test/hikefinder/",
                        "steward": "New York-New Jersey Trail Conference",
                        "reaches_hikers": True,
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(fetcher, "SOURCES_PATH", sources)
    monkeypatch.setattr(fetcher, "RAW_DIR", raw)
    monkeypatch.setattr(fetcher, "CACHE_PATH", raw / "hikefinder.json")
    monkeypatch.setattr(fetcher, "GPX_DIR", raw / "hikefinder_gpx")
    monkeypatch.setattr(fetcher, "session", lambda: object())
    recorded = []
    monkeypatch.setattr(fetcher, "record", lambda name, outputs, root=None: recorded.append((name, list(outputs))))
    return {"raw": raw, "recorded": recorded, "cache": raw / "hikefinder.json"}


def serve(monkeypatch, pages: dict, listing: str = LISTING, gpx: dict | None = None):
    """Answer every request from a dict, and count what was asked for."""
    asked: list[str] = []

    class Response:
        def __init__(self, text):
            self.text = text

    def request(url, **kwargs):
        asked.append(url)
        if url.endswith("hikes.php"):
            return Response(listing)
        for identifier, body in pages.items():
            if url.endswith(f"hike.php?id={identifier}"):
                return Response(body)
        for identifier, body in (gpx or {}).items():
            if url.endswith(f"download_gpx.php?id={identifier}"):
                return Response(body)
        raise AssertionError(f"unexpected request {url}")

    monkeypatch.setattr(fetcher, "request_with_retry", request)
    return asked


def test_a_clean_run_caches_every_hike_and_says_which_carry_a_route(sandbox, monkeypatch, capsys):
    serve(monkeypatch, {1: page(), 2: page(gpx=True)}, gpx={2: GPX})
    assert fetcher.main([]) == 0
    document = json.loads(sandbox["cache"].read_text())
    assert document["listed"] == 2
    assert document["parsed"] == 2
    assert document["with_published_route"] == 1
    assert set(document["hikes"]) == {"1", "2"}
    assert document["hikes"]["2"]["gpx_file"] == "2.gpx"
    assert document["hikes"]["1"]["gpx_file"] is None
    assert (sandbox["raw"] / "hikefinder_gpx" / "2.gpx").exists()


def test_the_tags_survive_the_round_trip_into_the_cache(sandbox, monkeypatch):
    """The maintainer's "keep ALL the data ... especially the tags". A parse
    that reads them and a cache that drops them is the same as not reading
    them."""
    serve(monkeypatch, {1: page(), 2: page()})
    assert fetcher.main([]) == 0
    assert json.loads(sandbox["cache"].read_text())["hikes"]["1"]["features"] == ["Views", "Birding"]


def test_a_listing_that_links_nothing_leaves_the_previous_cache_alone(sandbox, monkeypatch):
    """Failing is not the same as finding nothing. A listing this build cannot
    read is a changed export, not an empty one."""
    sandbox["cache"].write_text(json.dumps({"hikes": {"1": {"name": "kept"}}}))
    serve(monkeypatch, {}, listing="<html>nothing here</html>")
    assert fetcher.main([]) == 1
    assert json.loads(sandbox["cache"].read_text())["hikes"]["1"]["name"] == "kept"


def test_a_listing_whose_total_disagrees_with_its_links_is_refused(sandbox, monkeypatch):
    """The two are the same page describing itself. A disagreement means it
    paginated or a row lost its link, and caching the shorter answer would
    report a shrunken export as a complete one."""
    serve(monkeypatch, {1: page()}, listing='Results (9 hikes found) <a href="hike.php?id=1">a</a>')
    assert fetcher.main([]) == 1
    assert not sandbox["cache"].exists()


def test_one_unreadable_page_is_recorded_rather_than_failing_the_run(sandbox, monkeypatch):
    """384 hikes cached beats 385 refused, as long as the cache says which one
    is missing."""
    serve(monkeypatch, {1: page(), 2: "<html><body>no title</body></html>"})
    assert fetcher.main([]) == 0
    document = json.loads(sandbox["cache"].read_text())
    assert document["unreadable"] == [2]
    assert set(document["hikes"]) == {"1"}


def test_every_page_failing_to_parse_is_a_changed_export_and_leaves_the_cache(sandbox, monkeypatch):
    sandbox["cache"].write_text(json.dumps({"hikes": {"1": {"name": "kept"}}}))
    serve(monkeypatch, {1: "<html></html>", 2: "<html></html>"})
    assert fetcher.main([]) == 1
    assert json.loads(sandbox["cache"].read_text())["hikes"]["1"]["name"] == "kept"


def test_a_cached_track_is_not_downloaded_again(sandbox, monkeypatch):
    """The export publishes no per-hike validator, so a file already on disk
    is carried forward; only --refetch-gpx goes back for it."""
    serve(monkeypatch, {1: page(), 2: page(gpx=True)}, gpx={2: GPX})
    assert fetcher.main([]) == 0
    asked = serve(monkeypatch, {1: page(), 2: page(gpx=True)}, gpx={2: GPX})
    assert fetcher.main([]) == 0
    assert not any("download_gpx" in url for url in asked)


def test_refetch_gpx_goes_back_for_a_track_already_held(sandbox, monkeypatch):
    serve(monkeypatch, {1: page(), 2: page(gpx=True)}, gpx={2: GPX})
    assert fetcher.main([]) == 0
    asked = serve(monkeypatch, {1: page(), 2: page(gpx=True)}, gpx={2: GPX})
    assert fetcher.main(["--refetch-gpx"]) == 0
    assert any("download_gpx" in url for url in asked)


def test_a_track_that_holds_no_point_is_not_written_at_all(sandbox, monkeypatch):
    """A zero-point file saved under a name promising a route is worse than no
    file: every later stage would have to re-discover that it is empty."""
    serve(monkeypatch, {1: page(), 2: page(gpx=True)}, gpx={2: "<gpx></gpx>"})
    assert fetcher.main([]) == 0
    assert json.loads(sandbox["cache"].read_text())["hikes"]["2"]["gpx_file"] is None
    assert not (sandbox["raw"] / "hikefinder_gpx" / "2.gpx").exists()


def test_an_unregistered_source_fetches_nothing(sandbox, monkeypatch):
    monkeypatch.setattr(fetcher, "SOURCE_KEY", "not_registered")
    assert fetcher.main([]) == 1


def test_a_finished_run_records_its_receipt(sandbox, monkeypatch):
    serve(monkeypatch, {1: page(), 2: page()})
    assert fetcher.main([]) == 0
    assert sandbox["recorded"] == [("fetch_hikefinder", [sandbox["cache"]])]
