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

ROOT = Path(__file__).parent
ATC_MANIFEST = ROOT / "data" / "raw" / "manifest.json"
TOPO_MANIFEST = ROOT / "data" / "raw" / "topo_quads" / "manifest.json"
OPENTRAIL_STATE = ROOT / "data" / "raw" / "opentrail_state.json"
ELEVATION_INDEX = ROOT / "data" / "raw" / "elevation" / "tile_index.json"

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
    """Re-run the same TNM discovery the index was built from and compare the
    edition set. This is the only way to notice 3DEP republishing a cell:
    there is no per-file timestamp to HEAD, but a new survey arrives as a new
    dated filename.

    `recorded` is the marker to restrict the answer to. It defaults to reading
    the local tile index, which is the only source that exists when this runs
    beside a real fetch; a run comparing against a *published* state has no
    local index and passes that state's marker in instead."""
    try:
        import fetch_elevation

        cells = fetch_elevation.compute_grid_cells()
        items: list[dict] = []
        for cell in cells:
            items.extend(fetch_elevation.list_products_for_cell(cell))

        # Deduplicate exactly the way the index was built - newest edition per
        # footprint. Comparing the raw catalog (244 rows) against the deduped
        # index (110) would report STALE forever, which is the same failure as
        # reporting FRESH wrongly: an alarm that is always on gets ignored.
        index = fetch_elevation.build_tile_index(items, corridor_hit=lambda _bbox: True)

        # Restrict to the cells the recorded index already covers. The
        # upstream query is per 1-degree cell and is NOT corridor-clipped
        # here (that needs the corridor polygon and a DuckDB spatial
        # connection), so it returns tiles the index legitimately excluded -
        # comparing the raw sets would report STALE forever, and an alarm
        # that is always on gets ignored.
        #
        # Limitation, stated rather than hidden: this notices a NEW EDITION of
        # a cell we already track, not a brand-new cell entering the corridor.
        # The corridor is fixed, so that second case only arises if 3DEP
        # starts publishing somewhere it never has - rare, and caught by a
        # full fetch_elevation.py run.
        if recorded is None:
            recorded = recorded_elevation_marker()
        if recorded is None:
            return None
        tracked_cells = {key.split(":", 1)[0] for key in recorded.split("|")}

        keys = {edition_key(entry["url"]) for entry in index if edition_key(entry["url"]).split(":", 1)[0] in tracked_cells}
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
