"""Ask, as a browser would, whether a hiker can still download the map.

[pipeline/DATA_RELEASES.md](DATA_RELEASES.md) §3a is the design;
[.github/expected-origins.yml](../.github/expected-origins.yml) is the contract
this enforces. This is tier 1 of #431.

WHY THIS EXISTS, AND WHY NOTHING ELSE CAUGHT IT

The R2 bucket's CORS allow-list lost `https://ourhike.github.io`. Every data
fetch from production was refused by the browser, so the deployed app drew a
topo sheet with no Appalachian Trail on it, for eight days, while the published
data was correct throughout.

Every check stayed green because none of them is a browser. `check_freshness.py`
asks whether upstream *data* moved. `r2-credentials-check.yml` asks whether a
token still works. Both are right, and both send no `Origin` header - so the
bucket answered them perfectly while refusing every real device. A ranged GET
with no `Origin` returned 206 with `Content-Range`, `ETag` and `Accept-Ranges`
intact the whole time.

**`Origin` is the entire difference.** This check sends one, for every declared
origin, and asserts the bucket answers with a matching
`Access-Control-Allow-Origin`. That single header would have caught #427 on the
first run after the policy changed.

IT MUST NOT DOWNLOAD THE ARTIFACTS

`HEAD` and one-byte range requests answer every question here. Pulling the real
files would be ~1.6 GB of egress a day against a rate-limited `r2.dev`
subdomain, to learn what a one-byte request already said - the wrong trade for
a project whose eighth value is being cheap to run, and #395 is about putting a
ceiling on the bill. Proving the *bytes* are right is `verify_release.py`'s
job (check 5), at release time, once.

WHAT IT CANNOT CHECK, STATED RATHER THAN IMPLIED

`latest.json` publishes a sha256 per artifact and no size. So "exists at its
published size" - the phrasing #431 uses - is not available to ask: this
asserts each artifact answers `HEAD` with a `Content-Length` and
`Accept-Ranges: bytes`, which is what makes it fetchable and resumable, not
that it is the length anyone intended. A truncated-but-served artifact is
caught by the client's own per-chunk hashing (`client/src/lib/sha256.ts`) and
by `verify_release.py`, not here.

This is also not a release gate. `verify_release.py` verifies a staged release
before promotion; this watches a *good* release quietly stop being reachable,
days later, on nobody's schedule. Both are needed and they are different
checks.

    python check_deployment.py --base https://data.example.org
    python check_deployment.py --print-cors-policy
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent
ORIGINS_MANIFEST = ROOT.parent / ".github" / "expected-origins.yml"

MANIFEST_KEY = "latest.json"

HTTP_TIMEOUT = 30

# The verdict for one assertion. `ok` is the only passing value; everything
# else is a sentence a human reads in a tracking issue at 6am.
OK = "ok"
FAILED = "failed"
# Distinct from `failed` on purpose. A request that never completed says
# nothing about the CORS policy - it may be the bucket, the network, or
# Cloudflare having a moment - and #431 is explicit that a flaky third party
# must not be able to declare an outage. These are reported and, unlike a real
# refusal, do not on their own open the tracking issue.
UNREACHABLE = "unreachable"


def load_manifest(path: Path | None = None) -> dict:
    """The declared origins and CORS contract."""
    return yaml.safe_load((path or ORIGINS_MANIFEST).read_text())


def cors_policy(manifest: dict) -> list[dict]:
    """The policy to paste into Cloudflare, generated from the declaration.

    Generated rather than stored because a stored copy is a second home for
    the same fact, and the first one drifted: LAUNCH_CHECKLIST.md's embedded
    JSON carried `if-match`, which nothing sends, and not `if-range`, which
    every resume sends. `--print-cors-policy` is what the maintainer pastes,
    so the bucket and this check are configured from one source.
    """
    return [
        {
            "AllowedOrigins": [origin["pattern"] for origin in manifest["origins"]],
            "AllowedMethods": list(manifest["methods"]),
            "AllowedHeaders": list(manifest["request_headers"]),
            "ExposeHeaders": list(manifest["expose_headers"]),
            "MaxAgeSeconds": manifest["max_age_seconds"],
        }
    ]


def _header_list(value: str | None) -> set[str]:
    """A comma-separated header value as a lowercased set.

    Case-folded because header *values* here are header *names*, which are
    case-insensitive - a bucket answering `ETag` rather than `etag` is
    correct, and failing it would be this check inventing a rule.
    """
    if not value:
        return set()
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def check_origin_allowed(base: str, origin: dict, session: requests.Session | None = None) -> dict:
    """Does the bucket let a browser on this origin read `latest.json`?

    The whole outage, in one assertion. A wildcard pattern is probed with a
    concrete hostname it is supposed to match, because `*` is not something a
    browser would ever send and a rule that covers no real hostname covers
    nothing.

    `*` is accepted as an answer as well as an exact echo: it is a legal way
    to allow everyone, and refusing it would be this check enforcing a
    tightening nobody asked for.
    """
    getter = (session or requests).get
    probe = origin["probe"]
    try:
        response = getter(
            f"{base}/{MANIFEST_KEY}",
            headers={"Origin": probe},
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        return {
            "check": "origin",
            "origin": origin["pattern"],
            "state": UNREACHABLE,
            "detail": f"could not ask: {exc.__class__.__name__}",
        }

    allowed = response.headers.get("Access-Control-Allow-Origin")
    if allowed is not None and (allowed == "*" or allowed.rstrip("/") == probe.rstrip("/")):
        return {"check": "origin", "origin": origin["pattern"], "state": OK, "detail": f"allowed as {allowed}"}

    return {
        "check": "origin",
        "origin": origin["pattern"],
        "state": FAILED,
        "detail": (
            f"a browser on {probe} may not read this bucket - "
            + (f"Access-Control-Allow-Origin was {allowed!r}" if allowed else "no Access-Control-Allow-Origin at all")
            + ". Add the origin to the bucket's CORS policy; "
            "`check_deployment.py --print-cors-policy` prints what to paste."
        ),
    }


def check_preflight(base: str, origin: dict, request_headers: list[str], session: requests.Session | None = None) -> dict:
    """Would the browser's preflight for a RESUME succeed?

    `range` is CORS-safelisted for simple byte ranges, so a first download
    needs no preflight and works even against a wrong policy. `if-range` is
    not safelisted, and the client sends it on every resume - so this is the
    assertion that separates "downloads work" from "resumes work", and the
    second one only ever fails on a phone, mid-download, in a place with bad
    signal.
    """
    options = (session or requests).options
    probe = origin["probe"]
    asked = ", ".join(request_headers)
    try:
        response = options(
            f"{base}/{MANIFEST_KEY}",
            headers={
                "Origin": probe,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": asked,
            },
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        return {
            "check": "preflight",
            "origin": origin["pattern"],
            "state": UNREACHABLE,
            "detail": f"could not ask: {exc.__class__.__name__}",
        }

    allowed = _header_list(response.headers.get("Access-Control-Allow-Headers"))
    missing = sorted({header.lower() for header in request_headers} - allowed)
    if not missing:
        return {"check": "preflight", "origin": origin["pattern"], "state": OK, "detail": f"may send {asked}"}

    return {
        "check": "preflight",
        "origin": origin["pattern"],
        "state": FAILED,
        "detail": (
            f"a browser on {probe} may not send {', '.join(missing)}. "
            + (
                "`if-range` is what every RESUMED archive download sends, so this breaks resuming a "
                "1.18 GB download rather than starting one - invisible until it matters most. "
                if "if-range" in missing
                else ""
            )
            + "Add it to the bucket's AllowedHeaders."
        ),
    }


def check_exposed_headers(base: str, origin: dict, expose_headers: list[str], session: requests.Session | None = None) -> dict:
    """Can a browser READ the headers the download machinery depends on?

    Present and readable are different things, and the difference is invisible
    to curl: R2 sent all four of these throughout the outage. The resumable
    download reads `content-range` to decide whether a range was honoured, and
    a missing one means "start over" rather than a corrupted file.
    """
    getter = (session or requests).get
    probe = origin["probe"]
    try:
        response = getter(
            f"{base}/{MANIFEST_KEY}",
            headers={"Origin": probe},
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        return {
            "check": "expose-headers",
            "origin": origin["pattern"],
            "state": UNREACHABLE,
            "detail": f"could not ask: {exc.__class__.__name__}",
        }

    exposed = _header_list(response.headers.get("Access-Control-Expose-Headers"))
    missing = sorted({header.lower() for header in expose_headers} - exposed)
    if not missing:
        return {"check": "expose-headers", "origin": origin["pattern"], "state": OK, "detail": "all readable"}

    return {
        "check": "expose-headers",
        "origin": origin["pattern"],
        "state": FAILED,
        "detail": (
            f"a browser on {probe} cannot read {', '.join(missing)}. "
            "These are sent either way, so curl sees them and a browser does not - "
            "add them to the bucket's ExposeHeaders."
        ),
    }


def check_range_request(base: str, key: str, session: requests.Session | None = None) -> dict:
    """Is a range request still honoured?

    One byte, because the answer is in the status line and `Content-Range`,
    not in the payload. A 200 here means the server ignored the range and is
    sending the whole object - which for a 1.18 GB archive on a phone is the
    difference between resuming and starting again.
    """
    getter = (session or requests).get
    try:
        response = getter(f"{base}/{key}", headers={"Range": "bytes=0-0"}, timeout=HTTP_TIMEOUT)
    except requests.RequestException as exc:
        return {"check": "range", "key": key, "state": UNREACHABLE, "detail": f"could not ask: {exc.__class__.__name__}"}

    if response.status_code == 206 and response.headers.get("Content-Range"):
        return {"check": "range", "key": key, "state": OK, "detail": response.headers["Content-Range"]}

    return {
        "check": "range",
        "key": key,
        "state": FAILED,
        "detail": (
            f"a one-byte range answered {response.status_code} "
            f"with Content-Range {response.headers.get('Content-Range')!r}. "
            "A resumable download cannot resume against this."
        ),
    }


def check_artifact_present(base: str, key: str, session: requests.Session | None = None) -> dict:
    """Is the object `latest.json` names actually there and fetchable?

    Catches the deletion, the lifecycle rule and the permissions change - the
    ways a good release stops being reachable without anybody publishing
    anything. `Accept-Ranges` is asserted because an artifact that cannot be
    ranged cannot be resumed, and the archives are large enough that resuming
    is the normal case rather than the exception.
    """
    head = (session or requests).head
    try:
        response = head(f"{base}/{key}", timeout=HTTP_TIMEOUT)
    except requests.RequestException as exc:
        return {"check": "artifact", "key": key, "state": UNREACHABLE, "detail": f"could not ask: {exc.__class__.__name__}"}

    if response.status_code != 200:
        return {"check": "artifact", "key": key, "state": FAILED, "detail": f"HEAD answered {response.status_code}"}

    length = response.headers.get("Content-Length")
    if not length or not length.isdigit() or int(length) == 0:
        return {"check": "artifact", "key": key, "state": FAILED, "detail": f"Content-Length was {length!r}"}

    if response.headers.get("Accept-Ranges", "").lower() != "bytes":
        return {
            "check": "artifact",
            "key": key,
            "state": FAILED,
            "detail": f"Accept-Ranges was {response.headers.get('Accept-Ranges')!r}, so this cannot be resumed",
        }

    return {"check": "artifact", "key": key, "state": OK, "detail": f"{int(length)} bytes"}


def fetch_published_manifest(base: str, session: requests.Session | None = None) -> dict | None:
    """`latest.json`, or None if there is not one to read.

    None is not a verdict about the deployment - it is the absence of one, and
    the caller reports it as such. A bucket that has never published is the
    state this repository is in until LAUNCH_CHECKLIST.md step 1.6 runs, and
    failing daily until then is how an alarm gets muted.
    """
    getter = (session or requests).get
    try:
        response = getter(f"{base}/{MANIFEST_KEY}", timeout=HTTP_TIMEOUT)
        if response.status_code != 200:
            return None
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def check_all(base: str, manifest: dict | None = None, session: requests.Session | None = None) -> list[dict]:
    """Every assertion, against a live bucket. Never raises.

    A check that takes the whole run down on one bad response is a check that
    reports nothing about the other twelve, so each returns its own verdict
    and the caller decides what the set of them means.
    """
    manifest = manifest or load_manifest()
    base = base.rstrip("/")

    reports: list[dict] = []
    for origin in manifest["origins"]:
        reports.append(check_origin_allowed(base, origin, session))
        reports.append(check_preflight(base, origin, manifest["request_headers"], session))
        reports.append(check_exposed_headers(base, origin, manifest["expose_headers"], session))

    published = fetch_published_manifest(base, session)
    if published is None:
        return reports

    artifacts = sorted((published.get("artifacts") or {}).keys())
    for key in artifacts:
        reports.append(check_artifact_present(base, key, session))

    # One range request, not one per artifact. Range support is a property of
    # the bucket rather than of an object, so asking thirteen times would cost
    # thirteen round trips to learn the same fact - and the archives are the
    # only things large enough for it to matter, so the check is aimed at one
    # of those where possible.
    rangeable = next((key for key in artifacts if key.endswith(".pmtiles")), None)
    reports.append(check_range_request(base, rangeable or MANIFEST_KEY, session))

    return reports


def hiker_facing_failures(reports: list[dict], manifest: dict) -> list[dict]:
    """The failures that mean a hiker cannot get the map.

    #431's rule: fail on "a browser cannot get the map", never on "a tile host
    was slow". A preview origin losing CORS costs a reviewer a preview; the
    production origin losing it is the outage. Artifact and range checks are
    hiker-facing by construction - there is no such thing as an artifact only
    a developer downloads.
    """
    hiker_facing = {origin["pattern"] for origin in manifest["origins"] if origin.get("hiker_facing")}
    return [
        report for report in reports if report["state"] == FAILED and ("origin" not in report or report["origin"] in hiker_facing)
    ]


def verdict_document(base: str, reports: list[dict], manifest: dict, published: bool) -> dict:
    """The whole answer as plain JSON, for the workflow to render and for the
    status page (#431 tier 2) to read once it exists."""
    return {
        "checked_at": date.today().isoformat(),
        "base": base,
        "published": published,
        "checks": reports,
        "failed": [report for report in reports if report["state"] == FAILED],
        "unreachable": [report for report in reports if report["state"] == UNREACHABLE],
        "hiker_facing_failures": hiker_facing_failures(reports, manifest),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", metavar="URL", help="Public bucket base to check. Defaults to $DATA_BASE_URL.")
    parser.add_argument("--json", metavar="OUT", type=Path, help="Also write the verdict to OUT as JSON.")
    parser.add_argument(
        "--origins",
        metavar="PATH",
        type=Path,
        help="Origins manifest to read. Defaults to .github/expected-origins.yml.",
    )
    parser.add_argument(
        "--print-cors-policy",
        action="store_true",
        help="Print the bucket CORS policy this file implies, to paste into Cloudflare. Asks nothing.",
    )
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="Exit 0 even when something failed. For a reporter rather than a gate.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = load_manifest(args.origins)

    if args.print_cors_policy:
        print(json.dumps(cors_policy(manifest), indent=2))
        return 0

    base = (args.base or os.environ.get("DATA_BASE_URL", "")).strip().rstrip("/")
    if not base:
        print("No bucket to check: pass --base or set DATA_BASE_URL.", file=sys.stderr)
        return 2

    reports = check_all(base, manifest)
    published = any(report["check"] == "artifact" for report in reports)

    for report in reports:
        subject = report.get("origin") or report.get("key") or ""
        print(f"  {report['state'].upper():12} {report['check']:15} {subject:45} {report['detail']}")

    if not published:
        print(f"\nNothing is published at {base} yet, so only the CORS contract could be checked.")

    document = verdict_document(base, reports, manifest, published)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(document, indent=2))

    failed = document["failed"]
    unreachable = document["unreachable"]
    if failed:
        print(f"\n{len(failed)} check(s) failed; {len(document['hiker_facing_failures'])} of them stop a hiker.")
    if unreachable:
        print(f"{len(unreachable)} check(s) could not be made at all - reported, not counted as a refusal.")
    if not failed and not unreachable:
        print("\nA browser can still download the map from every declared origin.")

    if args.exit_zero:
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
