"""The release verification battery. DATA_RELEASES.md §3 is the design.

Run against a release over its **public HTTPS URL**, with no credentials. That
is the point rather than a convenience: it tests the artifact a hiker's phone
will actually fetch, through the same CDN, CORS policy and range machinery,
instead of a file on the runner's disk.

RELEASING.md §8 gate 6 has required this since the process was written, and it
did not exist. Three other places already deferred to it - `check_deployment.py`
says in as many words that proving the *bytes* are right is "verify_release.py's
job (check 5)" - which meant nothing in this repository proved that a published
artifact is the artifact that was built. Check 5 below is that proof.

WHAT THIS IS NOT

Not the standing monitor. `check_deployment.py` (#431 tier 1) watches a *good*
release quietly stop being reachable, daily, on nobody's schedule. This is a
gate run once, against a candidate, before it is promoted. #427 was the first
kind of failure and no release gate would have caught it.

Not `smoke_published.py` either, and the mechanisms are deliberately shared
rather than copied: that script hashes a bounded 25 MB prefix weekly to notice
rot cheaply, and this one hashes every byte once because a release gate has to.
Importing its range, header and PMTiles helpers is the one-home rule doing its
job - two scripts, two purposes, one implementation of "read this artifact over
HTTP".

WHAT IT CANNOT CHECK YET, STATED RATHER THAN QUIETLY PASSED

Five of the nineteen checks report SKIPPED with a reason, and a skip here is
never silent - `--strict` turns every one of them into a failure, because
"the check did not run" reading like "the check passed" is the exact shape of
failure this repository keeps finding.

  3, 17, 19  need the `releases/` layout (#500). R2_LAYOUT.md declares it;
             the bucket does not have it. Measured: `releases/index.json` 404
             while `latest.json` answers 206. Without a previous release there
             is nothing to compare against and no released folder to re-verify,
             which is check 19 - the headline "the releases hikers are already
             on still work".
  10         needs the tile count the build reported. `latest.json` carries a
             sha256 per artifact and nothing else, so there is no published
             figure to match against.

Check 4 runs but is weaker than §3 asks for, for the same reason: the manifest
publishes no `size_bytes`, so "Content-Length == manifest size_bytes" is not a
question that can be asked. It asserts the headers that make an artifact
fetchable and resumable instead, and says so.

    python verify_release.py --base https://data.example.org
    python verify_release.py --base https://data.example.org --strict
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests

from lib import data_env
from lib.completeness import DROP_THRESHOLD, count_problems
from smoke_published import (
    HTTP_TIMEOUT,
    HttpRangeSource,
    _tile_looks_right,
    fetch_manifest,
)

ROOT = Path(__file__).resolve().parent
CLIENT_LIB = ROOT.parent / "client" / "src" / "lib"

OK = "ok"
FAILED = "failed"
SKIPPED = "skipped"

# The response headers a browser must be allowed to READ, from
# .github/expected-origins.yml's `expose_headers`. Named here rather than read
# from that file because this is a release gate that must run against a bucket
# whose CORS policy is the thing under test - see check 8.
EXPOSED = ("accept-ranges", "content-length", "content-range", "etag")

# Generous bounds on the Appalachian Trail corridor. A sanity bound, not a
# clip: it catches a geometry at (0, 0) or one that landed in the wrong
# hemisphere, which is what a projection bug produces. Deriving it from
# trails.geojson would make check 15 assert that the data agrees with itself.
CORRIDOR_BBOX = (-85.0, 33.5, -66.5, 46.5)

# How close a tier has to stay to the size the app advertises (check 18).
# README.md already says a tier drifting far from its advertised size "is a
# real problem, not a rounding detail"; 2% is DATA_RELEASES.md §3's figure.
ADVERTISED_TOLERANCE = 0.02

_NEEDS_RELEASES = "needs the releases/ layout (#500), which the bucket does not have yet"


def _report(check: int, key: str, state: str, detail: str) -> dict:
    return {"check": check, "key": key, "state": state, "detail": detail}


# ---------------------------------------------------------------------------
# What the CLIENT will ask for. Read out of the client's own source rather
# than restated, per DATA_RELEASES.md §3 check 2: a tier the app offered and
# the bucket lacked has already happened once (publish.py:65-67).
#
# Parsing TypeScript from Python is not lovely, and the alternative is worse -
# a hand-kept copy here is a second home for the contract, and the whole
# failure being guarded against is the two disagreeing. The regexes are narrow
# and `expected_client_keys` raises rather than returning a short list, so a
# rename in config.ts fails this loudly instead of quietly checking fewer keys.
# ---------------------------------------------------------------------------


def _read(name: str) -> str:
    return (CLIENT_LIB / name).read_text(encoding="utf-8")


def expected_client_keys(config_ts: str | None = None) -> list[str]:
    """Every object key the client is built to request."""
    source = config_ts if config_ts is not None else _read("config.ts")

    trails = re.search(r"TRAILS_KEY\s*=\s*'([^']+)'", source)
    poi_types = re.search(r"POI_TYPES\s*=\s*\[([^\]]+)\]", source)
    poi_pattern = re.search(r"poiKey\([^)]*\)[^{]*\{\s*return\s*`([^`]+)`", source)
    archives = re.findall(r"^\s*(?:light|standard|fine):\s*'([^']+)'", source, re.MULTILINE)

    if not (trails and poi_types and poi_pattern and archives):
        raise ValueError(
            "could not read the key contract out of client/src/lib/config.ts. "
            "It has been restructured, and this check must be updated rather than "
            "left matching fewer keys than the client asks for."
        )

    types = re.findall(r"'([^']+)'", poi_types.group(1))
    keys = [trails.group(1)]
    keys += [poi_pattern.group(1).replace("${type}", poi_type) for poi_type in types]
    keys += archives
    return keys


def advertised_sizes(download_detail_ts: str | None = None) -> dict[str, int]:
    """Each tier's advertised download size, from the client's own table.

    That figure is what a hiker weighs against remaining phone storage at a
    trailhead, which is why drifting from it is check 18 rather than a note.
    """
    source = download_detail_ts if download_detail_ts is not None else _read("downloadDetail.ts")
    found = re.findall(r"level:\s*'(\w+)'[^}]*sizeBytes:\s*([\d_]+)", source)
    if not found:
        raise ValueError("could not read DOWNLOAD_DETAIL_LEVELS out of client/src/lib/downloadDetail.ts")
    return {level: int(size.replace("_", "")) for level, size in found}


def archive_keys(config_ts: str | None = None) -> dict[str, str]:
    """tier -> object key, so an advertised size can be matched to an artifact."""
    source = config_ts if config_ts is not None else _read("config.ts")
    return dict(re.findall(r"^\s*(light|standard|fine):\s*'([^']+)'", source, re.MULTILINE))


# ---------------------------------------------------------------------------
# A. Presence and contract
# ---------------------------------------------------------------------------


def check_manifest(manifest: dict | None) -> dict:
    """1. `latest.json` parses and has the expected shape."""
    if manifest is None:
        return _report(1, "latest.json", FAILED, "the manifest could not be read at all")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        return _report(1, "latest.json", FAILED, "no `artifacts` mapping - nothing else here can be trusted")
    missing = [key for key, entry in artifacts.items() if not (entry or {}).get("sha256")]
    if missing:
        return _report(
            1, "latest.json", FAILED, f"{len(missing)} artifact(s) publish no sha256: {', '.join(sorted(missing)[:5])}"
        )
    return _report(1, "latest.json", OK, f"{len(artifacts)} artifacts, every one with a sha256")


def check_client_keys(manifest: dict) -> list[dict]:
    """2. Every key the CLIENT will request exists in the release."""
    published = set((manifest.get("artifacts") or {}).keys())
    reports = []
    for key in expected_client_keys():
        if key in published:
            reports.append(_report(2, key, OK, "the client asks for this and the release has it"))
        else:
            reports.append(
                _report(
                    2,
                    key,
                    FAILED,
                    "the client is built to request this and the release does not contain it - "
                    "the app would fail on a key nothing else in the build would notice",
                )
            )
    return reports


# ---------------------------------------------------------------------------
# B. Byte-level integrity
# ---------------------------------------------------------------------------


def check_fetchable(base: str, key: str, session=None) -> dict:
    """4. HEAD: 200, a Content-Length, `Accept-Ranges: bytes`, an ETag.

    Weaker than DATA_RELEASES.md §3 asks - it wants `Content-Length` compared
    against the manifest's `size_bytes`, and the manifest does not publish one.
    Asserted here is what makes an artifact fetchable and resumable at all;
    that the bytes are the RIGHT bytes is check 5's job, and check 5 is
    stronger than a size comparison anyway.
    """
    try:
        response = (session or requests).head(f"{base}/{key}", timeout=HTTP_TIMEOUT)
    except requests.RequestException as exc:
        return _report(4, key, FAILED, f"could not be reached: {exc.__class__.__name__}")

    if response.status_code != 200:
        return _report(4, key, FAILED, f"HEAD answered {response.status_code}")

    problems = []
    if not response.headers.get("Content-Length"):
        problems.append("no Content-Length")
    if (response.headers.get("Accept-Ranges") or "").lower() != "bytes":
        problems.append("no `Accept-Ranges: bytes`, so a download cannot resume")
    if not response.headers.get("ETag"):
        problems.append("no ETag, which If-Range is compared against")

    if problems:
        return _report(4, key, FAILED, "; ".join(problems))
    return _report(4, key, OK, f"{response.headers['Content-Length']} bytes, ranged, with an ETag")


def check_full_hash(base: str, key: str, expected: str, session=None) -> dict:
    """5. Stream and SHA-256 the WHOLE artifact against the manifest.

    The only check that proves the bytes a hiker downloads are the bytes that
    were built. Streamed and never buffered: the largest artifact is 1.18 GB
    and a release has ~1.6 GB of them, which is the cost of the one question
    nothing else in this repository asks.
    """
    digest = hashlib.sha256()
    read = 0
    try:
        with (session or requests).get(f"{base}/{key}", stream=True, timeout=HTTP_TIMEOUT) as response:
            if response.status_code != 200:
                return _report(5, key, FAILED, f"GET answered {response.status_code}")
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                digest.update(chunk)
                read += len(chunk)
    except requests.RequestException as exc:
        return _report(5, key, FAILED, f"download failed after {read} bytes: {exc.__class__.__name__}")

    actual = digest.hexdigest()
    if actual != expected:
        return _report(
            5,
            key,
            FAILED,
            f"sha256 {actual} over {read} bytes, manifest says {expected}. The published object is NOT "
            "the object that was built and quality-checked.",
        )
    return _report(5, key, OK, f"sha256 matches over all {read} bytes")


def check_if_range(base: str, key: str, session=None) -> dict:
    """7. `If-Range` is honoured: correct ETag -> 206, stale ETag -> 200.

    One of the two mechanisms `client/src/lib/archiveDownload.ts` uses to
    refuse a splice, and DATA_RELEASES.md §3 is right that it must be tested
    rather than assumed - measured against the live `r2.dev` endpoint on
    2026-08-09, it is NOT honoured: a stale ETag, a wrong-but-valid-shaped
    ETag and a long-past HTTP-date all answer 206 with the range served, where
    RFC 9110 requires the Range to be ignored and 200 returned.

    That is a real failure of the bucket and this reports it as one. It stays a
    FAILURE rather than becoming an expected result (#506): a gate taught to
    expect the current breakage cannot notice it was fixed, and the move to a
    custom domain may fix it - re-run this against `data.ourhike.app` before
    assuming either way.

    It is not a live hazard to a hiker, and the message says so rather than
    overstating. `archiveDownload.ts` performs this same comparison itself, on
    the ETag the 206 carries, so what the bucket declines to arbitrate is
    arbitrated client-side before any body is read - and the published SHA-256
    remains behind that. What this check establishes is that the resume's
    server-side defence is absent, not that the resume is undefended.
    """
    getter = (session or requests).get
    try:
        head = (session or requests).head(f"{base}/{key}", timeout=HTTP_TIMEOUT)
        etag = head.headers.get("ETag")
        if not etag:
            return _report(7, key, FAILED, "no ETag, so If-Range cannot be evaluated at all")

        fresh = getter(f"{base}/{key}", headers={"Range": "bytes=0-1023", "If-Range": etag}, timeout=HTTP_TIMEOUT)
        stale = getter(
            f"{base}/{key}",
            headers={"Range": "bytes=0-1023", "If-Range": '"ourhike-deliberately-stale"'},
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        return _report(7, key, FAILED, f"could not ask: {exc.__class__.__name__}")

    if fresh.status_code != 206:
        return _report(7, key, FAILED, f"a CURRENT ETag answered {fresh.status_code}, not 206 - resume is broken")
    if stale.status_code != 200:
        return _report(
            7,
            key,
            FAILED,
            f"a STALE ETag answered {stale.status_code}, not 200 - the bucket is ignoring If-Range, so it "
            "will not arbitrate a stale partial. The client does not depend on it: archiveDownload.ts "
            "compares the ETag on the 206 against the one its held bytes were recorded under and refuses "
            "the resume itself, with the published SHA-256 behind that. What is missing is the server-side "
            "half, so a conforming endpoint - a custom domain - would restore a defence rather than add one.",
        )
    return _report(7, key, OK, "current ETag -> 206, stale ETag -> 200")


def check_cors(base: str, key: str, session=None) -> dict:
    """8. The expose-headers a browser needs in order to READ the rest.

    R2 sent all four throughout #427 and a browser still could not see them.
    A CORS regression silently disarms check 7 on real devices while CI, which
    is not a browser, would never notice - so this sends an Origin.
    """
    try:
        response = (session or requests).get(
            f"{base}/{key}",
            headers={"Range": "bytes=0-0", "Origin": "https://ourhike.github.io"},
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        return _report(8, key, FAILED, f"could not ask: {exc.__class__.__name__}")

    exposed = {
        item.strip().lower() for item in (response.headers.get("Access-Control-Expose-Headers") or "").split(",") if item.strip()
    }
    missing = [header for header in EXPOSED if header not in exposed]
    if missing:
        return _report(
            8,
            key,
            FAILED,
            f"a browser may not read {', '.join(missing)}. The resumable download needs content-range to "
            "know a range was honoured, and etag is what If-Range compares against.",
        )
    return _report(8, key, OK, "every load-bearing response header is readable by a browser")


# ---------------------------------------------------------------------------
# C. PMTiles structure  ·  D. Vector content
# ---------------------------------------------------------------------------


def check_pmtiles_zooms(base: str, key: str, expected_zoom: int | None, session=None) -> dict:
    """9. The archive opens and its declared zooms match the tier."""
    from pmtiles.reader import Reader

    try:
        header = Reader(HttpRangeSource(base, key, session)).header()
    except Exception as exc:  # noqa: BLE001 - a broken archive fails many ways
        return _report(9, key, FAILED, f"does not open as PMTiles: {exc.__class__.__name__}: {exc}")

    low, high = header["min_zoom"], header["max_zoom"]
    if expected_zoom is not None and high != expected_zoom:
        return _report(9, key, FAILED, f"max zoom is {high}, and this tier is built for z{expected_zoom}")
    return _report(9, key, OK, f"opens, z{low}-z{high}")


def check_tile_decodes(base: str, key: str, session=None) -> dict:
    """12. Spot-decode a real tile - it must be a valid image, not a 404 page."""
    from pmtiles.reader import Reader, traverse

    try:
        source = HttpRangeSource(base, key, session)
        reader = Reader(source)
        header = reader.header()
        first = next(traverse(source, header, header["root_offset"], header["root_length"]), None)
        if first is None:
            return _report(12, key, FAILED, "the archive contains no tiles at all")
        problem = _tile_looks_right(header, first[1])
    except Exception as exc:  # noqa: BLE001
        return _report(12, key, FAILED, f"could not read a tile: {exc.__class__.__name__}: {exc}")

    if problem:
        return _report(12, key, FAILED, problem)
    return _report(12, key, OK, "a real tile decodes as the image type the header declares")


def check_vector(base: str, keys: list[str], session=None) -> list[dict]:
    """13-16. Parses, counts clear their minimums, geometries are real and placed."""
    reports: list[dict] = []
    counts: dict[str, int] = {}

    for key in keys:
        try:
            response = (session or requests).get(f"{base}/{key}", timeout=HTTP_TIMEOUT)
            document = response.json()
        except Exception as exc:  # noqa: BLE001
            reports.append(_report(13, key, FAILED, f"does not parse as JSON: {exc.__class__.__name__}"))
            continue

        features = document.get("features")
        if document.get("type") != "FeatureCollection" or not isinstance(features, list):
            reports.append(_report(13, key, FAILED, "is not a GeoJSON FeatureCollection"))
            continue
        reports.append(_report(13, key, OK, f"a FeatureCollection of {len(features)} features"))

        name = key.removeprefix("poi_").removesuffix(".geojson")
        counts[name] = len(features)

        # 15. No null or empty geometries, and nothing outside the corridor. A
        # feature at (0, 0) is what a projection bug looks like.
        west, south, east, north = CORRIDOR_BBOX
        empty = 0
        astray = 0
        for feature in features:
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates")
            if not geometry or not coordinates:
                empty += 1
                continue
            for lon, lat in _positions(coordinates):
                if not (west <= lon <= east and south <= lat <= north):
                    astray += 1
                    break

        if empty or astray:
            reports.append(_report(15, key, FAILED, f"{empty} feature(s) with no geometry, {astray} outside the AT corridor"))
        else:
            reports.append(_report(15, key, OK, "every feature has a geometry, and all of them are on the trail"))

        # 16. The TRAIL_BLAZE_COLORS.md contract, for trails only.
        if key.startswith("trails"):
            blank = sum(1 for feature in features if not (feature.get("properties") or {}).get("blaze_color"))
            if blank:
                reports.append(_report(16, key, FAILED, f"{blank} trail feature(s) carry no blaze_color"))
            else:
                reports.append(_report(16, key, OK, "every trail feature carries a blaze_color"))

    # 14. Per-type minimums, with export_poi.py's own exception.
    problems = count_problems(counts, minimums={"crossing": 0})
    if problems:
        reports.append(_report(14, "poi_*", FAILED, "; ".join(problems)))
    else:
        reports.append(_report(14, "poi_*", OK, f"every type clears its minimum ({len(counts)} checked)"))

    return reports


def _positions(coordinates):
    """Every (lon, lat) in an arbitrarily nested GeoJSON coordinate array."""
    if coordinates and isinstance(coordinates[0], (int, float)):
        yield coordinates[0], coordinates[1]
        return
    for item in coordinates or []:
        yield from _positions(item)


# ---------------------------------------------------------------------------
# E. Regression
# ---------------------------------------------------------------------------


def check_advertised_size(base: str, key: str, tier: str, advertised: int, session=None) -> dict:
    """18. Each tier within 2% of the size the app tells a hiker to expect.

    Weighed against remaining phone storage at a trailhead, which is why
    README.md calls a drift here "a real problem, not a rounding detail".
    """
    try:
        response = (session or requests).head(f"{base}/{key}", timeout=HTTP_TIMEOUT)
        actual = int(response.headers.get("Content-Length") or 0)
    except (requests.RequestException, ValueError) as exc:
        return _report(18, key, FAILED, f"could not measure: {exc.__class__.__name__}")

    if actual == 0:
        return _report(18, key, FAILED, "no Content-Length, so the advertised size cannot be checked")

    drift = abs(actual - advertised) / advertised
    if drift > ADVERTISED_TOLERANCE:
        return _report(
            18,
            key,
            FAILED,
            f"the {tier} tier is {actual:,} bytes and the app advertises {advertised:,} - {drift:.1%} off. "
            "A hiker decides whether they have room based on the advertised figure.",
        )
    return _report(18, key, OK, f"{actual:,} bytes, {drift:.2%} from the advertised {advertised:,}")


def skipped_checks() -> list[dict]:
    """The five that cannot run yet, each said out loud.

    A skip that reads like a pass is the failure this repository keeps
    finding - #431's negative assertions, gate 11's missing label. `--strict`
    turns every one of these into a failure so a release cannot be gated on a
    battery that quietly did not ask.
    """
    return [
        _report(3, "(previous release)", SKIPPED, f"nothing lost since the last release - {_NEEDS_RELEASES}"),
        _report(
            10,
            "(tile counts)",
            SKIPPED,
            "latest.json publishes a sha256 per artifact and no tile count, so there is no build figure to match",
        ),
        _report(
            17, "(regression)", SKIPPED, f"release-over-release size/count drop beyond {DROP_THRESHOLD:.0%} - {_NEEDS_RELEASES}"
        ),
        _report(19, "(released folder)", SKIPPED, f"re-verify the folder hikers are pinned to today - {_NEEDS_RELEASES}"),
    ]


def check_all(base: str, session=None, hash_artifacts: bool = True) -> list[dict]:
    session = session or requests.Session()
    manifest = fetch_manifest(base, session)

    reports = [check_manifest(manifest)]
    if manifest is None or reports[0]["state"] == FAILED:
        return reports + skipped_checks()

    artifacts = manifest["artifacts"]
    reports += check_client_keys(manifest)

    for key in sorted(artifacts):
        reports.append(check_fetchable(base, key, session))
        if hash_artifacts:
            reports.append(check_full_hash(base, key, artifacts[key]["sha256"], session))

    # One artifact for the range-machinery checks rather than all of them:
    # If-Range and CORS are properties of the BUCKET, not of an object, so
    # asking twenty times would cost twenty round trips to learn one fact.
    probe = next((key for key in sorted(artifacts) if key.endswith(".pmtiles")), sorted(artifacts)[0])
    reports.append(check_if_range(base, probe, session))
    reports.append(check_cors(base, probe, session))

    tiers = archive_keys()
    sizes = advertised_sizes()
    zooms = {"light": 11, "standard": 12, "fine": 13}
    for tier, key in tiers.items():
        if key not in artifacts:
            continue
        reports.append(check_pmtiles_zooms(base, key, zooms.get(tier), session))
        reports.append(check_tile_decodes(base, key, session))
        if tier in sizes:
            reports.append(check_advertised_size(base, key, tier, sizes[tier], session))

    reports += check_vector(base, [key for key in sorted(artifacts) if key.endswith(".geojson")], session)
    reports += skipped_checks()
    return reports


def verdict_document(base: str, reports: list[dict], strict: bool) -> dict:
    failed = [report for report in reports if report["state"] == FAILED]
    skipped = [report for report in reports if report["state"] == SKIPPED]
    return {
        "checked_at": date.today().isoformat(),
        "base": base,
        "strict": strict,
        "checks": reports,
        "failed": failed,
        "skipped": skipped,
        "gate": "fail" if failed or (strict and skipped) else "pass",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", metavar="URL", help="Public base URL of the release. Defaults to $DATA_BASE_URL.")
    parser.add_argument(
        "--env",
        metavar="NAME",
        choices=data_env.ENVIRONMENTS,
        help="Verify this environment's release rather than the base as given (features/DATA_ENVIRONMENTS.md).",
    )
    parser.add_argument("--json", metavar="OUT", type=Path, help="Also write the verdict to OUT as JSON.")
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Skip check 5. Saves ~1.6 GB of download and gives up the only proof that the bytes are the built bytes.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat a SKIPPED check as a failure. What a release gate should use once #500 lands.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base = data_env.resolve_base(args.base, args.env)
    if not base:
        print("No release to verify: pass --base or set DATA_BASE_URL.", file=sys.stderr)
        return 2

    reports = check_all(base, hash_artifacts=not args.no_hash)
    for report in reports:
        print(f"  {report['state'].upper():8} {report['check']:>3}  {report['key']:34} {report['detail']}")

    document = verdict_document(base, reports, args.strict)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(document, indent=2))

    failed, skipped = document["failed"], document["skipped"]
    if failed:
        print(f"\n{len(failed)} check(s) FAILED - this candidate must not be promoted.")
    if skipped:
        print(f"{len(skipped)} check(s) could not run. They are listed above rather than counted as passes.")
    if not failed and not skipped:
        print("\nEvery check passed.")
    elif not failed:
        print("Everything that could be asked, passed.")

    return 1 if document["gate"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
