"""Spike: is a Flickr group pool a usable photo source for corridor POIs?

The question this answers is not "does Flickr have photos of A.T. shelters" -
it plainly does - but "how many of them may OurHike actually ship", which is a
licence question and cannot be answered by looking at the pool. Commons
coverage was measured on 2026-08-08 and came back at **0 usable photos for 280
shelters** (features/POI_PHOTOS.md), so the shelter photo slot has no source at
all today. The "Appalachian Trail Shelter" group (908185@N20, 527 photos) is
the most on-topic corpus found: photos filed under the shelter's actual name,
which is the matching problem Commons' proximity search fails at.

What makes it a spike rather than a fetcher: **a group pool carries no
licence.** Adding a photo to a pool is a filing decision by its owner, not a
grant of anything, so the licence stays per photo exactly as it does on
Commons. Until the CC-and-fresh subset is counted, nobody knows whether this
source is worth building a fetcher for or is a pool of All Rights Reserved
photographs with a hopeful name.

The bar applied here is the real one, not a restatement of it: Flickr's licence
catalogue is fetched from the API and each entry's Creative Commons URL is
mapped onto the same id shape Commons uses ("cc-by-sa-2.0", "cc0", "pd"), then
judged by lib/commons.license_allows_reuse - the function the Commons fetch
already gates on. If that function's policy changes, this measurement moves
with it. The freshness window is fetch_poi_images.MAX_PHOTO_AGE_DAYS, likewise
imported rather than repeated.

Expect the licence catalogue itself to be the finding. Flickr's picker has
historically offered the CC **2.0** suite, and POI_PHOTOS.md rejects pre-4.0 CC
wholesale because a one-link credit line cannot meet its terms - so a pool
could be entirely CC-licensed and still yield nothing shippable. That is a
result worth having in writing.

    FLICKR_API_KEY=... python spike_flickr_group.py
    FLICKR_API_KEY=... python spike_flickr_group.py --group 908185@N20

The key is read from the environment and never stored - same posture as
check_r2_connection.py's R2 credentials. Get one at
https://www.flickr.com/services/apps/create/apply/ (non-commercial keys are
issued immediately). Read-only: this calls only `flickr.*.get*` methods.
"""

from __future__ import annotations

import os
import re
import sys
import time
from collections import Counter
from datetime import date, timedelta

import requests

from fetch_poi_images import MAX_PHOTO_AGE_DAYS
from lib.commons import license_allows_reuse

API_URL = "https://api.flickr.com/services/rest/"
API_KEY_ENV_VAR = "FLICKR_API_KEY"

# "Appalachian Trail Shelter" - 527 photos, 105 members, established 2008.
DEFAULT_GROUP_ID = "908185@N20"

PER_PAGE = 500  # Flickr's maximum
THROTTLE_SECONDS = 1.0  # Flickr's limit is 3600 calls/hour; this stays far under
RETRY_BACKOFF_SECONDS = (5, 30)
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)

# A Creative Commons deed URL carries the licence and its version in the path:
# https://creativecommons.org/licenses/by-sa/2.0/  -> cc-by-sa-2.0
# https://creativecommons.org/publicdomain/zero/1.0/ -> cc0
# Parsing the URL rather than the human-readable name ("Attribution-ShareAlike
# License") is what lets one policy function judge both sources: the name has
# no version in it at all, which is the single most important thing here.
_CC_LICENCE_URL_RE = re.compile(r"creativecommons\.org/licenses/([a-z-]+)/(\d+\.\d+)")
_CC_ZERO_URL_RE = re.compile(r"creativecommons\.org/publicdomain/zero/")
_PD_MARK_URL_RE = re.compile(r"creativecommons\.org/publicdomain/mark/")


