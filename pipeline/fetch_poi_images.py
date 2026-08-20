"""Fetch openly-licensed, recent photos for corridor POIs from Wikimedia
Commons, for the waypoint card's photo slot (WIREFRAMES.md frames 6a-6b).

Source: the Wikimedia Commons API (commons.wikimedia.org/w/api.php), queried
per POI: a File-namespace geosearch around the POI's coordinates, then an
imageinfo lookup for the hits. What may ship is decided by lib/commons.py -
JPEG with an EXIF capture date inside MAX_PHOTO_AGE_DAYS, licensed public
domain/CC0/CC BY/CC BY-SA, with an author to credit where the licence
requires one. Licence, author and capture date travel with every photo into
data/raw/poi_images.json, and export_poi.py carries them onto the exported
POI features - per-photo licensing means the attribution is per-feature
data, not a single registry line (CONTRIBUTING.md "A note on data and
licences").

POIs come from the same unify + corridor-clip that export_poi.py performs
(its functions are imported and called, not its output files read), so photo
records are keyed by exactly the unified ids the export writes. Run this
after fetch_all.py and fetch_opentrail.py, before export_poi.py.

Change-aware, per POI rather than per source: every POI's outcome ("found"
with the photo record, or "none") is recorded with the date it was checked,
and a later run skips POIs that already have an outcome - except a found
photo whose capture date has aged past the freshness window, which gets
re-queried so a published photo is never older than the bar this script
claims to enforce. `--recheck` re-queries everything (new uploads appear on
Commons all the time; misses are otherwise never retried). A full first pass
is thousands of sequential throttled requests - expect tens of minutes; the
skip logic is what makes every later run cheap.

Coverage will be partial and that is expected honesty, not failure: most
water sources have no Commons photo at all, and the freshness bar rejects
plenty of real photos of real shelters. The card's category-glyph
placeholder is the designed fallback (client PoiCard.tsx). The completeness
gate here guards structure (no POIs to check, a degraded re-fetch wiping
photos), never coverage.
"""

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import duckdb
import requests

import export_poi
from lib import fetch_receipts
from lib.commons import eligible_photo, may_be_a_jpeg, pick_photo
from lib.completeness import fail_if_incomplete
from lib.corridor import build_corridor
from lib.photo_screen import screen_bytes
from lib.photo_store import local_photo_path, photo_digest

API_URL = "https://commons.wikimedia.org/w/api.php"
RAW_DIR = Path(__file__).parent / "data" / "raw"
OUT_PATH = RAW_DIR / "poi_images.json"

# The Wikimedia API etiquette page requires a descriptive User-Agent with a
# way to reach whoever runs the client - the repository is that contact.
USER_AGENT = "OurHike-pipeline/1.0 (https://github.com/OurHike/OurHike; contact via repository issues)"

# The freshness bar: a photo's EXIF capture date must be within four years
# of the run. A photo of a shelter that has since burned, moved or grown a
# graffiti problem is worse than the honest placeholder - but shelters
# change slowly, and the card always prints the capture month, so the hiker
# can see the age and judge for themselves rather than being protected from
# it. Four rather than two because the Commons corridor corpus is thin and
# old (see features/POI_PHOTOS.md); the bar is a judgement about how stale a
# picture may be, not a constant with a right answer, so it lives here in
# one place and moves when the measured coverage says it should.
MAX_PHOTO_AGE_DAYS = 1461  # four years, including one leap day

