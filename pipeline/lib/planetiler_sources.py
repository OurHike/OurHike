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

So fetch_planetiler_sources.py runs before the build, and ensure_sources()
leaves all three on disk. With all three present Planetiler queues nothing
and sends no request to any of their hosts. planetiler_args() points the
build at these exact paths, so a future jar whose defaults move cannot
quietly look somewhere else and fetch for itself.

WHERE EACH SOURCE COMES FROM: the first of these with a copy younger than
MAX_AGE_DAYS.

1. The Actions cache's copy, which build-basemap.yml restores into
   SOURCES_DIR.
2. The raw bucket's copy, under BUCKET_PREFIX in the private our-hike-raw
   bucket (ensure_sources()'s `copy`; fetch_planetiler_sources.py's
   RawBucketCopy). The cache alone was not enough: GitHub drops an entry
   nobody has used for 7 days, and the basemap's runs from 2026-09-24 to
   2026-11-04 left gaps of 8, 16 and 9 days, so a run would often start
   with nothing to fall back on. PR #1978's review raised it (finding 1),
   and the maintainer chose the bucket copy on 2026-11-04.
3. The source's own host, with lib/http_retry.py's retries.

When the host fails too, the newer of the two older copies stands. A copy
counts only when its manifest entry names this URL and its file's size
matches that entry, and nothing replaces a file unless it is a zip archive:
the same checks for a file from the bucket as for one from a host. Once
every source is settled, each one the bucket lacks, or holds an older copy
of, is uploaded, and the bucket's manifest is written last, so the next run
that finds the cache empty reads the bucket and asks no third party.

A bucket that cannot be read or written costs a warning, never the run. A
bucket whose manifest could not be read is not written either, so a read
that failed cannot drop the entries it did not see.

