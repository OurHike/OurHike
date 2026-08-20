"""Fetch what a hiker's phone fetches, from the bucket it fetches it from.

[#94](https://github.com/OurHike/OurHike/issues/94). Everything else in this
repository is verified against local files and mocks. Nothing had ever pulled a
real PMTiles archive over real HTTP range requests from R2 and read it, so the
failure modes left uncovered were exactly the ones that are hard to debug from
a trailhead - a bucket that ignores `Range` and sends the whole body, a
content-encoding that mangles the bytes, an artifact whose hash no longer
matches what `latest.json` promises.

NOT THE SAME QUESTION AS check_deployment.py, and the split is deliberate.

    check_deployment.py   daily, no downloads    "can a browser REACH it"
    smoke_published.py    on demand, bounded     "is what is there CORRECT"

The first sends an `Origin` and asks about CORS; it deliberately never
downloads an artifact, because doing so daily would be ~1.6 GB of egress
against a rate-limited subdomain. This one does download - a bounded subset -
because a hash cannot be checked any other way. Running it daily would be the
wrong trade; running it never is how #94 stayed open.

OVER THE MANIFEST, NEVER A HARDCODED LIST

#94's own follow-up is emphatic about this and it is the easiest thing to get
wrong: `publish.py` has grown `quad_sheet_z14.pmtiles`, a vector basemap
package and a DEM package since the issue was written. A smoke test naming
`background.pmtiles` would pass while the packages a hiker actually navigates
by went unchecked. So every artifact `latest.json` names is checked, and a new
one is covered the day it is published.

WHY THE HASH CHECK MATTERS MORE THAN IT LOOKS

`client/src/lib/sha256.ts` and `dataManifest.ts` already hold a completed
download to the SHA-256 `latest.json` publishes, and discard the bytes on a
mismatch. That is a real check that has only ever seen a mock. It raises the
stakes rather than lowering them: a bucket serving a 200-with-whole-body for a
range request, or a mangled encoding, now fails on the phone as *"the map that
arrived is not the one the server published"* - which reads to a hiker like
corruption rather than like a misconfigured bucket. This is the check that
tells those apart, on the ground rather than in a mock.

    python smoke_published.py --base https://data.example.org
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import requests
from pmtiles.reader import Reader, traverse

from lib import data_env
from lib.content_types import COMPRESSIBLE_TYPES
from lib.freshness_state import utc_today

MANIFEST_KEY = "latest.json"

HTTP_TIMEOUT = 60

OK = "ok"
FAILED = "failed"
UNREACHABLE = "unreachable"
# Checked nothing and says so. Distinct from `ok` because an artifact too large
# to hash is not an artifact whose hash was verified, and rolling that into a
# pass is how a green run comes to mean less than a reader assumes.
SKIPPED = "skipped"

# How much of one artifact this is willing to pull to check its hash. The
# archives run to 1.18 GB and there are several of them; hashing every one
# would be ~3 GB a run to re-derive what the phone already checks per download.
# 25 MB covers `trails.geojson` (12 MB), `trails.fgb`, every `poi_*` file and
# both `conditions/*.json` - roughly 18 MB in total - and skips the archives,
# which are covered structurally by the PMTiles read below instead.
DEFAULT_MAX_HASH_BYTES = 25 * 1024 * 1024

# A slice big enough to prove the server is really honouring a range and not
# just answering the first bytes, small enough to be free.
RANGE_PROBE_BYTES = 64 * 1024


def _report(check: str, key: str, state: str, detail: str) -> dict:
    return {"check": check, "key": key, "state": state, "detail": detail}


class HttpRangeSource:
    """A `get_bytes(offset, length)` for `pmtiles.reader.Reader`, backed by HTTP.

    **This class is the point of the whole file.** `Reader` is the same
    machinery `extract_package.py` runs against local files, and MapLibre's
    pmtiles protocol reads an archive the same way a phone does: a header read,
    a directory read, then a tile read, each one a `Range` request against a
    file far too large to hold. Pointing it at a URL is what turns "the archive
    is well-formed on the machine that built it" into "the archive is readable,
    over range requests, from the bucket, right now".

    Counts its requests and bytes so the caller can prove this stayed cheap
    rather than asserting it.
    """

    def __init__(self, base: str, key: str, session: requests.Session | None = None):
        self.url = f"{base}/{key}"
        self.session = session or requests
        self.requests_made = 0
        self.bytes_read = 0

    def __call__(self, offset: int, length: int) -> bytes:
        response = self.session.get(
            self.url,
            headers={"Range": f"bytes={offset}-{offset + length - 1}"},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        # 206 or nothing (#653). A server that ignores Range answers 200 with
        # the WHOLE body, so every "slice" of a 1.18 GB archive would buffer
        # the archive into memory - the counters below would record the
        # blowout with nothing gating on them, and a lucky parse could still
        # report OK. check_range reports the misconfiguration in its own
        # verdict; this makes it impossible to read past by accident.
        if response.status_code != 206:
            raise ValueError(
                f"asked for bytes {offset}-{offset + length - 1} and was answered {response.status_code} "
                "with the whole body - the server is ignoring Range, and reading on would download the archive"
            )
        self.requests_made += 1
        self.bytes_read += len(response.content)
        return response.content


def fetch_manifest(base: str, session: requests.Session | None = None) -> dict | None:
    """`latest.json`, or None if there is not one to read."""
    getter = (session or requests).get
    try:
        response = getter(f"{base}/{MANIFEST_KEY}", timeout=HTTP_TIMEOUT)
        if response.status_code != 200:
            return None
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def _encoding_problem(key: str, encoding: str | None) -> str | None:
    """Why this object's `Content-Encoding` is wrong, or None if it is fine.

    THE RULE IS PER ARTIFACT, AND IT USED NOT TO BE. This refused any encoding
    on anything until #732, which is a rule that was correct when written and
    became wrong under it: #717 taught `publish.py` to store `.json` and
    `.geojson` gzipped on purpose - 21.5 MB of first-launch fetches down to
    5.3 MB, measured against the live bucket 2026-08-15 - and nothing here was
    told. Measured against `https://data.ourhike.org` on 2026-08-17, all
    fifteen text artifacts answer `Content-Encoding: gzip` and
    `background_z11.pmtiles` answers none, which is exactly what publish.py
    intends and exactly what this function was calling a failure.

    That was not merely noise. `check_all` skips the range and hash checks for
    any artifact whose headers fail, so every `.geojson` and `.json` a hiker's
    map is made of - `trails.geojson`, all eight `poi_*`, the conditions files
    - went unhashed and unranged while the tracking issue reported them red.
    The check that exists to catch "the bytes and the manifest disagree" was
    not running on the artifacts that matter most.

    So the two halves are split by how the CLIENT reads the artifact:

    - **Read whole** (`COMPRESSIBLE_TYPES`, imported rather than restated so
      the two files cannot drift apart again the way they just did). Ranges
      never enter into it: `trailData.ts` fetches these with a plain `fetch`,
      which decodes the encoding before any of its code sees a byte, and the
      SHA-256 in `latest.json` is of the file on disk - so the hash still
      matches. `gzip` is expected, absent is merely a missed saving, and
      anything else means something between publish.py and here re-encoded the
      object, which is worth failing on because the published representation is
      no longer what is on the wire.
    - **Read by range** (everything else, which is `.pmtiles` and `.fgb` today).
      Here the original reasoning stands unchanged, and the default is refusal
      rather than permission on purpose: a new extension nobody has classified
      is likelier to be a new archive than a new text file, and the cheap
      failure is a false alarm on a file that is fine.
    """
    if Path(key).suffix in COMPRESSIBLE_TYPES:
        if not encoding or encoding == "gzip":
            return None
        return (
            f"served with Content-Encoding: {encoding}, where publish.py stores these gzipped or not at all. "
            "Something between the publisher and here has re-encoded the object, so what is on the wire is no "
            "longer the representation that was published."
        )

    if encoding:
        return (
            f"served with Content-Encoding: {encoding}. This artifact is read by RANGE - archiveDownload.ts "
            "resumes a partial transfer and pmtilesSource.ts seeks within the archive - so ranges apply to "
            "encoded bytes while the client's resume counts decoded ones, and a resumed download reads from "
            "the wrong offset and fails as a hash mismatch that names nothing about encoding."
        )
    return None


def check_headers(base: str, key: str, session: requests.Session | None = None) -> dict:
    """What the object says about itself before a byte of it is read.

    `Content-Encoding` is the one worth being careful about, and it is why this
    is not folded into the hash check: on a range-read artifact a resume
    silently reads from the wrong offset, and the failure surfaces as a hash
    mismatch on a 1.18 GB download rather than as anything naming encoding.
    `_encoding_problem` holds that rule and why it differs per artifact.

    A missing `Content-Type` is reported rather than failed. Since #717
    publish.py sets one for every extension it knows, and the live bucket
    serves it (`application/geo+json` on the POI files, measured 2026-08-17) -
    but nothing in the client depends on one, because `fetch().json()` ignores
    it and MapLibre reads bytes, so failing on it would be this check inventing
    a rule the app does not have.
    """
    head = (session or requests).head
    try:
        response = head(f"{base}/{key}", timeout=HTTP_TIMEOUT)
    except requests.RequestException as exc:
        return _report("headers", key, UNREACHABLE, f"could not ask: {exc.__class__.__name__}")

    if response.status_code != 200:
        return _report("headers", key, FAILED, f"HEAD answered {response.status_code}")

    encoding = response.headers.get("Content-Encoding")
    problem = _encoding_problem(key, encoding)
    if problem:
        return _report("headers", key, FAILED, problem)

    if response.headers.get("Accept-Ranges", "").lower() != "bytes":
        return _report("headers", key, FAILED, f"Accept-Ranges was {response.headers.get('Accept-Ranges')!r}")

    length = response.headers.get("Content-Length")
    if not length or not length.isdigit() or int(length) == 0:
        return _report("headers", key, FAILED, f"Content-Length was {length!r}")

    # Notes, never failures - each one is something a reader of this report
    # would otherwise have to work out for themselves. The size travels as
    # its own `size` field (#659) - check_all used to re-parse it out of
    # this human-readable sentence, which is a wording change away from
    # breaking every downstream check.
    notes = []
    if encoding:
        # Worth saying plainly: this is the STORED size, which is what a range
        # is measured in, and it is not the size `latest.json` records. For
        # trails.geojson the two are 4.1 MB and 12.3 MB (measured 2026-08-17)
        # and a reader comparing them without this note would file a bug.
        notes.append(f"{encoding}, so this is the encoded size and not the manifest's")
    elif Path(key).suffix in COMPRESSIBLE_TYPES:
        notes.append("no Content-Encoding, so a hiker pays the uncompressed size for a file publish.py gzips")
    if not response.headers.get("Content-Type"):
        notes.append("no Content-Type, which nothing here depends on")

    detail = f"{int(length)} bytes"
    if notes:
        detail += f" ({'; '.join(notes)})"
    return {**_report("headers", key, OK, detail), "size": int(length)}


def check_range(base: str, key: str, size: int, session: requests.Session | None = None) -> dict:
    """A range from the MIDDLE of the object, not the start.

    A prefix range is the one case a server that half-understands ranges is
    most likely to get right, so asking for one proves the least. The client
    resumes from wherever it got to, which is by definition not the start.

    A `200` here is the specific failure #94 names: the server ignored the
    range and is sending the whole body. `archiveDownload.ts` detects it and
    starts over, so it costs a hiker the entire transfer rather than corrupting
    the file - but on a 1.18 GB archive over trail signal, "starts over" is the
    whole problem.

    READ UNDECODED, and this is not a detail. A range addresses the bytes the
    bucket STORES, so a slice out of the middle of a gzipped object is a
    fragment of a deflate stream with no header in front of it, and letting
    `requests` apply `Content-Encoding` to it fails.

    Measured 2026-08-17 against a mock serving the shape R2 serves: with the
    decoding read, this returns UNREACHABLE for every gzipped artifact - not a
    crash, because `stream=False` materialises the body inside `send()` where
    the `except` below catches `ContentDecodingError`. That is the worse of the
    two outcomes to have shipped. A range check that reports "could not ask"
    reads as a transport wobble, and the workflow counts unreachable separately
    from failed, so the artifact would have gone unranged with the report
    saying so in the one line nobody treats as a finding. Nothing hit it only
    because `check_headers` used to fail every gzipped artifact first and
    `check_all` skipped this check entirely; #732 removed that shield.
    """
    if size <= RANGE_PROBE_BYTES * 2:
        return _report("range", key, SKIPPED, f"only {size} bytes, too small for a mid-file probe")

    start = size // 2
    end = start + RANGE_PROBE_BYTES - 1
    getter = (session or requests).get
    try:
        # `with`, because `stream=True` without it leaks the connection on
        # every path that does not read the body - and the 200 below is
        # exactly such a path, on a response whose unread body is the whole
        # 1.18 GB archive. check_hash uses the same form one function down.
        with getter(
            f"{base}/{key}",
            headers={"Range": f"bytes={start}-{end}"},
            timeout=HTTP_TIMEOUT,
            stream=True,
        ) as response:
            status = response.status_code
            content_range = response.headers.get("Content-Range", "")
            # decode_content=False is the whole point of the docstring's second
            # paragraph. Read inside the `try` so a decode or transport failure
            # is an UNREACHABLE verdict rather than an exception out of
            # check_all, and inside the `with` because after it there is no
            # connection left to read from.
            body = response.raw.read(decode_content=False) if status == 206 else b""
    except requests.RequestException as exc:
        return _report("range", key, UNREACHABLE, f"could not ask: {exc.__class__.__name__}")

    if status == 200:
        return _report(
            "range",
            key,
            FAILED,
            "a mid-file range was answered 200 with the whole body - the server ignored it. "
            "Every resumed download of this artifact restarts from zero.",
        )
    if status != 206:
        return _report("range", key, FAILED, f"a mid-file range answered {status}")

    got = len(body)
    if got != RANGE_PROBE_BYTES:
        return _report("range", key, FAILED, f"asked for {RANGE_PROBE_BYTES} bytes and got {got}")

    expected = f"bytes {start}-{end}/{size}"
    if content_range != expected:
        return _report("range", key, FAILED, f"Content-Range was {content_range!r}, expected {expected!r}")

    return _report("range", key, OK, content_range)


def check_hash(
    base: str,
    key: str,
    expected: str | None,
    size: int,
    max_bytes: int,
    session: requests.Session | None = None,
) -> dict:
    """The bytes behind the key, hashed and held to what `latest.json` promises.

    The same expectation `client/src/lib/dataManifest.ts` reads and
    `sha256.ts` computes, asked of the real bucket for the first time. Streamed
    rather than buffered: `trails.geojson` is 12 MB and there is no reason for
    this to hold it.

    Skipped above `max_bytes` rather than quietly passed. An artifact too large
    to hash here is one the phone hashes on every download anyway, and the
    PMTiles read covers its structure - but calling that `ok` would let a green
    run claim more than it checked.
    """
    if expected is None:
        return _report("hash", key, FAILED, "latest.json names this artifact but publishes no sha256 for it")

    if size > max_bytes:
        return _report(
            "hash", key, SKIPPED, f"{size} bytes is over the {max_bytes}-byte budget; the phone hashes it per download"
        )

    digest = hashlib.sha256()
    getter = (session or requests).get
    try:
        with getter(f"{base}/{key}", stream=True, timeout=HTTP_TIMEOUT) as response:
            if response.status_code != 200:
                return _report("hash", key, FAILED, f"GET answered {response.status_code}")
            for chunk in response.iter_content(chunk_size=1024 * 256):
                digest.update(chunk)
    except requests.RequestException as exc:
        return _report("hash", key, UNREACHABLE, f"could not read: {exc.__class__.__name__}")

    actual = digest.hexdigest()
    if actual != expected.lower():
        return _report(
            "hash",
            key,
            FAILED,
            f"published {expected.lower()[:16]}… but serves {actual[:16]}…. A phone downloading this "
            "discards it and retries forever - the bytes and the manifest disagree.",
        )
    return _report("hash", key, OK, f"matches {actual[:16]}…")


# What a tile's first bytes look like, per what the header says it is. Checked
# because "the range request returned bytes" and "the range request returned
# the tile" are different claims, and only the second one is a map. A
# gzip-compressed tile is gzip whatever it decodes to, so compression is
# consulted before type.
_TILE_MAGIC = {
    "WEBP": (b"RIFF", "a WebP"),
    "PNG": (b"\x89PNG", "a PNG"),
    "JPEG": (b"\xff\xd8", "a JPEG"),
}
_GZIP_MAGIC = b"\x1f\x8b"


def _tile_looks_right(header: dict, data: bytes) -> str | None:
    """None if the tile's first bytes match what the header promised, or the
    reason they do not."""
    if not data:
        return "the archive's first tile is empty"

    compression = str(header.get("tile_compression", "")).rsplit(".", 1)[-1]
    if compression == "GZIP":
        return None if data.startswith(_GZIP_MAGIC) else f"header says tiles are gzipped, but the first one starts {data[:4]!r}"

    tile_type = str(header.get("tile_type", "")).rsplit(".", 1)[-1]
    expected = _TILE_MAGIC.get(tile_type)
    if expected is None:
        # MVT stored uncompressed, or a type this does not know. Not something
        # to invent a rule about - the tile arrived and its length is real.
        return None
    magic, described = expected
    return None if data.startswith(magic) else f"header says tiles are {described}, but the first one starts {data[:4]!r}"


def check_pmtiles(base: str, key: str, session: requests.Session | None = None) -> dict:
    """Open the archive the way MapLibre opens it: over range requests.

    Header, then root directory, then a real tile - each one a `Range` against
    a file far too large to download. This is the check #94 was actually asking
    for, and the only one that proves an archive is *usable* rather than merely
    present and correctly hashed.

    `traverse` is the library's own directory walk, the same code
    `extract_package.py` runs against local files; only the byte source
    differs. Taking the first tile off its generator reads a header, a root
    directory and one tile and then stops - measured at 3-4 range requests and
    under 103 KB against the real archives, including the 1.18 GB one.

    A well-formed archive the bucket will not serve in ranges fails here with a
    readable error, instead of as a blank map on a ridge.
    """
    source = HttpRangeSource(base, key, session)
    try:
        header = Reader(source).header()
    except Exception as exc:
        return _report("pmtiles", key, FAILED, f"could not be opened over range requests: {exc.__class__.__name__}: {exc}")

    min_zoom, max_zoom = header.get("min_zoom"), header.get("max_zoom")
    tiles = header.get("addressed_tiles_count")

    if min_zoom is None or max_zoom is None or min_zoom > max_zoom:
        return _report("pmtiles", key, FAILED, f"header zooms are {min_zoom}..{max_zoom}")
    if not tiles:
        return _report("pmtiles", key, FAILED, "header reports no addressed tiles - an empty archive")

    try:
        first = next(traverse(source, header, header["root_offset"], header["root_length"]), None)
    except Exception as exc:
        return _report("pmtiles", key, FAILED, f"header read but no tile could be: {exc.__class__.__name__}: {exc}")

    if first is None:
        return _report("pmtiles", key, FAILED, f"header claims {tiles} tiles but the directory yielded none")

    (z, x, y), data = first
    wrong = _tile_looks_right(header, data)
    if wrong:
        return _report("pmtiles", key, FAILED, f"tile z{z}/{x}/{y}: {wrong}")

    return _report(
        "pmtiles",
        key,
        OK,
        f"z{min_zoom}-{max_zoom}, {tiles} tiles; read z{z}/{x}/{y} ({len(data)} bytes) in "
        f"{source.requests_made} range request(s) totalling {source.bytes_read} bytes",
    )


def check_all(
    base: str,
    manifest: dict,
    max_hash_bytes: int = DEFAULT_MAX_HASH_BYTES,
    session: requests.Session | None = None,
) -> list[dict]:
    """Every artifact the manifest names. Never raises."""
    base = base.rstrip("/")
    reports: list[dict] = []

    for key in sorted((manifest.get("artifacts") or {}).keys()):
        entry = manifest["artifacts"][key] or {}
        headers = check_headers(base, key, session)
        reports.append(headers)
        if headers["state"] != OK:
            # Everything below needs a size and a reachable object. Reporting
            # three more failures for one broken artifact would bury the one
            # that explains the rest.
            continue

        size = headers["size"]
        reports.append(check_range(base, key, size, session))
        reports.append(check_hash(base, key, entry.get("sha256"), size, max_hash_bytes, session))
        if key.endswith(".pmtiles"):
            reports.append(check_pmtiles(base, key, session))

    return reports


def verdict_document(base: str, reports: list[dict]) -> dict:
    return {
        "checked_at": utc_today().isoformat(),
        "base": base,
        "checks": reports,
        "failed": [r for r in reports if r["state"] == FAILED],
        "unreachable": [r for r in reports if r["state"] == UNREACHABLE],
        "skipped": [r for r in reports if r["state"] == SKIPPED],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", metavar="URL", help="Public bucket base. Defaults to $DATA_BASE_URL.")
    parser.add_argument(
        "--env",
        metavar="NAME",
        choices=data_env.ENVIRONMENTS,
        help="Smoke this environment's data rather than the base as given (features/DATA_ENVIRONMENTS.md).",
    )
    parser.add_argument("--json", metavar="OUT", type=Path, help="Also write the verdict to OUT as JSON.")
    parser.add_argument(
        "--max-hash-bytes",
        type=int,
        default=DEFAULT_MAX_HASH_BYTES,
        help="Largest artifact to download and hash. Above this, the hash is skipped and said to be skipped.",
    )
    parser.add_argument("--exit-zero", action="store_true", help="Exit 0 even when something failed.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    base = data_env.resolve_base(args.base, args.env)
    if not base:
        print("No bucket to check: pass --base or set DATA_BASE_URL.", file=sys.stderr)
        return 2

    manifest = fetch_manifest(base)
    if manifest is None:
        print(f"No {MANIFEST_KEY} published at {base} yet - nothing to smoke test.", file=sys.stderr)
        return 2

    reports = check_all(base, manifest, args.max_hash_bytes)
    for report in reports:
        print(f"  {report['state'].upper():12} {report['check']:9} {report['key']:34} {report['detail']}")

    document = verdict_document(base, reports)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(document, indent=2))

    failed, unreachable, skipped = document["failed"], document["unreachable"], document["skipped"]
    print(
        f"\n{len(reports)} check(s): {len(failed)} failed, {len(unreachable)} unreachable, "
        f"{len(skipped)} skipped, {len(reports) - len(failed) - len(unreachable) - len(skipped)} ok."
    )
    if not failed and not unreachable:
        print("What the bucket serves is what the manifest promises.")

    if args.exit_zero:
        return 0
    # Unreachable is not passed (#651). A run that could not ask has no
    # business exiting like one that asked and was answered well - this
    # module's own rule is that a green run must not claim more than it
    # checked, and the exit code is the claim a gate reads.
    return 1 if failed or unreachable else 0


if __name__ == "__main__":
    sys.exit(main())
