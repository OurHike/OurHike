"""OSM's Geofabrik state extracts: kept as files in the raw store, monthly, with one manifest row each for dlt.

#1652 — Download OSM's Geofabrik extracts at most once a month, into a
private raw bucket that outlives the 7-day Actions cache. Two halves:

    geofabrik_extracts(key)   the monthly lane's resource (_shared/osm/geofabrik.py)
    python -m extract._geofabrik pull ...    refresh-reference.yml's build job
    python -m extract._geofabrik landed ...  the same job, after its water scans

THE BYTES NEVER REACH dlt. A .pbf is a file to keep, not rows (decision 4,
"Manifest row first, then bytes as well"; ELT.md, "Storage tiers": "PBFs stay
bytes only"). So the resource is BucketListing's pattern rather than
ClubPdf's: one manifest row per file (where it is kept, its size, sha256,
Geofabrik's Last-Modified and ETag), and never the file. ClubPdf parses its
document into rows and holds the whole body in memory (`response.content`)
to do it, and nothing in a PBF is a row dlt should hold; BucketListing lists
objects it never fetches. The difference from BucketListing is whose objects
are listed: these are this store's own copies, which rows() puts there
first, streamed through lib/http_retry.py's download_with_retry to a
temporary file one state at a time (about 500 MB at most on disk, never in
memory) and then uploaded.

WHERE THE COPIES LIVE. INCREMENTAL.md's `current/` mirror and its
`index.json`, folded into the raw store's prefix layout rather than built as
a second store: `<lane bucket URL>/current/<path under data/raw/>`, beside
dlt's `raw/` dataset and the as-landed copy (`as_landed/`), so each state's
extract is `current/osm/<state>-latest.osm.pbf`, the path export_basemap.py's
OSM_RAW_DIR keeps it at, and `current/index.json` holds `{sha256,
size_bytes, pushed_at}` per file plus where it came from. Under the lane's
own prefix because each lane is the only writer of its prefix
(refresh-reference.yml's `raw-lake-monthly` group), and the index is read,
changed and written back. Every key passes lib/raw_keys.py, INCREMENTAL.md's
own validator for the private store. No `snapshots/` copy is kept: at 3.44
GB a month it would be the store's largest cost, and nothing reads an old
extract (Reasoned; ask before adding one).

THE CHANGE CHECK READS THE STORE, NEVER GEOFABRIK. Geofabrik republishes
every extract daily, so any validator it serves reads STALE (the dlt
skill's rule 4; export_basemap.py's docstring). A copy is read again only
once it is MAX_AGE_DAYS old, counted from the stored copy's own date: the
Last-Modified Geofabrik sent with it, which is the date of the data it
holds, else when it was stored. FRESH when every state's copy is present
and younger than that; STALE when one is older; UNKNOWN when one has no
copy, or its object is not the one the index describes. Only FRESH skips,
and rows() then reads only the states that need it.

NEVER EMPTIED BY ONE FAILED DOWNLOAD (the dlt skill, rule 2's second half).
A state whose download fails, is refused or does not start keeps its last
copy and its index entry, and its row says why (`read_error`). The object is
replaced only by a complete body that matches its Content-Length and opens
as a PBF, and the index only after the object. A run that downloads nothing
still lands every row the store's index holds.

TERMS AND ROBOTS. ODbL 1.0, quoted on sources.json's `osm_water` row.
Every request sends lib/user_agent.py's USER_AGENT, and robots.txt is read
before the first download of a run: a path it disallows for our agent is not
asked, a 5xx or no answer is read as disallowing everything (RFC 9309,
section 2.3.1.4), and its Crawl-delay is waited between requests, never
less than MIN_HOST_GAP_SECONDS. This sandbox could not read it:
download.geofabrik.de reset the connection on 2026-10-04, as it did for
ELT.md's probe, so what it says is read by CI's first run, not here.
Geofabrik describes its public server's extracts as carrying no user names
or ids (from its download pages as known before this work, not re-read from
here), and nothing here or in the scans reads any metadata but tags and
coordinates.

THE BUILD SIDE (`pull`, `landed`). refresh-reference.yml's build job pulls
each copy the index names into data/raw/osm/, holding it to the index's
sha256 and size, and places the last landed water scans (the newest earlier
pin's `derived/osm_water.geojson` and `derived/trail_water.json`) at the
paths fetch_osm_water.py and fetch_trail_water.py write, so each scan's own
drop guard compares against them and a refusal leaves them standing. Only a
complete set of fourteen is scanned; a missing or unreadable copy warns and
the build lands the last landed scans, never none, and with none landed
before it publishes no OSM water and says so in the run summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

from extract import _kinds
from extract._contract import Resource, Unavailable
from lib.freshness_state import Freshness
from lib.geofabrik import AT_STATES, extract_name, looks_like_pbf
from lib.http_retry import download_with_retry, request_with_retry
from lib.raw_keys import validate_raw_key
from lib.user_agent import USER_AGENT

#: The as-sent mirror's prefix under a lane's bucket URL, and its index (INCREMENTAL.md, "The store's layout").
CURRENT_PREFIX = "current"
INDEX_NAME = "index.json"
#: Where a state's extract sits under current/ and under data/raw/: export_basemap.py's OSM_RAW_DIR is data/raw/osm.
OSM_DIR = "osm"

# @unvalidated: how long a stored copy serves before it is downloaded again.
# 30 days is the maintainer's round number (#1652, 2026-09-24: "We should only
# download a lot of the data like once per month"; INCREMENTAL.md's four
# clocks), not a measurement of how fast OSM's water and stream tags change
# along the corridor. What would settle it: the monthly scans' own counts,
# fetch_osm_water.py's points and fetch_trail_water.py's site water, compared
# between consecutive copies over a few months. On the 3rd-of-the-month
# schedule (05:15 UTC) the gaps are 28 to 31 days, and the age is counted from
# Geofabrik's Last-Modified, a few hours before the download: so the run after
# a 28- or 29-day gap (February to March) finds the copy FRESH and the next
# run reads it at about 59 days old, once a year (Reasoned from the calendar).
MAX_AGE_DAYS = 30

# @unvalidated: how long one run may spend starting downloads. A state not
# started by then keeps its last copy and is read on the next run. The
# fourteen took under 1.5 minutes on build-basemap.yml run 30957719854
# (2026-08-04: its whole run was 12.5 minutes, Planetiler about 11 of them,
# pipeline/BASEMAP.md), so 20 minutes is about 13 times that; it is here so a
# slow host cannot push the monthly extract past its job's timeout
# (refresh-reference.yml says the arithmetic). A few months of
# `_extract_runs` timings would settle it.
DOWNLOAD_BUDGET_SECONDS = 20 * 60

#: The least wait between two requests to Geofabrik when robots.txt asks for
#: no Crawl-delay: the 2 seconds every extract waits for any host.
MIN_HOST_GAP_SECONDS = 2.0

#: download_with_retry's read timeout for one extract: export_basemap.py's
#: fetch_states uses the same 600 s for the same files (#1063).
READ_TIMEOUT_SECONDS = 600

# --- The raw store's as-sent mirror -------------------------------------------------------


class _Bound:
    """The raw store a running lane writes, bound by extract/_run.py's _run() for as long as the run lasts."""

    fs = None
    root: str | None = None