def commons_style_license_id(name: str, url: str) -> str:
    """Flickr's (name, url) licence pair as the id shape lib/commons.py judges,
    or "" when it is not an open licence at all.

    Flickr's own ids are small integers whose meaning is a runtime lookup, and
    its names omit the version entirely - so the deed URL is the only field
    that says what the licence actually is. No URL means All Rights Reserved
    (id 0) or one of the two non-CC public-domain assertions, handled by name.
    """
    if _CC_ZERO_URL_RE.search(url):
        return "cc0"
    if _PD_MARK_URL_RE.search(url):
        return "pd"
    match = _CC_LICENCE_URL_RE.search(url)
    if match is not None:
        return f"cc-{match.group(1)}-{match.group(2)}"
    # "United States Government Work" and "No known copyright restrictions"
    # carry no deed URL. The first is genuinely PD by statute; the second is
    # Flickr Commons' "we found no restrictions", which is an absence of
    # evidence rather than a licence and must not be treated as one.
    if name.strip().lower() == "united states government work":
        return "pd-usgov"
    return ""


def flickr_call(session: requests.Session, method: str, api_key: str, **params) -> dict:
    """One read-only Flickr API call, JSON-decoded, retried on transient
    failures and throttled on success. A Flickr-level error (stat != "ok")
    raises: a wrong answer counted quietly is worse than a dead spike."""
    full = {"method": method, "api_key": api_key, "format": "json", "nojsoncallback": "1", **params}
    for attempt, delay in enumerate((*RETRY_BACKOFF_SECONDS, None)):
        try:
            resp = session.get(API_URL, params=full, timeout=60)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if delay is None:
                raise
            print(f"  {method}: {type(e).__name__} on attempt {attempt + 1}, retrying in {delay}s")
            time.sleep(delay)
            continue
        if resp.status_code in RETRYABLE_STATUSES and delay is not None:
            print(f"  {method} answered {resp.status_code} on attempt {attempt + 1}, retrying in {delay}s")
            time.sleep(delay)
            continue
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("stat") != "ok":
            raise RuntimeError(f"Flickr API error on {method}: {payload.get('code')} {payload.get('message')}")
        time.sleep(THROTTLE_SECONDS)
        return payload
    raise AssertionError("unreachable")


def licence_catalogue(session: requests.Session, api_key: str) -> dict[str, dict]:
    """Flickr's licence list, keyed by its integer id as a string, each with
    the Commons-style id and whether OurHike may ship under it.

    Fetched rather than hardcoded because which licences Flickr *offers* is
    half the answer: if the picker only writes the CC 2.0 suite, no amount of
    coverage in the pool produces a shippable photo."""
    payload = flickr_call(session, "flickr.photos.licenses.getInfo", api_key)
    catalogue = {}
    for entry in payload["licenses"]["license"]:
        commons_id = commons_style_license_id(entry.get("name", ""), entry.get("url", ""))
        catalogue[str(entry["id"])] = {
            "name": entry.get("name", ""),
            "url": entry.get("url", ""),
            "commons_id": commons_id,
            "allowed": bool(commons_id) and license_allows_reuse(commons_id),
        }
    return catalogue


def group_photos(session: requests.Session, group_id: str, api_key: str) -> list[dict]:
    """Every photo in the group pool, with the extras this measurement needs.

    `license` and `date_taken` are the two bars; `geo` is what a real fetcher
    would match on, and counting how many photos carry it at all is part of
    knowing whether that fetcher is possible."""
    photos: list[dict] = []
    page = 1
    while True:
        payload = flickr_call(
            session,
            "flickr.groups.pools.getPhotos",
            api_key,
            group_id=group_id,
            per_page=str(PER_PAGE),
            page=str(page),
            extras="license,date_taken,owner_name,geo,url_c",
        )
        block = payload["photos"]
        photos.extend(block.get("photo", []))
        print(f"  page {page}/{block.get('pages', 1)}: {len(photos)} photos so far")
        if page >= int(block.get("pages", 1)):
            return photos
        page += 1


