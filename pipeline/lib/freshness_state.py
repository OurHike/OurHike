"""The *recorded* half of the freshness question, separated from the asking.

`check_freshness.py` answers "does any upstream data need refetching?" by
comparing two things: what we recorded when we last fetched, and what upstream
says now. Only the second half needs the network. The first half used to be
inseparable from `pipeline/data/raw/*`, which is gitignored - so the check
could only ever run on a machine that had already done a full fetch, and on a
hosted runner it would report every source STALE for the trivial reason that a
fresh checkout has no `data/raw/` at all.

That is the one thing standing between a working check and a scheduled one, so
the recorded side lives here instead:

    capture_state()   read data/raw/* after a fetch -> the marker dict
    load_state()      the same dict back, from a local file or an https URL
    compare_state()   recorded vs upstream -> one Freshness verdict per source

A build captures its state and publishes it next to the artifacts it built. A
scheduled job then loads that published state over plain HTTPS - the same
public URL a hiker's phone uses - and diffs it against live upstreams. It
needs no bucket credentials to do that, which is the point: a job that cannot
authenticate to R2 is *structurally* incapable of changing what anyone has
downloaded, rather than merely choosing not to.

THE FAILURE THAT MATTERS is a false "fresh". Reporting stale data as current
means the map quietly keeps showing a closed trail or a moved shelter, so
anything that cannot be verified reports UNKNOWN rather than being rounded
down to fine. That rule is why `compare_marker` treats a missing upstream
answer as UNKNOWN and a missing recorded one as STALE - never as FRESH.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

import requests

# Bumped only when the on-disk shape changes incompatibly. A state file
# written by a newer pipeline than the one reading it is refused rather than
# half-understood: a partially-parsed state means silently comparing fewer
# sources than you think you are, which reads as FRESH.
STATE_VERSION = 1

HTTP_TIMEOUT = 30


class Freshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class StateUnavailable(RuntimeError):
    """No state could be loaded from where one was asked for.

    Distinct from "the state says everything is stale". Nothing to compare
    against is not a verdict about the data - it is the absence of one, and a
    caller that flattened the two together would report a brand-new bucket as
    an upstream emergency.
    """


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


# --- Capture: data/raw/* -> the marker dict --------------------------------


def atc_sources(manifest_path: Path) -> dict[str, dict]:
    """Every layer in the ATC manifest, as `{key: {url, marker}}`.

    Both halves travel together because the checking job needs both and will
    not have the manifest: the marker is what gets compared, and the URL is
    where the comparison value is asked for. Splitting them would mean a
    scheduled check could load a state and still not know what to query.

    A null marker is kept, not filtered. That case is real rather than
    hypothetical - `fetch_all.py` tolerates a failed `dataLastEditDate`
    lookup and still fetches and records the layer rather than failing the
    whole run. An `is not None` guard here (which this code once had) drops
    such a layer before it ever reaches a comparison, so the rollup can print
    "atc: FRESH" for a set that includes a layer nobody ever checked. Every
    registered entry is returned, null or not, so the caller can classify it
    as UNKNOWN instead of it vanishing from consideration.
    """
    if not Path(manifest_path).exists():
        return {}
    manifest = json.loads(Path(manifest_path).read_text())
    return {
        key: {
            "url": entry.get("url"),
            "marker": None if entry.get("data_last_edit_date") is None else str(entry.get("data_last_edit_date")),
        }
        for key, entry in manifest.items()
    }


def opentrail_marker(state_path: Path) -> str | None:
    if not Path(state_path).exists():
        return None
    return json.loads(Path(state_path).read_text()).get("etag")


def topo_markers(manifest_path: Path) -> dict[str, str | None]:
    """Every fetched topo quad's recorded S3 `Last-Modified`, keyed by URL.

    All of them, not a sample. Sampling is a property of *asking* upstream -
    1,654 HEAD requests is a lot of traffic for a dataset USGS republishes in
    batches - and the sample is drawn fresh on each run. A state file that
    only recorded one run's sample would pin the check to whatever 25 quads
    happened to be picked the day it was built.
    """
    if not Path(manifest_path).exists():
        return {}
    manifest = json.loads(Path(manifest_path).read_text())
    return {url: entry.get("last_modified") for url, entry in manifest.items()}


def elevation_marker(index_path: Path) -> str | None:
    """Which tile editions the current index pinned, order-independent.

    TNM returns tiles in no guaranteed order, so a reshuffle must not read as
    a change - only a genuinely new edition should.
    """
    if not Path(index_path).exists():
        return None
    entries = json.loads(Path(index_path).read_text())
    return "|".join(sorted(edition_key(entry["url"]) for entry in entries))


SOURCES = ("atc", "opentrail", "topo_quads", "elevation")


def capture_state(
    *,
    atc_manifest: Path,
    opentrail_state: Path,
    topo_manifest: Path,
    elevation_index: Path,
    captured_at: str | None = None,
) -> dict:
    """Every upstream freshness marker this checkout currently records.

    All four sources are always present as keys. On a machine that has done
    the fetching, an empty/None value means "never fetched", which is a real
    answer the checking side needs - a source that silently vanished from the
    dict would instead read as one nobody has to worry about.
    """
    return {
        "version": STATE_VERSION,
        "captured_at": captured_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "atc": atc_sources(atc_manifest),
        "opentrail": opentrail_marker(opentrail_state),
        "topo_quads": topo_markers(topo_manifest),
        "elevation": elevation_marker(elevation_index),
    }


def drop_unrecorded(state: dict) -> dict:
    """The same state with sources it holds no record of removed entirely.

    For publishing, where the two meanings of "empty" come apart. On the
    machine that fetched, an empty ATC dict means *we looked and there is
    nothing* - STALE, go fetch. In a state published by a build that never
    ran the topo leg at all, the same empty dict would claim a verdict about
    something that build never touched.

    This matters because the two halves of the pipeline are deliberately
    separate workflows: the vector publish never fetches topo quads or DEM
    tiles (see .github/workflows/publish-vector-data.yml). A state it
    captured that carried empty topo/elevation entries would make the
    scheduled check report a daily STALE for the raster half, forever, for no
    reason - and an alarm that is always on gets ignored, which is how the
    real one gets missed.

    Dropped rather than nulled so `compare_state` reads it as "nobody
    checked" (UNKNOWN) rather than "checked, found nothing" (STALE). Silence
    about a source is never rounded down to fine.
    """
    kept = {key: value for key, value in state.items() if key not in SOURCES or value}
    return kept


# --- Load: a local file or a public URL ------------------------------------


def load_state(source: str | Path) -> dict:
    """A captured state, from a filesystem path or an `http(s)://` URL.

    The URL case is what lets a scheduled check hold no credentials at all:
    it reads the same public object a phone would. Anything that goes wrong -
    404, unparseable body, a version this code does not understand - raises
    `StateUnavailable` rather than returning a partial dict, because a state
    missing half its sources compares as FRESH on the half that is left.
    """
    text = _read_source(source)

    try:
        state = json.loads(text)
    except ValueError as exc:
        raise StateUnavailable(f"{source} is not valid JSON: {exc}") from exc

    if not isinstance(state, dict):
        raise StateUnavailable(f"{source} does not contain a state object")

    version = state.get("version")
    if version != STATE_VERSION:
        raise StateUnavailable(
            f"{source} is state version {version!r}, this pipeline reads version {STATE_VERSION}"
        )

    return state


def _read_source(source: str | Path) -> str:
    text = str(source)
    if urlparse(text).scheme in {"http", "https"}:
        try:
            response = requests.get(text, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise StateUnavailable(f"could not fetch {text}: {exc}") from exc
        return response.text

    path = Path(source)
    if not path.exists():
        raise StateUnavailable(f"no state file at {path}")
    return path.read_text()


# --- Compare: recorded vs upstream -----------------------------------------


def compare_state(recorded: dict, upstream: dict) -> list[dict]:
    """One verdict per source, from a recorded state and whatever upstream
    answered.

    `upstream` has the same shape as `recorded` but may be sparser: only the
    sampled topo quads appear, and an ATC layer with no recorded marker is
    deliberately never asked about. Anything present in `recorded` and absent
    from `upstream` is UNKNOWN - it was not checked, which is not the same as
    being current.

    Never raises. A source that cannot be checked reports UNKNOWN rather than
    taking the whole run down with it.
    """
    reports: list[dict] = []

    recorded_atc = recorded.get("atc") or {}
    if "atc" not in recorded:
        reports.append({"source": "atc", "freshness": Freshness.UNKNOWN, "detail": "not in this state"})
    elif not recorded_atc:
        reports.append({"source": "atc", "freshness": Freshness.STALE, "detail": "never fetched"})
    else:
        upstream_atc = upstream.get("atc") or {}
        changed, unknown = [], []
        for key, entry in recorded_atc.items():
            marker = entry.get("marker") if isinstance(entry, dict) else entry
            if marker is None:
                # Recorded, but with no edit date to compare against. Unknown,
                # not a stale/fresh guess - and not worth an upstream request
                # when there is nothing to compare the answer to.
                unknown.append(key)
                continue
            verdict = compare_marker(marker, upstream_atc.get(key))
            if verdict is Freshness.STALE:
                changed.append(key)
            elif verdict is Freshness.UNKNOWN:
                unknown.append(key)
        freshness = Freshness.STALE if changed else Freshness.UNKNOWN if unknown else Freshness.FRESH
        reports.append(
            {
                "source": "atc",
                "freshness": freshness,
                "detail": f"{len(changed)} changed, {len(unknown)} unknown of {len(recorded_atc)} layers",
                "changed": changed,
            }
        )

    if "opentrail" not in recorded:
        reports.append({"source": "opentrail", "freshness": Freshness.UNKNOWN, "detail": "not in this state"})
    else:
        reports.append(
            {
                "source": "opentrail",
                "freshness": compare_marker(recorded.get("opentrail"), upstream.get("opentrail")),
                "detail": "ETag",
            }
        )

    recorded_topo = recorded.get("topo_quads") or {}
    if "topo_quads" not in recorded:
        reports.append({"source": "topo_quads", "freshness": Freshness.UNKNOWN, "detail": "not in this state"})
    elif not recorded_topo:
        reports.append({"source": "topo_quads", "freshness": Freshness.STALE, "detail": "never fetched"})
    else:
        upstream_topo = upstream.get("topo_quads") or {}
        verdicts = [compare_marker(recorded_topo.get(url), upstream_topo[url]) for url in upstream_topo]
        freshness = (
            Freshness.STALE
            if Freshness.STALE in verdicts
            else Freshness.UNKNOWN
            if Freshness.UNKNOWN in verdicts or not verdicts
            else Freshness.FRESH
        )
        reports.append(
            {
                "source": "topo_quads",
                "freshness": freshness,
                "detail": f"sampled {len(upstream_topo)} of {len(recorded_topo)} quads",
            }
        )

    if "elevation" not in recorded:
        reports.append({"source": "elevation", "freshness": Freshness.UNKNOWN, "detail": "not in this state"})
    else:
        reports.append(
            {
                "source": "elevation",
                "freshness": compare_marker(recorded.get("elevation"), upstream.get("elevation")),
                "detail": "3DEP tile editions",
            }
        )

    return reports


def state_age_days(state: dict, today: date | None = None) -> int | None:
    """How long ago the state was captured, or None if it does not say.

    A check is only as good as the state it compares against: a FRESH verdict
    against a six-month-old capture means "nothing has changed since a build
    six months ago", which is a very different sentence from the one a reader
    assumes. Callers surface this next to the verdict rather than leaving it
    to be inferred.
    """
    captured = state.get("captured_at")
    if not isinstance(captured, str) or not captured:
        return None
    try:
        when = datetime.fromisoformat(captured)
    except ValueError:
        return None
    return ((today or date.today()) - when.date()).days