# How far from the POI a Commons file may sit and still plausibly depict it.
# Springs are point-precise and drown in near-miss trail/vista shots at any
# generous radius; a resupply point is a town whose photos legitimately
# spread over its blocks.
#
# **A poi_type absent from this map is not crawled at all**, and that is a
# decision rather than an oversight - `crawled_types()` below is what makes
# it one. `viewpoint`, `parking` and `privy` are the absences today:
#
#  - features/POI_PHOTOS.md measured this source and found 0 usable photos
#    for 280 shelters, with species uploads the plurality of what proximity
#    returns. Nothing about a vista or a car park makes proximity work
#    better; a Commons file near a privy is essentially never a photograph
#    of the privy.
#  - ATC's own inventory photographs cover exactly these three (95% of
#    privies, 58% of parking, 37% of vistas - same doc), and
#    fetch_atc_photos.py wins any overlap anyway, so a Commons crawl over
#    them would spend ~2,000 POIs' worth of API requests to be overruled.
#
# Adding a type here is how that gets revisited - with a measurement, the way
# the ATC source was.
# `crossing` is deliberately absent, and lib/poi_schema.py's POI_TYPES comment
# is where that silence is documented: an absent radius means this crawl skips
# the category. It carried 300 while the layer was empty, so nothing was ever
# skipped in practice; when fetch_trail_water.py filled it (#529) the choice
# became real, and the answer is no. A Commons photo matched by proximity to a
# stream-crossing coordinate is a photograph of whatever somebody uploaded
# nearby - features/POI_PHOTOS.md measured how often that is a plant - and a
# trail crossing a stream is the one waypoint type whose own name is the whole
# description. Paying an API round trip apiece to illustrate that is a cost
# with no reader.
SEARCH_RADIUS_M = {"shelter": 300, "campsite": 300, "water": 120, "resupply": 500}

GEOSEARCH_LIMIT = 30
IMAGE_WIDTH_PX = 640  # thumburl width: 2x the card's 264px slot, still tens of KB

# Sequential, throttled, single-session - the polite shape for a few
# thousand read requests against a public API.
THROTTLE_SECONDS = 0.1

# Connection faults, timeouts, 429s and 5xx answers all get another try
# after a pause - Wikimedia's API etiquette explicitly says to expect 429
# with Retry-After and back off, and a crawl this long WILL meet a transient
# edge 503. Only a non-retryable status (a 4xx that isn't 429) raises
# immediately: that is the API answering "no", not flaking. Broader than
# fetch_topo_quads.py's connection-faults-only posture on purpose - that
# script persists each quad as it lands, so one mid-run failure loses
# almost nothing; here an aborted pass loses every un-flushed outcome.
RETRY_BACKOFF_SECONDS = (5, 30)
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)

# A server-sent Retry-After is honored over the local backoff, but capped -
# an errant header must not park the crawl for an hour.
MAX_RETRY_AFTER_SECONDS = 120

# maxlag=5 asks the API to refuse work while replication lags; the refusal
# is explicitly retryable, and waiting through it is what the parameter is
# for. Escalating pauses, then give up loudly.
MAXLAG_SECONDS = 5
MAXLAG_RETRY_SECONDS = (5, 10, 30, 60)

# A re-fetch that loses a big share of the photos it should merely have
# re-confirmed must not be persisted - a broken-but-200 API response (empty
# geosearch for everything) would otherwise silently strip the cards. Only
# still-fresh prior photos count toward the ratio: one that aged past the
# freshness window and found no replacement is a legitimate,
# per-record-explainable loss, not breakage. Same posture as
# fetch_opentrail.py's MAX_FEATURE_DROP_RATIO.
MAX_PHOTO_DROP_RATIO = 0.5

# Progress print and progress flush share a cadence: every this-many
# queried POIs, the merged outcomes so far are guarded and atomically
# written, so an aborted forty-minute crawl resumes from its last flush
# instead of from zero.
PROGRESS_EVERY = 200


def retry_after_seconds(resp: requests.Response) -> int | None:
    """The integer Retry-After a 429/503 carries, capped, or None when the
    header is absent or in the HTTP-date form (rare; the local backoff is a
    fine substitute)."""
    header = resp.headers.get("Retry-After", "")
    if not header.isdigit():
        return None
    return min(int(header), MAX_RETRY_AFTER_SECONDS)


