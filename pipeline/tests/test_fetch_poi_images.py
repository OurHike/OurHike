"""Tests for fetch_poi_images.py - the Wikimedia Commons photo fetch for
corridor POIs. All HTTP is mocked with requests_mock (real network calls are
never allowed to fire during tests - TESTING.md), POI derivation is
monkeypatched to tiny synthetic unified records except where the real
corridor path is itself the thing under test, and every fixture is built in
test code.
"""

import json
from datetime import date, timedelta

import pytest
import requests

import export_poi
import fetch_poi_images
from lib.photo_store import local_photo_path, photo_digest
from tests.test_export_poi import _write_fixture_sources

FRESH = (date.today() - timedelta(days=100)).isoformat()
STALE = (date.today() - timedelta(days=fetch_poi_images.MAX_PHOTO_AGE_DAYS + 100)).isoformat()


def _poi(poi_id="atc_shelters:glob-1", poi_type="shelter", name="Test Shelter", lat=41.05, lon=-73.95):
    return {
        "id": poi_id,
        "poi_type": poi_type,
        "trail_id": "AT",
        "source": poi_id.split(":")[0],
        "source_feature_id": poi_id.split(":")[1],
        "name": name,
        "lat": lat,
        "lon": lon,
        "confidence": "high",
    }


def _geosearch(*hits):
    return {
        "query": {"geosearch": [{"pageid": index + 1, "title": title, "dist": dist} for index, (title, dist) in enumerate(hits)]}
    }


def _imageinfo_page(pageid, title, taken=None, license_id="cc-by-sa-4.0", license_short="CC BY-SA 4.0"):
    return {
        str(pageid): {
            "pageid": pageid,
            "title": title,
            "imageinfo": [
                {
                    "mime": "image/jpeg",
                    "url": f"https://upload.wikimedia.org/{pageid}.jpg",
                    "thumburl": f"https://upload.wikimedia.org/{pageid}-640.jpg",
                    "descriptionurl": f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}",
                    "extmetadata": {
                        "DateTimeOriginal": {"value": f"{taken or FRESH} 12:00:00"},
                        "License": {"value": license_id},
                        "LicenseShortName": {"value": license_short},
                        "Artist": {"value": "Jane Doe"},
                    },
                }
            ],
        }
    }


JPEG_BYTES = b"\xff\xd8\xff\xe0 pretend shelter photo"


def _use_pois(monkeypatch, tmp_path, pois):
    monkeypatch.setattr(fetch_poi_images, "corridor_pois", lambda: pois)
    monkeypatch.setattr(fetch_poi_images, "OUT_PATH", tmp_path / "poi_images.json")
    monkeypatch.setattr(fetch_poi_images, "RAW_DIR", tmp_path)


def _serve_image(requests_mock, pageid=1, content=JPEG_BYTES):
    """The thumbnail download #362 added. Registered separately from the API
    mock because the bytes come from a different host."""
    requests_mock.get(f"https://upload.wikimedia.org/{pageid}-640.jpg", content=content)


