"""Tests for fetch_atc_photos.py - the ATC facility-photo fetch. All HTTP is
mocked (TESTING.md); the ATC layers are tiny synthetic GeoJSON built in test
code, and the licence registry is written per-test so no test depends on the
real sources.json staying as it is.
"""

import json
from datetime import date, timedelta

import pytest

import fetch_atc_photos as atc
from lib.photo_store import local_photo_path, photo_digest

FRESH = date.today() - timedelta(days=100)
INVENTORY_ERA = date.today() - timedelta(days=int(365.25 * 10))  # ~2016: old, but inside ATC's window
ANCIENT = date.today() - timedelta(days=atc.MAX_PHOTO_AGE_DAYS + 400)

JPEG_BYTES = b"\xff\xd8\xff\xe0 pretend shelter rendering"

DRIVE_ID = "1c4xsm-MnGZPWtLxbaaTrY6g9vdCp0Z4m"
DRIVE_URL = f"https://drive.google.com/file/d/{DRIVE_ID}/view?usp=drivesdk"
WORKSPACE_URL = f"https://drive.google.com/a/appalachiantrail.org/file/d/{DRIVE_ID}/view?usp=drivesdk"


def _exif_header(taken: date) -> bytes:
    """A JPEG header carrying a DateTimeOriginal in the colon form cameras
    write, padded so the slicing is exercised."""
    stamp = taken.strftime("%Y:%m:%d 09:00:30").encode()
    return b"\xff\xd8\xff\xe1" + b"\x00" * 200 + b"Exif\x00\x00" + stamp + b"\x00" * 500


def _feature(global_id="glob-1", name="Test Shelter", **photos):
    props = {"GlobalID": global_id, "Name": name}
    props.update(photos)
    return {"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [-73.9, 41.0]}}


def _write_layers(tmp_path, monkeypatch, shelters=(), campsites=()):
    monkeypatch.setattr(atc, "RAW_DIR", tmp_path)
    monkeypatch.setattr(atc, "OUT_PATH", tmp_path / "poi_images_atc.json")
    for stem, feats in (("shelters", shelters), ("campsites", campsites)):
        (tmp_path / f"{stem}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": list(feats)}))


def _write_registry(tmp_path, monkeypatch, block=None):
    path = tmp_path / "sources.json"
    registry = {"sources": []}
    if block is not None:
        registry["photo_licence"] = block
    path.write_text(json.dumps(registry))
    monkeypatch.setattr(atc, "SOURCES_PATH", path)
    return path


DEFAULT_CREDIT = {"author": "Appalachian Trail Conservancy", "license": "© ATC, used with permission"}


def _no_sleep(monkeypatch):
    monkeypatch.setattr(atc.time, "sleep", lambda _s: None)


def _serve(requests_mock, taken=INVENTORY_ERA, image=JPEG_BYTES):
    """The two calls one photo costs: a Range read of the original for its
    EXIF date, then the 640px rendering."""
    requests_mock.get(atc.DOWNLOAD_URL, content=_exif_header(taken))
    requests_mock.get(atc.THUMBNAIL_URL, content=image)


def _saved(tmp_path):
    return json.loads((tmp_path / "poi_images_atc.json").read_text())["pois"]


# --- URL and EXIF parsing ---


@pytest.mark.parametrize("url", [DRIVE_URL, WORKSPACE_URL])
def test_the_drive_id_is_read_from_both_link_forms(url):
    """ATC's data mixes plain share links with Workspace-scoped
    /a/appalachiantrail.org/ ones. Handling only the first would silently drop
    a large share of the corpus."""
    assert atc.drive_file_id(url) == DRIVE_ID


def test_a_non_drive_url_has_no_file_id():
    assert atc.drive_file_id("https://example.org/photo.jpg") is None


def test_photo_urls_ignores_atcs_placeholder_values():
    """Roughly a third of these fields hold "0", "1" or "NoInfo" rather than a
    link. Treating those as URLs would turn a third of the corpus into fetch
    errors."""
    props = {"Photo1": "0", "Photo2": DRIVE_URL, "Photo3": "NoInfo", "Photo4": "", "Photo5": None, "Photo6": WORKSPACE_URL}

    assert atc.photo_urls(props) == [DRIVE_URL, WORKSPACE_URL]


