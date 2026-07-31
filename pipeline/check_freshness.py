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
"""

import json
import random
import re
import sys
from datetime import date
from enum import Enum
from pathlib import Path

import requests

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


class Freshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


def compare_marker(recorded, upstream) -> Freshness:
    """One source's verdict.

    Compared as strings so a JSON round trip cannot manufacture a difference:
    ArcGIS hands back an epoch-millisecond int, S3 an HTTP date string, and
    `json.load` will happily give back either type.
    """
    if upstream is None:
        # Could not ask. Never fresh - see the module docstring.
        return Freshness.UNKNOWN
    if recorded is None:
        return Freshness.STALE
    return Freshness.FRESH if str(recorded) == str(upstream) else Freshness.STALE


def summarise(reports: list[dict]) -> dict:
    """Roll per-source verdicts into one answer plus a process exit code.

    STALE and UNKNOWN are kept apart because they call for different
    responses - refetch versus retry - and merging them would hide which one
    happened.
    """
    stale = [r["source"] for r in reports if r["freshness"] is Freshness.STALE]
    unknown = [r["source"] for r in reports if r["freshness"] is Freshness.UNKNOWN]

    return {
        "needs_refetch": stale,
        "unknown": unknown,
        "exit_code": 0 if not stale and not unknown else 1,
    }


# --- Recorded markers ------------------------------------------------------


def recorded_atc_markers() -> dict[str, str | None]:
    """Every layer currently in the ATC manifest, keyed by source key, to
    its recorded edit-date marker - or None if fetch_all.py recorded the
    layer without one.

    That null case is real, not hypothetical: fetch_all.py tolerates a
    failed dataLastEditDate lookup and still fetches and records the layer
    rather than failing the whole run (see fetch_all.py's handling around
    get_layer_edit_date). This function used to filter such entries out via
    an `is not None` guard, which silently dropped them rather than
    reporting them - they never reached check_all()'s comparison loop at
    all, so the rollup could print "atc: FRESH" while that layer had never
    actually been checked. Every registered entry is returned now, null or
    not, so the caller can classify a null one as unknown instead of it
    vanishing from consideration.
    """
    if not ATC_MANIFEST.exists():
        return {}
    manifest = json.loads(ATC_MANIFEST.read_text())
    return {
        key: None if entry.get("data_last_edit_date") is None else str(entry.get("data_last_edit_date"))
        for key, entry in manifest.items()
    }


def recorded_opentrail_marker() -> str | None:
    if not OPENTRAIL_STATE.exists():
        return None
    return json.loads(OPENTRAIL_STATE.read_text()).get("etag")


def edition_key(url: str) -> str:
    """`n35w084:20230215` for a conventional 3DEP filename.

    An unparseable name still yields a key rather than being skipped: a tile
    silently dropped from the marker would make a real change look like no
    change at all.
    """
    name = url.rsplit("/", 1)[-1]
    match = re.match(r"USGS_1[3m]?_?(?P<cell>n\d+w\d+)_(?P<edition>\d{8})\.tif$", name)
    if match is None:
        return f"{name}:"
    return f"{match['cell']}:{match['edition']}"


def recorded_elevation_marker() -> str | None:
    """Which tile editions the current index pinned, order-independent.

    TNM returns tiles in no guaranteed order, so a reshuffle must not read as
    a change - only a genuinely new edition should.
    """
    if not ELEVATION_INDEX.exists():
        return None
    entries = json.loads(ELEVATION_INDEX.read_text())
    return "|".join(sorted(edition_key(entry["url"]) for entry in entries))


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


def upstream_elevation_marker() -> str | None:
    """Re-run the same TNM discovery the index was built from and compare the
    edition set. This is the only way to notice 3DEP republishing a cell:
    there is no per-file timestamp to HEAD, but a new survey arrives as a new
    dated filename."""
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
        recorded = recorded_elevation_marker()
        if recorded is None:
            return None
        tracked_cells = {key.split(":", 1)[0] for key in recorded.split("|")}

        keys = {edition_key(entry["url"]) for entry in index if edition_key(entry["url"]).split(":", 1)[0] in tracked_cells}
        return "|".join(sorted(keys)) if keys else None
    except Exception:
        return None


def check_all() -> list[dict]:
    """Every source's verdict. Never raises: a source that cannot be checked
    reports UNKNOWN rather than taking the whole run down with it."""
    reports: list[dict] = []

    recorded_atc = recorded_atc_markers()
    if not recorded_atc:
        reports.append({"source": "atc", "freshness": Freshness.STALE, "detail": "never fetched"})
    else:
        manifest = json.loads(ATC_MANIFEST.read_text())
        changed = []
        unknown = []
        for key, recorded in recorded_atc.items():
            if recorded is None:
                # Recorded but with no edit date (a tolerated failed lookup
                # in fetch_all.py) - unknown, not a stale/fresh guess, and
                # not worth an upstream request when there is nothing to
                # compare it to.
                unknown.append(key)
                continue
            upstream = upstream_atc_marker(manifest[key]["url"])
            verdict = compare_marker(recorded, upstream)
            if verdict is Freshness.STALE:
                changed.append(key)
            elif verdict is Freshness.UNKNOWN:
                unknown.append(key)
        freshness = Freshness.STALE if changed else Freshness.UNKNOWN if unknown else Freshness.FRESH
        detail = f"{len(changed)} changed, {len(unknown)} unknown of {len(recorded_atc)} layers"
        reports.append({"source": "atc", "freshness": freshness, "detail": detail})

    reports.append(
        {
            "source": "opentrail",
            "freshness": compare_marker(recorded_opentrail_marker(), upstream_opentrail_marker()),
            "detail": "ETag",
        }
    )

    if not TOPO_MANIFEST.exists():
        reports.append({"source": "topo_quads", "freshness": Freshness.STALE, "detail": "never fetched"})
    else:
        manifest = json.loads(TOPO_MANIFEST.read_text())
        sample = topo_sample(manifest)
        upstream = upstream_topo_markers(sample)
        verdicts = [compare_marker(manifest[url].get("last_modified"), upstream[url]) for url in sample]
        freshness = (
            Freshness.STALE
            if Freshness.STALE in verdicts
            else Freshness.UNKNOWN
            if Freshness.UNKNOWN in verdicts
            else Freshness.FRESH
        )
        reports.append(
            {
                "source": "topo_quads",
                "freshness": freshness,
                "detail": f"sampled {len(sample)} of {len(manifest)} quads",
            }
        )

    reports.append(
        {
            "source": "elevation",
            "freshness": compare_marker(recorded_elevation_marker(), upstream_elevation_marker()),
            "detail": "3DEP tile editions",
        }
    )

    return reports


def main() -> int:
    reports = check_all()
    for report in reports:
        print(f"  {report['freshness'].value.upper():8} {report['source']:12} {report['detail']}")

    summary = summarise(reports)
    if summary["needs_refetch"]:
        print(f"\nNeeds refetch: {', '.join(summary['needs_refetch'])}")
    if summary["unknown"]:
        print(f"Could not check: {', '.join(summary['unknown'])} - treat as unverified, not current.")
    if summary["exit_code"] == 0:
        print("\nEverything upstream is unchanged. No refetch or reprocessing needed.")

    return summary["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
