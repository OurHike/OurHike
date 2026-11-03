"""hand_off: hand an hourly build's warehouse to the run that checks it, through the leg's history store.

    python hand_off.py put --url URL --warehouse W --run RUN [--attempt N] [--commit SHA]
    python hand_off.py take --url URL --warehouse W --run RUN [--commit SHA]

publish-conditions.yml's dbt path builds and publishes; check-conditions.yml,
which it starts once its build has published, runs Elementary's checks over
that build's warehouse (build_marts.py's docstring, "THE HOURLY LANE'S CHECKS
RUN APART"). The two run on different runners, so the warehouse crosses
between them here. `put`, after the build's publish, writes it under the
leg's history store, the private raw store's history/conditions_<leg>/, which
both jobs already hold the key to:

    checks/warehouse.duckdb.gz  the newest build's warehouse, gzipped, overwritten by each build
    checks/hand_off.json        which run put it, from which commit, the sizes and sha256s of both: written last

and `take`, in the checks run, reads it back for the run it was asked to
check, refusing a warehouse another run put, and checking the upload's
sha256 before it unpacks it and the warehouse's after.

GZIPPED, at level 1, because most of a warehouse's bytes are the unused
part of DuckDB's blocks, a few per table. Measured 2026-10-09 in the shared
sandbox on the fixtures' hourly warehouse (701 raw tables, 11,446 raw rows,
built by `build_marts.py --lane hourly`): 257,699,840 bytes went to
6,074,009 in 0.65 s and came back in 0.51 s (level 6: 4,518,816 in 1.48 s).
A real leg reads 276 raw tables (run 593's log: 12, 263 and the registry's
1) and much more geometry, which compresses less, so its upload is larger
than the fixtures' and its size is @unvalidated until this file's own log
line on the first dispatch says it.

THE CHECKS RUN THE BUILD'S OWN COMMIT, OR NONE. check-conditions.yml is
dispatched on a branch, and GitHub runs it from that branch's newest commit,
which a push between the build and its checks makes a later one than the
build's. Its checks would then parse a project the warehouse was not built
from, and a check of a model added or changed in between would error or
read the old table, on a page that says what the data is. So `put` records
the build's commit and `take`, given the checkout's, finds nothing to check
when they differ (Reasoned; how often a push lands in those few minutes is
not measured): that hour keeps the last data-quality file, whose
`built_at` says how old it is.

NOT AN ACTIONS ARTIFACT. Downloading one needs read access to the
repository and nothing more ("Read access to the repository is required to
perform these steps", GitHub's docs, "Downloading workflow artifacts", read
2026-10-08), and every GitHub account has read access to a public
repository, so an artifact here is a publication for as long as it lasts
(Reasoned). The warehouse holds every raw table the leg read, those of
sources the registry holds back among them, and OurHike's own reports:
the data-quality rule "no row leaves the warehouse" reaches it. The history store
is private, and already holds the snapshots of every mart row.

ONE COPY A LEG, OVERWRITTEN EACH BUILD, so nothing piles up. The checks run
waits for nothing to be uploaded, and shares no concurrency group with the
build (row_history.py, "TWO WRITERS, ONE POINTER"; #1513 — A queued publish
is silently cancelled when another one joins publish-data, and it looks like
a green build), so the next hourly build's `put` can land at any point of a
take. A checks run that starts after a later build has put its own finds
that build's run in hand_off.json and stops, exit NOT_HANDED_OFF, rather than
checking the wrong hour; and one whose download no longer matches
hand_off.json reads it again, and stops the same way when it now names a
later put, so a replacement is never reported as a torn upload.

EXITS. 0 when the warehouse moved and both sha256s matched; NOT_HANDED_OFF (4)
from `take` when nothing at the store is the asked run's, or it is but
from another commit, which check-conditions.yml reads as "this leg's build
left nothing to check" (an exporters-path leg, a build that failed before
its put, or a push since the build); STALE (5) in place of 4 when
--max-age-hours is given and the store's newest put is older than that, or
there is none; 1 for anything else, a store that cannot be read, a torn
upload, a warehouse still holding a write-ahead log.

ONE HOUR WITHOUT ONE IS A WARNING, NONE IN 2.5 HOURS IS RED (the
maintainer, 2026-10-15: "Red if none in 2.5 h"). Every hour
that takes nothing reads green on its own, and the soak's routine reads only
red or green, so eight hours of soak runs 666 to 676 compared nothing and
looked clean. So check-conditions.yml passes gate_report.py's
SOAK_MAX_GAP_HOURS, the soak's allowed gap, as --max-age-hours to both takes, and
an hour whose store's newest warehouse or bundle is older than that, or that
holds none, goes red. With the soak's hourly runs, 55.6 to 63.0 minutes
apart (gate_report.py's measurement), the newest put is about an hour old
after one hour without one and about two after two, so it is the third such
hour in a row that goes red, or the second when the hours drift half an
hour apart (Reasoned).

THE HOUR'S COMPARISON TAKES A BUNDLE, NOT THE WAREHOUSE (the maintainer,
2026-10-10: "Compare every soak hour"):

    python hand_off.py put-bundle --url URL --bundle DIR --run RUN [--attempt N] [--commit SHA]
    python hand_off.py take-bundle --url URL --out DIR --run RUN [--commit SHA]

hourly_parity.py's bundle, the answers today's exporters need and the six
files the writers wrote, 1,632,706 bytes gzipped in soak run 653 (2026-10-11)
where run 676's warehouse was 3,055,300,608 bytes (2026-10-15; both their
logs), goes beside the warehouse with a pointer of its own:

    checks/parity_inputs.json.gz  every file of the bundle, as one gzipped JSON document {path: text}
    checks/parity_inputs.json     which run put it, from which commit, its size and sha256: written last

The same rules as the warehouse's, on their own pointer, so neither can make
the other's take fail: one copy a leg, overwritten each build; `take-bundle`
finds nothing to compare (NOT_HANDED_OFF) for another run's or another
commit's bundle, and answers a later put landing mid-download the same way.
The publish job puts it BEFORE the warehouse, in the same step and under a
ceiling of its own, because it is about 2 s against the warehouse's 27 to 72 s
(the UA soak runs of 2026-10-10 to 2026-10-15, Measured from their logs), and
none of the eight soak runs 666 to 676 put one while it came second; the
warehouse then gets what the job has left (publish-conditions.yml's "Hand this
build's warehouse to its checks" has the figures). A bundle is text alone, and a
path in it that is absolute or climbs out of the directory is refused rather
than written. It holds rows, so purge_person_fields.py unpacks
it and reads each of its files' keys (read_bundle()), as it reads the
warehouse beside it, and deletes the two together.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from row_history import Refused, Store, _sha256

FOLDER = "checks"
WAREHOUSE = f"{FOLDER}/warehouse.duckdb.gz"
POINTER = f"{FOLDER}/hand_off.json"
FORMAT = 1
#: The module docstring, "GZIPPED": the fastest level, which already takes the empty blocks out.
GZIP_LEVEL = 1
CHUNK = 1 << 20
#: `take`'s exit when no warehouse at the store is the asked run's: something to say, not a failure of this file's.
NOT_HANDED_OFF = 4
#: In place of NOT_HANDED_OFF, under --max-age-hours, when the store's newest put is older than that or there is none:
#: the module docstring, "ONE HOUR WITHOUT ONE IS A WARNING, NONE IN 2.5 HOURS IS RED".
STALE = 5
#: The module docstring, "THE HOUR'S COMPARISON TAKES A BUNDLE".
BUNDLE = f"{FOLDER}/parity_inputs.json.gz"
BUNDLE_POINTER = f"{FOLDER}/parity_inputs.json"
BUNDLE_FORMAT = 1
#: The bundle's files are text, compressed at gzip's default level: a few megabytes, where the warehouse's level 1
#: buys time on gigabytes (GZIP_LEVEL).
BUNDLE_GZIP_LEVEL = 6
#: A bundle path: relative, made of these characters alone, and never `..` (bundle_files()).
BUNDLE_PATH = re.compile(r"[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*")


class NotHandedOff(Exception):
    """No warehouse at the store is the asked run's. `put_at` is when the store's newest one was put, None when it holds
    none (the module docstring, "ONE HOUR WITHOUT ONE IS A WARNING")."""

    def __init__(self, message: str, put_at: str | None = None):
        super().__init__(message)
        self.put_at = put_at


def put(url: str, warehouse: Path, run: str, attempt: str = "1", commit: str | None = None) -> str:
    """Checkpoint the warehouse, so the one file is the whole database, upload it gzipped, then write hand_off.json
    naming `run` and the `commit` it was built from. Returns what it did, for the log."""
    started = time.monotonic()
    if not warehouse.is_file():
        raise Refused(f"there is no warehouse at {warehouse} to hand off")
    with duckdb.connect(str(warehouse)) as con:
        con.execute("checkpoint")
    wal = warehouse.with_name(warehouse.name + ".wal")
    if wal.exists() and wal.stat().st_size:
        raise Refused(f"{wal} still holds a write-ahead log after a checkpoint, so {warehouse} alone is not the database")
    store = Store(url)
    store.check_reachable()
    size, digest = warehouse.stat().st_size, _sha256(warehouse)
    with tempfile.TemporaryDirectory(dir=warehouse.parent) as scratch:
        packed = Path(scratch) / "warehouse.duckdb.gz"
        _pack(warehouse, packed)
        packed_size, packed_digest = packed.stat().st_size, _sha256(packed)
        store.put(packed, WAREHOUSE)
    pointer = {
        "format": FORMAT,
        "run": run,
        "attempt": attempt,
        "commit": commit,
        "bytes": size,
        "sha256": digest,
        "gzip_bytes": packed_size,
        "gzip_sha256": packed_digest,
        "put_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    store.write_text(POINTER, json.dumps(pointer, indent=2, sort_keys=True) + "\n")
    return (
        f"handed run {run}.{attempt}'s warehouse, {size} bytes, {packed_size} gzipped, to {url}/{FOLDER}/, in "
        f"{time.monotonic() - started:.2f} s"
    )


def _pack(source: Path, packed: Path) -> None:
    with source.open("rb") as raw, gzip.GzipFile(packed, "wb", compresslevel=GZIP_LEVEL, mtime=0) as out:
        shutil.copyfileobj(raw, out, CHUNK)


def _unpack(packed: Path, target: Path) -> None:
    with gzip.open(packed, "rb") as raw, target.open("wb") as out:
        shutil.copyfileobj(raw, out, CHUNK)


def _refuse_if_replaced(store: Store, url: str, run: str, pointer: dict) -> None:
    """NotHandedOff when hand_off.json no longer names the put this take began from: a later build's put landed while
    it downloaded (the module docstring, "ONE COPY A LEG"). Returns when it still does, which is an upload that tore.

    Read once, straight after the download: a put writes hand_off.json just after its upload, and the take's download
    and hash outlast that gap (Reasoned; neither time is measured on R2)."""
    text = store.read_text(POINTER)
    now = json.loads(text) if text is not None else {}
    if str(now.get("run")) != str(run) or now.get("gzip_sha256") != pointer.get("gzip_sha256"):
        raise NotHandedOff(
            f"{url}/{FOLDER}/ now holds run {now.get('run')}'s warehouse, put at {now.get('put_at')}: a later build "
            f"replaced run {run}'s while this take was downloading it, so nothing is checked this hour",
            now.get("put_at"),
        )


def take(url: str, warehouse: Path, run: str, commit: str | None = None) -> str:
    """Download the warehouse `run` put, into `warehouse`: the upload checked against its size and sha256 before it is
    unpacked, and the warehouse after. Returns what it did, for the log; raises NotHandedOff when no warehouse at the store is `run`'s, or when it was built from a commit
    other than `commit`, the checkout's (the module docstring, "THE CHECKS RUN THE BUILD'S OWN COMMIT, OR NONE")."""
    started = time.monotonic()
    store = Store(url)
    store.check_reachable()
    text = store.read_text(POINTER)
    if text is None:
        raise NotHandedOff(f"no build has handed a warehouse to {url}/{FOLDER}/")
    pointer = json.loads(text)
    if pointer.get("format") != FORMAT:
        raise Refused(f"{url}/{POINTER} is format {pointer.get('format')!r}; this file reads format {FORMAT}")
    if str(pointer.get("run")) != str(run):
        raise NotHandedOff(
            f"{url}/{FOLDER}/ holds run {pointer.get('run')}'s warehouse, put at {pointer.get('put_at')}, not run {run}'s",
            pointer.get("put_at"),
        )
    if commit and pointer.get("commit") and pointer["commit"] != commit:
        raise NotHandedOff(
            f"run {run}'s build ran on {pointer['commit'][:12]} and this checkout is {commit[:12]}, so its checks would "
            "parse a project the warehouse was not built from: nothing is checked this hour",
            pointer.get("put_at"),
        )
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=warehouse.parent) as scratch:
        packed = Path(scratch) / "warehouse.duckdb.gz"
        store.get(WAREHOUSE, packed, POINTER)
        if (size := packed.stat().st_size) != pointer["gzip_bytes"] or _sha256(packed) != pointer["gzip_sha256"]:
            _refuse_if_replaced(store, url, run, pointer)
            raise Refused(
                f"{url}/{WAREHOUSE} is {size} bytes, and {POINTER} says {pointer['gzip_bytes']} with sha256 "
                f"{pointer['gzip_sha256']}: a later build's upload landed, or this one tore. Nothing was checked."
            )
        local = Path(scratch) / warehouse.name
        _unpack(packed, local)
        if (size := local.stat().st_size) != pointer["bytes"] or (digest := _sha256(local)) != pointer["sha256"]:
            raise Refused(
                f"the warehouse unpacked from {url}/{WAREHOUSE} is {size} bytes, and {POINTER} says {pointer['bytes']} "
                f"with sha256 {pointer['sha256']}. Nothing was checked."
            )
        warehouse.unlink(missing_ok=True)
        shutil.move(str(local), str(warehouse))
    return (
        f"took run {run}.{pointer.get('attempt')}'s warehouse, {pointer['bytes']} bytes from {pointer['gzip_bytes']} "
        f"gzipped, sha256 {digest}, put at {pointer.get('put_at')}, from {url}/{FOLDER}/, in "
        f"{time.monotonic() - started:.2f} s"
    )