NOT A SAFETY PATH. These are the basemap's coastline, lakes and small-scale
context. A stale copy draws water a month out of date at basemap zooms, and
a bad file fails Planetiler loudly rather than drawing wrong water.
"""

from __future__ import annotations

import json
import os
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import requests

from lib.atomic_write import write_text_atomically
from lib.http_retry import download_with_retry

#: Where Planetiler looks for its profile sources when run from pipeline/
#: (its own `download_dir=data/sources`, read from run 58's argument dump),
#: and the directory build-basemap.yml restores and saves.
SOURCES_DIR = Path(__file__).resolve().parent.parent / "data" / "sources"

#: One small JSON file beside the sources, saying what each one is and when
#: it was fetched. A file it does not vouch for is fetched again. The bucket
#: keeps one of the same shape beside its copies.
MANIFEST_NAME = "planetiler_sources.json"

#: The raw bucket's folder for its copy: each source under its own filename,
#: and the bucket's manifest beside them. A top-level folder of its own,
#: because prune_raw_store.py deletes only inside steps/raw_inputs/,
#: steps/dbt_warehouse/, raw/dlt/monthly/as_landed/ and history/, and lists
#: everything else without deleting it.
BUCKET_PREFIX = "planetiler_sources"

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


@dataclass(frozen=True)
class Outcome:
    """What happened to one source, or to the bucket as a whole (`name`
    "raw_bucket"): `kept` (the cache's copy is young enough), `from_bucket`,
    `fetched` (from its host), `kept_stale` (its host failed and an older
    copy stands), `uploaded` (the bucket now holds this run's copy), and the
    two warnings `bucket_unusable` and `upload_failed`."""

    name: str
    action: str
    detail: str


#: The outcomes fetch_planetiler_sources.py prints as warnings.
WARNINGS = frozenset({"kept_stale", "bucket_unusable", "upload_failed"})


class SourceUnavailable(RuntimeError):
    """A source is missing, could not be fetched, and has no older copy.
    `outcomes` says what happened to everything else first."""

    def __init__(self, message: str, outcomes: Iterable[Outcome] = ()):
        super().__init__(message)
        self.outcomes = list(outcomes)


class CopyFailed(RuntimeError):
    """The bucket's copy could not be read or written: its store refused, or
    did not answer."""


class SourceCopy(Protocol):
    """A copy of the sources kept beyond the Actions cache. Each method
    raises CopyFailed when its store fails; read_manifest() answers None when
    the store holds no manifest yet."""

    def read_manifest(self) -> dict | None: ...

    def get(self, filename: str, dest: Path) -> None: ...

    def put(self, path: Path, filename: str) -> None: ...

    def write_manifest(self, manifest: dict) -> None: ...


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
#: `.incoming` file, download_with_retry's `.part` beside it, and boto3's
#: own temporary name for a bucket download, `<file>.incoming.` and 8 hex
#: digits (s3transfer 0.19.2's OSUtils.get_temp_filename()). None is ever
#: read, but the save step runs on always(), so any of them can end up in a
#: cache entry and come back on the next restore.
LEFTOVER_PATTERNS = ("*.incoming", "*.incoming.*", "*.part", "*.tmp")

#: The failures a fetch is allowed to survive by keeping an older copy:
#: the network (requests' own exceptions), the disk, and an answer that is
#: not a zip archive. Anything else is a bug, and fails the run.
FETCH_FAILURES = (requests.RequestException, OSError, ValueError)

#: The failures the bucket's copy may cost a warning rather than the run:
#: its store (CopyFailed), the disk, and a file or manifest that is not what
#: it should be (ValueError). Anything else is a bug, and fails the run.
COPY_FAILURES = (CopyFailed, OSError, ValueError)


def _entry_age_days(source: Source, entry: object, today: date) -> int | None:
    """Days since a manifest entry says `source` was fetched, or None when it
    is no entry for this URL."""
    if not isinstance(entry, dict) or entry.get("url") != source.url or not isinstance(entry.get("bytes"), int):
        return None
    try:
        return (today - date.fromisoformat(entry["fetched"])).days
    except (KeyError, TypeError, ValueError):
        return None


def _vouched_age_days(source: Source, path: Path, entry: dict | None, today: date) -> int | None:
    """Days since `path` was fetched, or None when the manifest cannot vouch
    for it: no file, no entry, another URL, or a size that disagrees."""
    if not path.is_file() or not isinstance(entry, dict) or entry.get("bytes") != path.stat().st_size:
        return None
    return _entry_age_days(source, entry, today)


def _as_entry(entry: dict) -> dict:
    return {"url": entry["url"], "bytes": entry["bytes"], "fetched": entry["fetched"]}


def _read_bucket_manifest(copy: SourceCopy | None, outcomes: list[Outcome]) -> dict | None:
    """The bucket's manifest, {} when it holds none yet, or None when there
    is no bucket or its manifest cannot be read (with a warning)."""
    if copy is None:
        return None
    try:
        held = copy.read_manifest()
        if held is not None and not isinstance(held, dict):
            raise ValueError("it is not a JSON object")
    except COPY_FAILURES as error:
        outcomes.append(
            Outcome(
                "raw_bucket",
                "bucket_unusable",
                f"its manifest could not be read ({error}); nothing is read from it or written to it this run",
            )
        )
        return None
    return {} if held is None else held


def _take_from_bucket(copy: SourceCopy, source: Source, path: Path, held: dict, outcomes: list[Outcome]) -> bool:
    """Put the bucket's copy of `source` at `path` once it passes an upstream
    download's checks: its size is the one its manifest entry gives, and it
    is a zip archive. False, with a warning, when it cannot be used."""
    incoming = path.with_name(path.name + ".incoming")
    try:
        copy.get(source.filename, incoming)
        size = incoming.stat().st_size
        if size != held["bytes"]:
            raise ValueError(f"it is {size:,} bytes and its manifest entry says {held['bytes']:,}")
        if not zipfile.is_zipfile(incoming):
            raise ValueError("it is not a zip archive")
        incoming.replace(path)
    except COPY_FAILURES as error:
        incoming.unlink(missing_ok=True)
        outcomes.append(Outcome(source.name, "bucket_unusable", f"the raw bucket's copy could not be used ({error})"))
        return False
    return True


def _bring_bucket_up_to_date(
    copy: SourceCopy, sources_dir: Path, manifest: dict, held: dict, today: date, outcomes: list[Outcome]
) -> None:
    """Upload each source the bucket lacks, or holds an older copy of, and
    then the bucket's manifest, last, so the bucket never vouches for a file
    before the file is there."""
    changed = False
    for source in SOURCES:
        path = sources_dir / source.filename
        entry = manifest.get(source.name)
        age = _vouched_age_days(source, path, entry, today)
        if age is None:
            continue
        held_age = _entry_age_days(source, held.get(source.name), today)
        if held_age is not None and held_age <= age:
            continue
        try:
            copy.put(path, source.filename)
        except COPY_FAILURES as error:
            outcomes.append(Outcome(source.name, "upload_failed", f"could not be uploaded to the raw bucket ({error})"))
            continue
        held[source.name] = _as_entry(entry)
        changed = True
        outcomes.append(
            Outcome(source.name, "uploaded", f"{entry['bytes']:,} bytes to the raw bucket, fetched {entry['fetched']}")
        )
    if not changed:
        return
    try:
        copy.write_manifest(held)
    except COPY_FAILURES as error:
        outcomes.append(
            Outcome(
                "raw_bucket",
                "upload_failed",
                f"its manifest could not be written ({error}), so it does not vouch for what was uploaded this run",
            )
        )


def ensure_sources(
    sources_dir: Path = SOURCES_DIR,
    *,
    today: date,
    max_age_days: int = MAX_AGE_DAYS,
    download: Callable[..., Path] = download_with_retry,
    on_fetched: Callable[[str], None] | None = None,
    copy: SourceCopy | None = None,
) -> list[Outcome]:
    """Leave every source on disk and vouched for, each from the first of the
    cache, the bucket (`copy`) and its host whose copy is younger than
    `max_age_days` (the module docstring, "WHERE EACH SOURCE COMES FROM").

    A source whose host fails keeps the newer of the cache's and the
    bucket's older copies (`kept_stale`). A source with neither that cannot
    be fetched raises SourceUnavailable, but only after the others have been
    tried and the bucket brought up to date, so whatever did arrive is kept.
    `on_fetched(name)` runs as each file lands from the bucket or a host,
    which is how the CLI tells the workflow there is something new to save
    even when a later source fails. A download that is not a zip archive
    never replaces anything.
    """
    sources_dir.mkdir(parents=True, exist_ok=True)
    for pattern in LEFTOVER_PATTERNS:
        for leftover in sources_dir.glob(pattern):
            leftover.unlink(missing_ok=True)
    manifest = _read_manifest(sources_dir)
    outcomes: list[Outcome] = []
    unavailable: list[str] = []
    in_bucket = _read_bucket_manifest(copy, outcomes)

    def landed(source: Source, entry: dict, outcome: Outcome) -> None:
        manifest[source.name] = entry
        _write_manifest(sources_dir, manifest)
        outcomes.append(outcome)
        if on_fetched is not None:
            on_fetched(source.name)

    for source in SOURCES:
        path = sources_dir / source.filename
        entry = manifest.get(source.name)
        age = _vouched_age_days(source, path, entry, today)
        if age is not None and age < max_age_days:
            outcomes.append(Outcome(source.name, "kept", f"fetched {entry['fetched']}, {age} days ago"))
            continue

        held = (in_bucket or {}).get(source.name)
        held_age = _entry_age_days(source, held, today)
        if held_age is not None and held_age < max_age_days:
            if _take_from_bucket(copy, source, path, held, outcomes):
                detail = f"{held['bytes']:,} bytes from the raw bucket, fetched {held['fetched']}, {held_age} days ago"
                landed(source, _as_entry(held), Outcome(source.name, "from_bucket", detail))
                continue
            held_age = None  # it failed its checks, so it is no fallback either

        incoming = path.with_name(path.name + ".incoming")
        try:
            download(source.url, incoming, label=source.name, timeout=SOURCE_TIMEOUT_SECONDS)
            if not zipfile.is_zipfile(incoming):
                raise ValueError(f"{source.url} did not answer with a zip archive")
            incoming.replace(path)
        except FETCH_FAILURES as error:
            incoming.unlink(missing_ok=True)
            if held_age is not None and (age is None or held_age < age):
                if _take_from_bucket(copy, source, path, held, outcomes):
                    detail = (
                        f"refetch failed ({error}); using the raw bucket's copy fetched {held['fetched']}, {held_age} days ago"
                    )
                    landed(source, _as_entry(held), Outcome(source.name, "kept_stale", detail))
                    continue
            if age is not None:
                detail = f"refetch failed ({error}); keeping the copy fetched {entry['fetched']}, {age} days ago"
                outcomes.append(Outcome(source.name, "kept_stale", detail))
                continue
            unavailable.append(f"{source.name}: {source.url} could not be fetched and there is no earlier copy to keep ({error})")
            continue

        size = path.stat().st_size
        fresh = {"url": source.url, "bytes": size, "fetched": today.isoformat()}
        landed(source, fresh, Outcome(source.name, "fetched", f"{size:,} bytes from {source.url}"))

    if copy is not None and in_bucket is not None:
        _bring_bucket_up_to_date(copy, sources_dir, manifest, in_bucket, today, outcomes)

    if unavailable:
        raise SourceUnavailable("; ".join(unavailable), outcomes)
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