_STORE = _Bound()


def bind_store(fs, root: str) -> None:
    """Name the store a lane writes: `fs`, its filesystem client, and `root`, its bucket URL as an fsspec path.

    extract/_run.py's _run() binds dlt's own client for the lane
    (`pipeline.destination_client().fs_client`), made on the run's own
    thread, so the copies go through the same credentials and the same R2
    upload settings as dlt's files. A module global rather than a context
    variable, because the change checks run on worker threads, which a
    context variable does not reach.
    """
    _STORE.fs, _STORE.root = fs, root.rstrip("/")


def unbind_store() -> None:
    _STORE.fs, _STORE.root = None, None


def bound_store():
    """(filesystem, root) of the lane running now. Unavailable outside a run: nothing here knows where to keep a file."""
    if _STORE.fs is None or _STORE.root is None:
        raise Unavailable("no raw store is bound: extract/_run.py binds the lane's store before its change checks")
    return _STORE.fs, _STORE.root


def object_path(root: str, key: str) -> str:
    """The fsspec path of `key` under `<root>/current/`, refused when it is not a raw-store key or would be the index."""
    if validate_raw_key(key) == INDEX_NAME:
        raise ValueError(f"{key!r} is the mirror's own index, not a file it holds")
    return f"{root}/{CURRENT_PREFIX}/{key}"


