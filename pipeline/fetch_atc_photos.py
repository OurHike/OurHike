"""Fetch ATC's own facility photos for corridor POIs, for the waypoint card's
photo slot (WIREFRAMES.md frames 6a-6b).

Source: the `Photo1`..`Photo10` attribute fields already present on the ATC
facilities layers this pipeline fetches (`fetch_all.py`). They hold Google
Drive links to photographs ATC's own crews took during the 2015-2017 trail
inventory, and they cover **270 of 280 shelters** where Wikimedia Commons
covers, measured, zero (features/POI_PHOTOS.md). Unlike a proximity match,
these are photographs *of the facility*, framed as documentation of it.

Run after fetch_all.py, before export_poi.py. No corridor clip and no spatial
work is needed: the photo reference travels on the source feature, so the
unified id is derived directly from the same `GlobalID` export_poi.py keys on
(lib/poi_schema.unify_poi builds `f"{source}:{source_feature_id}"`).

Two deliberate differences from fetch_poi_images.py, both because the source is
different in kind:

**The freshness bar is this source's own, not Commons'.** Every one of these
photographs fails Commons' four-year window - the newest sampled is 2017. That
window exists to stop a stranger's stale snapshot misrepresenting a place, and
the trail-managing organisation's own facility documentation is a different
risk: it is the authoritative picture of the structure, and the card prints its
capture month so a hiker reads "September 2016" and discounts it themselves. A
decade is still long enough that a shelter may have been rebuilt or burned, so
the bar is long rather than absent - MAX_PHOTO_AGE_DAYS below.

**The capture date is read over a Range request, not from the rendering.**
Drive's thumbnailer strips EXIF, and the honesty rule needs a real date rather
than "sometime in the inventory". Originals run to 6.8 MB, so the first 64 KB
is fetched to parse EXIF and the rest is never transferred.

Licensing: these are ATC's photographs, not openly licensed ones, and
CONTRIBUTING.md requires the basis to be established and recorded rather than
assumed. That record lives in sources.json's `photo_licence` block for the
layers this reads - not invented here, and not a Creative Commons claim, which
would be false.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

from lib import fetch_receipts
from lib.completeness import fail_if_incomplete
from lib.photo_store import local_photo_path, photo_digest

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = RAW_DIR / "poi_images_atc.json"
SOURCES_PATH = ROOT / "sources.json"

# (raw filename stem, unified source name) for the ATC layers whose features
# become POIs export_poi.py writes. Still not every layer carrying photo
# fields - `bridges` is well covered (47%) and is not a POI type, so fetching
# its photos would download bytes nothing can render.
#
# Vistas, parking and privies were in that same sentence until they became
# POI types; their coverage (37%, 58%, 95% - features/POI_PHOTOS.md) is now
# renderable, and this is the only source that has any of it, because
# fetch_poi_images.py deliberately does not crawl Commons for them. The
# source pairs must stay exactly export_poi.DIRECT_SOURCES' names or the
# keys here resolve to nothing on export - test_fetch_atc_photos.py pins
# that rather than trusting the two lists to be edited together.
PHOTO_LAYERS = (
    ("shelters", "atc_shelters"),
    ("campsites", "atc_campsites"),
    ("viewpoints", "atc_viewpoints"),
    ("parking", "atc_parking"),
    ("privies", "atc_privies"),
)

# ATC's own documentation of its own structures, so the window is long. See the
# module docstring: it is long rather than absent because ten years is enough
# for a shelter to have been rebuilt, and a confident photo of a structure that
# is gone is the failure this bar exists to prevent. Twelve years admits the
# whole 2015-2017 inventory with room for the 2007 stragglers to fall out.
MAX_PHOTO_AGE_DAYS = 4383  # twelve years, including three leap days

# Drive serves a width-sized rendering of any image it holds, which is what
# keeps this source inside "never run an image pipeline of our own" - the same
# role Wikimedia's thumbnailer plays for Commons. 640px is 2x the card's 264px
# slot; originals are 0.2-6.8 MB and must never be what a hiker downloads.
THUMBNAIL_URL = "https://drive.google.com/thumbnail"
IMAGE_WIDTH_PX = 640
DOWNLOAD_URL = "https://drive.google.com/uc"

# EXIF sits in the file header; 64 KB has been enough for every sampled photo
# and bounds what a date costs to establish.
EXIF_HEADER_BYTES = 65536

THROTTLE_SECONDS = 0.2
RETRY_BACKOFF_SECONDS = (5, 30)
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)

# A photo reference that Drive will not serve: the file is deleted, or its
# sharing was changed, or the id in ATC's column was never right. Not a
# transport failure and not worth retrying - it is a fact about one slot in
# one feature's Photo1..Photo10, and the honest handling is the same as an
# undated photo's: skip it and take the next.
#
# This is not hypothetical. The first run after vistas, parking and privies
# became POI types died on
# `Annapolis Rock (US 40) Parking Area`'s Photo2 after 30 minutes and ~1,050
# POIs, and took the whole data release with it - every export, the quality
# gate and the publish step were skipped behind it. A sample of 80 links
# across the new layers found no other dead one, which is exactly the shape
# of failure worth guarding: too rare to design around, fatal when it lands.
MISSING_PHOTO_STATUSES = (403, 404, 410)

# The 403 in that tuple cuts both ways (#659): Drive answers 403 for a file
# whose sharing was revoked AND for rate limiting ("too many users have
# viewed or downloaded this file"). One dead link is a fact about one slot;
# a run whose 403s keep mounting is being throttled, and treating every one
# as "file gone" would let a throttled crawl finish green having silently
# recorded hundreds of POIs as photo-less. The same 80-link sample above
# that motivated skipping is what bounds this: genuinely dead links are
# rare, so a run that crosses this many 403s is almost certainly throttled
# and must die loudly instead of finishing wrong.
# @unvalidated - the ceiling is reasoned from that one 80-link sample, not
# from an observed throttling incident; the first real one will say whether
# 10 is the right number.
MAX_FORBIDDEN_SKIPS = 10

# A "none" outcome is re-checked once it is this old (#659): ATC keeps
# filling Photo1..Photo10, and a carried-forward "none" used to be
# permanent - a POI checked once on a bad day stayed photo-less forever.
# @unvalidated - thirty days trades ~a few hundred extra requests a month
# against how often ATC actually adds photos, which nobody has measured.
RECHECK_NONE_AFTER_DAYS = 30

# Refuse to overwrite the outcomes file when a re-fetch loses this share of
# the prior "found" records it re-processed - the same guard, ratio and
# override (delete the outcomes file deliberately) as fetch_poi_images.py,
# whose own comment this module cited while not having one (#659).
MAX_PHOTO_DROP_RATIO = 0.5

USER_AGENT = "OurHike-pipeline/1.0 (https://github.com/OurHike/OurHike; contact via repository issues)"

# A Drive share link carries the file id between /d/ and the next slash, in
# both the plain and the Workspace-scoped (/a/appalachiantrail.org/) forms.
_DRIVE_ID_RE = re.compile(r"/d/([A-Za-z0-9_-]{10,})")

# EXIF DateTimeOriginal, as the colon-separated form cameras write.
_EXIF_DATE_RE = re.compile(rb"(20\d\d):(\d\d):(\d\d) \d\d:\d\d:\d\d")


# A photo field holding "0", "1", "NoInfo" or "" is ATC's placeholder for "no
# photo", not a link - roughly a third of the values in these layers. Only an
# http(s) value is a reference to anything.
def photo_urls(properties: dict) -> list[str]:
    """Every real photo URL on one ATC feature, in Photo1..Photo10 order."""
    urls = []
    for index in range(1, 11):
        value = properties.get(f"Photo{index}")
        if isinstance(value, str) and value.strip().startswith("http"):
            urls.append(value.strip())
    return urls


def drive_file_id(url: str) -> str | None:
    """The Drive file id in a share link, or None when the URL is not one."""
    match = _DRIVE_ID_RE.search(url)
    return match.group(1) if match else None


def parse_exif_date(header: bytes) -> date | None:
    """The capture date in a JPEG header, or None when there isn't a parseable
    one. None is a verdict, not a gap - the card prints this month, and an
    undated photo cannot honestly claim an age (same posture as
    lib/commons.parse_date_taken)."""
    match = _EXIF_DATE_RE.search(header)
    if match is None:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def request_with_retry(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """session.get retried over RETRY_BACKOFF_SECONDS on connection faults and
    RETRYABLE_STATUSES, throttled on success so the pace is set in one place.

    Local rather than shared with fetch_poi_images.py's near-twin on purpose:
    that one implements Wikimedia's published etiquette (maxlag, Retry-After),
    which is a contract with a specific API rather than a general politeness."""
    attempts = len(RETRY_BACKOFF_SECONDS) + 1
    for attempt, delay in enumerate((*RETRY_BACKOFF_SECONDS, None)):
        try:
            resp = session.get(url, timeout=60, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if delay is None:
                raise
            print(f"  {url}: {type(e).__name__} on attempt {attempt + 1}/{attempts}, retrying in {delay}s")
            time.sleep(delay)
            continue
        if resp.status_code in RETRYABLE_STATUSES and delay is not None:
            print(f"  {url} answered {resp.status_code} on attempt {attempt + 1}/{attempts}, retrying in {delay}s")
            time.sleep(delay)
            continue
        resp.raise_for_status()
        time.sleep(THROTTLE_SECONDS)
        return resp
    raise AssertionError("unreachable")


def capture_date(session: requests.Session, file_id: str) -> date | None:
    """The photo's EXIF capture date, read from the first EXIF_HEADER_BYTES of
    the original rather than the whole file. Drive answers a Range request with
    206; a server that ignored it would return the entire image, so the slice
    is applied locally too rather than trusting the status."""
    resp = request_with_retry(
        session,
        DOWNLOAD_URL,
        params={"export": "download", "id": file_id},
        headers={"Range": f"bytes=0-{EXIF_HEADER_BYTES - 1}"},
    )
    return parse_exif_date(resp.content[:EXIF_HEADER_BYTES])


def store_rendering(session: requests.Session, file_id: str) -> str:
    """Download the 640px rendering, cache it under its own content digest, and
    return the digest. Same content-addressed store fetch_poi_images.py writes
    to, so publish.py uploads both sources' photos with no change: an image
    already cached under its digest is already the right bytes."""
    resp = request_with_retry(session, THUMBNAIL_URL, params={"id": file_id, "sz": f"w{IMAGE_WIDTH_PX}"})
    image_bytes = resp.content
    digest = photo_digest(image_bytes)

    path = local_photo_path(RAW_DIR, digest)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        # Sibling temp then replace: a half-written image is a file whose name
        # promises a digest its bytes do not have.
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(image_bytes)
        os.replace(tmp_path, path)
    return digest


def photo_credit() -> dict:
    """The author and licence strings the card's credit line renders, read from
    sources.json rather than written here.

    The credit is not decoration: it is the recorded basis on which these bytes
    may be served at all (CONTRIBUTING.md, "establish the licence first and
    record it"). Keeping it in the registry means the club that inherits this
    finds the answer where it looks for every other source's terms, instead of
    reverse-engineering it from a string constant."""
    registry = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    licence = registry.get("photo_licence")
    if not licence or not licence.get("author") or not licence.get("license"):
        raise RuntimeError(
            f"{SOURCES_PATH} has no usable `photo_licence` block - the basis for serving ATC photos "
            "must be recorded before they are fetched (CONTRIBUTING.md, 'A note on data and licences')"
        )
    return licence


def load_prior(path: Path) -> dict[str, dict]:
    """Prior per-POI outcomes from an earlier run, or {} on the first one."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("pois", {})


def record_photos(record: dict) -> list[dict]:
    """The photo list on an outcome record, reading both shapes.

    Runs before this one wrote a single `photo` object, because a POI got one
    photo. It gets all of them now (ATC fills Photo1..Photo10 and 89% of these
    features use more than one), so the record holds a `photos` list - and an
    outcome file written by the older shape must still be readable, or the
    first run after upgrading re-fetches every image it already has."""
    if "photos" in record:
        return record.get("photos") or []
    photo = record.get("photo")
    return [photo] if photo else []


def cached_photo_missing(record: dict) -> bool:
    """Whether a prior "found" outcome has lost any of the bytes it recorded -
    a cleared data/ tree leaves the outcomes file pointing at images publish.py
    would never upload.

    Any one missing re-fetches the POI's whole set rather than the single gap:
    the photos are fetched together, the outcome is recorded together, and a
    partial repair would leave the record claiming a list it cannot back."""
    if record.get("status") != "found":
        return False
    photos = record_photos(record)
    if not photos:
        return True
    return any(photo.get("digest") is None or not local_photo_path(RAW_DIR, photo["digest"]).exists() for photo in photos)


def collect_candidates() -> list[dict]:
    """Every ATC feature carrying at least one photo URL, as
    {id, name, urls} keyed by the unified POI id export_poi.py will write."""
    candidates = []
    for stem, source in PHOTO_LAYERS:
        path = RAW_DIR / f"{stem}.geojson"
        if not path.exists():
            continue
        for feature in json.loads(path.read_text(encoding="utf-8")).get("features", []):
            properties = feature.get("properties") or {}
            urls = photo_urls(properties)
            # `is None` at each step, not truthiness - the exact chain
            # lib/poi_schema.unify_poi resolves the export's id with. These
            # records join the export on that id, and a truthiness fallback
            # here (#659) repeats the drift lib/feature_id.py documents as
            # a past bug: a feature with GlobalID "" would take the
            # feature's own id here while the export published "", and its
            # photos would silently never attach.
            feature_id = properties.get("GlobalID")
            if feature_id is None:
                feature_id = feature.get("id")
            if not urls or feature_id is None:
                continue
            candidates.append({"id": f"{source}:{feature_id}", "name": properties.get("Name"), "urls": urls})
    return candidates


def eligible_photos(
    session: requests.Session,
    candidate: dict,
    cutoff: date,
    credit: dict,
    unresolved: list[str] | None = None,
) -> list[dict]:
    """Every shippable photo for a POI, in ATC's own Photo1..Photo10 order.

    `unresolved`, when given, collects (url, status) pairs Drive would not
    serve (see MISSING_PHOTO_STATUSES) so the run can report how much of
    ATC's column no longer resolves - and, since #659, so the caller can
    count the 403s among them against MAX_FORBIDDEN_SKIPS. A list the
    caller owns rather than a return value, because a slowly rotting corpus
    is a thing to notice across a whole run and not a fact about any one
    POI.

    All of them, not the first: 433 of the 489 features carrying a photo carry
    more than one, and taking only the first discarded 812 real photographs of
    real shelters (measured 2026-08-09). The card shows one and the rest sit
    behind it.

    **The order is ATC's and is preserved exactly.** Photo1 is their judgement
    about which picture best shows the facility, so it becomes the card photo;
    re-ranking by date or file size would be substituting a preference we have
    no basis for. A slot with no Drive id or no parseable capture date is
    skipped without disturbing the rest - the survivors keep their relative
    order, so a POI whose Photo1 is undated still shows Photo2 first.
    """
    photos = []
    for url in candidate["urls"]:
        file_id = drive_file_id(url)
        if file_id is None:
            continue
        try:
            taken = capture_date(session, file_id)
            if taken is None or taken < cutoff:
                continue
            digest = store_rendering(session, file_id)
        except requests.exceptions.HTTPError as error:
            # Both calls are wrapped, not just the first: a file can answer a
            # Range request and then refuse the rendering, and either way this
            # slot has no photo to ship. Any other status still raises - a 500
            # from Drive is Drive being broken, and finishing a crawl by
            # quietly dropping every photo is the failure this pipeline's
            # drop guards exist to catch.
            status = error.response.status_code if error.response is not None else None
            if status not in MISSING_PHOTO_STATUSES:
                raise
            if unresolved is not None:
                unresolved.append((url, status))
            continue
        photos.append(
            {
                "title": candidate["name"],
                "url": url,
                "page_url": url,
                "author": credit["author"],
                "license": credit["license"],
                "taken": taken.isoformat(),
                "digest": digest,
            }
        )
    return photos


def keep_prior(record: dict | None, today: date) -> bool:
    """Whether an earlier run's outcome for a POI still stands, sparing its
    API calls. A "found" that lost its cached bytes does not stand (see
    cached_photo_missing), and neither - since #659 - does a "none" older
    than RECHECK_NONE_AFTER_DAYS: ATC keeps adding photos, and a POI
    checked once on a bad day used to stay photo-less forever."""
    if record is None:
        return False
    if cached_photo_missing(record):
        return False
    if record.get("status") == "none":
        checked = record.get("checked")
        if not checked:
            return False
        return (today - date.fromisoformat(checked)).days <= RECHECK_NONE_AFTER_DAYS
    return True


def drop_problems(lost_fresh: int, fresh_prior: int) -> list[str]:
    """Problem strings when a run loses a suspicious share of the
    still-fresh photos it re-processed - fetch_poi_images.drop_problems'
    logic with this module's names (#659: this file's own comment cited
    "the failure this pipeline's drop guards exist to catch" while having
    no drop guard). If a big loss is real (ATC pulled the files), deleting
    the outcomes file and re-running is the deliberate override."""
    if fresh_prior == 0:
        return []
    if lost_fresh >= fresh_prior:
        return [f"ATC photos fetch lost all {fresh_prior} still-fresh photo records - refusing to overwrite {OUT_PATH}"]
    if lost_fresh > fresh_prior * MAX_PHOTO_DROP_RATIO:
        return [
            f"ATC photos fetch lost {lost_fresh} of {fresh_prior} still-fresh photo records "
            f"({lost_fresh / fresh_prior:.0%}, over the {MAX_PHOTO_DROP_RATIO:.0%} threshold) "
            f"- refusing to overwrite {OUT_PATH}"
        ]
    return []


def persist(records: dict[str, dict], prior: dict[str, dict], cutoff: date) -> None:
    """Guard, then write OUT_PATH atomically.

    The guard first (#659, mirroring fetch_poi_images.persist): a run that
    lost a suspicious share of the still-fresh prior "found" records it
    actually re-processed exits here, leaving OUT_PATH as it was, so the
    next run still compares against last-known-good. Only prior records
    present in `records` count - a mid-crawl call guards the processed
    subset without indicting the remainder. Then the sibling-temp write:
    OUT_PATH is the crawl's output, the guard's baseline, and the next
    run's skip input, and a truncate killed midway destroys all three."""
    cutoff_iso = cutoff.isoformat()
    fresh_prior_ids = {
        poi_id
        for poi_id, record in prior.items()
        if record.get("status") == "found"
        and poi_id in records
        and any(photo.get("taken", "") >= cutoff_iso for photo in record_photos(record))
    }
    lost_fresh = sum(1 for poi_id in fresh_prior_ids if records[poi_id].get("status") != "found")
    fail_if_incomplete(drop_problems(lost_fresh, len(fresh_prior_ids)), label="Refusing to persist ATC photos fetch")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = OUT_PATH.parent / (OUT_PATH.name + ".tmp")
    tmp_path.write_text(json.dumps({"pois": records}, indent=2, sort_keys=True))
    os.replace(tmp_path, OUT_PATH)


def main(recheck: bool = False) -> None:
    cutoff = date.today() - timedelta(days=MAX_PHOTO_AGE_DAYS)
    credit = photo_credit()
    print(f"Freshness cutoff for ATC photos: taken on or after {cutoff.isoformat()}")

    candidates = collect_candidates()
    fail_if_incomplete(
        [] if candidates else ["no ATC features with photo references - run fetch_all.py first"],
        label="Nothing to fetch ATC photos for",
    )
    print(f"{len(candidates)} ATC features carry a photo reference.")

    prior = load_prior(OUT_PATH)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    today_date = date.today()
    today = today_date.isoformat()
    records: dict[str, dict] = {}
    unresolved: list[tuple[str, int]] = []
    kept = fetched = 0
    for index, candidate in enumerate(candidates, start=1):
        prior_record = prior.get(candidate["id"])
        if not recheck and keep_prior(prior_record, today_date):
            records[candidate["id"]] = prior_record
            kept += 1
        else:
            photos = eligible_photos(session, candidate, cutoff, credit, unresolved)
            records[candidate["id"]] = (
                {"status": "none", "checked": today} if not photos else {"status": "found", "checked": today, "photos": photos}
            )
            fetched += 1
            forbidden = sum(1 for _url, status in unresolved if status == 403)
            if forbidden > MAX_FORBIDDEN_SKIPS:
                # Mass 403 is Drive throttling, not a mass deletion - see
                # MAX_FORBIDDEN_SKIPS. Die before recording another POI as
                # photo-less; the outcomes already persisted this run heal
                # on the next one (a "none" is re-checked, see keep_prior).
                raise SystemExit(
                    f"{forbidden} photo requests answered 403 this run (ceiling {MAX_FORBIDDEN_SKIPS}) - "
                    "this is the shape of Drive rate limiting, not of dead links. "
                    "Re-run later rather than recording throttled POIs as photo-less."
                )
        if index % 50 == 0:
            found = sum(1 for r in records.values() if r.get("status") == "found")
            print(f"  {index}/{len(candidates)} ({kept} carried forward), {found} POIs with photos")
            persist(records, prior, cutoff)

    persist(records, prior, cutoff)
    # OUT_PATH alone, not the photo store beside it. The images are
    # content-addressed bytes whose count publish.py reports separately (the
    # workflow's "How many photos would be published" step); this index is
    # the thing an export reads and the thing worth re-hashing.
    fetch_receipts.record("fetch_atc_photos", [OUT_PATH])
    found = [r for r in records.values() if r.get("status") == "found"]
    images = sum(len(record_photos(r)) for r in found)
    print(f"Saved -> {OUT_PATH} ({kept} carried forward, {fetched} fetched)")
    print(f"{len(found)}/{len(candidates)} ATC features have a shippable photo; {images} images in total.")
    if unresolved:
        # Said out loud rather than swallowed: these are references in ATC's
        # own column that no longer resolve, and a number that grows run over
        # run is worth telling them about.
        example_url, example_status = unresolved[0]
        print(f"{len(unresolved)} photo reference(s) Drive would not serve, skipped - e.g. {example_url} ({example_status})")


def run(argv: list[str]) -> None:
    """Flag handling split from main() so tests can drive each side alone."""
    recheck = False
    for flag in argv:
        if flag == "--recheck":
            recheck = True
        else:
            print(f"Unknown flag {flag!r} - usage: python fetch_atc_photos.py [--recheck]")
            raise SystemExit(2)
    main(recheck=recheck)


if __name__ == "__main__":
    run(sys.argv[1:])
