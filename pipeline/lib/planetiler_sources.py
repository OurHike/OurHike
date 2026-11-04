"""The three files Planetiler's OpenMapTiles profile reads besides the OSM
extract, and how build-basemap.yml makes sure they are on disk before the
build asks for them (#1970).

WHY THIS FETCHES THEM AND PLANETILER DOES NOT. Read from Planetiler v0.10.2,
the jar build-basemap.yml pins:

- With `--download`, a profile source is queued for download only when its
  file is missing or `refresh_<name>` is set (Planetiler.java, lines 1104
  to 1107).
- Every queued source then gets a fixed 10-second wait for its size before
  anything downloads (Downloader.java line 177,
  `item.metadata.get(10, TimeUnit.SECONDS)`). That wait does not read
  `--http-timeout`, which only times the request itself (line 344).

Measured 2026-11-03: build-basemap.yml runs 57 and 58 both died in that wait,
on osmdata.openstreetmap.de's water polygons ("Error getting size of ...
TimeoutException"), 12 to 19 minutes into the run, after the 14 state
extracts had been fetched and clipped. Run 55, the same morning, had fetched
all three in 42 s.

So fetch_planetiler_sources.py runs before the build: it keeps each file the
Actions cache restored, fetches one that is missing or older than
MAX_AGE_DAYS with lib/http_retry.py's retries, and keeps an older copy when
a refetch fails. With all three present Planetiler queues nothing and sends
no request to any of their hosts. planetiler_args() points the build at
these exact paths, so a future jar whose defaults move cannot quietly look
somewhere else and fetch for itself.

NOT A SAFETY PATH. These are the basemap's coastline, lakes and small-scale
context. A stale copy draws water a month out of date at basemap zooms, and
a bad file fails Planetiler loudly rather than drawing wrong water.
"""

from __future__ import annotations

import json
import os
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

from lib.atomic_write import write_text_atomically
from lib.http_retry import download_with_retry

#: Where Planetiler looks for its profile sources when run from pipeline/
#: (its own `download_dir=data/sources`, read from run 58's argument dump),
#: and the directory build-basemap.yml restores and saves.
SOURCES_DIR = Path(__file__).resolve().parent.parent / "data" / "sources"

#: One small JSON file beside the sources, saying what each one is and when
#: it was fetched. A file it does not vouch for is fetched again.
MANIFEST_NAME = "planetiler_sources.json"

#: @unvalidated - picked, and nobody has checked it. A source older than
#: this is fetched again; younger, it is used as it is. What would settle
#: it: how much the water polygons and Natural Earth change between basemap
#: builds at the zooms this basemap ships (BASEMAP.md), which nobody has
#: measured. The lake centerlines URL names a fixed release (v12), so a
#: refetch of that one changes nothing; it is refetched anyway, because one
#: rule for all three is simpler than a rule per source and costs 80M.
MAX_AGE_DAYS = 30

#: @unvalidated - picked. requests' connect and per-read timeout for each
#: attempt; download_with_retry's own 600 s default would let a host that
#: never answers hold a run for about half an hour across its three
#: attempts, which is worse than the 12 to 19 minutes this exists to cut.
#: 120 s is four times Planetiler's own 30 s request timeout, which all
#: three hosts met in run 55, and twelve times the 10 s size wait that
#: osmdata.openstreetmap.de missed. It bounds a silent host at about 6.5 minutes:
#: three 120 s attempts plus the 5 s and 30 s backoffs. What would settle
#: it: how long osmdata.openstreetmap.de takes to answer on a bad day, which
#: nobody has measured past "more than 10 s" (runs 57 and 58, and PR #1978's
#: spike run on 2026-11-04).
SOURCE_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class Source:
    """One profile source: `name` is Planetiler's own argument prefix
    (`--<name>_path`, `--<name>_url`), `filename` the file it reads."""

    name: str
    url: str
    filename: str


#: Planetiler v0.10.2's own defaults for the OpenMapTiles profile, measured
#: from run 58's argument dump (2026-11-03): `<name>_url` and `<name>_path`.
#: Run 55 reported their sizes as 931M, 434M and 80M.
SOURCES = (
    Source(
        "water_polygons",
        "https://osmdata.openstreetmap.de/download/water-polygons-split-3857.zip",
        "water-polygons-split-3857.zip",
    ),
    Source(
        "natural_earth",
        "https://naciscdn.org/naturalearth/packages/natural_earth_vector.sqlite.zip",
        "natural_earth_vector.sqlite.zip",
    ),
    Source(
        "lake_centerlines",
        "https://github.com/acalcutt/osm-lakelines/releases/download/v12/lake_centerline.shp.zip",
        "lake_centerline.shp.zip",
    ),
)


class SourceUnavailable(RuntimeError):
    """A source is missing, could not be fetched, and has no older copy."""


@dataclass(frozen=True)
class Outcome:
    """What happened to one source: `kept` (fresh enough), `fetched`, or
    `kept_stale` (a refetch failed and the older copy stands)."""

    name: str
    action: str
    detail: str