def request_with_retry(session: requests.Session, url: str, params: dict | None = None) -> requests.Response:
    """session.get against `url`, retried over RETRY_BACKOFF_SECONDS on
    connection faults and on RETRYABLE_STATUSES (honoring Retry-After),
    throttled on success so the crawl's pace is set here in one place.

    Takes a url rather than assuming API_URL because photo bytes come from
    upload.wikimedia.org while the metadata comes from the API host, and
    both want identical politeness - one throttle, one backoff, one place."""
    attempts = len(RETRY_BACKOFF_SECONDS) + 1
    for attempt, delay in enumerate((*RETRY_BACKOFF_SECONDS, None)):
        try:
            resp = session.get(url, params=params, timeout=60)
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError, requests.exceptions.Timeout) as e:
            if delay is None:
                raise
            print(f"  {url}: {type(e).__name__} on attempt {attempt + 1}/{attempts}, retrying in {delay}s")
            time.sleep(delay)
            continue
        if resp.status_code in RETRYABLE_STATUSES and delay is not None:
            wait = retry_after_seconds(resp) or delay
            print(f"  {url} answered {resp.status_code} on attempt {attempt + 1}/{attempts}, retrying in {wait}s")
            time.sleep(wait)
            continue
        # Out of retries, or a status that is an answer rather than a flake
        # (404, 400...) - raise_for_status turns any error status into the
        # loud failure; a clean response returns.
        resp.raise_for_status()
        time.sleep(THROTTLE_SECONDS)
        return resp
    raise AssertionError("unreachable")


def api_get(session: requests.Session, params: dict) -> dict:
    """One Commons API call, JSON-decoded, with maxlag refusals waited out
    per MAXLAG_RETRY_SECONDS. Any other API-level error raises - a wrong
    answer persisted quietly is worse than a loud dead run."""
    full = {**params, "format": "json", "maxlag": str(MAXLAG_SECONDS)}
    for attempt, delay in enumerate((*MAXLAG_RETRY_SECONDS, None)):
        payload = request_with_retry(session, API_URL, full).json()
        error = payload.get("error")
        if error is None:
            return payload
        if error.get("code") != "maxlag" or delay is None:
            raise RuntimeError(f"Commons API error {error.get('code')!r}: {error.get('info')}")
        attempts = len(MAXLAG_RETRY_SECONDS) + 1
        print(f"  Commons replication is lagged (attempt {attempt + 1}/{attempts}), waiting {delay}s")
        time.sleep(delay)
    raise AssertionError("unreachable")


def nearby_files(session: requests.Session, lat: float, lon: float, radius_m: int) -> list[dict]:
    """File-namespace pages within radius_m of the point, nearest first
    (geosearch's own ordering), each {"title": ..., "dist": ...}."""
    payload = api_get(
        session,
        {
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": str(radius_m),
            "gsnamespace": "6",
            "gslimit": str(GEOSEARCH_LIMIT),
        },
    )
    return (payload.get("query") or {}).get("geosearch") or []


def file_details(session: requests.Session, titles: list[str]) -> dict[str, dict]:
    """imageinfo for up to 50 File: titles in one batched call, keyed by the
    title as *requested* - the API answers under normalized titles and says
    so in a `normalized` list, which is mapped back here so callers can join
    against their geosearch hits without knowing normalization rules.

    Titles that cannot be the JPEG the eligibility rule wants are dropped
    before the request rather than after the answer: the sized-thumbnail
    parameter this asks for is unformable for a multipage file, and the API
    rejects the entire batch over one of them (lib/commons.may_be_a_jpeg)."""
    titles = [title for title in titles if may_be_a_jpeg(title)]
    if not titles:
        return {}
    payload = api_get(
        session,
        {
            "action": "query",
            "prop": "imageinfo",
            "titles": "|".join(titles),
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": str(IMAGE_WIDTH_PX),
            "iiextmetadatafilter": "DateTimeOriginal|License|LicenseShortName|Artist|Attribution",
        },
    )
    query = payload.get("query") or {}
    denormalize = {n["to"]: n["from"] for n in query.get("normalized") or []}
    details = {}
    for page in (query.get("pages") or {}).values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        title = page.get("title", "")
        details[denormalize.get(title, title)] = infos[0]
    return details