def index_path(root: str) -> str:
    return f"{root}/{CURRENT_PREFIX}/{INDEX_NAME}"


def read_index(fs, root: str) -> dict[str, dict]:
    """`current/index.json`'s files, {key: entry}; {} when there is no index yet. Raises on one that will not parse."""
    path = index_path(root)
    if not fs.exists(path):
        return {}
    with fs.open(path, "r") as handle:
        files = json.load(handle).get("files")
    if not isinstance(files, dict):
        raise ValueError(f"{path} holds no `files` object")
    return files


def write_index(fs, root: str, files: dict[str, dict]) -> None:
    """Replace `current/index.json` with `files`. A put is whole or not at all on R2, so a reader sees one index or the other."""
    fs.makedirs(f"{root}/{CURRENT_PREFIX}", exist_ok=True)
    body = json.dumps({"files": dict(sorted(files.items())), "written_at": _stamp(_now())}, indent=2, sort_keys=True)
    with fs.open(index_path(root), "w") as handle:
        handle.write(body)


def listed_sizes(fs, root: str, folder: str) -> dict[str, int]:
    """{key under current/: size} for the objects in one folder of the mirror, from one listing; {} for no folder."""
    try:
        entries = fs.ls(f"{root}/{CURRENT_PREFIX}/{folder}", detail=True)
    except FileNotFoundError:
        return {}
    return {f"{folder}/{os.path.basename(entry['name'].rstrip('/'))}": int(entry.get("size") or 0) for entry in entries}


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def copy_date(entry: dict) -> datetime | None:
    """The stored copy's own date: the Last-Modified Geofabrik sent with it, else when it was stored; None when neither reads."""
    if entry.get("last_modified"):
        try:
            return parsedate_to_datetime(entry["last_modified"]).astimezone(UTC)
        except (TypeError, ValueError):
            pass
    if entry.get("pushed_at"):
        try:
            return datetime.strptime(entry["pushed_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


# --- robots.txt -------------------------------------------------------------------------------


@dataclass
class Robots:
    """What a host's robots.txt lets our agent ask, read once per run before the first download."""

    allows: Callable[[str], bool]
    delay: float
    said: str


def read_robots(http: requests.Session, base_url: str) -> Robots:
    """robots.txt for `base_url`'s host, under our agent, through lib/http_retry.py's retry. A 4xx other than 429 is no
    rules (RFC 9309, 2.3.1.3); a 5xx, a 429 or no answer is a host that cannot be read, which refuses everything
    (2.3.1.4)."""
    parts = urlsplit(base_url)
    url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        response = request_with_retry(url, session=http, timeout=60, label="robots.txt")
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else None
        if status is not None and 400 <= status < 500 and status != 429:
            return Robots(lambda target: True, MIN_HOST_GAP_SECONDS, f"{url} answered {status}: no rules")
        return Robots(lambda target: False, MIN_HOST_GAP_SECONDS, f"{url} answered {status}, read as disallow")
    except requests.RequestException as error:
        return Robots(
            lambda target: False, MIN_HOST_GAP_SECONDS, f"{url} gave no answer ({type(error).__name__}), read as disallow"
        )
    rules = RobotFileParser()
    rules.parse(response.text.splitlines())
    delay = rules.crawl_delay(USER_AGENT)
    return Robots(
        lambda target: rules.can_fetch(USER_AGENT, target),
        max(MIN_HOST_GAP_SECONDS, float(delay or 0)),
        f"{url} read ({len(response.text)} bytes, Crawl-delay {delay if delay is not None else 'none'})",
    )


# --- The resource -----------------------------------------------------------------------------


@dataclass(frozen=True)
class GeofabrikExtracts(Resource):
    """The fourteen A.T. states' Geofabrik extracts, kept in the raw store; one manifest row per state, never the bytes.

    The module docstring is the design. The registry row's `url` is
    Geofabrik's directory of US state extracts; each state is
    `<url>/<state>-latest.osm.pbf` (lib/geofabrik.py's extract_name()).
    """

    states: tuple[str, ...] = tuple(AT_STATES)
    max_age_days: int = MAX_AGE_DAYS

    @property
    def may_be_empty(self) -> bool:
        """True, with the store's own index as the count: a first run that downloads nothing has no copy to list, and
        that zero is exact. The collapse floor still refuses a store that lost its copies (extract/_run.py's run_check)."""
        return True

    @property
    def exact_proof(self) -> bool:
        return True

    def base_url(self) -> str:
        return _kinds.registry_entry(self.key)["url"].rstrip("/")

    def url(self, state: str) -> str:
        return f"{self.base_url()}/{extract_name(state)}"

    @staticmethod
    def path(state: str) -> str:
        """Where the state's copy sits under current/, and where the build puts it under data/raw/."""
        return f"{OSM_DIR}/{extract_name(state)}"

    def column_hints(self) -> dict:
        text = {"data_type": "text"}
        return {
            "state": text,
            "path": text,
            "source_url": text,
            "size_bytes": {"data_type": "bigint"},
            "sha256": text,
            "last_modified": text,
            "etag": text,
            "pushed_at": text,
            "read_this_run": {"data_type": "bool"},
            "read_error": text,
        }

    def verdicts(self, index: dict[str, dict], sizes: dict[str, int], now: datetime) -> dict[str, Freshness]:
        """Each state's copy: FRESH inside its max age, STALE past it, UNKNOWN with no copy the index describes."""
        found = {}
        for state in self.states:
            entry = index.get(self.path(state))
            if entry is None or sizes.get(self.path(state)) != entry.get("size_bytes"):
                found[state] = Freshness.UNKNOWN
                continue
            dated = copy_date(entry)
            if dated is None or now - dated >= timedelta(days=self.max_age_days):
                found[state] = Freshness.STALE
            else:
                found[state] = Freshness.FRESH
        return found

    def _marker(self, index: dict[str, dict]) -> dict:
        copies = {state: (index.get(self.path(state)) or {}).get("sha256") for state in self.states}
        dates = [copy_date(index[self.path(state)]) for state in self.states if self.path(state) in index]
        oldest = min((dated for dated in dates if dated is not None), default=None)
        return {"copies": copies, "oldest": _stamp(oldest) if oldest else None}

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """The store's own copies, never Geofabrik's validators: FRESH only when all are present and young enough."""
        fs, root = bound_store()
        try:
            index = read_index(fs, root)
            sizes = listed_sizes(fs, root, OSM_DIR)
        except (OSError, ValueError) as error:
            print(f"  {self.key}: the store's index could not be read ({error}); reading the extracts")
            return Freshness.UNKNOWN, None
        verdicts = self.verdicts(index, sizes, _now())
        marker = self._marker(index)
        if Freshness.UNKNOWN in verdicts.values():
            return Freshness.UNKNOWN, marker
        if Freshness.STALE in verdicts.values():
            return Freshness.STALE, marker
        return Freshness.FRESH, marker

    def rows(self, proofs: dict[str, int]):
        fs, root = bound_store()
        try:
            index = read_index(fs, root)
        except (OSError, ValueError) as error:
            print(f"::warning title={self.key}: the store's index is unreadable::{error}; every extract is read again")
            index = {}
        sizes = listed_sizes(fs, root, OSM_DIR)
        verdicts = self.verdicts(index, sizes, _now())
        present = {state for state, verdict in verdicts.items() if verdict is not Freshness.UNKNOWN}
        wanted = [state for state in self.states if verdicts[state] is not Freshness.FRESH]
        read, errors = self._read(fs, root, index, wanted) if wanted else (set(), {})
        present |= read
        rows = []
        for state in self.states:
            if state not in present:
                continue
            entry = index[self.path(state)]
            rows.append(
                {
                    "state": state,
                    "path": self.path(state),
                    "source_url": entry.get("source_url"),
                    "size_bytes": entry.get("size_bytes"),
                    "sha256": entry.get("sha256"),
                    "last_modified": entry.get("last_modified"),
                    "etag": entry.get("etag"),
                    "pushed_at": entry.get("pushed_at"),
                    "read_this_run": state in read,
                    "read_error": errors.get(state),
                }
            )
        for state in self.states:
            if state not in present:
                print(f"::warning title={self.key}: no copy of {state}::{errors.get(state, 'never landed')}")
        proofs[self.table] = len(rows)
        yield from rows

    def _read(self, fs, root: str, index: dict[str, dict], states: list[str]) -> tuple[set[str], dict[str, str]]:
        """Download each state, one at a time, into the store. Returns (the states now holding a new copy, why each other failed).

        The index is written after each state, so a run that dies part way
        keeps every copy it finished.
        """
        http = _kinds.session()
        robots = read_robots(http, self.base_url())
        print(f"  {self.key}: {robots.said}")
        deadline = time.monotonic() + DOWNLOAD_BUDGET_SECONDS
        last_request = time.monotonic()
        read, errors = set(), {}
        for state in states:
            url = self.url(state)
            if not robots.allows(url):
                errors[state] = f"not asked: {robots.said}"
                continue
            if time.monotonic() > deadline:
                errors[state] = f"not started: the run's {DOWNLOAD_BUDGET_SECONDS // 60}-minute download budget was spent"
                continue
            if (wait := robots.delay - (time.monotonic() - last_request)) > 0:
                time.sleep(wait)
            try:
                entry = self._download(fs, root, state, url, http)
            except (requests.RequestException, OSError, ValueError) as error:
                errors[state] = f"{type(error).__name__}: {error}"
                print(f"::warning title={self.key}: {state} kept its last copy::{errors[state]}")
                continue
            finally:
                last_request = time.monotonic()
            index[self.path(state)] = entry
            write_index(fs, root, index)
            read.add(state)
            print(f"  {self.key}: {state}, {entry['size_bytes'] / 1e6:.0f} MB, stored")
        return read, errors

    def _download(self, fs, root: str, state: str, url: str, http: requests.Session) -> dict:
        """One state's extract, streamed through `http` to a temporary file, checked, then uploaded. Returns its index entry.

        `http` is the session robots.txt was read through, extract/_kinds.py's session(), so an extract redirected to
        another host raises RedirectRefused and the state keeps its last copy (review finding SEC-5 of PR #1805).
        """
        with tempfile.TemporaryDirectory(prefix="geofabrik-") as folder:
            local = Path(folder) / extract_name(state)
            headers: dict = {}
            download_with_retry(
                url,
                local,
                timeout=READ_TIMEOUT_SECONDS,
                headers={"User-Agent": USER_AGENT},
                label=f"osm/{state}",
                response_headers=headers,
                session=http,
            )
            size = local.stat().st_size
            stated = headers.get("Content-Length")
            if stated is not None and not headers.get("Content-Encoding") and int(stated) != size:
                raise ValueError(f"{url}: {size} bytes arrived of the {stated} its Content-Length promised")
            if not looks_like_pbf(local):
                raise ValueError(f"{url}: the body does not open as an OSM PBF (no OSMHeader block)")
            sha256 = _sha256(local)
            fs.makedirs(f"{root}/{CURRENT_PREFIX}/{OSM_DIR}", exist_ok=True)
            fs.put_file(str(local), object_path(root, self.path(state)))
        return {
            "sha256": sha256,
            "size_bytes": size,
            "pushed_at": _stamp(_now()),
            "source_key": self.key,
            "source_url": url,
            "last_modified": headers.get("Last-Modified"),
            "etag": headers.get("ETag"),
        }


def geofabrik_extracts(key: str, **overrides) -> GeofabrikExtracts:
    entry = _kinds.registry_entry(key)
    if not str(entry.get("url", "")).startswith("https://"):
        raise KeyError(f"{key}: its sources.json row has no https url for Geofabrik's directory of extracts")
    return GeofabrikExtracts(key=key, **overrides)


# --- The build side: pull the copies, and the last landed scans -------------------------------

#: The water scans the build pins beside its raw inputs, by their path in the pin (under data/raw/ once
#: materialised), each with the path its scanner writes and reads back for its own drop guard. Not at the
#: scanners' own paths in the pin, because parity.py's old side would then find osm_water.geojson without the
#: reach file export_poi.py demands beside it, and refuse every POI family.
SCANS = {
    "derived/osm_water.geojson": "osm_water.geojson",  # fetch_osm_water.py's OUT_PATH under data/raw/
    "derived/trail_water.json": "trail_water.json",  # fetch_trail_water.py's OUT_PATH under data/raw/
}
#: How many earlier pins a degraded build looks back through for the last landed scans.
LOOKBACK_PINS = 12
#: The pull's own record, beside the extracts it pulled: what `landed` reads to say where each scan came from.
PULL_RECORD = "pull.json"


@dataclass
class Pulled:
    """What `pull` found: each state's copy, and which earlier pin each scan was placed from."""

    states: dict[str, str] = field(default_factory=dict)  # state -> "ok" | "missing" | "unreadable: <why>"
    scans: dict[str, dict] = field(default_factory=dict)  # pin path -> {"raw_run", "sha256"}
    index_error: str | None = None

    @property
    def extracts(self) -> str:
        """`complete` when all fourteen pulled, `none` when none did, else `partial`."""
        good = sum(1 for status in self.states.values() if status == "ok")
        return "complete" if good == len(self.states) and good else ("none" if not good else "partial")


def pull_extracts(fs, root: str, raw_dir: Path, states: tuple[str, ...] = tuple(AT_STATES)) -> Pulled:
    """Each state's copy into raw_dir/osm/, held to the index's sha256 and size; a copy that is not what the index says is unreadable."""
    pulled = Pulled()
    try:
        index = read_index(fs, root)
    except (OSError, ValueError) as error:
        pulled.index_error = f"{index_path(root)}: {error}"
        index = {}
    for state in states:
        key = GeofabrikExtracts.path(state)
        target = raw_dir / key
        target.unlink(missing_ok=True)
        entry = index.get(key)
        if entry is None:
            pulled.states[state] = "missing"
            continue
        part = target.with_name(target.name + ".part")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            fs.get_file(object_path(root, key), str(part))
            if part.stat().st_size != entry.get("size_bytes") or _sha256(part) != entry.get("sha256"):
                raise ValueError("its bytes are not the ones the index records")
            if not looks_like_pbf(part):
                raise ValueError("it does not open as an OSM PBF")
            part.replace(target)
            pulled.states[state] = "ok"
        except (OSError, ValueError) as error:
            pulled.states[state] = f"unreadable: {error}"
        finally:
            part.unlink(missing_ok=True)
    return pulled


def place_last_landed(fs, steps_root: str, raw_run: str, raw_dir: Path) -> dict[str, dict]:
    """The newest earlier pin's copy of each scan in SCANS, put at its scanner's path under raw_dir. Returns what was placed."""
    from extract._warehouse import PIN_MANIFEST, RAW_INPUTS_PREFIX

    try:
        runs = sorted(
            (os.path.basename(path.rstrip("/")) for path in fs.ls(f"{steps_root}/{RAW_INPUTS_PREFIX}", detail=False)),
            reverse=True,
        )
    except FileNotFoundError:
        runs = []
    placed: dict[str, dict] = {}
    for earlier in [run for run in runs if run < raw_run][:LOOKBACK_PINS]:
        manifest_path = f"{steps_root}/{RAW_INPUTS_PREFIX}/{earlier}/{PIN_MANIFEST}"
        if not fs.exists(manifest_path):
            continue  # a pin that did not finish is never read
        with fs.open(manifest_path, "r") as handle:
            landed = json.load(handle).get("as_landed") or {}
        for pinned, local in SCANS.items():
            if pinned in placed or pinned not in landed:
                continue
            target = raw_dir / local
            target.parent.mkdir(parents=True, exist_ok=True)
            fs.get_file(f"{steps_root}/{RAW_INPUTS_PREFIX}/{earlier}/as_landed/{pinned}", str(target))
            if _sha256(target) != landed[pinned]["sha256"]:
                target.unlink()
                continue  # a pin that changed is no evidence; an older one may still be
            placed[pinned] = {"raw_run": earlier, "sha256": landed[pinned]["sha256"]}
        if len(placed) == len(SCANS):
            break
    return placed


def _counted(path: Path) -> str:
    """The count a summary line ends with: points for an OSM water scan, sites with water for a site water one, or
    nothing for a file that will not read."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if "features" in document:
        return f", {len(document['features']):,} points"
    sites = document.get("sites") or []
    return f", {sum(1 for site in sites if site.get('water') is not None):,} of {len(sites):,} sites with water"


def _pull_command(args) -> int:
    from extract._run import _client, fs_path, make_pipeline

    pipeline = make_pipeline(args.lane, args.bucket_url)
    fs = _client(pipeline).fs_client
    raw_dir = Path(args.raw_dir)
    pulled = pull_extracts(fs, fs_path(args.bucket_url), raw_dir)
    pulled.scans = place_last_landed(fs, fs_path(args.steps_url), args.raw_run, raw_dir)
    (raw_dir / OSM_DIR).mkdir(parents=True, exist_ok=True)
    (raw_dir / OSM_DIR / PULL_RECORD).write_text(
        json.dumps({"states": pulled.states, "scans": pulled.scans, "extracts": pulled.extracts}, indent=2), encoding="utf-8"
    )
    lines = ["## OSM's Geofabrik extracts", ""]
    if pulled.index_error:
        print(f"::warning title=The extracts' index is unreadable::{pulled.index_error}")
        lines.append(f"The raw store's index could not be read: {pulled.index_error}")
    good = [state for state, status in pulled.states.items() if status == "ok"]
    lines.append(f"{len(good)} of {len(pulled.states)} state extracts pulled from the raw store.")
    for state, status in pulled.states.items():
        if status != "ok":
            print(f"::warning title=No usable copy of {state}'s extract::{status}; this build does not scan the extracts")
            lines.append(f"- {state}: {status}")
    for pinned, local in SCANS.items():
        found = pulled.scans.get(pinned)
        lines.append(
            f"- last landed `{pinned}`: "
            + (f"raw_run `{found['raw_run']}`, placed at data/raw/{local}" if found else "none in the last pins")
        )
    if pulled.extracts != "complete":
        if pulled.scans:
            lines.append("The build lands the last landed water scans above rather than scanning a partial set.")
        else:
            print(
                "::warning title=No OSM water this build::no complete set of extracts and no water scan landed before; "
                "this build publishes no OSM water and no site water"
            )
            lines.append("**No OSM water and no site water this build**: no complete set of extracts, and no earlier scan.")
    print("\n".join(lines))
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as page:
            page.write("\n".join(lines) + "\n\n")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as out:
            out.write(f"extracts={pulled.extracts}\n")
    return 0


def _landed_command(args) -> int:
    """Say which water scans this build lands, and from where, once its scans have run or not."""
    raw_dir = Path(args.raw_dir)
    try:
        record = json.loads((raw_dir / OSM_DIR / PULL_RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = {"scans": {}, "extracts": "none"}
    lines = ["## The water scans this build lands", ""]
    for pinned, local in SCANS.items():
        path = raw_dir / local
        earlier = (record.get("scans") or {}).get(pinned)
        if not path.exists():
            origin = "**none**: no scan this build and none landed before"
            print(f"::warning title=No {local} this build::the build lands none")
        elif earlier and _sha256(path) == earlier["sha256"]:
            origin = f"the last landed scan, from raw_run `{earlier['raw_run']}`"
            if record.get("extracts") == "complete":
                print(f"::warning title={local} kept from raw_run {earlier['raw_run']}::this build's scan was refused or failed")
        else:
            origin = "this build's scan of the extracts"
        lines.append(f"- `{pinned}`: {origin}{_counted(path)}")
    print("\n".join(lines))
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as page:
            page.write("\n".join(lines) + "\n\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    pull = commands.add_parser("pull", help="the copies into --raw-dir/osm/, and the last landed scans at their paths")
    pull.add_argument("--lane", default="monthly", help="the lane whose store holds the copies")
    pull.add_argument("--bucket-url", required=True, help="the lane's raw store, as extract/_run.py was given it")
    pull.add_argument("--steps-url", required=True, help="the step cache, whose raw_inputs/ pins hold the last landed scans")
    pull.add_argument("--raw-run", required=True, help="this build's raw_run: only earlier pins are looked through")
    pull.add_argument("--raw-dir", required=True, help="pipeline/data/raw, or where the build keeps it")
    pull.add_argument("--summary", help="a file to append the run summary's lines to ($GITHUB_STEP_SUMMARY)")
    pull.add_argument("--github-output", help="a file to append `extracts=complete|partial|none` to ($GITHUB_OUTPUT)")
    landed = commands.add_parser("landed", help="say which water scans the build lands, after its scans")
    landed.add_argument("--raw-dir", required=True)
    landed.add_argument("--summary", help="a file to append the run summary's lines to ($GITHUB_STEP_SUMMARY)")
    args = parser.parse_args(argv)
    return _pull_command(args) if args.command == "pull" else _landed_command(args)


if __name__ == "__main__":
    sys.exit(main())
