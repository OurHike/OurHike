"""Tests for fetch_atc_photos.py - the ATC facility-photo fetch. All HTTP is
mocked (TESTING.md); the ATC layers are tiny synthetic GeoJSON built in test
code, and the licence registry is written per-test so no test depends on the
real sources.json staying as it is.
"""

import json
from datetime import date, timedelta

import pytest
import requests

import export_poi
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


def _write_layers(tmp_path, monkeypatch, shelters=(), campsites=(), viewpoints=(), parking=(), privies=()):
    monkeypatch.setattr(atc, "RAW_DIR", tmp_path)
    monkeypatch.setattr(atc, "OUT_PATH", tmp_path / "poi_images_atc.json")
    for stem, feats in (
        ("shelters", shelters),
        ("campsites", campsites),
        ("viewpoints", viewpoints),
        ("parking", parking),
        ("privies", privies),
    ):
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
    assert len(record["photos"]) == 1
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


def test_every_photo_layer_is_wired_to_the_source_name_the_export_publishes():
    """The layer list and export_poi.DIRECT_SOURCES must agree, name for name.

    The mechanism is the same silence test_ids_match_what_export_poi_will_write
    covers, reached the other way: that test proves the id SHAPE is right for
    the layers this fixture happens to write, and would pass just as happily
    with a layer wired to "atc_vistas" while the export publishes
    "atc_viewpoints". Nothing would raise - the photos would simply attach to
    no POI, and the export would print a smaller number nobody has a
    reference for.
    """
    export_sources = {stem: source for stem, _poi_type, source, _fields in export_poi.DIRECT_SOURCES}

    for stem, source in atc.PHOTO_LAYERS:
        assert stem in export_sources, f"{stem} carries photos but export_poi.py publishes no such layer"
        assert export_sources[stem] == source, f"{stem}: photos keyed {source!r}, export publishes {export_sources[stem]!r}"


def test_every_atc_layer_carrying_photos_is_fetched_for_every_poi_type_that_has_one(tmp_path, monkeypatch, requests_mock):
    """The three layers that joined shelters and campsites when they became
    POI types (#POI vistas/parking/privies).

    They are the whole photo story for those categories: fetch_poi_images.py
    deliberately does not crawl Commons for them, so a layer quietly dropped
    from PHOTO_LAYERS is a category whose cards all fall back to the glyph
    placeholder with nothing anywhere reporting a loss.
    """
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(
        tmp_path,
        monkeypatch,
        viewpoints=[_feature(global_id="vp-1", name="Test Vista", Photo1=DRIVE_URL)],
        parking=[_feature(global_id="pk-1", name="Test Rd Parking Area", Photo1=DRIVE_URL)],
        privies=[_feature(global_id="pv-1", name="Test Shelter Privy", Photo1=DRIVE_URL)],
    )
    _serve(requests_mock)

    atc.main()

    assert set(_saved(tmp_path)) == {"atc_viewpoints:vp-1", "atc_parking:pk-1", "atc_privies:pv-1"}


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


# --- every photo, not just the first ---


def test_every_eligible_photo_is_kept_in_atcs_own_order(tmp_path, monkeypatch, requests_mock):
    """The whole point of #471: 433 of 489 features carry more than one photo,
    and taking only the first discarded 812 real photographs. ATC's
    Photo1..Photo10 order is their judgement about which best shows the
    facility, so it is preserved rather than re-ranked."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    second = "https://drive.google.com/file/d/2bbbbbbbbbbbbbbbbbbb/view"
    third = "https://drive.google.com/a/appalachiantrail.org/file/d/3ccccccccccccccccccc/view"
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL, Photo2=second, Photo3=third)])
    requests_mock.get(atc.DOWNLOAD_URL, content=_exif_header(INVENTORY_ERA))
    requests_mock.get(
        atc.THUMBNAIL_URL, [{"content": b"\xff\xd8 one"}, {"content": b"\xff\xd8 two"}, {"content": b"\xff\xd8 three"}]
    )

    atc.main()

    photos = _saved(tmp_path)["atc_shelters:glob-1"]["photos"]
    assert [p["url"] for p in photos] == [DRIVE_URL, second, third]
    assert [p["digest"] for p in photos] == [photo_digest(b) for b in (b"\xff\xd8 one", b"\xff\xd8 two", b"\xff\xd8 three")]


def test_an_ineligible_slot_is_skipped_without_disturbing_the_order_of_the_rest(tmp_path, monkeypatch, requests_mock):
    """A POI whose Photo1 is undated still shows Photo2 first - the survivors
    keep their relative order rather than the whole POI being lost."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    second = "https://drive.google.com/file/d/2bbbbbbbbbbbbbbbbbbb/view"
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL, Photo2=second)])
    requests_mock.get(atc.DOWNLOAD_URL, [{"content": b"\xff\xd8" + b"\x00" * 900}, {"content": _exif_header(INVENTORY_ERA)}])
    requests_mock.get(atc.THUMBNAIL_URL, content=JPEG_BYTES)

    photos = _saved_after(atc, tmp_path)

    assert [p["url"] for p in photos] == [second]


def _saved_after(module, tmp_path):
    module.main()
    return _saved(tmp_path)["atc_shelters:glob-1"]["photos"]


