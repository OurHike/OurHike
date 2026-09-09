"""fetch_nynjtc_hikes.py - the registry-driven Favorite Hikes fetch (#1290).

Everything here runs against a temp directory and a stubbed HTTP layer -
never nynjtc.org (TESTING.md). The posts are synthetic, in the real
skeleton; the parser they feed is tested against markup in
test_lib_nynjtc_hikes.py.

The behaviours worth pinning are the fetcher's promises, not requests
plumbing: the password-protected posts are counted and never fetched; a
photograph with no credit is never downloaded, because publish.py takes
every cached photo; a photograph already in the previous cache is carried
rather than re-downloaded; a public post that no longer parses leaves the
previous cache exactly as it was and fails the run; and an unregistered
source is an exit, not a fetch.
"""

from __future__ import annotations

import json

import pytest

import fetch_nynjtc_hikes as fetcher
from lib.photo_store import photo_digest, photo_key
from tests.test_lib_nynjtc_hikes import body, post

ENTRY = {"key": "nynjtc_favorite_hikes", "kind": "published_hikes", "provider": "NYNJTC", "reaches_hikers": True}

JPEG = b"\xff\xd8\xff\xe0" + b"synthetic jpeg bytes" * 40


class FakeResponse:
    def __init__(self, content=JPEG, content_type="image/jpeg"):
        self.content = content
        self.headers = {"Content-Type": content_type}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    registry_path = tmp_path / "sources.json"
    registry_path.write_text(json.dumps({"sources": [ENTRY]}))
    raw = tmp_path / "raw"
    monkeypatch.setattr(fetcher, "SOURCES_PATH", registry_path)
    monkeypatch.setattr(fetcher, "RAW_DIR", raw)
    monkeypatch.setattr(fetcher, "CACHE_PATH", raw / "nynjtc_hikes.json")
    monkeypatch.setattr(fetcher, "THROTTLE_SECONDS", 0)
    recorded = []
    monkeypatch.setattr(fetcher, "record", lambda name, paths, root=None: recorded.append((name, list(paths))))
    return {"registry_path": registry_path, "raw": raw, "recorded": recorded}


def stub_api(monkeypatch, posts, photos=None):
    """The listing and the photo downloads; records every photo URL asked for."""
    downloads = []

    def fake_paged(route, http, params=None):
        assert route == "hike"
        assert params == {"_embed": 1}
        return posts

    def fake_request(url, **kwargs):
        downloads.append(url)
        return (photos or {}).get(url, FakeResponse())

    monkeypatch.setattr(fetcher, "fetch_paged", fake_paged)
    monkeypatch.setattr(fetcher, "request_with_retry", fake_request)
    return downloads


def protected_post(slug: str) -> dict:
    return post(id=hash(slug) % 100000, slug=slug, content={"rendered": "", "protected": True})


def cache(sandbox) -> dict:
    return json.loads((sandbox["raw"] / "nynjtc_hikes.json").read_text())


def test_a_first_fetch_caches_the_public_hikes_and_their_photos(sandbox, monkeypatch, capsys):
    downloads = stub_api(monkeypatch, [post(), protected_post("hike-secret-one"), protected_post("hike-secret-two")])

    assert fetcher.main([]) == 0

    document = cache(sandbox)
    assert document["listed"] == 3
    assert document["public"] == 1
    assert document["protected"] == ["hike-secret-one", "hike-secret-two"]
    hike = document["hikes"]["hike-vista-loop-trail"]
    assert hike["name"] == "Vista Loop Trail"
    assert hike["start"] == {"lat": 41.077853, "lon": -74.187596, "basis": "marker"}
    assert hike["problems"] == []
    # The 1024 rendition, not the 2000px original, into the content-addressed store.
    assert downloads == ["https://x/IMG-1024x529.jpg"]
    digest = photo_digest(JPEG)
    assert hike["photo"]["digest"] == digest
    assert hike["photo"]["key"] == photo_key(digest)
    assert hike["photo"]["credit"] == "Daniel Chazin"
    assert (sandbox["raw"] / "poi_photos" / f"{digest}.jpg").read_bytes() == JPEG
    assert sandbox["recorded"] == [("fetch_nynjtc_hikes", [sandbox["raw"] / "nynjtc_hikes.json"])]
    out = capsys.readouterr().out
    assert "1 public, 2 behind NYNJTC's password and not fetched" in out


def test_the_protected_posts_are_never_parsed_or_fetched(sandbox, monkeypatch):
    """A protected post carries an empty body. Parsed, it would be a hike
    with no prose and no start - indistinguishable from a broken page."""
    downloads = stub_api(monkeypatch, [protected_post("hike-secret")])

    assert fetcher.main([]) == 1
    assert downloads == []
    assert not (sandbox["raw"] / "nynjtc_hikes.json").exists()