def test_photo_urls_preserves_atcs_own_ordering():
    props = {"Photo3": "https://drive.google.com/file/d/cccccccccc/view", "Photo1": DRIVE_URL}

    assert atc.photo_urls(props)[0] == DRIVE_URL


def test_parse_exif_date_reads_the_capture_date_out_of_a_header():
    assert atc.parse_exif_date(_exif_header(date(2016, 9, 12))) == date(2016, 9, 12)


def test_parse_exif_date_returns_none_rather_than_guessing():
    """An undated photo cannot honestly claim an age, and the card prints this
    month - so no date means no photo, not a photo with a made-up date."""
    assert atc.parse_exif_date(b"\xff\xd8" + b"\x00" * 1000) is None
    assert atc.parse_exif_date(_exif_header(date(2016, 9, 12)).replace(b"2016:09:12", b"2016:99:99")) is None


# --- the freshness bar is this source's own ---


def test_the_inventory_era_photos_this_source_exists_for_are_inside_its_window(tmp_path, monkeypatch, requests_mock):
    """The whole point of a per-source bar: a ~2016 ATC photo ships here,
    where Commons' four-year window would reject every one of them."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])
    _serve(requests_mock, taken=INVENTORY_ERA)

    atc.main()

    record = _saved(tmp_path)["atc_shelters:glob-1"]
    assert record["status"] == "found"
    assert record["photos"][0]["taken"] == INVENTORY_ERA.isoformat()
    assert record["photos"][0]["author"] == "Appalachian Trail Conservancy"
    assert record["photos"][0]["license"] == "© ATC, used with permission"


def test_a_photo_older_than_this_sources_own_window_is_still_rejected(tmp_path, monkeypatch, requests_mock):
    """Long is not absent. Twelve years is a judgement that a shelter may have
    been rebuilt since; past it the placeholder is the honest answer."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])
    _serve(requests_mock, taken=ANCIENT)

    atc.main()

    assert _saved(tmp_path)["atc_shelters:glob-1"]["status"] == "none"


def test_a_later_photo_slot_is_tried_when_an_earlier_one_is_undatable(tmp_path, monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    second = "https://drive.google.com/file/d/2bbbbbbbbbbbbbbbbbb/view"
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL, Photo2=second)])
    requests_mock.get(atc.DOWNLOAD_URL, [{"content": b"\xff\xd8" + b"\x00" * 900}, {"content": _exif_header(INVENTORY_ERA)}])
    requests_mock.get(atc.THUMBNAIL_URL, content=JPEG_BYTES)

    atc.main()

    assert _saved(tmp_path)["atc_shelters:glob-1"]["status"] == "found"


# --- the licence basis is recorded, not invented ---


def test_a_missing_licence_record_stops_the_fetch_before_a_single_byte(tmp_path, monkeypatch, requests_mock):
    """CONTRIBUTING.md: establish the licence first and record it. A fetch that
    downloaded ATC's photographs and then wondered what to credit them as would
    have the order exactly backwards."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, None)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])

    with pytest.raises(RuntimeError, match="photo_licence"):
        atc.main()

    assert requests_mock.call_count == 0


def test_an_incomplete_licence_record_is_refused_too(tmp_path, monkeypatch):
    _write_registry(tmp_path, monkeypatch, {"author": "Appalachian Trail Conservancy"})

    with pytest.raises(RuntimeError, match="photo_licence"):
        atc.photo_credit()


def test_the_real_registry_carries_a_usable_licence_block(monkeypatch):
    """Guards the shipped sources.json rather than a fixture: if the recorded
    basis is ever dropped, this fetch must not quietly keep running."""
    credit = atc.photo_credit()

    assert credit["author"]
    assert credit["license"]
    assert credit["basis"]


# --- bytes, caching, and the store publish.py reads ---


def test_the_rendering_is_cached_under_its_own_digest(tmp_path, monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])
    _serve(requests_mock)

    atc.main()

    digest = photo_digest(JPEG_BYTES)
    assert _saved(tmp_path)["atc_shelters:glob-1"]["photos"][0]["digest"] == digest
    assert local_photo_path(tmp_path, digest).read_bytes() == JPEG_BYTES


def test_the_sized_rendering_is_requested_never_the_original(tmp_path, monkeypatch, requests_mock):
    """Originals run to 6.8 MB for a 264px slot. Asking Drive for the width-
    sized rendering is also what keeps this source inside "no image pipeline of
    our own"."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])
    _serve(requests_mock)

    atc.main()

    thumb_request = [r for r in requests_mock.request_history if atc.THUMBNAIL_URL in r.url][0]
    assert thumb_request.qs["sz"] == [f"w{atc.IMAGE_WIDTH_PX}"]