def best_photo(session: requests.Session, poi: dict, cutoff: date) -> dict | None:
    """The one shippable photo for a unified POI record, or None - geosearch
    around the POI, imageinfo for the hits, lib/commons eligibility, nearest
    eligible file wins."""
    hits = nearby_files(session, poi["lat"], poi["lon"], SEARCH_RADIUS_M[poi["poi_type"]])
    if not hits:
        return None
    details = file_details(session, [hit["title"] for hit in hits])
    candidates = []
    for hit in hits:
        info = details.get(hit["title"])
        if info is None:
            continue
        record = eligible_photo(hit["title"], hit["dist"], info, cutoff=cutoff)
        if record is not None:
            candidates.append(record)
    return pick_photo(candidates)


def store_photo(session: requests.Session, photo: dict) -> dict:
    """Download a chosen photo's bytes, cache them under RAW_DIR, and return
    the record with its content digest attached.

    Downloading rather than linking is the whole of #362: a hotlinked card
    depends on upload.wikimedia.org being up, and spends a nonprofit's
    bandwidth on our traffic. `url` stays on the record as provenance - where
    these bytes came from - while `digest` is what names them in our bucket.

    Idempotent by construction: an image already cached under its own digest
    is already the right bytes, so a re-run costs nothing.

    The face screen (#836) runs here because this is the one moment the
    bytes are guaranteed in hand - the result rides inside the record so no
    later stage needs the image to know what the check found.
    """
    resp = request_with_retry(session, photo["url"])
    image_bytes = resp.content
    digest = photo_digest(image_bytes)

    path = local_photo_path(RAW_DIR, digest)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        # Same sibling-temp-then-replace as the outcomes file: a half-written
        # image is a file whose name promises a digest its bytes do not have,
        # which is the one thing content-addressing must never allow.
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(image_bytes)
        os.replace(tmp_path, path)

    return {**photo, "digest": digest, "screen": screen_bytes(image_bytes)}


def cached_photo_missing(record: dict) -> bool:
    """Whether a prior "found" outcome fails to VOUCH for its photo.

    Until #465 this required the bytes on local disk, which was right when
    local disk was the only evidence a photo had ever been obtained - and
    made every cold publish re-crawl a corpus the bucket already held. The
    digest is the evidence now: photos are content-addressed, so a record
    that names its digest can be published from directly, and
    publish.verify_photo_promises() settles every published photo key
    against the bucket at the moment it matters - a cleared data/ tree
    publishing a key nobody ever uploaded fails THERE, loudly, instead of
    being re-downloaded here preemptively. A record with no digest still
    re-fetches: nothing can be published from it."""
    if record.get("status") != "found":
        return False
    return record.get("photo", {}).get("digest") is None


def screen_carried_forward(record: dict) -> dict:
    """Fill in the face screen (#836) for a prior "found" record from before
    the check existed, using the cached bytes - so the screen reaches the
    standing corpus without a re-crawl, and each photo is screened exactly
    once (the result persists inside the record; a screened record passes
    straight through here).

    A record whose bytes are gone (digest-only, #465) stays unscreened
    rather than being re-downloaded for this: export_poi.py's gate counts
    unscreened photos and ships them - unscreened is not flagged - and the
    next --recheck screens the fresh download anyway."""
    photo = record.get("photo", {})
    if "screen" in photo or not photo.get("digest"):
        return record
    path = local_photo_path(RAW_DIR, photo["digest"])
    if not path.exists():
        return record
    return {**record, "photo": {**photo, "screen": screen_bytes(path.read_bytes())}}


