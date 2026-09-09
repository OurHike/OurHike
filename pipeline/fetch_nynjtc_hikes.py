"""Read NYNJTC's Favorite Hikes off their WordPress API into a cache, with
each hike's photograph (#1290).

    python fetch_nynjtc_hikes.py                # the twenty public hikes and their photos
    python fetch_nynjtc_hikes.py --refetch-photos

WHAT THIS IS FOR. nynjtc.org/favorite-hikes is fifty-nine written-up day
hikes across the parks this build already draws - a name, an overview, a
turn-by-turn description somebody walked and dated, a photograph with a
credit, and the trailhead as a pin on a map. The maintainer asked for all of
them on the Suggested-hikes shelf (#1290), with NYNJTC's permission relayed
in the same ask; sources.json's `nynjtc_hikes_licence` is the record of what
that permission is and is not. lib/nynjtc_hikes.py is the reading; this is
the fetch.

THE OUTPUT IS A CACHE, NOT AN ARTIFACT. It lands in `data/raw/`, which is
gitignored and is where CONTRIBUTING.md puts anything fetched:

    data/raw/nynjtc_hikes.json          every public hike, parsed, with what it is missing
    data/raw/poi_photos/<digest>.jpg    each hike's photograph, content-addressed

The photographs go into the SAME content-addressed store the POI photos use
(lib/photo_store.py), for the reason that module gives: the key is the
checksum, identical bytes dedupe, and publish.py already uploads every file
in that directory under `photos/<digest>.jpg` with no change. What is NOT
copied from the Commons crawl is the face screen (lib/photo_screen.py): that
gate exists because a Commons photographer is an anonymous stranger and the
subject may be too, and these are the club's own published photographs,
credited by name, republished on the club's permission - the footing
fetch_atc_photos.py already ships ATC's facility photographs on, and that
fetcher screens nothing either. A photograph with NO credit is not fetched
at all: the credit line is the licence's condition, an uncredited image can
never reach a card, and publish.py takes every cached photo, so leaving it
out of the cache is what keeps it out of the bucket.

THE 39 PASSWORD-PROTECTED HIKES ARE NOT FETCHED, and the reason is worth
one sentence because it is the first thing the next session will want to
change. `content.protected: true` is NYNJTC's own gate on their own site;
the maintainer's instruction was "just do the 20 public ones", and walking
through somebody's password with their blessing is a different act from
reading their public pages, needing a credential this repository does not
hold (.github/expected-settings.yml has none for it). They are COUNTED, so
the shelf's coverage is a number a reader can see.

BEING POLITE TO SOMEBODY ELSE'S SERVER. One request lists everything - the
`hike` route pages at 100 and there are 59 - and one request per photograph
the cache does not already hold, throttled to two a second. A photograph is
downloaded ONCE: a hike whose rendition URL and digest are already in the
previous cache carries them forward, because the digest is the evidence a
photo was obtained and publish.verify_photo_promises() settles it against
the bucket at the moment it matters (the #465 argument, unchanged).

NO FRESHNESS MARKER, and check_freshness.py is deliberately not taught one:
the REST route serves neither an ETag nor a Last-Modified, and the post
type has no feed (`/hike/feed/` answers 404) - both read 2026-09-09. What
moves is `modified_gmt` on each post, which this fetch compares against its
own previous cache and reports, the same shape fetch_nynjtc_long_path_guide
.py settled on for pages that serve no validator.

FAILING IS NOT THE SAME AS FINDING NOTHING - `fetch_atc_updates.py`'s rule,
and it transfers unchanged. A run that cannot reach NYNJTC, reads a payload
it does not recognise, or finds no public hike at all leaves the previous
cache in place and exits non-zero. The cache is written atomically at the
end for that reason; a photograph that fails to download is a line in the
log and a hike with no photo, never a failed run, because the prose is the
hike and the picture is not.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from fetch_nynjtc_alerts import USER_AGENT, fetch_paged, session
from lib.fetch_receipts import record
from lib.http_retry import request_with_retry
from lib.nynjtc_hikes import (
    HIKE_ROUTE,
    SOURCE_KEY,
    ParsedHike,
    as_cache_entry,
    is_public,
    parse_hike,
    rendition_url,
)
from lib.photo_store import local_photo_path, photo_digest, photo_key
from lib.source_registry import find_source, load_registry

ROOT = Path(__file__).resolve().parent
SOURCES_PATH = ROOT / "sources.json"
RAW_DIR = ROOT / "data" / "raw"
CACHE_PATH = RAW_DIR / "nynjtc_hikes.json"

#: Half a second between photograph downloads - fetch_nynjtc_long_path_guide
#: .py's pace against the same host. Twenty images a run at most.
THROTTLE_SECONDS = 0.5
TIMEOUT = 60

#: What a rendition may be. lib/photo_store.py names every object `.jpg`, so
#: a PNG would be a file whose name promises bytes it does not hold.
JPEG_TYPES = ("image/jpeg", "image/jpg")


def load_previous(path: Path | None = None) -> dict:
    """The last run's hikes, keyed by slug, or {} on the first run or on a
    cache this build cannot read - a cache is a convenience, and a corrupt
    one costs a re-download rather than a run."""
    path = path or CACHE_PATH
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    hikes = document.get("hikes")
    return hikes if isinstance(hikes, dict) else {}


def store_photo(http, url: str) -> tuple[str, int] | None:
    """Download one rendition into the content-addressed store; the digest
    and the byte count, or None when the host did not answer with a JPEG.

    Same shape as fetch_atc_photos.store_rendering: a sibling temp then
    os.replace, so a half-written image is never a file whose name promises
    a digest its bytes do not have.
    """
    response = request_with_retry(url, session=http, timeout=TIMEOUT, label="nynjtc/photo", throttle_seconds=THROTTLE_SECONDS)
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if content_type not in JPEG_TYPES:
        print(f"    not a JPEG ({content_type or 'no content-type'}): {url}")
        return None
    image_bytes = response.content
    digest = photo_digest(image_bytes)
    path = local_photo_path(RAW_DIR, digest)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(image_bytes)
        os.replace(tmp_path, path)
    return digest, len(image_bytes)


def photo_record(hike: ParsedHike, post: dict, previous: dict | None, http, refetch: bool, now: str) -> tuple[dict | None, str]:
    """The cache's photo block for one hike, and one word for the log:
    `carried`, `fetched`, `uncredited`, `none` or `failed`."""
    if hike.photo is None:
        return None, "none"
    base = hike.photo.to_dict()
    if hike.photo.credit is None:
        # Not fetched, on purpose - see the module docstring.
        return base, "uncredited"
    url = rendition_url(post) if hike.photo.basis == "featured_media" else hike.photo.source_url
    if url is None:
        return base, "none"
    base["rendition_url"] = url
    prior = (previous or {}).get("photo") or {}
    if not refetch and prior.get("rendition_url") == url and prior.get("digest"):
        return {
            **base,
            "digest": prior["digest"],
            "key": prior.get("key") or photo_key(prior["digest"]),
            "bytes": prior.get("bytes"),
            "fetched_at": prior.get("fetched_at"),
        }, "carried"
    try:
        stored = store_photo(http, url)
    except Exception as error:  # noqa: BLE001 - one photo must not end the run
        print(f"    photo failed for {hike.slug}: {type(error).__name__}: {error}")
        return base, "failed"
    if stored is None:
        return base, "failed"
    digest, size = stored
    return {**base, "digest": digest, "key": photo_key(digest), "bytes": size, "fetched_at": now}, "fetched"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    refetch = "--refetch-photos" in argv

    registry = load_registry(SOURCES_PATH)
    source = find_source(registry, SOURCE_KEY)
    if source is None:
        print(f"{SOURCE_KEY} is not registered in sources.json - nothing to fetch", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    http = session()
    http.headers["User-Agent"] = USER_AGENT

    posts = fetch_paged(HIKE_ROUTE, http, {"_embed": 1})
    if not posts:
        print("NYNJTC's hike route returned no posts at all, which means the parse broke rather than that there are none.")
        return 1

    public = [post for post in posts if isinstance(post, dict) and is_public(post)]
    protected = sorted(
        str(post.get("slug") or post.get("id") or "?") for post in posts if isinstance(post, dict) and not is_public(post)
    )
    if not public:
        print(
            f"{len(posts)} posts and none of them public - a password gate on everything is a change worth a look, not a cache."
        )
        return 1

    parsed: list[tuple[ParsedHike, dict]] = []
    unreadable = []
    for post in public:
        hike = parse_hike(post)
        if hike is None:
            unreadable.append(str(post.get("slug") or post.get("id") or "?"))
            continue
        parsed.append((hike, post))
    if unreadable:
        # Zero tolerance, for fetch_atc_updates.py's reason: a payload this
        # build cannot read is a payload whose shape has changed, and caching
        # the subset that still parsed would look like NYNJTC had fewer hikes.
        print(f"Could not read {len(unreadable)}: {', '.join(unreadable[:5])}")
        print("Leaving the previous cache in place - see this file's docstring.")
        return 1

    previous = load_previous()
    hikes: dict[str, dict] = {}
    outcomes: dict[str, int] = {}
    changed = []
    for hike, post in sorted(parsed, key=lambda pair: pair[0].slug):
        prior = previous.get(hike.slug)
        photo, outcome = photo_record(hike, post, prior, http, refetch, stamp)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        entry = as_cache_entry(hike, stamp)
        entry["photo"] = photo
        hikes[hike.slug] = entry
        if prior is None or prior.get("modified_at") != hike.modified_at:
            changed.append(hike.slug)

    document = {
        "source": SOURCE_KEY,
        "fetched_at": stamp,
        "listed": len(posts),
        "public": len(hikes),
        "protected": protected,
        "hikes": hikes,
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CACHE_PATH.with_suffix(CACHE_PATH.suffix + ".tmp")
    tmp_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp_path, CACHE_PATH)

    print(f"{len(posts)} hikes listed: {len(hikes)} public, {len(protected)} behind NYNJTC's password and not fetched.")
    print("photos: " + ", ".join(f"{count} {word}" for word, count in sorted(outcomes.items())))
    if previous:
        print(f"{len(changed)} hike(s) new or modified since the last run" + (f": {', '.join(changed)}" if changed else ""))
    else:
        print("first fetch")
    for slug, entry in hikes.items():
        start = entry["start"]
        where = f"{start['lat']:.5f},{start['lon']:.5f} ({start['basis']})" if start else "no start"
        miles = f"{entry['stated_miles']} mi" if entry["stated_miles"] is not None else "miles unstated"
        print(f"  {slug[:52]:52} {str(entry['difficulty'] or '-'):19} {miles:14} {where}")
        for problem in entry["problems"]:
            print(f"      - {problem}")
    print(f"-> {CACHE_PATH}")
    if not source.get("reaches_hikers"):
        print(f"   {SOURCE_KEY} carries reaches_hikers: false - export_suggested_hikes.py will not publish from this cache")

    record("fetch_nynjtc_hikes", [CACHE_PATH], root=ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