def bundle_files(folder: Path) -> dict[str, str]:
    """{path under `folder`: its text} for every file in it, refusing a path BUNDLE_PATH does not allow."""
    files = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            relative = path.relative_to(folder).as_posix()
            if not BUNDLE_PATH.fullmatch(relative) or ".." in relative.split("/"):
                raise Refused(f"{relative} is not a path a bundle may carry")
            files[relative] = path.read_text(encoding="utf-8")
    return files


def put_bundle(url: str, folder: Path, run: str, attempt: str = "1", commit: str | None = None) -> str:
    """hourly_parity.py's bundle in `folder`, as one gzipped document under the store, then its pointer naming `run` and
    `commit`. Returns what it did, for the log."""
    started = time.monotonic()
    if not folder.is_dir():
        raise Refused(f"there is no bundle at {folder} to hand on")
    files = bundle_files(folder)
    store = Store(url)
    store.check_reachable()
    with tempfile.TemporaryDirectory() as scratch:
        packed = Path(scratch) / "parity_inputs.json.gz"
        text = json.dumps({"format": BUNDLE_FORMAT, "files": files}, sort_keys=True, ensure_ascii=False)
        with gzip.GzipFile(packed, "wb", compresslevel=BUNDLE_GZIP_LEVEL, mtime=0) as out:
            out.write(text.encode("utf-8"))
        packed_size, packed_digest = packed.stat().st_size, _sha256(packed)
        store.put(packed, BUNDLE)
    pointer = {
        "format": BUNDLE_FORMAT,
        "run": run,
        "attempt": attempt,
        "commit": commit,
        "files": len(files),
        "gzip_bytes": packed_size,
        "gzip_sha256": packed_digest,
        "put_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    store.write_text(BUNDLE_POINTER, json.dumps(pointer, indent=2, sort_keys=True) + "\n")
    return (
        f"handed run {run}.{attempt}'s comparison bundle, {len(files)} files, {packed_size} bytes gzipped, to "
        f"{url}/{FOLDER}/, in {time.monotonic() - started:.2f} s"
    )


def take_bundle(url: str, out: Path, run: str, commit: str | None = None) -> str:
    """The bundle `run` put, unpacked under `out`, its upload checked against its size and sha256 first. Raises
    NotHandedOff when the store holds another run's or another commit's bundle, or none."""
    started = time.monotonic()
    store = Store(url)
    store.check_reachable()
    text = store.read_text(BUNDLE_POINTER)
    if text is None:
        raise NotHandedOff(f"no build has handed a comparison bundle to {url}/{FOLDER}/")
    pointer = json.loads(text)
    if pointer.get("format") != BUNDLE_FORMAT:
        raise Refused(f"{url}/{BUNDLE_POINTER} is format {pointer.get('format')!r}; this file reads format {BUNDLE_FORMAT}")
    if str(pointer.get("run")) != str(run):
        raise NotHandedOff(
            f"{url}/{FOLDER}/ holds run {pointer.get('run')}'s comparison bundle, put at {pointer.get('put_at')}, not run {run}'s",
            pointer.get("put_at"),
        )
    if commit and pointer.get("commit") and pointer["commit"] != commit:
        raise NotHandedOff(
            f"run {run}'s bundle was built on {pointer['commit'][:12]}, not this checkout's {commit[:12]}", pointer.get("put_at")
        )
    with tempfile.TemporaryDirectory() as scratch:
        packed = Path(scratch) / "parity_inputs.json.gz"
        store.get(BUNDLE, packed, BUNDLE_POINTER)
        if (size := packed.stat().st_size) != pointer["gzip_bytes"] or _sha256(packed) != pointer["gzip_sha256"]:
            now = json.loads(store.read_text(BUNDLE_POINTER) or "{}")
            if str(now.get("run")) != str(run) or now.get("gzip_sha256") != pointer.get("gzip_sha256"):
                raise NotHandedOff(f"a later build replaced run {run}'s bundle while it was being taken", now.get("put_at"))
            raise Refused(f"{url}/{BUNDLE} is {size} bytes, and {BUNDLE_POINTER} says {pointer['gzip_bytes']}: it tore")
        with gzip.open(packed, "rb") as raw:
            document = json.loads(raw.read().decode("utf-8"))
    if document.get("format") != BUNDLE_FORMAT:
        raise Refused(f"{url}/{BUNDLE} is format {document.get('format')!r}; this file reads format {BUNDLE_FORMAT}")
    if out.exists():
        shutil.rmtree(out)
    for relative, body in sorted(document["files"].items()):
        if not BUNDLE_PATH.fullmatch(relative) or ".." in relative.split("/"):
            raise Refused(f"{url}/{BUNDLE} names {relative!r}, which is not a path a bundle may carry; nothing was written")
    for relative, body in sorted(document["files"].items()):
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return (
        f"took run {run}.{pointer.get('attempt')}'s comparison bundle, {len(document['files'])} files from "
        f"{pointer['gzip_bytes']} bytes gzipped, put at {pointer.get('put_at')}, in {time.monotonic() - started:.2f} s"
    )


MAX_AGE_HELP = (
    "with nothing of --run's to take: exit STALE, not NOT_HANDED_OFF, when the store's newest put is older than this "
    "many hours or there is none (check-conditions.yml passes gate_report.py's SOAK_MAX_GAP_HOURS)"
)


def nothing_or_stale(nothing: NotHandedOff, max_age_hours: float | None, what: str, now: datetime | None = None) -> int:
    """NOT_HANDED_OFF, or STALE when `max_age_hours` is given and the store's newest `what` is older than that, or the
    store holds none or one it cannot date (the module docstring, "ONE HOUR WITHOUT ONE IS A WARNING")."""
    if max_age_hours is None:
        return NOT_HANDED_OFF
    try:
        put_at = datetime.fromisoformat(str(nothing.put_at).replace("Z", "+00:00")) if nothing.put_at else None
    except ValueError:
        put_at = None
    if put_at is not None and put_at.tzinfo is not None:
        hours = ((now or datetime.now(UTC)) - put_at).total_seconds() / 3600
        if hours <= max_age_hours:
            print(
                f"hand_off: the store's newest {what} was put {hours:.1f} h ago, inside {max_age_hours:g} h, so this "
                "hour is a warning and not red",
                flush=True,
            )
            return NOT_HANDED_OFF
        said = f"its newest was put {hours:.1f} h ago, at {nothing.put_at}"
    else:
        said = "it holds none" if not nothing.put_at else f"its newest one's put_at, {nothing.put_at!r}, cannot be read"
    print(
        f"::error title=No {what} handed off for over {max_age_hours:g} h::the leg's history store has had no {what} "
        f"put in the last {max_age_hours:g} hours: {said}. Each hour without one alone is a warning; this many in a "
        "row is a soak that compares or checks nothing, so this run goes red.",
        flush=True,
    )
    return STALE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_ in (("put", "hand this build's warehouse on"), ("take", "take the warehouse a build handed on")):
        command = commands.add_parser(name, help=help_)
        command.add_argument("--url", required=True, help="the leg's history store, as build_marts.py's --history-url")
        command.add_argument("--warehouse", required=True, type=Path)
        command.add_argument("--run", required=True, help="the publish-conditions.yml run whose build it is")
        command.add_argument("--commit", help="put: the commit the build ran on; take: the checkout's, which must match")
        if name == "put":
            command.add_argument("--attempt", default="1", help="that run's attempt, for the log")
        else:
            command.add_argument("--max-age-hours", type=float, help=MAX_AGE_HELP)
    for name, help_ in (
        ("put-bundle", "hand this build's comparison bundle on (hourly_parity.py bundle)"),
        ("take-bundle", "take the comparison bundle a build handed on"),
    ):
        command = commands.add_parser(name, help=help_)
        command.add_argument("--url", required=True, help="the leg's history store, as build_marts.py's --history-url")
        command.add_argument("--run", required=True, help="the publish-conditions.yml run whose build it is")
        command.add_argument("--commit", help="put-bundle: the commit the build ran on; take-bundle: the checkout's")
        if name == "put-bundle":
            command.add_argument("--bundle", required=True, type=Path, help="hourly_parity.py bundle's --out")
            command.add_argument("--attempt", default="1", help="that run's attempt, for the log")
        else:
            command.add_argument("--out", required=True, type=Path, help="where the bundle's files are written")
            command.add_argument("--max-age-hours", type=float, help=MAX_AGE_HELP)
    args = parser.parse_args(argv)
    if args.command in ("put-bundle", "take-bundle"):
        # A bundle that does not move costs this hour its comparison and nothing else: a warning, and the job that
        # compares says the hour was not compared (hourly_parity.py). Never the warehouse's ::error.
        try:
            if args.command == "put-bundle":
                message = put_bundle(args.url, args.bundle, args.run, args.attempt, args.commit)
            else:
                message = take_bundle(args.url, args.out, args.run, args.commit)
        except NotHandedOff as nothing:
            print(f"hand_off: {nothing}", flush=True)
            return nothing_or_stale(nothing, args.max_age_hours if args.command == "take-bundle" else None, "comparison bundle")
        except Exception as failed:  # noqa: BLE001 - any failure here is this hour's comparison's, said by name
            print(f"::warning title=Comparison bundle not moved::{type(failed).__name__}: {failed}", flush=True)
            return 1
        print(f"hand_off: {message}", flush=True)
        return 0
    try:
        if args.command == "put":
            message = put(args.url, args.warehouse, args.run, args.attempt, args.commit)
        else:
            message = take(args.url, args.warehouse, args.run, args.commit)
    except NotHandedOff as nothing:
        print(f"hand_off: {nothing}", flush=True)
        return nothing_or_stale(nothing, args.max_age_hours if args.command == "take" else None, "warehouse")
    except Refused as refused:
        print(f"::error title=Warehouse not handed off::{refused}", flush=True)
        return 1
    print(f"hand_off: {message}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
