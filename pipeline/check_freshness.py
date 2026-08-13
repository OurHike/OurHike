"""Answer "does any upstream data need refetching?" without doing the work.

Every fetcher here already skips unchanged data, but each only discovers that
*while fetching*. There was no way to ask the question cheaply - and the work
is now genuinely expensive: a full elevation export streams from 110 remote
DEM tiles for ~25 minutes, and a background rebuild re-tiles the whole
2,190-mile corridor.

These sources also move slowly. ATC layers change a few times a year; USGS
topo quads and 3DEP elevation are re-flown on multi-year cycles. So "nothing
changed" is the usual answer, and finding that out should cost a handful of
metadata requests rather than a re-download.

Each upstream exposes a different freshness marker, so this normalises them:

    ATC layers    ArcGIS `editingInfo.dataLastEditDate` (epoch ms)
    Topo quads    S3 `Last-Modified` per quad
    opentrail     HTTP ETag
    Elevation     the set of edition dates TNM currently publishes, since
                  3DEP has no per-file timestamp worth trusting but does
                  embed an edition date in every filename
    ATC updates   HTTP ETag on ATC's trail-updates feed, compared against
                  what a human recorded in reference/atc_updates.json when
                  they last reviewed it (#459)

The fifth one is the odd one and worth reading the difference off: the other
four say *the pipeline should refetch*, and it says *a person should go and
look*. Nothing fetches ATC's Trail Updates on a schedule - they are prose on
a website, reviewed into a file in git and released by a merged pull request
(features/ATC_TRAIL_UPDATES.md) - so no automated run can clear a STALE here.
Its recorded side is therefore in git rather than in gitignored `data/raw/`,
which also means it is the one source this check can answer from a bare
checkout.

THE FAILURE THAT MATTERS is a false "fresh". Reporting stale data as current
means the map quietly keeps showing a closed trail or a moved shelter, so
anything this cannot verify reports UNKNOWN and exits non-zero rather than
being rounded down to fine. Silence about a source nobody could check is
exactly how stale data survives.

    .venv/Scripts/python check_freshness.py

The *recorded* side lives in lib/freshness_state.py, so that this check can
run somewhere other than the machine that did the fetching:

    check_freshness.py                     compare against local data/raw/*
    check_freshness.py --state URL|PATH    compare against a published capture
    check_freshness.py --capture OUT       write this checkout's state, ask
                                           nothing upstream
    check_freshness.py --json OUT          also write the verdict as JSON
    check_freshness.py --exit-zero         report; never fail on staleness

`--state` is what makes a scheduled run possible at all: `data/raw/` is
gitignored, so a fresh checkout would otherwise report every source STALE for
the trivial reason that it has never fetched anything. A build captures its
state and publishes it; the scheduled check reads that over plain HTTPS and
needs no credentials to do it.

`--exit-zero` exists because this module has two callers wanting opposite
things from the same verdict. As a pre-build gate, exiting non-zero on
stale-or-unknown is right - that is the gate doing its job. As a scheduled
reporter it is wrong: staleness is the *normal* state between weekly builds,
and a red X every single day for a legitimately-changed upstream trains
people to ignore the one signal that matters. See pipeline/DATA_RELEASES.md.
"""

import argparse
import json
import random
import re
import sys
from datetime import date
from pathlib import Path

import requests

from lib import freshness_state
from lib.freshness_state import (
    Freshness,
    StateUnavailable,
    capture_state,
    compare_marker,
    compare_state,
    edition_key,
    load_state,
    state_age_days,
    summarise,
)
from lib.source_registry import find_source, load_registry

ROOT = Path(__file__).parent
ATC_MANIFEST = ROOT / "data" / "raw" / "manifest.json"
TOPO_MANIFEST = ROOT / "data" / "raw" / "topo_quads" / "manifest.json"
OPENTRAIL_STATE = ROOT / "data" / "raw" / "opentrail_state.json"
ELEVATION_INDEX = ROOT / "data" / "raw" / "elevation" / "tile_index.json"

