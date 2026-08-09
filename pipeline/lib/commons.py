"""Eligibility and selection rules for Wikimedia Commons POI photos.

fetch_poi_images.py asks the Commons API two questions per POI - "which File:
pages sit near these coordinates" (geosearch) and "what are those files"
(imageinfo) - and this module decides which of the answers are photos OurHike
may actually ship on a waypoint card. The bar is set by CONTRIBUTING.md's "A
note on data and licences" (establish the licence first) and by the sourcing
decision in features/POI_PHOTOS.md: a real camera photo, openly licensed with
attribution we can render, taken recently enough to still look like the place.

"Real camera photo, recently" is enforced with one honest proxy: the file must
be a JPEG carrying a parseable EXIF capture date (Commons surfaces it as
DateTimeOriginal) inside the freshness window. Maps, SVG diagrams, PNG
screenshots and old scans fail that test naturally; nothing here tries to
classify image content.

Pure module - no I/O, no network. fetch_poi_images.py wires this up against
the live API.
"""

import html
import re
from datetime import date

# The one CC shape whose terms a one-link credit line can actually meet:
# CC BY / CC BY-SA at version 4.0 or newer. 4.0's s3(a)(2) explicitly allows
# satisfying attribution "by providing a URI or hyperlink to a resource that
# includes the required information" - the Commons file page carries author,
# licence notice and deed link, so the card's single link to it complies.
# Pre-4.0 versions (2.0/2.5/3.0) have no such clause: their s4(a) requires
# the licence URI itself to ship with every copy, which a 10px credit line
# cannot honestly do without growing a second link. Rejected wholesale, the
# same reject-when-arguable posture as NC (breaks any future paid tier), ND
# (arguably forbids the card's crop-to-slot rendering) and GFDL (demands the
# full licence text ride along) - none of which match this pattern either.
_CC_ATTRIBUTION_RE = re.compile(r"^cc-by(-sa)?-(\d+(?:\.\d+)?)$")

# ISO dates ("2024-06-18", also inside <time datetime="2024-06-18">) and EXIF
# colon dates ("2024:06:18 14:22:31") - the two shapes Commons actually emits
# for DateTimeOriginal. Anything else ("May 2016", "circa 1998") is treated as
# no date: an unparseable age cannot honestly pass a freshness bar.
_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_EXIF_DATE_RE = re.compile(r"(\d{4}):(\d{2}):(\d{2})")

_TAG_RE = re.compile(r"<[^>]*>")

# Commons' File namespace holds far more than photographs, and a geosearch
# returns whatever is geotagged near the point - including PDFs and DjVu
# scans of old survey maps, which carry coordinates precisely because they
# depict a place. Those are multipage documents, and imageinfo cannot
# normalize a width-based thumbnail request (iiurlwidth) for one: it answers
# `urlparamnormal` and fails the WHOLE batched call, so a single geotagged PDF
# near a single POI aborts the crawl and takes the eligible JPEGs batched
# alongside it. Filtering by extension before the request is what keeps that
# request formable.
#
# This is a pre-filter, not the rule. eligible_photo() still decides on the
# file's declared mime type - a .jpg that is really something else is rejected
# there, as it always was.
_JPEG_TITLE_RE = re.compile(r"\.jpe?g$", re.IGNORECASE)


def may_be_a_jpeg(title: str) -> bool:
    """Whether a File: title could be the JPEG eligible_photo() requires -
    cheap enough to apply before asking the API anything, and the only thing
    standing between a geotagged PDF and a dead crawl (see _JPEG_TITLE_RE)."""
    return _JPEG_TITLE_RE.search(title.strip()) is not None


def meta_value(extmetadata: dict, key: str) -> str:
    """One extmetadata field as a stripped string - the API wraps each in
    {"value": ..., "source": ...} and omits the key entirely when unknown."""
    field = extmetadata.get(key)
    if not isinstance(field, dict):
        return ""
    return str(field.get("value") or "").strip()