def _cache_image(tmp_path, content=JPEG_BYTES):
    """Put an image in the local cache the way a previous run would have,
    and return its digest."""
    digest = photo_digest(content)
    path = local_photo_path(tmp_path, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return digest


def _no_sleep(monkeypatch):
    """Record pauses (throttle and backoff both) instead of taking them."""
    naps = []
    monkeypatch.setattr(fetch_poi_images.time, "sleep", naps.append)
    return naps


def _saved(tmp_path):
    return json.loads((tmp_path / "poi_images.json").read_text())["pois"]


def test_a_nearby_eligible_photo_is_recorded_with_its_licence_attribution_and_date(tmp_path, monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(
        fetch_poi_images.API_URL,
        [
            {"json": _geosearch(("File:Test Shelter.jpg", 40.0))},
            {"json": {"query": {"pages": _imageinfo_page(1, "File:Test Shelter.jpg")}}},
        ],
    )
    _serve_image(requests_mock)

    fetch_poi_images.main()

    record = _saved(tmp_path)["atc_shelters:glob-1"]
    assert record["status"] == "found"
    assert record["photo"]["url"] == "https://upload.wikimedia.org/1-640.jpg"
    assert record["photo"]["author"] == "Jane Doe"
    assert record["photo"]["license"] == "CC BY-SA 4.0"
    assert record["photo"]["taken"] == FRESH
    # Licence, credit and capture date all present: this record is the whole
    # basis for the card's credit line, so a gap here is a licence breach
    # there, not a cosmetic miss.


def test_the_wikimedia_required_user_agent_rides_every_request(tmp_path, monkeypatch, requests_mock):
    """Wikimedia's API etiquette requires a descriptive User-Agent with a
    contact route; anonymous default UAs get throttled or blocked, which
    would read as "no photos on Commons" rather than as the config error it
    is."""
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(fetch_poi_images.API_URL, json=_geosearch())

    fetch_poi_images.main()

    assert requests_mock.last_request.headers["User-Agent"] == fetch_poi_images.USER_AGENT


def test_a_poi_with_no_nearby_files_is_recorded_as_a_miss_without_an_imageinfo_call(tmp_path, monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(fetch_poi_images.API_URL, json=_geosearch())

    fetch_poi_images.main()

    assert _saved(tmp_path)["atc_shelters:glob-1"] == {"status": "none", "checked": date.today().isoformat()}
    assert requests_mock.call_count == 1  # geosearch only - nothing to look up details for


def test_search_radius_follows_the_poi_type(tmp_path, monkeypatch, requests_mock):
    """A spring drowns in near-miss trail shots at a shelter-sized radius;
    the per-type radii are the "is this actually a photo of the thing"
    knob, so the request must really carry them."""
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi(poi_id="opentrail_at:100", poi_type="water")])
    requests_mock.get(fetch_poi_images.API_URL, json=_geosearch())

    fetch_poi_images.main()

    assert requests_mock.last_request.qs["gsradius"] == [str(fetch_poi_images.SEARCH_RADIUS_M["water"])]


def test_a_poi_type_with_no_radius_is_not_crawled_at_all(tmp_path, monkeypatch, requests_mock):
    """A missing radius means "this source is not searched for that type", and
    it has to mean it in behaviour rather than in a comment.

    Vistas, parking and privies are the three: features/POI_PHOTOS.md
    measured Commons at zero usable photos for 280 shelters, ATC's own
    inventory covers these three instead, and fetch_atc_photos.py wins any
    overlap - so crawling them would be ~2,000 POIs of requests to be
    overruled. This used to be a KeyError waiting for whoever added the
    fourth type.
    """
    _no_sleep(monkeypatch)
    _use_pois(
        monkeypatch,
        tmp_path,
        [_poi(), _poi(poi_id="atc_privies:glob-9", poi_type="privy", name="Test Shelter Privy")],
    )
    requests_mock.get(fetch_poi_images.API_URL, json=_geosearch())

    fetch_poi_images.main()

    saved = _saved(tmp_path)
    assert "atc_shelters:glob-1" in saved
    # Absent, not recorded as a miss: "checked, nothing there" is a claim
    # this run has no basis for.
    assert "atc_privies:glob-9" not in saved
    assert requests_mock.call_count == 1  # the shelter's geosearch, and nothing for the privy


def test_a_prior_outcome_is_carried_forward_without_any_api_calls(tmp_path, monkeypatch, requests_mock):
    """The change-aware core: a full crawl is thousands of requests, and the
    per-POI outcome file is what makes every later run cheap. A recorded
    miss counts as an outcome too - otherwise every photo-less spring gets
    re-queried forever."""
    _no_sleep(monkeypatch)
    found = _poi()
    missed = _poi(poi_id="opentrail_at:100", poi_type="water")
    _use_pois(monkeypatch, tmp_path, [found, missed])
    digest = _cache_image(tmp_path)
    prior = {
        "pois": {
            found["id"]: {
                "status": "found",
                "checked": "2026-08-01",
                "photo": {"url": "u", "taken": FRESH, "digest": digest},
            },
            missed["id"]: {"status": "none", "checked": "2026-08-01"},
        }
    }
    (tmp_path / "poi_images.json").write_text(json.dumps(prior))
    requests_mock.get(fetch_poi_images.API_URL, json=_geosearch())

    fetch_poi_images.main()

    assert requests_mock.call_count == 0
    assert _saved(tmp_path) == prior["pois"]


def test_a_found_photo_whose_cached_bytes_are_gone_is_refetched_without_a_new_search(tmp_path, monkeypatch, requests_mock):
    """publish.py uploads from the cached files, so an outcomes file claiming
    photos whose images were cleared would publish POIs pointing at objects
    nobody ever uploaded - a 404 on a mountain. The recorded answer still
    stands, though, so only the image is re-fetched, not the geosearch that
    produced it."""
    _no_sleep(monkeypatch)
    poi = _poi()
    _use_pois(monkeypatch, tmp_path, [poi])
    prior = {
        "pois": {
            poi["id"]: {
                "status": "found",
                "checked": "2026-08-01",
                # Recorded by a previous run, whose data/ tree has since been
                # cleared - the digest is here, the file is not.
                "photo": {"url": "https://upload.wikimedia.org/1-640.jpg", "taken": FRESH, "digest": photo_digest(JPEG_BYTES)},
            }
        }
    }
    (tmp_path / "poi_images.json").write_text(json.dumps(prior))
    _serve_image(requests_mock)

    fetch_poi_images.main()

    # One request, and it was for the image rather than the API.
    assert requests_mock.call_count == 1
    assert requests_mock.last_request.url == "https://upload.wikimedia.org/1-640.jpg"
    assert local_photo_path(tmp_path, photo_digest(JPEG_BYTES)).read_bytes() == JPEG_BYTES
    assert _saved(tmp_path)[poi["id"]]["status"] == "found"


def test_a_downloaded_photo_is_cached_under_its_own_digest_and_carries_it(tmp_path, monkeypatch, requests_mock):
    """The content-addressing contract: what lands on disk is named by the
    hash of its own bytes, and the record carries that name so export_poi.py
    can point the artifact at the same object publish.py will upload."""
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(
        fetch_poi_images.API_URL,
        [
            {"json": _geosearch(("File:Test Shelter.jpg", 40.0))},
            {"json": {"query": {"pages": _imageinfo_page(1, "File:Test Shelter.jpg")}}},
        ],
    )
    _serve_image(requests_mock)

    fetch_poi_images.main()

    digest = photo_digest(JPEG_BYTES)
    assert _saved(tmp_path)["atc_shelters:glob-1"]["photo"]["digest"] == digest
    assert local_photo_path(tmp_path, digest).read_bytes() == JPEG_BYTES
    # No stray temp file: the write is atomic, so a half-written image can
    # never sit under a name promising a digest its bytes do not have.
    assert list(local_photo_path(tmp_path, digest).parent.glob("*.tmp")) == []


def test_a_found_photo_that_aged_past_the_freshness_window_is_requeried(tmp_path, monkeypatch, requests_mock):
    """Carrying an aged-out photo forward would quietly break the exact
    promise MAX_PHOTO_AGE_DAYS makes - "within two years" has to mean two
    years from the run, not from whenever the photo was first found."""
    _no_sleep(monkeypatch)
    poi = _poi()
    _use_pois(monkeypatch, tmp_path, [poi])
    prior = {"pois": {poi["id"]: {"status": "found", "checked": "2024-01-01", "photo": {"url": "u", "taken": STALE}}}}
    (tmp_path / "poi_images.json").write_text(json.dumps(prior))
    requests_mock.get(fetch_poi_images.API_URL, json=_geosearch())

    fetch_poi_images.main()

    assert requests_mock.call_count == 1  # re-queried rather than trusted
    assert _saved(tmp_path)[poi["id"]]["status"] == "none"


def test_recheck_requeries_poi_outcomes_that_would_otherwise_be_skipped(tmp_path, monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    poi = _poi()
    _use_pois(monkeypatch, tmp_path, [poi])
    prior = {"pois": {poi["id"]: {"status": "none", "checked": "2026-08-01"}}}
    (tmp_path / "poi_images.json").write_text(json.dumps(prior))
    requests_mock.get(
        fetch_poi_images.API_URL,
        [
            {"json": _geosearch(("File:Test Shelter.jpg", 40.0))},
            {"json": {"query": {"pages": _imageinfo_page(1, "File:Test Shelter.jpg")}}},
        ],
    )
    _serve_image(requests_mock)

    fetch_poi_images.run(["--recheck"])

    assert _saved(tmp_path)[poi["id"]]["status"] == "found"


def test_an_unknown_flag_is_rejected_rather_than_silently_ignored(monkeypatch):
    monkeypatch.setattr(fetch_poi_images, "main", lambda recheck=False: pytest.fail("main must not run on a bad flag"))

    with pytest.raises(SystemExit) as exc_info:
        fetch_poi_images.run(["--rechek"])

    assert exc_info.value.code == 2


def test_a_run_that_would_wipe_the_photo_set_refuses_to_persist(tmp_path, monkeypatch, requests_mock):
    """Same posture as fetch_opentrail.py's drop guard: a broken-but-200 API
    (geosearch answering empty for everything) during a --recheck must not
    silently strip every card back to placeholders. On refusal the prior
    file stays byte-identical, so the next run still compares against
    last-known-good."""
    _no_sleep(monkeypatch)
    pois = [_poi(), _poi(poi_id="atc_shelters:glob-2", name="Other Shelter", lat=41.06, lon=-73.94)]
    _use_pois(monkeypatch, tmp_path, pois)
    prior = {
        "pois": {
            pois[0]["id"]: {"status": "found", "checked": "2026-08-01", "photo": {"url": "u1", "taken": FRESH}},
            pois[1]["id"]: {"status": "found", "checked": "2026-08-01", "photo": {"url": "u2", "taken": FRESH}},
        }
    }
    prior_bytes = json.dumps(prior)
    (tmp_path / "poi_images.json").write_text(prior_bytes)
    requests_mock.get(fetch_poi_images.API_URL, json=_geosearch())

    with pytest.raises(SystemExit) as exc_info:
        fetch_poi_images.run(["--recheck"])

    assert exc_info.value.code == 1
    assert (tmp_path / "poi_images.json").read_text() == prior_bytes


def test_a_maxlag_refusal_is_waited_out_and_retried(tmp_path, monkeypatch, requests_mock):
    """maxlag=5 asks the API to refuse work while replication lags, and the
    refusal is explicitly retryable - a lagged Sunday afternoon must not
    kill a forty-minute crawl."""
    naps = _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(
        fetch_poi_images.API_URL,
        [
            {"json": {"error": {"code": "maxlag", "info": "Waiting for a database server"}}},
            {"json": _geosearch()},
        ],
    )

    fetch_poi_images.main()

    assert requests_mock.call_count == 2
    assert fetch_poi_images.MAXLAG_RETRY_SECONDS[0] in naps
    assert _saved(tmp_path)["atc_shelters:glob-1"]["status"] == "none"


def test_any_other_api_error_raises_instead_of_being_recorded_as_no_photo(tmp_path, monkeypatch, requests_mock):
    """An API error is not "this shelter has no photo" - persisting that
    reading would stick (the miss is carried forward) and be
    indistinguishable from an honest miss forever after."""
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(fetch_poi_images.API_URL, json={"error": {"code": "invalidparammix", "info": "bad request"}})

    with pytest.raises(RuntimeError, match="invalidparammix"):
        fetch_poi_images.main()

    assert not (tmp_path / "poi_images.json").exists()


def test_a_connection_fault_gets_the_backoff_then_succeeds(tmp_path, monkeypatch, requests_mock):
    naps = _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(
        fetch_poi_images.API_URL,
        [{"exc": requests.exceptions.ConnectionError}, {"json": _geosearch()}],
    )

    fetch_poi_images.main()

    assert fetch_poi_images.RETRY_BACKOFF_SECONDS[0] in naps
    assert _saved(tmp_path)["atc_shelters:glob-1"]["status"] == "none"


def test_a_429_is_retried_after_the_seconds_the_server_asked_for(tmp_path, monkeypatch, requests_mock):
    """Wikimedia's API etiquette says to expect 429 with Retry-After and back
    off. On a crawl this long that WILL happen; treating it as fatal would
    kill a forty-minute pass at POI 1900 and - worse - answer the server's
    "slow down" by re-issuing all 1900 requests on the next run."""
    naps = _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(
        fetch_poi_images.API_URL,
        [{"status_code": 429, "headers": {"Retry-After": "7"}}, {"json": _geosearch()}],
    )

    fetch_poi_images.main()

    assert 7 in naps  # the server's number, not the local backoff
    assert _saved(tmp_path)["atc_shelters:glob-1"]["status"] == "none"


def test_a_transient_5xx_is_retried_on_the_local_backoff(tmp_path, monkeypatch, requests_mock):
    naps = _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(
        fetch_poi_images.API_URL,
        [{"status_code": 503}, {"json": _geosearch()}],
    )

    fetch_poi_images.main()

    assert fetch_poi_images.RETRY_BACKOFF_SECONDS[0] in naps
    assert _saved(tmp_path)["atc_shelters:glob-1"]["status"] == "none"


def test_a_non_retryable_http_status_raises_on_the_first_attempt(tmp_path, monkeypatch, requests_mock):
    """A 404/400 is the API answering "no", not flaking - burning 35 seconds
    of backoff on an answer that already arrived helps nobody (same posture
    as fetch_topo_quads.py's retry helper)."""
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(fetch_poi_images.API_URL, status_code=404)

    with pytest.raises(requests.exceptions.HTTPError):
        fetch_poi_images.main()

    assert requests_mock.call_count == 1
    assert not (tmp_path / "poi_images.json").exists()


def test_progress_is_flushed_periodically_so_an_aborted_crawl_resumes_from_its_last_flush(tmp_path, monkeypatch, requests_mock):
    """The change-aware skip only helps across completed runs unless progress
    lands on disk mid-run: without the periodic flush, a fatal error at POI
    1900 of 2000 would discard every collected outcome and the next run
    would re-issue all 1900 requests from scratch."""
    _no_sleep(monkeypatch)
    monkeypatch.setattr(fetch_poi_images, "PROGRESS_EVERY", 1)
    first = _poi()
    second = _poi(poi_id="atc_shelters:glob-2", name="Other Shelter", lat=41.06, lon=-73.94)
    _use_pois(monkeypatch, tmp_path, [first, second])
    requests_mock.get(
        fetch_poi_images.API_URL,
        [{"json": _geosearch()}, {"status_code": 400}],
    )

    with pytest.raises(requests.exceptions.HTTPError):
        fetch_poi_images.main()

    # The first POI's outcome survived the abort; the second was never
    # recorded - so the next run re-queries exactly the unfinished remainder.
    saved = _saved(tmp_path)
    assert saved[first["id"]]["status"] == "none"
    assert second["id"] not in saved


def test_the_write_is_atomic_leaving_no_temp_file_behind(tmp_path, monkeypatch, requests_mock):
    """The output is written to a sibling temp file and os.replace'd into
    place: poi_images.json is simultaneously tens of minutes of crawling,
    the drop guard's baseline and the next run's parse input, so a plain
    truncate-and-write killed mid-way would destroy all three at once."""
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(fetch_poi_images.API_URL, json=_geosearch())

    fetch_poi_images.main()

    assert (tmp_path / "poi_images.json").exists()
    assert not (tmp_path / "poi_images.json.tmp").exists()


def test_normalized_titles_are_mapped_back_to_the_geosearch_hit(tmp_path, monkeypatch, requests_mock):
    """Real trap: ask imageinfo about "File:Test_Shelter.jpg" (underscores,
    as titles often circulate) and the API answers under the normalized
    "File:Test Shelter.jpg" plus a `normalized` mapping. Joining responses
    back to geosearch hits by raw title would silently lose every such file
    - a coverage hole with no error anywhere."""
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(
        fetch_poi_images.API_URL,
        [
            {"json": _geosearch(("File:Test_Shelter.jpg", 40.0))},
            {
                "json": {
                    "query": {
                        "normalized": [{"from": "File:Test_Shelter.jpg", "to": "File:Test Shelter.jpg"}],
                        "pages": _imageinfo_page(1, "File:Test Shelter.jpg"),
                    }
                }
            },
        ],
    )
    _serve_image(requests_mock)

    fetch_poi_images.main()

    assert _saved(tmp_path)["atc_shelters:glob-1"]["status"] == "found"


def test_the_nearest_eligible_file_wins_over_a_newer_farther_one(tmp_path, monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    nearer_older = (date.today() - timedelta(days=400)).isoformat()
    pages = {
        **_imageinfo_page(1, "File:Near.jpg", taken=nearer_older),
        **_imageinfo_page(2, "File:Far.jpg", taken=FRESH),
    }
    requests_mock.get(
        fetch_poi_images.API_URL,
        [
            {"json": _geosearch(("File:Near.jpg", 15.0), ("File:Far.jpg", 250.0))},
            {"json": {"query": {"pages": pages}}},
        ],
    )
    _serve_image(requests_mock, pageid=1)
    _serve_image(requests_mock, pageid=2)

    fetch_poi_images.main()

    assert _saved(tmp_path)["atc_shelters:glob-1"]["photo"]["title"] == "File:Near.jpg"


def test_corridor_pois_derives_exactly_the_ids_export_poi_will_write(tmp_path, monkeypatch):
    """The photo file is keyed by unified POI ids, so the derivation must
    match export_poi.py's exactly - same unify, same corridor clip - or
    photos would be fetched for ids the export never writes. Uses the real
    DuckDB corridor path on the same synthetic fixtures the export tests
    use, not a mock."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_fixture_sources(raw_dir)
    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)

    pois = fetch_poi_images.corridor_pois()

    assert {p["id"] for p in pois} == {
        "atc_shelters:shelter-glob-1",
        "atc_campsites:campsite-glob-1",
        "atc_communities:community-glob-1",
        "atc_viewpoints:viewpoint-glob-1",
        "atc_parking:parking-glob-1",
        "atc_privies:privy-glob-1",
        "opentrail_at:100",
        "opentrail_at:101",
        "opentrail_at:102",
    }


def test_a_run_with_no_corridor_pois_fails_loudly_instead_of_writing_an_empty_file(tmp_path, monkeypatch):
    _use_pois(monkeypatch, tmp_path, [])

    with pytest.raises(SystemExit) as exc_info:
        fetch_poi_images.main()

    assert exc_info.value.code == 1
    assert not (tmp_path / "poi_images.json").exists()


def test_a_geotagged_pdf_beside_a_real_photo_does_not_abort_the_crawl(tmp_path, monkeypatch, requests_mock):
    """Measured against the live API (2026-08-08): asking imageinfo for a
    sized thumbnail of a multipage file answers `urlparamnormal` and fails
    the WHOLE batched call, not just that title. Since api_get raises on any
    non-maxlag error, one geotagged PDF - a scanned survey map carries
    coordinates precisely because it depicts a place - would abort the crawl
    and lose the eligible JPEG batched next to it. So the PDF must never
    reach the request."""
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(
        fetch_poi_images.API_URL,
        [
            {"json": _geosearch(("File:Old survey of the gap.pdf", 10.0), ("File:Test Shelter.jpg", 40.0))},
            {"json": {"query": {"pages": _imageinfo_page(1, "File:Test Shelter.jpg")}}},
        ],
    )
    _serve_image(requests_mock)

    fetch_poi_images.main()

    assert _saved(tmp_path)["atc_shelters:glob-1"]["status"] == "found"
    imageinfo_request = requests_mock.request_history[1]
    assert imageinfo_request.qs["titles"] == ["file:test shelter.jpg"]  # the PDF was never asked about


def test_a_poi_whose_only_nearby_files_are_unusable_types_skips_the_imageinfo_call(tmp_path, monkeypatch, requests_mock):
    """Nothing shippable nearby means nothing to ask about - and an
    all-filtered batch must not send `titles=` empty, which the API answers
    as an error rather than an empty result."""
    _no_sleep(monkeypatch)
    _use_pois(monkeypatch, tmp_path, [_poi()])
    requests_mock.get(
        fetch_poi_images.API_URL,
        json=_geosearch(("File:Trail map.svg", 10.0), ("File:Scan.djvu", 20.0)),
    )

    fetch_poi_images.main()

    assert _saved(tmp_path)["atc_shelters:glob-1"] == {"status": "none", "checked": date.today().isoformat()}
    assert requests_mock.call_count == 1  # geosearch only