def planetiler_args(sources_dir: Path = SOURCES_DIR) -> list[str]:
    """`--<name>_path` and `--<name>_url` for each source, so the build reads
    the files ensure_sources() put in place."""
    args: list[str] = []
    for source in SOURCES:
        args.append(f"--{source.name}_path={sources_dir / source.filename}")
        args.append(f"--{source.name}_url={source.url}")
    return args


def _read_manifest(sources_dir: Path) -> dict:
    try:
        return json.loads((sources_dir / MANIFEST_NAME).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_manifest(sources_dir: Path, manifest: dict) -> None:
    write_text_atomically(sources_dir / MANIFEST_NAME, json.dumps(manifest, indent=2, sort_keys=True) + "\n")


#: What a fetch interrupted by a killed job leaves behind: this module's
#: `.incoming` file and download_with_retry's `.part` beside it. Neither is
#: ever read, but the save step runs on always(), so either can end up in
#: a cache entry and come back on the next restore.
LEFTOVER_PATTERNS = ("*.incoming", "*.part", "*.tmp")

#: The failures a fetch is allowed to survive by keeping an older copy:
#: the network (requests' own exceptions), the disk, and an answer that is
#: not a zip archive. Anything else is a bug, and fails the run.
FETCH_FAILURES = (requests.RequestException, OSError, ValueError)


def _vouched_age_days(source: Source, path: Path, entry: dict | None, today: date) -> int | None:
    """Days since `path` was fetched, or None when the manifest cannot vouch
    for it: no file, no entry, another URL, or a size that disagrees."""
    if entry is None or not path.is_file():
        return None
    if entry.get("url") != source.url or entry.get("bytes") != path.stat().st_size:
        return None
    try:
        return (today - date.fromisoformat(entry["fetched"])).days
    except (KeyError, TypeError, ValueError):
        return None


def ensure_sources(
    sources_dir: Path = SOURCES_DIR,
    *,
    today: date,
    max_age_days: int = MAX_AGE_DAYS,
    download: Callable[..., Path] = download_with_retry,
    on_fetched: Callable[[str], None] | None = None,
) -> list[Outcome]:
    """Leave every source on disk and vouched for, fetching only what is
    missing or at least `max_age_days` old.

    A refetch that fails keeps the older copy (`kept_stale`). A source with
    no copy that cannot be fetched raises SourceUnavailable, but only after
    the others have been tried, so whatever did arrive can still be saved.
    `on_fetched(name)` runs as each fetch lands, which is how the CLI tells
    the workflow there is something new to save even when a later source
    fails. A download that is not a zip archive never replaces anything.
    """
    sources_dir.mkdir(parents=True, exist_ok=True)
    for pattern in LEFTOVER_PATTERNS:
        for leftover in sources_dir.glob(pattern):
            leftover.unlink(missing_ok=True)
    manifest = _read_manifest(sources_dir)
    outcomes: list[Outcome] = []
    unavailable: list[str] = []

    for source in SOURCES:
        path = sources_dir / source.filename
        entry = manifest.get(source.name)
        age = _vouched_age_days(source, path, entry, today)
        if age is not None and age < max_age_days:
            outcomes.append(Outcome(source.name, "kept", f"fetched {entry['fetched']}, {age} days ago"))
            continue

        incoming = path.with_name(path.name + ".incoming")
        try:
            download(source.url, incoming, label=source.name, timeout=SOURCE_TIMEOUT_SECONDS)
            if not zipfile.is_zipfile(incoming):
                raise ValueError(f"{source.url} did not answer with a zip archive")
            incoming.replace(path)
        except FETCH_FAILURES as error:
            incoming.unlink(missing_ok=True)
            if age is not None:
                outcomes.append(
                    Outcome(
                        source.name,
                        "kept_stale",
                        f"refetch failed ({error}); keeping the copy fetched {entry['fetched']}, {age} days ago",
                    )
                )
                continue
            unavailable.append(f"{source.name}: {source.url} could not be fetched and no earlier copy is cached ({error})")
            continue

        manifest[source.name] = {"url": source.url, "bytes": path.stat().st_size, "fetched": today.isoformat()}
        _write_manifest(sources_dir, manifest)
        outcomes.append(Outcome(source.name, "fetched", f"{path.stat().st_size:,} bytes from {source.url}"))
        if on_fetched is not None:
            on_fetched(source.name)

    if unavailable:
        raise SourceUnavailable("; ".join(unavailable))
    return outcomes


def github_output_marker(output_path: str | None = None) -> Callable[[str], None]:
    """An `on_fetched` that writes `fetched=true` to the step's
    $GITHUB_OUTPUT once, so the save step runs only when something new
    landed. Outside Actions there is no such file and it does nothing."""
    target = output_path if output_path is not None else os.environ.get("GITHUB_OUTPUT")
    written = False

    def mark(_name: str) -> None:
        nonlocal written
        if target and not written:
            with open(target, "a") as handle:
                handle.write("fetched=true\n")
            written = True

    return mark