# The one recorded marker that is checked in rather than fetched - see the
# module docstring's fifth row. `data/raw/` is gitignored; this is not.
ATC_UPDATES_FILE = ROOT / "reference" / "atc_updates.json"
SOURCES_PATH = ROOT / "sources.json"

OPENTRAIL_URL = "https://opentrail.org/api/getData?trail=AT"
HTTP_TIMEOUT = 30

# How many topo quads to spot-check. All 1,654 would mean 1,654 HEAD requests
# for a dataset that is re-published as a batch, so a sample is enough to
# notice a new release - and a sample that finds nothing is reported as a
# sample, not as proof the whole set is current. See topo_sample() for how
# the sample is actually chosen - it must not be a flat alphabetical slice
# (see that function's docstring for the state-bias bug that was).
TOPO_SAMPLE_SIZE = 25

# Re-exported rather than redefined. These moved to lib/freshness_state.py so
# a build could capture state without importing the whole checking machinery,
# but this module is still where callers and tests reach for them.
__all__ = [
    "Freshness",
    "compare_marker",
    "summarise",
    "edition_key",
    "check_all",
    "recorded_state",
]


# --- Recorded markers ------------------------------------------------------
#
# Thin wrappers over lib/freshness_state.py that bind the module-level paths
# above. The paths stay module attributes, read at call time, so a test can
# point any single source at a nonexistent file and exercise the others.


def recorded_state() -> dict:
    """This checkout's recorded markers for every source."""
    return capture_state(
        atc_manifest=ATC_MANIFEST,
        opentrail_state=OPENTRAIL_STATE,
        topo_manifest=TOPO_MANIFEST,
        elevation_index=ELEVATION_INDEX,
        atc_updates_file=ATC_UPDATES_FILE,
    )


def recorded_atc_markers() -> dict[str, str | None]:
    """Every layer currently in the ATC manifest, keyed by source key, to
    its recorded edit-date marker - or None if fetch_all.py recorded the
    layer without one. See lib/freshness_state.atc_sources for why a null
    marker is kept rather than filtered out."""
    return {key: entry["marker"] for key, entry in freshness_state.atc_sources(ATC_MANIFEST).items()}


def recorded_opentrail_marker() -> str | None:
    return freshness_state.opentrail_marker(OPENTRAIL_STATE)


def recorded_elevation_marker() -> str | None:
    """Which tile editions the current index pinned, order-independent.

    TNM returns tiles in no guaranteed order, so a reshuffle must not read as
    a change - only a genuinely new edition should.
    """
    return freshness_state.elevation_marker(ELEVATION_INDEX)


def recorded_atc_updates_marker() -> str | None:
    return freshness_state.atc_updates_marker(ATC_UPDATES_FILE)


# --- Upstream markers ------------------------------------------------------