def corridor_pois() -> list[dict]:
    """The same unified, corridor-clipped POI records export_poi.py exports,
    derived the same way - by calling its functions, not by reading its
    output files - so the ids photos are keyed by are exactly the ids the
    export will write, with no ordering dependency between the two scripts."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    build_corridor(con, export_poi.RAW_DIR / "centerline.geojson")
    return export_poi.clip_to_corridor(con, export_poi.unify_all_sources())


def load_prior(path: Path) -> dict[str, dict]:
    """Prior per-POI outcomes from an earlier run, or {} on the first one."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("pois", {})


def keep_prior(record: dict | None, cutoff: date, recheck: bool) -> bool:
    """Whether an earlier run's outcome for a POI still stands, sparing its
    API calls. A found photo whose capture date has slid past the freshness
    window does NOT stand - keeping it would quietly break the exact promise
    MAX_PHOTO_AGE_DAYS makes - and --recheck stands nothing."""
    if recheck or record is None:
        return False
    if record.get("status") == "found":
        return record.get("photo", {}).get("taken", "") >= cutoff.isoformat()
    return True


def persist(records: dict[str, dict], prior: dict[str, dict], cutoff: date) -> None:
    """Guard, then write OUT_PATH atomically.

    The guard first: a run that lost a suspicious share of the still-fresh
    photos it merely had to re-confirm exits here, leaving OUT_PATH exactly
    as it was so the next run still compares against last-known-good. Only
    prior records whose POI this run has actually processed (present in
    `records`) count, so calling this mid-crawl guards the processed subset
    without indicting the unprocessed remainder.

    Then the write, via a sibling temp file and os.replace: OUT_PATH is
    simultaneously tens of minutes of crawling, the drop guard's baseline,
    and the next run's parse input - a plain truncate-and-write killed
    mid-way (Ctrl-C, OOM, full disk) would destroy all three at once."""
    cutoff_iso = cutoff.isoformat()
    fresh_prior_ids = {
        poi_id
        for poi_id, record in prior.items()
        if record.get("status") == "found" and record.get("photo", {}).get("taken", "") >= cutoff_iso and poi_id in records
    }
    lost_fresh = sum(1 for poi_id in fresh_prior_ids if records[poi_id].get("status") != "found")
    fail_if_incomplete(drop_problems(lost_fresh, len(fresh_prior_ids)), label="Refusing to persist poi images fetch")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = OUT_PATH.parent / (OUT_PATH.name + ".tmp")
    tmp_path.write_text(json.dumps({"pois": records}, indent=2, sort_keys=True))
    os.replace(tmp_path, OUT_PATH)


def drop_problems(lost_fresh: int, fresh_prior: int) -> list[str]:
    """Problem strings (for fail_if_incomplete) when a run loses a
    suspicious share of the still-fresh photos it should merely have
    re-confirmed - see MAX_PHOTO_DROP_RATIO. `fresh_prior` counts prior
    "found" records whose photo is still inside the freshness window and
    whose POI is still in the corridor; `lost_fresh` is how many of those
    came back photo-less this run. Nothing fresh on disk means nothing worth
    guarding. If a big loss is genuinely real (files deleted upstream),
    deleting the output file and re-running is the deliberate override."""
    if fresh_prior == 0:
        return []
    if lost_fresh >= fresh_prior:
        return [f"poi images fetch lost all {fresh_prior} still-fresh photos - refusing to overwrite {OUT_PATH}"]
    if lost_fresh > fresh_prior * MAX_PHOTO_DROP_RATIO:
        return [
            f"poi images fetch lost {lost_fresh} of {fresh_prior} still-fresh photos "
            f"({lost_fresh / fresh_prior:.0%}, over the {MAX_PHOTO_DROP_RATIO:.0%} threshold) "
            f"- refusing to overwrite {OUT_PATH}"
        ]
    return []


def crawled_types() -> set[str]:
    """The poi_types this source is searched for - see SEARCH_RADIUS_M.

    Derived from the radius map rather than kept as a second list, so "has a
    radius" and "is crawled" cannot drift apart: that pair is the whole reason
    a missing radius is a decision instead of the KeyError it used to be.
    """
    return set(SEARCH_RADIUS_M)


