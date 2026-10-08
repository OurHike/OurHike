"""hand_off: hand an hourly build's warehouse to the run that checks it, through the leg's history store (decision 110).

    python hand_off.py put --url URL --warehouse W --run RUN [--attempt N]
    python hand_off.py take --url URL --warehouse W --run RUN

publish-conditions.yml's dbt path builds and publishes; check-conditions.yml,
which it starts once its build has published, runs Elementary's checks over
that build's warehouse (build_marts.py's docstring, "THE HOURLY LANE'S CHECKS
RUN APART"). The two run on different runners, so the warehouse crosses
between them here. `put`, after the build's publish, writes it under the
leg's history store, the private raw store's history/conditions_<leg>/, which
both jobs already hold the key to:

    checks/warehouse.duckdb   the newest build's warehouse, overwritten by each build
    checks/hand_off.json      which run put it, its size and sha256: written last

and `take`, in the checks run, reads it back for the run it was asked to
check, refusing a warehouse another run put.

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
waits for nothing to be uploaded: publish-conditions.yml's leg and
check-conditions.yml's share the concurrency group conditions-history-<leg>,
so the next hourly build's `put` cannot land while a checks run is still
reading; a checks run that starts after a later build has put its own finds
that build's run in hand_off.json and stops, exit NOT_HANDED_OFF, rather than
checking the wrong hour.

EXITS. 0 when the warehouse moved and its sha256 matched; NOT_HANDED_OFF (4)
from `take` when nothing at the store is the asked run's, which
check-conditions.yml reads as "this leg's build left nothing to check" (an
exporters-path leg, or a build that failed before its put); 1 for anything
else, a store that cannot be read, a torn upload, a warehouse still holding
a write-ahead log.
"""

from __future__ import annotations

import argparse
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
WAREHOUSE = f"{FOLDER}/warehouse.duckdb"
POINTER = f"{FOLDER}/hand_off.json"
FORMAT = 1
#: `take`'s exit when no warehouse at the store is the asked run's: something to say, not a failure of this file's.
NOT_HANDED_OFF = 4


class NotHandedOff(Exception):
    """No warehouse at the store is the asked run's."""


def put(url: str, warehouse: Path, run: str, attempt: str = "1") -> str:
    """Checkpoint the warehouse, so the one file is the whole database, upload it, then write hand_off.json naming
    `run`. Returns what it did, for the log."""
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
    store.put(warehouse, WAREHOUSE)
    pointer = {
        "format": FORMAT,
        "run": run,
        "attempt": attempt,
        "bytes": size,
        "sha256": digest,
        "put_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    store.write_text(POINTER, json.dumps(pointer, indent=2, sort_keys=True) + "\n")
    return f"handed run {run}.{attempt}'s warehouse, {size} bytes, to {url}/{FOLDER}/, in {time.monotonic() - started:.2f} s"


def take(url: str, warehouse: Path, run: str) -> str:
    """Download the warehouse `run` put, into `warehouse`, checked against its size and sha256. Returns what it did,
    for the log; raises NotHandedOff when no warehouse at the store is `run`'s."""
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
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=warehouse.parent) as scratch:
        local = Path(scratch) / warehouse.name
        store.get(WAREHOUSE, local, POINTER)
        if (size := local.stat().st_size) != pointer["bytes"] or (digest := _sha256(local)) != pointer["sha256"]:
            raise Refused(
                f"{url}/{WAREHOUSE} is {size} bytes, and {POINTER} says {pointer['bytes']} with sha256 "
                f"{pointer['sha256']}: a later build's upload landed, or this one tore. Nothing was checked."
            )
        warehouse.unlink(missing_ok=True)
        shutil.move(str(local), str(warehouse))
    return (
        f"took run {run}.{pointer.get('attempt')}'s warehouse, {pointer['bytes']} bytes, sha256 {digest}, put at "
        f"{pointer.get('put_at')}, from {url}/{FOLDER}/, in {time.monotonic() - started:.2f} s"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_ in (("put", "hand this build's warehouse on"), ("take", "take the warehouse a build handed on")):
        command = commands.add_parser(name, help=help_)
        command.add_argument("--url", required=True, help="the leg's history store, as build_marts.py's --history-url")
        command.add_argument("--warehouse", required=True, type=Path)
        command.add_argument("--run", required=True, help="the publish-conditions.yml run whose build it is")
        if name == "put":
            command.add_argument("--attempt", default="1", help="that run's attempt, for the log")
    args = parser.parse_args(argv)
    try:
        if args.command == "put":
            message = put(args.url, args.warehouse, args.run, args.attempt)
        else:
            message = take(args.url, args.warehouse, args.run)
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