def test_an_uncredited_photo_is_recorded_but_never_downloaded(sandbox, monkeypatch, capsys):
    """publish.py uploads every file in the store, so the only way to keep an
    uncredited image out of the bucket is to keep it out of the cache."""
    embedded = post()["_embedded"]
    embedded["wp:featuredmedia"][0]["alt_text"] = "A view"
    embedded["wp:featuredmedia"][0]["caption"] = {"rendered": ""}
    uncredited = post(_embedded=embedded, content={"rendered": body(caption_paragraph=""), "protected": False})
    downloads = stub_api(monkeypatch, [uncredited])

    assert fetcher.main([]) == 0

    photo = cache(sandbox)["hikes"]["hike-vista-loop-trail"]["photo"]
    assert photo["credit"] is None
    assert "digest" not in photo
    assert downloads == []
    assert "1 uncredited" in capsys.readouterr().out


def test_a_photo_already_cached_is_carried_not_downloaded_again(sandbox, monkeypatch, capsys):
    stub_api(monkeypatch, [post()])
    assert fetcher.main([]) == 0
    first = cache(sandbox)["hikes"]["hike-vista-loop-trail"]["photo"]

    downloads = stub_api(monkeypatch, [post()])
    assert fetcher.main([]) == 0

    second = cache(sandbox)["hikes"]["hike-vista-loop-trail"]["photo"]
    assert downloads == []
    assert second["digest"] == first["digest"]
    assert second["fetched_at"] == first["fetched_at"]
    assert "1 carried" in capsys.readouterr().out


def test_refetch_photos_downloads_again(sandbox, monkeypatch):
    stub_api(monkeypatch, [post()])
    assert fetcher.main([]) == 0
    downloads = stub_api(monkeypatch, [post()])

    assert fetcher.main(["--refetch-photos"]) == 0
    assert downloads == ["https://x/IMG-1024x529.jpg"]


def test_a_changed_rendition_url_is_a_new_download(sandbox, monkeypatch):
    stub_api(monkeypatch, [post()])
    assert fetcher.main([]) == 0
    embedded = post()["_embedded"]
    embedded["wp:featuredmedia"][0]["media_details"]["sizes"]["large"]["source_url"] = "https://x/NEW-1024x529.jpg"
    downloads = stub_api(monkeypatch, [post(_embedded=embedded)])

    assert fetcher.main([]) == 0
    assert downloads == ["https://x/NEW-1024x529.jpg"]


def test_a_photo_that_is_not_a_jpeg_is_not_stored(sandbox, monkeypatch, capsys):
    """lib/photo_store.py names every object `.jpg`; a PNG under that name
    would be a file whose name promises bytes it does not hold."""
    stub_api(monkeypatch, [post()], photos={"https://x/IMG-1024x529.jpg": FakeResponse(b"\x89PNG", "image/png")})

    assert fetcher.main([]) == 0
    photo = cache(sandbox)["hikes"]["hike-vista-loop-trail"]["photo"]
    assert "digest" not in photo
    assert not (sandbox["raw"] / "poi_photos").exists()
    assert "1 failed" in capsys.readouterr().out


def test_a_photo_download_failure_costs_the_photo_not_the_run(sandbox, monkeypatch):
    def failing_request(url, **kwargs):
        raise ConnectionError("nynjtc's CDN is having a moment")

    monkeypatch.setattr(fetcher, "fetch_paged", lambda route, http, params=None: [post()])
    monkeypatch.setattr(fetcher, "request_with_retry", failing_request)

    assert fetcher.main([]) == 0
    assert "digest" not in cache(sandbox)["hikes"]["hike-vista-loop-trail"]["photo"]


def test_a_public_post_that_no_longer_parses_leaves_the_previous_cache_and_fails(sandbox, monkeypatch, capsys):
    stub_api(monkeypatch, [post()])
    assert fetcher.main([]) == 0
    before = (sandbox["raw"] / "nynjtc_hikes.json").read_text()

    stub_api(monkeypatch, [post(), post(id=2, slug="hike-broken", link="not a url")])
    assert fetcher.main([]) == 1

    assert (sandbox["raw"] / "nynjtc_hikes.json").read_text() == before
    assert "Could not read 1: hike-broken" in capsys.readouterr().out


def test_an_empty_listing_is_a_failure_not_an_empty_cache(sandbox, monkeypatch):
    stub_api(monkeypatch, [])

    assert fetcher.main([]) == 1
    assert not (sandbox["raw"] / "nynjtc_hikes.json").exists()


def test_an_unregistered_source_is_an_exit_not_a_fetch(sandbox, monkeypatch):
    sandbox["registry_path"].write_text(json.dumps({"sources": []}))
    downloads = stub_api(monkeypatch, [post()])

    assert fetcher.main([]) == 1
    assert downloads == []


def test_the_change_report_names_what_moved(sandbox, monkeypatch, capsys):
    stub_api(monkeypatch, [post()])
    assert fetcher.main([]) == 0
    stub_api(monkeypatch, [post(modified_gmt="2026-01-01T00:00:00")])

    assert fetcher.main([]) == 0
    assert "1 hike(s) new or modified since the last run: hike-vista-loop-trail" in capsys.readouterr().out
