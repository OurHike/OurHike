"""Recover NYNJTC's hike photographs from the Internet Archive, ONCE (#1450).

    python fetch_wayback_hike_photos.py --list        what the archive holds
    python fetch_wayback_hike_photos.py               fetch the bytes
    python fetch_wayback_hike_photos.py --limit 20    a sample, for a first look

THIS IS A ONE-TIME ARCHIVE RECOVERY, NOT A FETCHER ON A SCHEDULE, and that is
the maintainer's instruction rather than an implementation detail. Nothing in
`.github/workflows/` calls it and nothing should: the source is a frozen
capture of a site that has already changed, so a second run can only re-fetch
what the first one got. The code is committed anyway - the images are the
thing at risk, and if the archive loses them or the capture rots, what this
build did has to be reconstructable from the repository rather than from
somebody's memory of a session.

WHAT WAS LOST, AND WHERE IT WENT. #1450 records the loss exactly: the Hike
Finder export carries no photographs, and the four `<img>` tags in its prose
point at `/sites/default/files/u26/...` paths that **404 on both hosts**. True
of the live hosts. Not true of web.archive.org, which holds **403 of them**.

TWO ERAS, AND THEY HAVE OPPOSITE PROBLEMS (measured 2026-09-15):

    era                    referenced          archived      filename
    WordPress 2024-26      yes, ideal          2 of 1719     Hike149_MtMinsi1_Wagstaff2011.jpg
    Drupal u26 2017-24     -                   403           landmark names, some credits

The modern era's filenames are everything a join could want - a hike ID, the
name, the photographer, the year - and the bytes are not there:
`Hike149_MtMinsi1_Wagstaff2011.jpg` is referenced on the 2026-05-20 capture of
the Mt. Minsi page and 404s in the archive. The Drupal era has the bytes. So
this fetches the Drupal set, and the modern filenames are recorded in
`MODERN_ERA_NOTE` below because they are the shape to ask NYNJTC for.

**THE LATEST CAPTURE, NOT THE FIRST**, and this is the trap that cost this
work an hour. A CDX query with `collapse=urlkey` returns the FIRST capture of
each URL, which silently pins everything to 2019. `latest_captures()` below
groups by URL and keeps the newest timestamp: 331 are still 2019, 36 were
refetched through 2024, the rest fall in 2020-23. Older captures of a changing
site are harder to match against today's export, which is the maintainer's own
reason for wanting the newest.

THE LICENCE IS THE STRONGEST OF ANY SOURCE THIS PROJECT HAS MEASURED, which is
worth stating plainly because every other photo source here failed on it.
These are NYNJTC's own photographs; `sources.json`'s `nynjtc_hikes_licence`
records the maintainer's relay of NYNJTC's permission ("we have their
permission", 2026-09-08; "We can use anything", 2026-09-09). Compare
`spike_flickr_group.py` (right subject, unusable licence) and
`spike_hike_photo_by_name.py` (right subject, seven of ten pre-4.0 CC).

READING THE ARCHIVE IS NOT READING NYNJTC.ORG. #1450 closes the road to
scraping nynjtc.org and this does not reopen it: every request here goes to
web.archive.org. The CONTENT is still NYNJTC's and every condition
`nynjtc_hikes_licence` names applies to it unchanged.

WHAT THIS DOES NOT DO. It does not match a photograph to a hike - that is
`match_wayback_hike_photos.py`, behind a review sheet, because a filename
saying "Awosting Falls" is evidence about the photograph and not yet evidence
about which of 385 hikes it belongs to. It does not upload: `publish.py`
already takes everything in the content-addressed store, and the load is a
deliberate act somebody runs once.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import time
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from lib.photo_store import local_photo_path, photo_digest
from lib.user_agent import CONTACTABLE_USER_AGENT as USER_AGENT

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = RAW_DIR / "wayback_hike_photos.json"

CDX_API = "https://web.archive.org/cdx/search/cdx"

#: The Drupal-era upload directory NYNJTC's hike write-ups drew their
#: photographs from. `u26` is a Drupal user-files folder - user 26 being
#: whoever uploaded the hike photos - which is why one prefix reaches the
#: whole corpus and nothing else.
ARCHIVE_PREFIX = "nynjtc.org/sites/default/files/u26"

#: `id_` asks the archive for the ORIGINAL bytes rather than its rewritten
#: page furniture. Without it the Wayback Machine may return a viewer wrapper,
#: and for an image that means HTML where a JPEG was promised - which
#: `looks_like_jpeg()` below exists to catch either way.
RAW_CAPTURE_SUFFIX = "id_"

#: One request at a time with a pause between. The archive is a donation-
#: funded public good and this is a few hundred reads against it.
THROTTLE_SECONDS = 1.0
RETRY_BACKOFF_SECONDS = (5, 20)
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)
TIMEOUT = 90

#: What the modern site names its hike photographs, recorded here rather than
#: in a session that ends. THIS IS THE SHAPE TO ASK NYNJTC FOR: a hike id, the
#: subject, the photographer and the year, which would settle both the join
#: and the credit line in one move. Two are archived; the rest are referenced
#: on archived pages and 404.
MODERN_ERA_NOTE = "wp-content/uploads/YYYY/MM/Hike<id>_<Subject>_<Photographer><Year>.jpg"

#: A credit embedded in the filename, e.g.
#: "Awosting Falls. Photo by Keith Shane. 250 0105151418a.jpg".
#: The credit is the licence's condition (#1450), so a name found here is
#: worth strictly more than one inferred later, and is recorded as MEASURED
#: rather than guessed. Absence is not evidence of no photographer - it means
#: this filename does not say, and the record carries None.
_CREDIT_RE = re.compile(r"photo\s+by\s+([A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*){0,3})", re.I)

#: Digits that are a rendition width rather than part of a place's name -
#: "Terrace Pond South Trail 250 x 188 MG_8444.jpg". Stripped before the
#: filename is offered to the matcher as a description of the subject.
_SIZE_TOKEN_RE = re.compile(r"\b\d{2,4}\s*[x×]\s*\d{2,4}\b|\b(?:1[0-9]{2}|[2-9][0-9]{2})\b")

#: Camera filenames carry no information about the subject. Two shapes, both
#: read off the real corpus: a prefixed serial ("IMG_1574", "MG_8444"), and a
#: bare run of digits with an optional trailing letter ("0105151418a"), which
#: is a camera's own date-time name. The separator allows a SPACE because
#: _split_camel_case runs first and turns "IMG_1574" into "IMG 1574".
#: SIX digits is the floor deliberately - it
#: is long enough that no place name reaches it, while "fire tower 2" and a
#: four-digit year survive, and both of those carry meaning a matcher wants.
_CAMERA_NOISE_RE = re.compile(r"\b(?:I?MG|DSC|DSCN|IMGP)[_\-\s]?\d{3,}[a-z]?\b|\b\d{6,}[a-z]?\b", re.I)


@dataclass(frozen=True)
class Capture:
    """One archived image at its most recent capture."""

    original_url: str
    timestamp: str
    length: int

    @property
    def filename(self) -> str:
        return urllib.parse.unquote(self.original_url.rsplit("/", 1)[-1])

    @property
    def fetch_url(self) -> str:
        return f"https://web.archive.org/web/{self.timestamp}{RAW_CAPTURE_SUFFIX}/{self.original_url}"


@dataclass(frozen=True)
class Recovered:
    """An image whose bytes are now in the content-addressed store."""

    original_url: str
    timestamp: str
    digest: str
    bytes: int
    width: int | None
    height: int | None
    filename: str
    #: The subject as the filename states it, cleaned of rendition sizes and
    #: camera noise. The matcher's input - and only ever a description of the
    #: PHOTOGRAPH, never a claim about which hike it belongs to.
    subject: str
    #: A photographer named in the filename, or None. Measured, not inferred.
    credit: str | None


def session() -> requests.Session:
    made = requests.Session()
    made.headers["User-Agent"] = USER_AGENT
    return made


def _get(made: requests.Session, url: str, params: dict | None = None) -> requests.Response:
    """One throttled, retried GET. A non-retryable status raises rather than
    returning empty: this run's whole output is a count of what survived, so a
    failure counted as "not archived" would be a loss reported as a fact."""
    for attempt, delay in enumerate((*RETRY_BACKOFF_SECONDS, None)):
        try:
            response = made.get(url, params=params or {}, timeout=TIMEOUT)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
            if delay is None:
                raise
            print(f"    {type(error).__name__} on attempt {attempt + 1}, retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
            continue
        if response.status_code in RETRYABLE_STATUSES and delay is not None:
            print(f"    {response.status_code} on attempt {attempt + 1}, retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
            continue
        response.raise_for_status()
        time.sleep(THROTTLE_SECONDS)
        return response
    raise AssertionError("unreachable")


def latest_captures(made: requests.Session, prefix: str = ARCHIVE_PREFIX) -> list[Capture]:
    """Every archived image under `prefix`, at its MOST RECENT capture.

    Deliberately NOT `collapse=urlkey`: that returns the first capture of each
    URL and would pin the whole corpus to 2019. The grouping happens here so
    the choice is visible rather than hidden in a query string.
    """
    response = _get(
        made,
        CDX_API,
        {
            "url": f"{prefix}*",
            "output": "json",
            "filter": ["statuscode:200", "mimetype:image/jpeg"],
            "fl": "original,timestamp,length",
        },
    )
    rows = response.json()
    if not rows:
        return []
    newest: dict[str, Capture] = {}
    for original, timestamp, length in rows[1:]:  # row 0 is the header
        if not str(length).isdigit():
            continue
        found = newest.get(original)
        if found is None or timestamp > found.timestamp:
            newest[original] = Capture(original, timestamp, int(length))
    return sorted(newest.values(), key=lambda c: c.original_url)


def looks_like_jpeg(data: bytes) -> bool:
    """Whether these bytes actually start a JPEG.

    The archive answers a missing capture with an HTML error page at HTTP 200
    often enough that trusting the status would store web pages under names
    ending `.jpg` - which `lib/photo_store.py` would then content-address and
    `publish.py` would upload.
    """
    return data[:2] == b"\xff\xd8"


def jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    """(width, height) read from the JPEG's own start-of-frame, or None.

    Read here rather than left to the client because the frame the card picks
    depends on it: a hero box for a real photograph, a crisp inset for the
    250px renditions this corpus is mostly made of. A dimension the pipeline
    does not know is a decision the phone cannot make.
    """
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[index + 5 : index + 9])
            return width, height
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        (segment,) = struct.unpack(">H", data[index + 2 : index + 4])
        index += 2 + segment
    return None


def _split_camel_case(text: str) -> str:
    """ "AccessibleTrailAlongHugeBoulderJustBeforeMajorWelchJunction" ->
    "Accessible Trail Along Huge Boulder Just Before Major Welch Junction".

    A third of this corpus is named without separators, and the landmark a
    matcher needs is buried inside the run: that example carries "Major Welch
    Junction", which is a real place on a real hike and is invisible to any
    word-based comparison until the words exist. Splits on a lower-to-upper
    boundary and on the tail of an acronym ("ATIrisLoop" -> "AT Iris Loop"),
    which is the shape these filenames actually use.
    """
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)


def subject_from(filename: str) -> str:
    """The filename as a description of what the photograph shows.

    NYNJTC named these files after the thing in them - "Ashokan Reservoir from
    the viewpoint on Cross Mountain 250 IMG_1574.jpg" - which is why this
    corpus can be matched at all. Stripped of the rendition width and the
    camera's own serial, both of which describe the file rather than the
    place.
    """
    stem = filename.rsplit(".", 1)[0]
    # Separators go FIRST. `_` is a word character, so `\b` does not fire
    # between it and a digit - leaving "Bridge_300x420" with its rendition
    # size intact, which is how this was wrong on its first run.
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = _split_camel_case(stem)
    stem = _CREDIT_RE.sub(" ", stem)
    stem = _CAMERA_NOISE_RE.sub(" ", stem)
    stem = _SIZE_TOKEN_RE.sub(" ", stem)
    return " ".join(stem.split()).strip(" .,")


def credit_from(filename: str) -> str | None:
    """A photographer named in the filename, or None. See _CREDIT_RE."""
    found = _CREDIT_RE.search(filename)
    if not found:
        return None
    return found.group(1).strip(" .").strip() or None


def recover(made: requests.Session, capture: Capture, raw_dir: Path) -> Recovered | None:
    """One image's bytes into the content-addressed store, or None.

    Returning None is an ordinary outcome, not a failure: a capture the
    archive will not serve is one photograph missing, and the run reports how
    many rather than stopping.
    """
    try:
        response = _get(made, capture.fetch_url)
    except requests.exceptions.RequestException as error:
        print(f"  {capture.filename[:52]}: {type(error).__name__}", file=sys.stderr)
        return None

    data = response.content
    if not looks_like_jpeg(data):
        print(f"  {capture.filename[:52]}: not a JPEG ({len(data)} bytes)", file=sys.stderr)
        return None

    digest = photo_digest(data)
    target = local_photo_path(raw_dir, digest)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temporary = target.with_suffix(".part")
        temporary.write_bytes(data)
        temporary.replace(target)

    dimensions = jpeg_dimensions(data)
    return Recovered(
        original_url=capture.original_url,
        timestamp=capture.timestamp,
        digest=digest,
        bytes=len(data),
        width=dimensions[0] if dimensions else None,
        height=dimensions[1] if dimensions else None,
        filename=capture.filename,
        subject=subject_from(capture.filename),
        credit=credit_from(capture.filename),
    )


def summarise(recovered: list[Recovered]) -> None:
    if not recovered:
        print("\nNothing recovered.")
        return
    widths = [r.width for r in recovered if r.width]
    hero = sum(1 for w in widths if w >= 640)
    credited = sum(1 for r in recovered if r.credit)
    total_bytes = sum(r.bytes for r in recovered)
    print()
    print(f"  recovered              {len(recovered)}")
    print(f"  total bytes            {total_bytes / 1_000_000:.1f} MB")
    print(f"  with a credit in the filename  {credited}")
    if widths:
        widths.sort()
        print(f"  width  min {widths[0]}  median {widths[len(widths) // 2]}  max {widths[-1]}")
        print(f"  >= 640px (hero frame)  {hero}   below it (inset frame)  {len(widths) - hero}")
    print()
    print("  The frame each one gets is decided on the phone from these dimensions;")
    print("  a 250px rendition is an inset at its native aspect, never a hero box")
    print("  upscaled 2.1x and cropped to 16:10.")


def main(limit: int | None, listing_only: bool) -> int:
    made = session()
    print(f"Asking the archive what it holds under {ARCHIVE_PREFIX} ...")
    captures = latest_captures(made)
    if not captures:
        print("The archive returned nothing. That is a finding worth checking by hand before believing.")
        return 1

    years: dict[str, int] = {}
    for capture in captures:
        years[capture.timestamp[:4]] = years.get(capture.timestamp[:4], 0) + 1
    print(f"{len(captures)} images, at their most recent capture:")
    for year in sorted(years):
        print(f"  {year}  {years[year]:>4}")

    if listing_only:
        print()
        print(f"Modern-era naming, which is the shape to ask NYNJTC for: {MODERN_ERA_NOTE}")
        return 0

    chosen = captures[:limit] if limit else captures
    print(f"\nFetching {len(chosen)} ...")
    recovered: list[Recovered] = []
    for index, capture in enumerate(chosen, 1):
        got = recover(made, capture, RAW_DIR)
        if got:
            recovered.append(got)
        if index % 25 == 0:
            print(f"  {index}/{len(chosen)} ... {len(recovered)} recovered")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "source": "web.archive.org",
                "prefix": ARCHIVE_PREFIX,
                "one_time": True,
                "photos": [asdict(r) for r in recovered],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    summarise(recovered)
    print(f"\n  written to {OUT_PATH}")
    print("  Nothing is matched to a hike yet - match_wayback_hike_photos.py does that,")
    print("  behind a review sheet, because a filename is evidence about the photograph.")
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None, help="Fetch only the first N (a sample).")
    parser.add_argument("--list", action="store_true", dest="listing", help="Say what is there; fetch nothing.")
    args = parser.parse_args(argv)
    return main(args.limit, args.listing)


if __name__ == "__main__":
    raise SystemExit(run())