def test_every_photos_bytes_must_be_present_or_the_poi_is_refetched(tmp_path, monkeypatch):
    """A POI's photos are fetched and recorded together, so a half-present set
    is not a usable outcome - publish.py would upload some of a list the
    artifact claims in full, and the card's later slots would 404."""
    monkeypatch.setattr(atc, "RAW_DIR", tmp_path)
    present = _cache(tmp_path, b"\xff\xd8 here")

    intact = {"status": "found", "photos": [{"digest": present}]}
    partial = {"status": "found", "photos": [{"digest": present}, {"digest": "absent"}]}

    assert atc.cached_photo_missing(intact) is False
    assert atc.cached_photo_missing(partial) is True


def _cache(tmp_path, content):
    digest = photo_digest(content)
    path = local_photo_path(tmp_path, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return digest


def test_an_outcome_file_written_before_galleries_is_still_read(tmp_path, monkeypatch):
    """Runs before #471 wrote a single `photo` object. Failing to read that
    shape would make the first run after upgrading re-fetch every image it
    already holds - ~450 downloads to learn nothing."""
    monkeypatch.setattr(atc, "RAW_DIR", tmp_path)
    digest = _cache(tmp_path, JPEG_BYTES)
    old_shape = {"status": "found", "checked": "2026-08-08", "photo": {"digest": digest}}

    assert atc.record_photos(old_shape) == [{"digest": digest}]
    assert atc.cached_photo_missing(old_shape) is False


# --- a photo reference Drive will not serve --------------------------------


def test_a_dead_photo_link_skips_that_slot_instead_of_killing_the_run(tmp_path, monkeypatch, requests_mock):
    """The failure that took a whole data release down.

    One of the 1,524 references - `Annapolis Rock (US 40) Parking Area`'s
    Photo2 - 404s, and `raise_for_status` turned that into an unhandled
    HTTPError 30 minutes and ~1,050 POIs into the crawl. Every export, the
    quality gate and the publish step were skipped behind it, so a single
    deleted file in somebody else's Drive folder meant no data release at all.

    A file Drive will not serve is a fact about that slot, not a broken run,
    and it is handled the way an undated photo already was: skip it, take the
    next one.
    """
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    second = "https://drive.google.com/file/d/2bbbbbbbbbbbbbbbbbb/view"
    _write_layers(tmp_path, monkeypatch, parking=[_feature(global_id="pk-1", Photo1=DRIVE_URL, Photo2=second)])
    requests_mock.get(atc.DOWNLOAD_URL, [{"status_code": 404}, {"content": _exif_header(INVENTORY_ERA)}])
    requests_mock.get(atc.THUMBNAIL_URL, content=JPEG_BYTES)

    atc.main()

    record = _saved(tmp_path)["atc_parking:pk-1"]
    assert record["status"] == "found"
    assert [photo["url"] for photo in record["photos"]] == [second]


@pytest.mark.parametrize("status", [403, 404, 410])
def test_every_way_drive_says_no_such_file_is_treated_the_same(status, tmp_path, monkeypatch, requests_mock):
    """Deleted, sharing changed, or an id that was never right - one slot with
    no photo behind it, whichever way Drive words it."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, privies=[_feature(global_id="pv-1", Photo1=DRIVE_URL)])
    requests_mock.get(atc.DOWNLOAD_URL, status_code=status)

    atc.main()

    assert _saved(tmp_path)["atc_privies:pv-1"]["status"] == "none"


def test_a_rendering_that_disappears_between_the_two_calls_is_skipped_too(tmp_path, monkeypatch, requests_mock):
    """Both fetches are wrapped, not just the first. A file can answer the
    Range request for its EXIF and then refuse the thumbnail, and the slot has
    no photo either way."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, viewpoints=[_feature(global_id="vp-1", Photo1=DRIVE_URL)])
    requests_mock.get(atc.DOWNLOAD_URL, content=_exif_header(INVENTORY_ERA))
    requests_mock.get(atc.THUMBNAIL_URL, status_code=404)

    atc.main()

    assert _saved(tmp_path)["atc_viewpoints:vp-1"]["status"] == "none"


def test_drive_being_broken_still_stops_the_run(tmp_path, monkeypatch, requests_mock):
    """The other half of the decision, and the one that keeps this narrow. A
    500 after its retries is Drive failing, not a file that is gone - and a
    crawl that finished by quietly dropping every photo is exactly what this
    pipeline's drop guards exist to catch."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, shelters=[_feature(Photo1=DRIVE_URL)])
    requests_mock.get(atc.DOWNLOAD_URL, status_code=500)

    with pytest.raises(requests.exceptions.HTTPError):
        atc.main()


def test_the_skipped_references_are_reported_rather_than_swallowed(tmp_path, monkeypatch, requests_mock, capsys):
    """A corpus rotting quietly is the thing to notice: these are references
    in ATC's own column that no longer resolve, and the count is what would
    tell them."""
    _no_sleep(monkeypatch)
    _write_registry(tmp_path, monkeypatch, DEFAULT_CREDIT)
    _write_layers(tmp_path, monkeypatch, parking=[_feature(global_id="pk-1", Photo1=DRIVE_URL)])
    requests_mock.get(atc.DOWNLOAD_URL, status_code=404)

    atc.main()

    assert "1 photo reference(s) Drive would not serve" in capsys.readouterr().out