def upstream_atc_marker(url: str) -> str | None:
    """One cheap metadata request per layer - the same field fetch_all.py
    compares, asked without pulling any features."""
    try:
        response = requests.get(f"{url}?f=json", timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        edit = response.json().get("editingInfo", {}).get("dataLastEditDate")
        return None if edit is None else str(edit)
    except (requests.RequestException, ValueError):
        return None


def upstream_opentrail_marker() -> str | None:
    try:
        response = requests.head(OPENTRAIL_URL, timeout=HTTP_TIMEOUT)
        return response.headers.get("ETag")
    except requests.RequestException:
        return None


def atc_updates_feed_url() -> str | None:
    """Where to ask about ATC's Trail Updates, from sources.json.

    Read from the registry rather than written here, which is the point of
    registering the source at all (#459): the URL, the licence and the trust
    tier are one entry a person can read, not three facts scattered across
    the scripts that happen to use them. A registry that cannot be reached or
    has no such entry answers None, which the caller turns into UNKNOWN.
    """
    try:
        registry = load_registry(SOURCES_PATH)
    except (OSError, ValueError):
        return None
    entry = find_source(registry, "atc_trail_updates") or {}
    return (entry.get("freshness") or {}).get("url")


def upstream_atc_updates_marker(url: str | None = None) -> str | None:
    """The ETag on ATC's trail-updates feed, or None if it cannot be had.

    HEAD, and the feed rather than the listing page, for two measured
    reasons. The feed answers a HEAD with the same strong ETag it puts on a
    GET, so the change signal costs no body at all. The listing page answers
    a scripted request with 403 (measured 2026-08-12), so asking it would
    report UNKNOWN forever - which is the honest verdict for "could not ask",
    and exactly why it is not the thing to ask.

    Using the feed here is not the mistake features/ATC_TRAIL_UPDATES.md
    warns about. That warning is about *content*: the feed held 3 items while
    the page showed 9, so building the artifact from it would silently drop
    the closures that matter most. As a "did anything move?" signal it is
    fine, and the design names it as exactly that.
    """
    url = url or atc_updates_feed_url()
    if not url:
        return None
    try:
        response = requests.head(url, timeout=HTTP_TIMEOUT)
        return response.headers.get("ETag")
    except requests.RequestException:
        return None


def topo_quad_state(url: str) -> str:
    """The state-code path segment of a topo-quad manifest key.

    Manifest keys are full S3 URLs of the form `.../GeoTIFF/<STATE>/<file>`
    (see fetch_topo_quads.py's BUCKET_URL/GEOTIFF_PREFIX/<state>/<filename>
    construction) - the state is always the segment immediately before the
    filename, regardless of how deep the prefix in front of it is.
    """
    parts = url.rsplit("/", 2)
    return parts[-2] if len(parts) >= 2 else url


def topo_sample(manifest: dict, size: int | None = None, seed: str | None = None) -> list[str]:
    """`size` quad URLs to spot-check upstream, spread across states rather
    than a flat alphabetical slice.

    `sorted(manifest)[:size]` (the old implementation) sorts full S3 URLs,
    which sorts by state code before anything else in the path - so a flat
    slice is always the same alphabetically-first state's quads, every run,
    forever (verified against the real manifest: 100% Connecticut, out of
    15 registered states, while 2 of the 3 known-corrupted quads live in
    VA/WV - states a flat sorted slice could never reach). A real USGS
    release to any of the other 14 states was permanently invisible to this
    check, no matter how many times it ran.

    Fixed two ways, both stateless (no persisted cursor file needed):
    quads are grouped by state and round-robin picked, so one run's sample
    spans every state rather than one; and both the state visiting order
    and which quads are picked within each state are seeded from `seed`
    (today's date by default), so a manifest with more states than `size`,
    or a state with more quads than its round-robin share, gets different
    coverage on different days rather than the same slice forever.

    `size` defaults via a None sentinel rather than `=TOPO_SAMPLE_SIZE`
    directly in the signature - a plain default is bound once at import
    time, so monkeypatch.setattr(module, "TOPO_SAMPLE_SIZE", ...) in a test
    would silently stop taking effect on this parameter.
    """
    if size is None:
        size = TOPO_SAMPLE_SIZE
    if seed is None:
        seed = date.today().isoformat()

    by_state: dict[str, list[str]] = {}
    for key in manifest:
        by_state.setdefault(topo_quad_state(key), []).append(key)

    states = sorted(by_state)
    random.Random(seed).shuffle(states)
    for state in states:
        keys = by_state[state]
        keys.sort()
        random.Random(f"{seed}:{state}").shuffle(keys)

    sample: list[str] = []
    round_index = 0
    while len(sample) < size and any(by_state[s] for s in states):
        state = states[round_index % len(states)]
        if by_state[state]:
            sample.append(by_state[state].pop())
        round_index += 1

    return sample


def upstream_topo_markers(sample: list[str]) -> dict[str, str | None]:
    """S3 Last-Modified for a sample of quads. Sampled rather than exhaustive
    because 1,654 HEAD requests is a lot of traffic for a dataset USGS
    republishes in batches - a new release shows up in any sample."""
    markers: dict[str, str | None] = {}
    for url in sample:
        try:
            response = requests.head(url, timeout=HTTP_TIMEOUT)
            markers[url] = response.headers.get("Last-Modified")
        except requests.RequestException:
            markers[url] = None
    return markers


def upstream_elevation_marker(recorded: str | None = None) -> str | None:
    """HEAD each tracked 3DEP cell and read its `Last-Modified`.

    This is the only way to notice 3DEP republishing a cell, and the mechanism
    changed under it (#550). It used to re-run the TNM catalogue query,
    because a republished cell arrived as a new DATED FILENAME and there was
    no per-file timestamp to ask for. Reading `current/` there is: the name is
    stable and the header is what moves.

    That is a better question as well as a cheaper one. The old path asked a
    gateway that gives up at 30 seconds, then had to dedupe 244 rows down to
    110 and clip the answer to the cells already tracked - because the query
    was per 1-degree cell and not corridor-clipped, so comparing the raw sets
    reported STALE forever. None of that applies to one HEAD per cell.

    `recorded` is the marker whose cells are asked about. It defaults to
    reading the local tile index, which is the only source that exists when
    this runs beside a real fetch; a run comparing against a *published* state
    has no local index and passes that state's marker in instead.

    Limitation, stated rather than hidden and unchanged from before: this
    notices a new edition of a cell already tracked, not a brand-new cell
    entering the corridor. The corridor is fixed, so that only arises if 3DEP
    starts publishing where it never has - rare, and caught by a full
    fetch_elevation.py run.

    One consequence worth expecting rather than debugging: **the first
    comparison after this change reads STALE**, once, for every state captured
    while the marker was still a set of filename dates. The two shapes are not
    comparable, and the honest report for "the version scheme changed" is not
    FRESH.
    """
    try:
        import fetch_elevation

        if recorded is None:
            recorded = recorded_elevation_marker()
        if recorded is None:
            return None

        tracked_cells = sorted({key.split(":", 1)[0] for key in recorded.split("|")})
        keys = set()
        for cell in tracked_cells:
            # Only cells whose name is one this bucket could hold. A legacy
            # marker's keys are whole filenames where the name did not parse,
            # and asking S3 about those would be a guaranteed 404 read as a
            # coverage loss.
            if not re.fullmatch(r"n\d+w\d+", cell):
                continue
            last_modified = fetch_elevation._head(fetch_elevation.cell_url(cell))
            if last_modified is None:
                continue
            keys.add(edition_key(fetch_elevation.cell_url(cell), last_modified))
        return "|".join(sorted(keys)) if keys else None
    except Exception:
        return None


def gather_upstream(state: dict, *, local: bool = True) -> dict:
    """Ask every upstream what it says now, shaped like the recorded state.

    Deliberately sparser than `state` in two places, both of which
    `compare_state` reads as "not checked", never as "current":

    - An ATC layer with no recorded marker is not asked about at all. There
      would be nothing to compare the answer to, and the request would cost a
      round trip to learn nothing.
    - Only a sample of topo quads is asked about. 1,654 HEAD requests is a lot
      of traffic for a dataset USGS republishes in batches, and a new release
      shows up in any sample.
    - A source the state does not mention at all is not asked about either.
      There is nothing to compare an answer to, and `compare_state` already
      reports it as unchecked.
    """
    upstream: dict = {"atc": {}, "topo_quads": {}}

    for key, entry in (state.get("atc") or {}).items():
        marker = entry.get("marker") if isinstance(entry, dict) else entry
        url = entry.get("url") if isinstance(entry, dict) else None
        if marker is None or not url:
            continue
        upstream["atc"][key] = upstream_atc_marker(url)

    if "opentrail" in state:
        upstream["opentrail"] = upstream_opentrail_marker()

    recorded_topo = state.get("topo_quads") or {}
    if recorded_topo:
        upstream["topo_quads"] = upstream_topo_markers(topo_sample(recorded_topo))

    if "elevation" in state:
        # Called with no arguments on the local path, exactly as it always was,
        # so that it reads the tile index itself. A published state has no local
        # index to read, so its recorded marker is handed in instead.
        upstream["elevation"] = upstream_elevation_marker() if local else upstream_elevation_marker(state.get("elevation"))

    if "atc_trail_updates" in state:
        upstream["atc_trail_updates"] = upstream_atc_updates_marker()

    return upstream


def check_all(state: dict | None = None) -> list[dict]:
    """Every source's verdict. Never raises: a source that cannot be checked
    reports UNKNOWN rather than taking the whole run down with it.

    `state` is the recorded side to compare against, defaulting to whatever
    this checkout's own `data/raw/` records."""
    local = state is None
    if state is None:
        state = recorded_state()
    return compare_state(state, gather_upstream(state, local=local))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--state",
        metavar="PATH|URL",
        help="Compare against a published capture instead of this checkout's data/raw/.",
    )
    parser.add_argument(
        "--capture",
        metavar="OUT",
        type=Path,
        help="Write this checkout's recorded state to OUT and exit. Asks nothing upstream.",
    )
    parser.add_argument("--json", metavar="OUT", type=Path, help="Also write the verdict to OUT as JSON.")
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="Exit 0 even when something is stale or unknown. For a reporter rather than a gate.",
    )
    return parser.parse_args(argv)