def report(photos: list[dict], catalogue: dict[str, dict], cutoff: date) -> dict:
    """Print the measurement and return its headline numbers."""
    print("\n=== Flickr licence catalogue (what the picker can even write) ===")
    for lic_id, info in sorted(catalogue.items(), key=lambda kv: int(kv[0])):
        verdict = "SHIPPABLE" if info["allowed"] else "no"
        commons_id = info["commons_id"] or "-"
        print(f"  {lic_id:>2}  {info['name'][:44]:<46} {commons_id:<16} {verdict}")

    by_licence = Counter(p.get("license", "?") for p in photos)
    print(f"\n=== Licences across {len(photos)} pool photos ===")
    for lic_id, count in by_licence.most_common():
        info = catalogue.get(lic_id, {"name": f"unknown id {lic_id}", "allowed": False})
        flag = "SHIPPABLE" if info["allowed"] else ""
        print(f"  {count:>4}  {info['name'][:50]:<52} {flag}")

    open_licensed = [p for p in photos if catalogue.get(p.get("license", ""), {}).get("allowed")]
    fresh = [p for p in open_licensed if (p.get("datetaken") or "")[:10] >= cutoff.isoformat()]
    geotagged = [p for p in photos if p.get("latitude") not in (None, "0", 0)]

    print("\n=== Against OurHike's actual bars ===")
    print(f"  {len(photos):>4} photos in the pool")
    print(f"  {len(open_licensed):>4} under a licence OurHike may ship (PD/CC0/CC BY/BY-SA 4.0+)")
    print(f"  {len(fresh):>4} of those also taken on or after {cutoff.isoformat()}")
    print(f"  {len(geotagged):>4} carry coordinates (what a proximity matcher would need)")

    years = Counter((p.get("datetaken") or "????")[:4] for p in photos)
    print("\n=== Capture year across the whole pool ===")
    for year, count in sorted(years.items(), reverse=True)[:15]:
        print(f"  {year}: {count}")

    if fresh:
        print("\n=== Shippable and fresh ===")
        for p in fresh[:25]:
            print(f"  {(p.get('datetaken') or '')[:10]}  {p.get('title', '')[:46]:<48} {p.get('ownername', '')[:24]}")
    else:
        print("\n  Nothing in this pool clears both bars.")

    return {
        "pool": len(photos),
        "open_licensed": len(open_licensed),
        "fresh_and_open": len(fresh),
        "geotagged": len(geotagged),
    }


def main(group_id: str = DEFAULT_GROUP_ID) -> None:
    api_key = os.environ.get(API_KEY_ENV_VAR, "").strip()
    if not api_key:
        print(f"No {API_KEY_ENV_VAR} in the environment.")
        print("Get a non-commercial key at https://www.flickr.com/services/apps/create/apply/ then:")
        print(f"  {API_KEY_ENV_VAR}=... python spike_flickr_group.py")
        raise SystemExit(2)

    cutoff = date.today() - timedelta(days=MAX_PHOTO_AGE_DAYS)
    session = requests.Session()

    print(f"Group {group_id}; freshness cutoff {cutoff.isoformat()}")
    catalogue = licence_catalogue(session, api_key)
    photos = group_photos(session, group_id, api_key)
    report(photos, catalogue, cutoff)


def run(argv: list[str]) -> None:
    """Flag handling split from main() so tests can drive each side alone -
    same shape as fetch_poi_images.py. An unknown flag is rejected rather than
    ignored."""
    group_id = DEFAULT_GROUP_ID
    rest = list(argv)
    while rest:
        flag = rest.pop(0)
        if flag == "--group" and rest:
            group_id = rest.pop(0)
        else:
            print(f"Unknown flag {flag!r} - usage: python spike_flickr_group.py [--group <id>]")
            raise SystemExit(2)
    main(group_id=group_id)


if __name__ == "__main__":
    run(sys.argv[1:])