def main(recheck: bool = False) -> None:
    cutoff = date.today() - timedelta(days=MAX_PHOTO_AGE_DAYS)
    print(f"Freshness cutoff: photos taken on or after {cutoff.isoformat()}")

    all_pois = corridor_pois()
    fail_if_incomplete(
        [] if all_pois else ["no corridor POIs to look up - run fetch_all.py and fetch_opentrail.py first"],
        label="Nothing to fetch photos for",
    )
    # Filtered here rather than skipped inside the loop, so the count printed
    # below is the work this run will actually do.
    pois = [poi for poi in all_pois if poi["poi_type"] in crawled_types()]
    skipped = len(all_pois) - len(pois)
    print(f"{len(pois)} corridor POIs to check ({skipped} in poi_types this source is not crawled for).")

    prior = load_prior(OUT_PATH)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    today = date.today().isoformat()
    records = {}
    kept = fetched = redownloaded = 0
    for index, poi in enumerate(pois, start=1):
        prior_record = prior.get(poi["id"])
        if keep_prior(prior_record, cutoff, recheck) and not cached_photo_missing(prior_record):
            records[poi["id"]] = screen_carried_forward(prior_record)
            kept += 1
        elif keep_prior(prior_record, cutoff, recheck):
            # The outcome still stands; only its bytes went missing (a
            # cleared data/ tree). Re-fetch the image alone rather than
            # re-running the geosearch that already answered this.
            records[poi["id"]] = {**prior_record, "photo": store_photo(session, prior_record["photo"])}
            redownloaded += 1
            fetched += 1
        else:
            photo = best_photo(session, poi, cutoff)
            if photo is None:
                records[poi["id"]] = {"status": "none", "checked": today}
            else:
                records[poi["id"]] = {"status": "found", "checked": today, "photo": store_photo(session, photo)}
            fetched += 1
            # Flush on queried-POI boundaries, not loop boundaries: a run
            # that is all carry-forwards has nothing new worth writing, and
            # a run that dies mid-crawl resumes from its last flush instead
            # of re-issuing every request (the retries above absorb flakes;
            # this bounds what a genuine abort can cost).
            if fetched % PROGRESS_EVERY == 0:
                persist(records, prior, cutoff)
        if index % PROGRESS_EVERY == 0:
            found_so_far = sum(1 for record in records.values() if record.get("status") == "found")
            print(f"  {index}/{len(pois)} checked ({kept} carried forward), {found_so_far} photos")

    persist(records, prior, cutoff)
    fetch_receipts.record("fetch_poi_images", [OUT_PATH])
    redownload_note = f", {redownloaded} image(s) re-fetched for a cleared cache" if redownloaded else ""
    print(f"Saved -> {OUT_PATH} ({kept} carried forward, {fetched} queried{redownload_note})")

    totals: dict[str, list[int]] = {}
    for poi in pois:
        counts = totals.setdefault(poi["poi_type"], [0, 0])
        counts[1] += 1
        if records[poi["id"]].get("status") == "found":
            counts[0] += 1
    print("Coverage (partial is expected - the card's placeholder is the designed fallback):")
    for poi_type, (found, total) in sorted(totals.items()):
        print(f"  {poi_type}: {found}/{total} with a photo")


def run(argv: list[str]) -> None:
    """Flag handling split from main() so tests can drive each side alone -
    same shape as fetch_topo_quads.py. An unknown flag is rejected rather
    than silently ignored: a typo like --rechek must not quietly run a
    skip-everything pass that looks like a successful recheck."""
    recheck = False
    for flag in argv:
        if flag == "--recheck":
            recheck = True
        else:
            print(f"Unknown flag {flag!r} - usage: python fetch_poi_images.py [--recheck]")
            raise SystemExit(2)
    main(recheck=recheck)


if __name__ == "__main__":
    run(sys.argv[1:])