def test_the_capture_date_is_read_over_a_range_request(tmp_path, monkeypatch, requests_mock):
    """The date must be real, and the whole file must not be transferred to get
    it - 270 shelters at ~2 MB each is half a gigabyte for a date."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])
    _serve(requests_mock)

    atc.main()

    original_request = [r for r in requests_mock.request_history if atc.DOWNLOAD_URL in r.url][0]
    assert original_request.headers["Range"] == f"bytes=0-{atc.EXIF_HEADER_BYTES - 1}"


def test_a_prior_outcome_is_carried_forward_without_refetching(tmp_path, monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])
    digest = photo_digest(JPEG_BYTES)
    path = local_photo_path(tmp_path, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(JPEG_BYTES)
    (tmp_path / "poi_images_atc.json").write_text(
        json.dumps({"pois": {"atc_shelters:glob-1": {"status": "found", "checked": "2026-08-08", "photo": {"digest": digest}}}})
    )

    atc.main()

    assert requests_mock.call_count == 0


def test_a_found_photo_whose_bytes_are_gone_is_refetched(tmp_path, monkeypatch, requests_mock):
    """A cleared data/ tree must not leave the outcomes file promising images
    publish.py would never upload - a card pointing at a 404."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])
    (tmp_path / "poi_images_atc.json").write_text(
        json.dumps({"pois": {"atc_shelters:glob-1": {"status": "found", "checked": "2026-08-08", "photo": {"digest": "beef"}}}})
    )
    _serve(requests_mock)

    atc.main()

    assert _saved(tmp_path)["atc_shelters:glob-1"]["photos"][0]["digest"] == photo_digest(JPEG_BYTES)


# --- ids, layers, flags ---


def test_ids_match_what_export_poi_will_write(tmp_path, monkeypatch, requests_mock):
    """The join key between this fetch and the export. lib/poi_schema builds
    f"{source}:{GlobalID}"; if these drift, every photo silently fails to
    attach and the export reports zero with no error anywhere."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(
        tmp_path,
        monkeypatch,
        shelters=[_feature(global_id="sh-9", Photo1=DRIVE_URL)],
        campsites=[_feature(global_id="cs-4", Photo1=DRIVE_URL)],
    )
    _serve(requests_mock)

    atc.main()

    assert set(_saved(tmp_path)) == {"atc_shelters:sh-9", "atc_campsites:cs-4"}


def test_a_feature_with_no_photo_reference_is_not_recorded_at_all(tmp_path, monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(
        tmp_path, monkeypatch, shelters=[_feature(global_id="sh-1", Photo1="0"), _feature(global_id="sh-2", Photo1=DRIVE_URL)]
    )
    _serve(requests_mock)

    atc.main()

    assert set(_saved(tmp_path)) == {"atc_shelters:sh-2"}


def test_a_run_with_no_atc_features_fails_loudly_instead_of_writing_an_empty_file(tmp_path, monkeypatch):
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch)

    with pytest.raises(SystemExit):
        atc.main()

    assert not (tmp_path / "poi_images_atc.json").exists()


def test_an_unknown_flag_is_rejected_rather_than_silently_ignored(monkeypatch):
    with pytest.raises(SystemExit) as excinfo:
        atc.run(["--rechek"])

    assert excinfo.value.code == 2


# --- Every eligible photo, not just the first (#471) ---


def _url(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view?usp=drivesdk"


def _serve_per_id(requests_mock, ids: dict[str, date], image_for=None):
    """Distinct bytes per Drive id, so digests differ and order is provable.

    `_serve` answers every id identically, which is fine when there is one
    photo and useless when the question is which ones came back and in what
    order.
    """

    def exif(request, context):
        return _exif_header(ids[request.qs["id"][0]])

    def rendering(request, context):
        file_id = request.qs["id"][0]
        return (image_for or (lambda fid: JPEG_BYTES + fid.encode()))(file_id)

    requests_mock.get(atc.DOWNLOAD_URL, content=exif)
    requests_mock.get(atc.THUMBNAIL_URL, content=rendering)


def test_every_eligible_photo_is_kept_in_atcs_own_order(tmp_path, monkeypatch, requests_mock):
    """The finding behind #471: 433 of 489 POIs carry more than one photo and
    812 were being discarded. ATC's Photo1..Photo10 order is its judgement
    about which picture best shows the facility, so it is preserved rather
    than re-ranked."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(
        tmp_path,
        monkeypatch,
        shelters=[_feature(Photo1=_url("aaa1111111"), Photo2=_url("bbb2222222"), Photo3=_url("ccc3333333"))],
    )
    _serve_per_id(requests_mock, {"aaa1111111": INVENTORY_ERA, "bbb2222222": INVENTORY_ERA, "ccc3333333": INVENTORY_ERA})

    atc.main()

    photos = _saved(tmp_path)["atc_shelters:glob-1"]["photos"]
    assert [photo["url"] for photo in photos] == [_url("aaa1111111"), _url("bbb2222222"), _url("ccc3333333")]
    assert len({photo["digest"] for photo in photos}) == 3


