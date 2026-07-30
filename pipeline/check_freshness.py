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
import re
import sys
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
# sample, not as proof the whole set is current.
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


def recorded_atc_markers() -> dict[str, str]:
    if not ATC_MANIFEST.exists():
        return {}
    manifest = json.loads(ATC_MANIFEST.read_text())
    return {
        key: str(entry.get("data_last_edit_date"))
        for key, entry in manifest.items()
        if entry.get("data_last_edit_date") is not None
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
            upstream = upstream_atc_marker(manifest[key]["url"])
            verdict = compare_marker(recorded, upstream)
            if verdict is Freshness.STALE:
                changed.append(key)
            elif verdict is Freshness.UNKNOWN:
                unknown.append(key)
        freshness = Freshness.STALE if changed else Freshness.UNKNOWN if unknown else Freshness.FRESH
        detail = f"{len(changed)} changed, {len(unknown)} unreachable of {len(recorded_atc)} layers"
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
        sample = sorted(manifest)[:TOPO_SAMPLE_SIZE]
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
