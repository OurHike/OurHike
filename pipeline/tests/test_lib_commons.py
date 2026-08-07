"""Tests for lib/commons.py - the pure eligibility/selection rules deciding
which Wikimedia Commons files may ship on a waypoint card. All fixtures are
tiny synthetic imageinfo dicts built in test code (see TESTING.md); the API
shapes they imitate were checked against real Commons API responses while
building fetch_poi_images.py (2026-08-07).
"""

from datetime import date

import pytest

from lib.commons import eligible_photo, license_allows_reuse, meta_value, parse_date_taken, pick_photo, strip_html

CUTOFF = date(2024, 8, 7)


def _meta(value):
    return {"value": value, "source": "commons-desc-page"}


def _imageinfo(
    taken="2025-06-18 14:22:31",
    license_id="cc-by-sa-4.0",
    license_short="CC BY-SA 4.0",
    artist='<a href="//commons.wikimedia.org/wiki/User:JD">Jane Doe</a>',
    attribution=None,
    mime="image/jpeg",
    thumburl="https://upload.wikimedia.org/thumb/shelter-640.jpg",
    url="https://upload.wikimedia.org/shelter.jpg",
):
    """One imageinfo entry the way the API really shapes it - extmetadata
    values wrapped in {"value": ...} dicts, keys absent when unknown."""
    extmetadata = {}
    if taken is not None:
        extmetadata["DateTimeOriginal"] = _meta(taken)
    if license_id is not None:
        extmetadata["License"] = _meta(license_id)
    if license_short is not None:
        extmetadata["LicenseShortName"] = _meta(license_short)
    if artist is not None:
        extmetadata["Artist"] = _meta(artist)
    if attribution is not None:
        extmetadata["Attribution"] = _meta(attribution)
    info = {"mime": mime, "url": url, "descriptionurl": "https://commons.wikimedia.org/wiki/File:Shelter.jpg"}
    if thumburl is not None:
        info["thumburl"] = thumburl
    return {**info, "extmetadata": extmetadata}


# --- license_allows_reuse ---


@pytest.mark.parametrize(
    ("license_id", "allowed"),
    [
        ("cc-by-sa-4.0", True),
        ("cc-by-4.0", True),
        ("CC-BY-SA-4.0", True),  # case must not matter
        ("cc0", True),
        ("pd", True),
        ("pd-us", True),
        ("cc-by-nc-4.0", False),
        ("cc-by-nc-sa-2.0", False),
        ("cc-by-nd-4.0", False),
        ("gfdl", False),
        ("copyrighted-free-use-maybe", False),  # unknown ids are rejected, not shipped-and-hoped
        ("", False),
    ],
)
def test_license_allows_reuse(license_id, allowed):
    assert license_allows_reuse(license_id) is allowed


def test_nc_is_rejected_even_though_the_id_starts_with_cc_by():
    """The trap a naive prefix allowlist would fall into: "cc-by-nc-4.0"
    starts with "cc-by", so prefix matching would ship NonCommercial photos -
    putting any future paid tier (features/PRICING_MODEL.md territory) in
    licence breach the day it launches."""
    assert license_allows_reuse("cc-by-nc-4.0") is False
    assert license_allows_reuse("cc-by-4.0") is True


@pytest.mark.parametrize("license_id", ["cc-by-2.0", "cc-by-2.5", "cc-by-3.0", "cc-by-sa-2.0", "cc-by-sa-3.0"])
def test_pre_4_0_cc_licences_are_rejected_because_one_link_cannot_meet_them(license_id):
    """CC 4.0's s3(a)(2) lets a single link to the Commons file page satisfy
    attribution; the 2.0/2.5/3.0 licences instead require the licence URI
    itself to ship with every copy, which the card's one-link credit line
    does not do. Realistic input, not a corner: Flickr-to-Commons imports
    arrive as cc-by-2.0 with current EXIF dates, so without this gate a
    fresh, ineligible photo ships in breach."""
    assert license_allows_reuse(license_id) is False


# --- parse_date_taken ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2025-06-18 14:22:31", date(2025, 6, 18)),  # the common Commons shape
        ("2025:06:18 14:22:31", date(2025, 6, 18)),  # raw EXIF colons
        ('<time class="dtstart" datetime="2013-07-29">29 July 2013</time>', date(2013, 7, 29)),
        ("May 2016", None),  # a prose age cannot honestly pass a freshness bar
        ("circa 1998", None),
        ("", None),
        ("2025-99-99", None),  # digits in the right shape but not a date
    ],
)
def test_parse_date_taken(raw, expected):
    assert parse_date_taken(raw) == expected


# --- strip_html / meta_value ---


def test_strip_html_flattens_commons_artist_markup_to_a_creditable_name():
    assert strip_html('<a href="//commons.wikimedia.org/wiki/User:JD">Jane&nbsp;Doe</a>') == "Jane Doe"
    assert strip_html("  plain   name  ") == "plain name"


def test_meta_value_reads_the_api_wrapper_and_tolerates_absent_keys():
    extmetadata = {"License": _meta("cc0"), "Artist": {"value": None}}
    assert meta_value(extmetadata, "License") == "cc0"
    assert meta_value(extmetadata, "Artist") == ""
    assert meta_value(extmetadata, "DateTimeOriginal") == ""


# --- eligible_photo ---