def test_the_first_eligible_photo_is_still_the_card_photo(tmp_path, monkeypatch, requests_mock):
    """Photo1 being unusable used to mean Photo2 became the single record.
    It still becomes the first of the list, so the card is unchanged by this."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(
        tmp_path,
        monkeypatch,
        shelters=[_feature(Photo1="NoInfo", Photo2=_url("bbb2222222"), Photo3=_url("ccc3333333"))],
    )
    _serve_per_id(requests_mock, {"bbb2222222": INVENTORY_ERA, "ccc3333333": INVENTORY_ERA})

    photos = (atc.main(), _saved(tmp_path)["atc_shelters:glob-1"]["photos"])[1]

    assert photos[0]["url"] == _url("bbb2222222")
    assert len(photos) == 2


def test_an_undated_slot_is_skipped_without_ending_the_scan(tmp_path, monkeypatch, requests_mock):
    """A middle slot failing the bar must not truncate the ones after it -
    that would be the old early-return wearing a different shape."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(
        tmp_path,
        monkeypatch,
        shelters=[_feature(Photo1=_url("aaa1111111"), Photo2=_url("bbb2222222"), Photo3=_url("ccc3333333"))],
    )
    # The middle one predates even this source's long window.
    _serve_per_id(
        requests_mock,
        {"aaa1111111": INVENTORY_ERA, "bbb2222222": date(1999, 1, 1), "ccc3333333": INVENTORY_ERA},
    )

    atc.main()

    photos = _saved(tmp_path)["atc_shelters:glob-1"]["photos"]
    assert [photo["url"] for photo in photos] == [_url("aaa1111111"), _url("ccc3333333")]


def test_a_prior_record_in_the_old_single_photo_shape_is_still_understood(tmp_path, monkeypatch, requests_mock):
    """This file is the next run's SKIP input. Refusing to read the shape
    written before #471 would re-fetch all 489 POIs and ~1,600 slots to learn
    what is already on disk."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])
    digest = photo_digest(JPEG_BYTES)
    path = local_photo_path(tmp_path, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(JPEG_BYTES)
    (tmp_path / "poi_images_atc.json").write_text(
        json.dumps({"pois": {"atc_shelters:glob-1": {"status": "found", "checked": "2026-08-08", "photo": {"digest": digest}}}})
    )

    atc.main()

    assert requests_mock.call_count == 0
    assert atc.record_photos(_saved(tmp_path)["atc_shelters:glob-1"]) == [{"digest": digest}]


def test_one_missing_digest_among_several_refetches_the_whole_poi(tmp_path, monkeypatch, requests_mock):
    """Otherwise the export ships references to objects publish.py never
    uploaded, and a hiker paging through the card reaches a broken image."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])
    present = photo_digest(JPEG_BYTES)
    path = local_photo_path(tmp_path, present)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(JPEG_BYTES)
    (tmp_path / "poi_images_atc.json").write_text(
        json.dumps(
            {
                "pois": {
                    "atc_shelters:glob-1": {
                        "status": "found",
                        "checked": "2026-08-08",
                        "photos": [{"digest": present}, {"digest": "beef"}],
                    }
                }
            }
        )
    )
    _serve(requests_mock)

    atc.main()

    assert requests_mock.call_count > 0
