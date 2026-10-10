"""hand_off: hand an hourly build's warehouse to the run that checks it, through the leg's history store (decision 110).

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
decision 102's "no row leaves the warehouse" reaches it. The history store
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
its put, or a push since the build); 1 for anything
else, a store that cannot be read, a torn upload, a warehouse still holding
a write-ahead log.
"""

from __future__ import annotations

import argparse
import gzip
import json
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


class NotHandedOff(Exception):
    """No warehouse at the store is the asked run's."""


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
            f"replaced run {run}'s while this take was downloading it, so nothing is checked this hour"
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
            f"{url}/{FOLDER}/ holds run {pointer.get('run')}'s warehouse, put at {pointer.get('put_at')}, not run {run}'s"
        )
    if commit and pointer.get("commit") and pointer["commit"] != commit:
        raise NotHandedOff(
            f"run {run}'s build ran on {pointer['commit'][:12]} and this checkout is {commit[:12]}, so its checks would "
            "parse a project the warehouse was not built from: nothing is checked this hour"
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
    args = parser.parse_args(argv)
    try:
        if args.command == "put":
            message = put(args.url, args.warehouse, args.run, args.attempt, args.commit)
        else:
            message = take(args.url, args.warehouse, args.run, args.commit)
    except NotHandedOff as nothing:
        print(f"hand_off: {nothing}", flush=True)
        return NOT_HANDED_OFF
    except Refused as refused:
        print(f"::error title=Warehouse not handed off::{refused}", flush=True)
        return 1
    print(f"hand_off: {message}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