def verdict_document(reports: list[dict], state: dict | None) -> dict:
    """The whole answer as plain JSON, for a workflow to render or a later
    build to read.

    Carries the age of the state it compared against, because "fresh" against
    a six-month-old capture is a different sentence from the one a reader
    assumes, and a number nobody printed is a number nobody checked.
    """
    summary = summarise(reports)

    sources = []
    for report in reports:
        entry = {
            "source": report["source"],
            "freshness": report["freshness"].value,
            "detail": report["detail"],
        }
        # Which ATC layers moved, when the comparison knows. Naming them is
        # the difference between "refetch something" and "refetch this".
        if report.get("changed"):
            entry["changed"] = report["changed"]
        sources.append(entry)

    return {
        "checked_at": date.today().isoformat(),
        "state_captured_at": (state or {}).get("captured_at"),
        "state_age_days": state_age_days(state) if state else None,
        "sources": sources,
        "needs_refetch": summary["needs_refetch"],
        "unknown": summary["unknown"],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.capture:
        # Sources this checkout holds no record of are dropped rather than
        # published as empty - see lib/freshness_state.drop_unrecorded. The
        # vector and raster halves of the pipeline are separate workflows, and
        # a state must not claim a verdict about a leg that never ran.
        state = freshness_state.drop_unrecorded(recorded_state())
        captured = [name for name in freshness_state.SOURCES if name in state]
        args.capture.parent.mkdir(parents=True, exist_ok=True)
        args.capture.write_text(json.dumps(state, indent=2))
        print(f"Captured {', '.join(captured) or 'nothing'} to {args.capture}")
        return 0

    state: dict | None = None
    if args.state:
        try:
            state = load_state(args.state)
        except StateUnavailable as exc:
            # Not a verdict about the data - the absence of one. Reported as
            # its own outcome (exit 2) so a caller can tell "there is nothing
            # published to compare against yet" apart from "an upstream
            # changed", which is exactly the distinction a scheduled reporter
            # needs to avoid crying wolf on a bucket that has never published.
            print(f"No state to compare against: {exc}", file=sys.stderr)
            return 2

    reports = check_all(state)
    for report in reports:
        print(f"  {report['freshness'].value.upper():8} {report['source']:12} {report['detail']}")

    if state is not None:
        age = state_age_days(state)
        captured = state.get("captured_at") or "an unrecorded date"
        print(f"\nCompared against a state captured {captured}" + (f" ({age} days ago)" if age is not None else ""))

    summary = summarise(reports)
    if summary["needs_refetch"]:
        print(f"\nNeeds refetch: {', '.join(summary['needs_refetch'])}")
    if summary["unknown"]:
        print(f"Could not check: {', '.join(summary['unknown'])} - treat as unverified, not current.")
    if summary["exit_code"] == 0:
        print("\nEverything upstream is unchanged. No refetch or reprocessing needed.")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(verdict_document(reports, state), indent=2))

    return 0 if args.exit_zero else summary["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