def strip_html(text: str) -> str:
    """Commons metadata fields (Artist especially) arrive as HTML fragments -
    '<a href="...">Jane Doe</a>' - but the card renders plain text. Tags go,
    entities unescape, whitespace collapses."""
    return " ".join(html.unescape(_TAG_RE.sub(" ", text)).split())


def license_allows_reuse(license_id: str) -> bool:
    """Whether a Commons machine-readable licence id (extmetadata "License":
    "cc-by-sa-4.0", "cc0", "pd", ...) is one OurHike can ship under - public
    domain, CC0, or CC BY / CC BY-SA at 4.0+ (see _CC_ATTRIBUTION_RE's
    comment for why older CC versions are out). Unknown ids are rejected,
    not shipped-and-hoped: an unlicensed photo is exactly the inherited
    problem CONTRIBUTING.md's licence note warns about."""
    normalized = license_id.lower().strip()
    if not normalized:
        return False
    if normalized == "cc0" or normalized.split("-")[0] == "pd":
        return True
    match = _CC_ATTRIBUTION_RE.match(normalized)
    return match is not None and float(match.group(2)) >= 4


def parse_date_taken(raw: str) -> date | None:
    """The capture date buried in a DateTimeOriginal value, or None when
    there isn't a parseable one. None is a verdict, not a gap: a photo whose
    age cannot be established cannot pass an age requirement."""
    for pattern in (_ISO_DATE_RE, _EXIF_DATE_RE):
        match = pattern.search(raw)
        if match is None:
            continue
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return None


def eligible_photo(title: str, distance_m: float, imageinfo: dict, *, cutoff: date) -> dict | None:
    """The shippable photo record for one geosearch hit, or None.

    `imageinfo` is one entry of the API's imageinfo array (url/mime/
    extmetadata included). To come back non-None the file must be a JPEG,
    carry an EXIF capture date on or after `cutoff`, be licensed per
    license_allows_reuse, and - for the CC attribution licences - name an
    author we can credit. Public domain and CC0 files may credit nobody;
    a CC BY photo with no attributable author is unusable, not "usable,
    uncredited".
    """
    if imageinfo.get("mime") != "image/jpeg":
        return None

    extmetadata = imageinfo.get("extmetadata") or {}

    license_id = meta_value(extmetadata, "License")
    if not license_allows_reuse(license_id):
        return None

    taken = parse_date_taken(meta_value(extmetadata, "DateTimeOriginal"))
    if taken is None or taken < cutoff:
        return None

    # A file's own Attribution field is the uploader saying "credit me exactly
    # like this" - honored over the Artist field when present.
    author = strip_html(meta_value(extmetadata, "Attribution") or meta_value(extmetadata, "Artist"))
    if license_id.lower().startswith("cc-by") and not author:
        return None

    # The thumbnail, and never the original. Commons originals are full-
    # resolution camera files - a shelter photo is routinely 3-15 MB - and
    # the card's slot is 264 CSS pixels wide. Falling back to `url` when the
    # thumbnailer has no rendering would put a multi-megabyte download on a
    # hiker's data plan to fill a thumbnail-sized box, which is value #8's
    # exact argument. A file we cannot get a sized rendering of is not
    # shippable; the placeholder is the honest fallback.
    url = imageinfo.get("thumburl")
    if not url:
        return None

    license_label = meta_value(extmetadata, "LicenseShortName") or license_id.upper()
    return {
        "title": title,
        "distance_m": distance_m,
        "url": url,
        "page_url": imageinfo.get("descriptionurl") or "",
        "author": author or None,
        "license": license_label,
        "taken": taken.isoformat(),
    }


def pick_photo(candidates: list[dict]) -> dict | None:
    """The one photo a waypoint card gets: nearest to the POI first (the
    closest file is the likeliest to actually depict the point rather than
    the view from it), newest capture date as the tiebreak. Two stable sorts
    rather than one clever key - ISO dates order lexically, so "newest" is a
    reverse sort on the string."""
    if not candidates:
        return None
    newest_first = sorted(candidates, key=lambda c: c["taken"], reverse=True)
    return sorted(newest_first, key=lambda c: c["distance_m"])[0]