def test_eligible_photo_builds_the_full_record_for_a_shippable_file():
    record = eligible_photo("File:Shelter.jpg", 42.5, _imageinfo(), cutoff=CUTOFF)

    assert record == {
        "title": "File:Shelter.jpg",
        "distance_m": 42.5,
        "url": "https://upload.wikimedia.org/thumb/shelter-640.jpg",  # the sized thumb, not the original
        "page_url": "https://commons.wikimedia.org/wiki/File:Shelter.jpg",
        "author": "Jane Doe",
        "license": "CC BY-SA 4.0",
        "taken": "2025-06-18",
    }


def test_eligible_photo_rejects_non_jpeg_files():
    """The mime gate is the maps-and-diagrams filter: Commons geosearch
    happily returns SVG trail maps and PNG elevation charts sitting on the
    same coordinates, and none of those are "a picture of the place"."""
    assert eligible_photo("File:Map.svg", 5.0, _imageinfo(mime="image/svg+xml"), cutoff=CUTOFF) is None
    assert eligible_photo("File:Chart.png", 5.0, _imageinfo(mime="image/png"), cutoff=CUTOFF) is None


def test_eligible_photo_rejects_a_photo_older_than_the_cutoff():
    assert eligible_photo("File:Old.jpg", 5.0, _imageinfo(taken="2019-05-01 09:00:00"), cutoff=CUTOFF) is None


def test_eligible_photo_rejects_a_file_with_no_parseable_capture_date():
    """No EXIF date, no deal - both because an unknown age cannot pass an
    age bar, and because scans/diagrams/renders are exactly the files that
    lack one."""
    assert eligible_photo("File:Scan.jpg", 5.0, _imageinfo(taken=None), cutoff=CUTOFF) is None
    assert eligible_photo("File:Scan.jpg", 5.0, _imageinfo(taken="around 2003"), cutoff=CUTOFF) is None


def test_eligible_photo_rejects_licences_ourhike_cannot_meet():
    assert eligible_photo("File:NC.jpg", 5.0, _imageinfo(license_id="cc-by-nc-4.0"), cutoff=CUTOFF) is None
    assert eligible_photo("File:NoLicence.jpg", 5.0, _imageinfo(license_id=None), cutoff=CUTOFF) is None


def test_eligible_photo_requires_an_author_for_attribution_licences():
    """CC BY's whole deal is the credit. A CC BY photo with nobody to name
    is unusable, not "usable, uncredited"."""
    assert eligible_photo("File:Anon.jpg", 5.0, _imageinfo(artist=None), cutoff=CUTOFF) is None


def test_eligible_photo_ships_public_domain_files_with_no_author_to_credit():
    record = eligible_photo(
        "File:PD.jpg", 5.0, _imageinfo(license_id="pd", license_short="Public domain", artist=None), cutoff=CUTOFF
    )

    assert record is not None
    assert record["author"] is None
    assert record["license"] == "Public domain"


def test_eligible_photo_honors_an_explicit_attribution_field_over_artist():
    """A file's Attribution field is the uploader saying "credit me exactly
    like this" - the licence makes honoring it the condition of use."""
    info = _imageinfo(attribution="Photo courtesy of the Green Mountain Club")
    record = eligible_photo("File:GMC.jpg", 5.0, info, cutoff=CUTOFF)

    assert record is not None
    assert record["author"] == "Photo courtesy of the Green Mountain Club"


def test_eligible_photo_rejects_a_file_with_no_sized_thumbnail_rather_than_shipping_the_original():
    """Commons originals are full-resolution camera files - a shelter photo
    is routinely 3-15 MB - and the card's slot is 264 CSS pixels wide.
    Falling back to the original would put a multi-megabyte download on a
    hiker's data plan to fill a thumbnail-sized box. No sized rendering
    means no photo; the placeholder is the honest fallback."""
    info = _imageinfo(thumburl=None)
    assert info["url"] == "https://upload.wikimedia.org/shelter.jpg"  # the original IS available

    assert eligible_photo("File:Shelter.jpg", 5.0, info, cutoff=CUTOFF) is None


def test_eligible_photo_ships_the_sized_thumbnail_not_the_original():
    record = eligible_photo("File:Shelter.jpg", 5.0, _imageinfo(), cutoff=CUTOFF)

    assert record is not None
    assert record["url"] == "https://upload.wikimedia.org/thumb/shelter-640.jpg"
    assert record["url"] != _imageinfo()["url"]


def test_eligible_photo_labels_the_licence_from_its_id_when_no_short_name_exists():
    record = eligible_photo("File:Shelter.jpg", 5.0, _imageinfo(license_short=None), cutoff=CUTOFF)

    assert record is not None
    assert record["license"] == "CC-BY-SA-4.0"


# --- pick_photo ---


def _candidate(distance_m, taken):
    return {"title": f"File:{distance_m}-{taken}.jpg", "distance_m": distance_m, "taken": taken}


def test_pick_photo_prefers_the_nearest_file_over_a_newer_farther_one():
    """The closest file is the likeliest to depict the point rather than the
    view from it - a month of recency does not outweigh 200 metres of
    being a photo of something else."""
    near_older = _candidate(12.0, "2024-10-01")
    far_newer = _candidate(210.0, "2026-01-01")

    assert pick_photo([far_newer, near_older]) is near_older


def test_pick_photo_breaks_a_distance_tie_toward_the_newest_capture_date():
    older = _candidate(30.0, "2024-09-15")
    newer = _candidate(30.0, "2026-02-20")

    assert pick_photo([older, newer]) is newer


def test_pick_photo_returns_none_for_no_candidates():
    assert pick_photo([]) is None
