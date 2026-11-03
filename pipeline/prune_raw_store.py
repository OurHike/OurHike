"""prune_raw_store: the raw store's retention step. List what the raw store keeps and why, and what it no longer needs,
and with --delete delete exactly that.

    python prune_raw_store.py --raw-bucket NAME --data-base-url URL --keep-raw-run ua=RAW_RUN [--delete] [--summary FILE]
    python prune_raw_store.py --bucket-url file:///a/local/store --data-base-url file:///a/public/bucket [--delete]

build-reference.yml's `maintain` job runs it with the raw store's key only, inside raw-lake-monthly: after
each build whose confirm job found UA serving what it wrote, and alone when dispatched with retention_only. Its
`retention` input is `delete`, the default (which passes --delete), or `list`. It runs on the
extract's own venv, as purge_person_fields.py does, whose bucket listing, units and delete it shares. The tests run it
on a local `file://` store (tests/test_prune_raw_store.py).

WHY. The maintainer, 2026-10-15: "The R2 bucket already has 233.23 GB in the raw data folder. Should some of that get
cleaned up? What's going on that we have so many copies of the raw data?" Every monthly run wrote a pin, its loads'
as-landed files and a row-history save, every build stored a warehouse, and nothing deleted any of them: ELT.md planned a
maintenance step after each monthly build, and it was never built. The maintainer chose (2026-10-15) "Retention step,
then delete", and "3 saves" for the monthly row-history store.

WHAT IS KEPT, kind by kind. No rule is a date alone: each names the reader that needs what it keeps.
  PINS, steps/raw_inputs/<raw_run>/ (extract/_warehouse.py's pin_raw_inputs()):
    - each environment's served raw_run (SERVED, below): the promotion builds from UA's pin, so that what is promoted
      is what UA showed (ELT.md, "Why a scheduled run cannot reach production"), and production's, once one is built
      from a pin, is what a rollback rebuilds;
    - one step back: the newest finished pin older than UA's newest served raw_run that no environment serves, the way
      back if UA's month is pulled. Counted from UA's newest, so a --keep-raw-run naming an older pin by mistake keeps
      that pin as well and never costs the real step back;
    - every pin newer than the newest served one, finished or not. A newer pin is one no environment has been built from yet, after a build that failed or before its first,
      and a rebuild after a fix starts from it (ELT.md, "Rebuilding from a pin"), so deleting it would
      throw away the extract that path exists to save. Kept, and the listing says why.
    - a pin a build is reading: none can be. This job is a job of a build-reference.yml run, which holds
      raw-lake-monthly from its first job to its last, so no other run of build-reference.yml, refresh-reference.yml or
      purge-person-fields.yml is going, and this run's own parity groups read its own raw_run's pin, which is UA's once
      its confirm job has passed.
    Every other pin goes whole, raw_inputs.json first (purge_person_fields.py, "A UNIT GOES WHOLE": half a pin still
    answers has_pin()). A folder under steps/raw_inputs/ whose name is not an extract run's id is kept: no rule places it.
  STORED WAREHOUSES, steps/dbt_warehouse/<environment>/<raw_run>/: each environment's served raw_run's, which the next
    monthly build is to restore and each hourly leg to attach (ELT.md, "Which warehouse a later run restores"; neither
    reads one yet). The rest go whole, warehouse.duckdb first. One under an environment this job does not read is kept.
  AS-LANDED FILES, raw/dlt/monthly/as_landed/<load_id>/ (extract/_run.py's upload_as_landed()):
    - each table's current committed load's file, and that load's index.json: committed_tables() over the monthly
      lane's run log, as the next run reads it. Its fresh_but_unserved() reads that index for each table it finds
      FRESH, and pin_raw_inputs() and materialize_committed() copy that file, so the last landing of a table that has
      not changed is kept however old it is;
    - each file a kept pin's raw_inputs.json names by its load (each `as_landed` entry's load_id and path), and that
      load's index.json: what the kept pins were copied from.
    Every other file goes. A load none of whose files stays goes whole, index.json first, so a delete cut short leaves
    no index naming files that are gone. A current load whose index.json is not there is kept whole.
  ROW-HISTORY SAVES, history/<store>/saves/<save_id>/ and history/<store>/elementary/<save_id>/ (row_history.py): the
    newest keep_saves(<store>) of each folder, by save id, which sorts in the order the saves were made, and every save
    the store's own pointer names (history.json's or elementary.json's save_id and previous_save_id), as row_history.py's
    _prune() keeps them. row_history_stores.toml's [keep_saves] holds the count, read through keep_saves() here as there:
    3 for the monthly store, KEEP_SAVES (24) for every other. Deleted here only in PRUNED_STORES, whose
    one writer is build-reference.yml's build job, inside raw-lake-monthly. The hourly stores' writers,
    publish-conditions.yml and check-conditions.yml, run outside that group and prune their own stores on each save, so
    their saves are listed and left: a folder deleted here between one of their saves listing it and removing it would
    make that save's remove find nothing, which fsspec answers with FileNotFoundError (Reasoned, not reproduced).
  EVERYTHING ELSE: listed by area with its objects and bytes, and never deleted.

SERVED: which raw_run each environment's data was built from, kept with everything it needs.
  - latest.json's `raw_run` (lib/releases.py's RAW_RUN_FIELD), read over public HTTPS from --data-base-url, as
    build-reference.yml's confirm job reads the same file. publish.py records it from OURHIKE_RAW_RUN, which
    build-reference.yml's UA publish sets, and every other publish carries it forward. A release published before the
    field existed carries none, so UA names none until the next build from a pin publishes there.
  - --keep-raw-run ENVIRONMENT=RAW_RUN, which build-reference.yml passes as ua=<its raw_run>: after its own confirm job
    found every file its build wrote on UA, or, under retention_only, as the dispatcher names it.
  Both are kept when they differ: a build whose files UA already serves writes no version, so latest.json goes on
  naming the pin that built those bytes first.
  WHY THESE AND NOT ANOTHER RECORD (which is reliable):
    - a stored warehouse's manifest is dbt's, which names no raw_run but by its key; and a warehouse is stored before
      the publish, so one is there for a build UA never served (a publish cancelled in publish-data: #1513 — A queued
      publish is silently cancelled when another one joins publish-data, and it looks like a green build), while a
      rebuild from an older pin moves UA back and leaves the newer warehouse standing (ELT.md, "Rebuilding from a pin");
    - build-reference.yml's runs, whose titles name their raw_run and whose confirm job says one refreshed UA, date UA in
      check-upstream-freshness.yml, but they say which build last refreshed UA and not what UA serves since; reading
      them needs the Actions API in a job holding the raw store's key; and that check reads runs on main only, while
      UA's current release came from build-reference.yml run 2, dispatched, as run 1 was, on the branch of PR #1805 —
      dlt → dbt re-platform as one go/no-go change (the Actions API's run list, read 2026-10-15);
    - channels.json names release ids, not raw_runs (channels.py moves it).
  UA MUST BE KNOWN: with no raw_run in UA's latest.json and no --keep-raw-run ua=..., --delete deletes nothing.
  Production's latest.json naming none is read as serving no pin, because no publish to production has been built from
  one: build-reference.yml publishes only to UA, and the release train's promotion still re-fetches (ELT.md, "Why a
  scheduled run cannot reach production"). So a promotion built from a pin has to set OURHIKE_RAW_RUN for its pin to be
  kept. dev is not read: lib/data_env.py's dev is published to by hand, never from a pin.

REFUSED, nothing deleted, each named in the listing: an environment's latest.json that could not be read, or names a
raw_run that is not an extract run's id; UA's raw_run not known; a served raw_run with no finished pin (a mistyped
raw_run, or a pin a purge removed: a person looks first, either way); the monthly lane's run log, a kept pin's
raw_inputs.json, a current load's as-landed index, a row-history pointer or row_history_stores.toml that could not be
read. An answer about part of the bucket is not an answer about the bucket (purge_person_fields.py).

THE DELETE is purge_person_fields.py's delete(): every unit's first object before any other, each key printed as it
goes, then the bucket listed again and every deleted key checked gone. A key gone already counts as deleted.

THE COST LINES: R2's $0.015 per GB-month past the free 10 GB-month (Cloudflare's pricing page, read 2026-10-01: ELT.md,
"What storage costs on R2"), in decimal GB, as the dashboard's 233.23 GB is. The free 10 GB is the account's and the
public bucket shares it, so the before and after figures are this bucket's alone, and their difference holds while the
account stays past 10 GB (Reasoned).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from extract._run import (
    AS_LANDED_INDEX,
    AS_LANDED_PREFIX,
    DATASET,
    RAW_STORE_PREFIX,
    committed_load_ids,
    make_pipeline,
    raw_store_url,
    run_log_rows,
)
from extract._warehouse import PIN_MANIFEST, RAW_INPUTS_PREFIX, committed_tables
from lib import data_env, releases
from lib.user_agent import USER_AGENT
from purge_person_fields import (
    HISTORY_PREFIX,
    READERS,
    STEPS_PREFIX,
    WAREHOUSE_PREFIX,
    Store,
    Stored,
    _why,
    delete,
    open_store,
)
from row_history import ELEMENTARY_POINTER, ELEMENTARY_SAVES, POINTER, SAVES, Refused, keep_saves

#: The environments whose served raw_run is read (the module docstring, SERVED). dev is not: it is published to by
#: hand, never from a pin (lib/data_env.py).
SERVING = (data_env.UA, data_env.PRODUCTION)
#: The environment whose raw_run must be known before anything is deleted: build-reference.yml publishes to it from
#: pins, and its releases from before RAW_RUN_FIELD existed name none.
MUST_KNOW = data_env.UA
#: publish.py's MANIFEST_KEY, each environment's pointer (publish.py imports boto3, which the extract's venv lacks;
#: tests/test_prune_raw_store.py holds the two equal).
LATEST = "latest.json"
#: The row-history stores this job deletes saves in: written by build-reference.yml's build job alone, inside
#: raw-lake-monthly (tests hold it to that job's --history-url). Every other store is listed and left.
PRUNED_STORES = ("monthly",)
#: The lane whose as-landed files the pins copy: refresh-reference.yml's monthly extract, run with --as-landed.
LANE = "monthly"
#: R2's price and free tier (the module docstring, THE COST LINES), and a decimal GB.
PRICE_PER_GB_MONTH = 0.015
FREE_GB_MONTH = 10
GB = 1_000_000_000

#: The unit kinds the rules decide on, as the listing names them.
PIN, WAREHOUSE, LOAD, SAVE = "pin", "stored warehouse", "as-landed load", "row-history save"


# --- What each environment serves ------------------------------------------------------------------------------------


@dataclass
class Served:
    """What one environment serves: the raw_run its latest.json names, the ones --keep-raw-run names for it, or why its
    latest.json could not be read."""

    environment: str
    url: str | None = None
    release: str | None = None
    recorded: str | None = None  # latest.json's raw_run
    named: list[str] = field(default_factory=list)  # --keep-raw-run's, for this environment
    error: str | None = None

    @property
    def raw_runs(self) -> list[str]:
        return sorted({*([self.recorded] if self.recorded else []), *self.named})

    @property
    def known(self) -> bool:
        """Whether what it serves is known: its latest.json read, and for MUST_KNOW, a raw_run from either source."""
        if self.error is not None:
            return False
        return bool(self.raw_runs) or self.environment != MUST_KNOW


def read_latest(base_url: str, environment: str) -> tuple[str, dict]:
    """(its URL, its contents): `environment`'s latest.json at the public `base_url`, with lib/user_agent.py's agent,
    without which data.ourhike.org answered 403 (publish.served_entries() measured it)."""
    url = f"{base_url.rstrip('/')}/{data_env.scope_key(environment, LATEST)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return url, json.load(response)


def read_served(base_url: str | None, named: dict[str, list[str]]) -> dict[str, Served]:
    """Each SERVING environment's Served. Never raises: a latest.json that could not be read is its `error`."""
    served = {}
    for environment in SERVING:
        found = Served(environment, named=sorted(set(named.get(environment, []))))
        if not base_url:
            found.error = "no --data-base-url (DATA_BASE_URL) to read its latest.json from"
        else:
            try:
                found.url, latest = read_latest(base_url, environment)
                raw_run = latest.get(releases.RAW_RUN_FIELD)
                found.release = latest.get("release")
                if raw_run is not None and not (isinstance(raw_run, str) and releases.RAW_RUN_PATTERN.match(raw_run)):
                    found.error = f"its latest.json names raw_run {raw_run!r}, which is not an extract run's id"
                else:
                    found.recorded = raw_run
            except Exception as failure:  # noqa: BLE001 - unread is not known, and refuses the delete
                found.error = f"its latest.json could not be read ({_why(failure)})"
        served[environment] = found
    return served


# --- The units -------------------------------------------------------------------------------------------------------


@dataclass
class Unit:
    """One thing a rule decides on: a pin, a stored warehouse, an as-landed load or a row-history save. A load is
    decided file by file (`kept`); every other unit whole."""

    kind: str
    prefix: str  # its key prefix, ending in /
    name: str  # the raw_run, load id or save id
    objects: list[Stored]
    keep: bool = True
    why: str = ""
    environment: str | None = None  # a stored warehouse's
    store: str | None = None  # a row-history save's store and folder
    folder: str | None = None
    kept: set[str] = field(default_factory=set)  # a load's keys that stay

    @property
    def size(self) -> int:
        return sum(stored.size for stored in self.objects)

    @property
    def doomed(self) -> list[Stored]:
        if self.kind == LOAD:
            return [stored for stored in self.objects if stored.key not in self.kept]
        return [] if self.keep else list(self.objects)


@dataclass
class Plan:
    """What the rules decided, over one listing of the bucket. `store` and `doomed` are what
    purge_person_fields.delete() reads."""

    store: Store
    served: dict[str, Served]
    units: list[Unit]
    other: dict[str, list[Stored]]  # area -> objects no rule decides on
    problems: list[str]
    notes: list[str]
    timings: dict[str, float]

    def of(self, kind: str) -> list[Unit]:
        return [unit for unit in self.units if unit.kind == kind]

    @property
    def doomed(self) -> list[Stored]:
        return [stored for unit in self.units for stored in unit.doomed]

    @property
    def total(self) -> int:
        return sum(stored.size for stored in self.store.objects)


def _group(objects: list[Stored], depth: int) -> dict[str, list[Stored]]:
    """{the first `depth` parts of each key, with a trailing /: its objects}."""
    groups: dict[str, list[Stored]] = defaultdict(list)
    for stored in objects:
        groups["/".join(stored.key.split("/")[:depth]) + "/"].append(stored)
    return dict(groups)


def _shaped(raw_run: str) -> bool:
    return bool(releases.RAW_RUN_PATTERN.match(raw_run))


def _record(store: Store, key: str) -> dict:
    with store.fs.open(f"{store.root}/{key}", "r") as handle:
        return json.load(handle)


def decide_pins(store: Store, served: dict[str, Served], problems: list[str]) -> list[Unit]:
    """Every pin, kept or not, with why (the module docstring, PINS)."""
    root = f"{STEPS_PREFIX}/{RAW_INPUTS_PREFIX}/"
    units = []
    for prefix, objects in sorted(_group([s for s in store.objects if s.key.startswith(root)], 3).items()):
        if prefix.count("/") == 3 and all(stored.key != prefix.rstrip("/") for stored in objects):
            units.append(Unit(PIN, prefix, prefix.split("/")[2], objects))
    finished = {unit.name for unit in units if any(stored.key == f"{unit.prefix}{PIN_MANIFEST}" for stored in unit.objects)}
    serving: dict[str, list[str]] = defaultdict(list)
    for environment, found in served.items():
        for raw_run in found.raw_runs:
            serving[raw_run].append(environment)
            if raw_run not in finished:
                problems.append(
                    f"{environment} serves raw_run {raw_run}, which has no finished pin ({root}{raw_run}/{PIN_MANIFEST}): "
                    "a mistyped raw_run, or a pin a purge removed. Nothing is deleted until a person has looked."
                )
    decided = all(found.known for found in served.values())
    ua = served[MUST_KNOW].raw_runs if MUST_KNOW in served else []
    # Before UA's newest, so that a --keep-raw-run naming an older pin by mistake keeps that pin too and never costs
    # the real one step back; a served pin is no step back.
    back = max((name for name in finished if _shaped(name) and ua and name < max(ua) and name not in serving), default=None)
    newest = max(serving, default=None)
    for unit in units:
        if not _shaped(unit.name):
            unit.why = "its name is not an extract run's id, so no rule places it"
        elif unit.name in serving:
            unit.why = f"{' and '.join(sorted(serving[unit.name]))} serve{'s' if len(serving[unit.name]) == 1 else ''} it"
        elif not decided:
            unit.why = "not decided: what each environment serves is not known"
        elif unit.name == back:
            unit.why = f"one step back: the newest finished pin before {MUST_KNOW}'s"
        elif newest is not None and unit.name > newest:
            unit.why = (
                "newer than every served pin: no environment has been built from it yet, and a rebuild after a fix starts from it"
            )
        else:
            unit.keep = False
            unit.why = "not served, not one step back, and older than the newest served pin: nothing reads it"
            if unit.name not in finished:
                unit.why = "never finished (no raw_inputs.json), and older than the newest served pin: nothing reads it"
    return units


def decide_warehouses(store: Store, served: dict[str, Served]) -> list[Unit]:
    """Every stored warehouse, kept or not, with why (the module docstring, STORED WAREHOUSES)."""
    root = f"{STEPS_PREFIX}/{WAREHOUSE_PREFIX}/"
    units = []
    for prefix, objects in sorted(_group([s for s in store.objects if s.key.startswith(root)], 4).items()):
        if prefix.count("/") != 4 or any(stored.key == prefix.rstrip("/") for stored in objects):
            continue  # not <environment>/<raw_run>/: everything else
        environment, raw_run = prefix.split("/")[2:4]
        unit = Unit(WAREHOUSE, prefix, raw_run, objects, environment=environment)
        found = served.get(environment)
        if found is None:
            unit.why = f"{environment} is not an environment whose served raw_run this step reads"
        elif not _shaped(raw_run):
            unit.why = "its name is not an extract run's id, so no rule places it"
        elif raw_run in found.raw_runs:
            unit.why = f"{environment} serves it: the next monthly build is to restore it"
        elif not found.known:
            unit.why = f"not decided: what {environment} serves is not known"
        else:
            unit.keep = False
            unit.why = f"not what {environment} serves: nothing reads it"
        units.append(unit)
    return units


def _named(names: set[str], many: str) -> str:
    """Up to three names, or how many there are."""
    return ", ".join(sorted(names)) if len(names) <= 3 else f"{len(names):,} {many}"


def decide_landed(
    store: Store, pins: list[Unit], pipelines_dir: str, problems: list[str], timings: dict[str, float]
) -> list[Unit]:
    """Every as-landed load of LANE, with the files it keeps and why (the module docstring, AS-LANDED FILES)."""
    root = f"{RAW_STORE_PREFIX}/{LANE}/{AS_LANDED_PREFIX}/"
    depth = root.count("/") + 1
    loads = {}
    for prefix, objects in sorted(_group([s for s in store.objects if s.key.startswith(root)], depth).items()):
        if prefix.count("/") == depth and all(stored.key != prefix.rstrip("/") for stored in objects):
            loads[prefix.split("/")[depth - 1]] = Unit(LOAD, prefix, prefix.split("/")[depth - 1], objects)
    keys = {stored.key for stored in store.objects}
    current_of: dict[str, set[str]] = defaultdict(set)  # load id -> the tables whose current load it is
    copied_by: dict[str, set[str]] = defaultdict(set)  # load id -> the kept pins copied from it
    whole: set[str] = set()  # current loads with no index: kept whole

    def keep(load_id: str, path: str) -> bool:
        unit = loads.get(load_id)
        if unit is None:
            return False  # gone already: nothing to keep
        unit.kept |= {key for key in (f"{unit.prefix}{path}", f"{unit.prefix}{AS_LANDED_INDEX}") if key in keys}
        return True

    started = time.monotonic()
    try:
        pipeline = make_pipeline(LANE, f"{store.url}/{RAW_STORE_PREFIX}/{LANE}", pipelines_dir)
        loads_listed = any(s.key.startswith(f"{RAW_STORE_PREFIX}/{LANE}/{DATASET}/_dlt_loads/") for s in store.objects)
        complete = committed_load_ids(pipeline) if loads_listed else set()
        current = committed_tables(pipeline, log=run_log_rows(pipeline), complete=complete) if complete else {}
    except Exception as failure:  # noqa: BLE001 - unknown current loads refuse the delete
        problems.append(f"the {LANE} lane's run log could not be read ({_why(failure)}): which loads are current is not known")
        current = None
    if current is not None and loads and not complete:
        # upload_as_landed() writes a load's files only after the load commits, so as-landed files beside no committed
        # load mean the listing or the lane is not what this step expects: nothing current can be told.
        problems.append(
            f"{root} holds {len(loads):,} loads and the {LANE} lane records no committed load: which loads are current "
            "is not known"
        )
        current = None
    timings[f"the {LANE} lane's run log"] = time.monotonic() - started

    for table, load_id in sorted((current or {}).items()):
        unit = loads.get(load_id)
        if unit is None:
            continue  # its load wrote no as-landed file
        index = f"{unit.prefix}{AS_LANDED_INDEX}"
        if index not in keys:
            unit.kept |= {stored.key for stored in unit.objects}
            whole.add(load_id)
            current_of[load_id].add(table)
            continue
        try:
            path = _record(store, index).get(table)
        except Exception as failure:  # noqa: BLE001 - as above
            problems.append(f"{index} could not be read ({_why(failure)}): which of its files is current is not known")
            continue
        if path is not None and keep(load_id, path):
            current_of[load_id].add(table)
    for pin in pins:
        if not pin.keep or not any(stored.key == f"{pin.prefix}{PIN_MANIFEST}" for stored in pin.objects):
            continue
        try:
            landed = _record(store, f"{pin.prefix}{PIN_MANIFEST}").get("as_landed") or {}
        except Exception as failure:  # noqa: BLE001 - as above
            problems.append(
                f"{pin.prefix}{PIN_MANIFEST} could not be read ({_why(failure)}): what it was copied from is not known"
            )
            continue
        for path, entry in sorted(landed.items()):
            if entry.get("load_id") and keep(entry["load_id"], path):
                copied_by[entry["load_id"]].add(pin.name)
    for load_id, unit in loads.items():
        reasons = []
        if current is None:
            unit.kept = {stored.key for stored in unit.objects}
            reasons.append("not decided: which loads are current is not known")
        if current_of[load_id]:
            reasons.append(f"the current load of {_named(current_of[load_id], 'tables')}")
        if load_id in whole:
            reasons.append("its index is not there, so it is kept whole")
        if copied_by[load_id]:
            pins_ = copied_by[load_id]
            reasons.append(f"copied into pin{'s' if len(pins_) > 1 else ''} {_named(pins_, 'pins')}")
        unit.keep = bool(unit.kept)
        if not unit.kept:
            for stored in unit.objects:
                stored.first = stored.key == f"{unit.prefix}{AS_LANDED_INDEX}"
        unit.why = "; ".join(reasons) or "no table's current load, and no kept pin was copied from it"
    return list(loads.values())


def decide_saves(store: Store, problems: list[str], notes: list[str]) -> list[Unit]:
    """Every row-history save, kept or not, with why (the module docstring, ROW-HISTORY SAVES). A store this step
    leaves (not in PRUNED_STORES) is one unit per folder, every save of it kept."""
    units = []
    stores = sorted({stored.key.split("/")[1] for stored in store.objects if stored.key.startswith(f"{HISTORY_PREFIX}/")})
    for name in stores:
        try:
            keep = keep_saves(name)
        except Refused as refused:
            problems.append(str(refused))
            keep = None
        for folder, pointer in ((SAVES, POINTER), (ELEMENTARY_SAVES, ELEMENTARY_POINTER)):
            root = f"{HISTORY_PREFIX}/{name}/{folder}/"
            groups = _group([s for s in store.objects if s.key.startswith(root)], 4)
            found = {
                prefix.split("/")[3]: objects
                for prefix, objects in groups.items()
                if prefix.count("/") == 4 and all(stored.key != prefix.rstrip("/") for stored in objects)
            }
            if not found:
                continue
            ids = sorted(found)
            if name not in PRUNED_STORES:
                past = f", {len(ids) - keep:,} past it" if keep is not None and len(ids) > keep else ""
                unit = Unit(SAVE, root, "*", [stored for save in ids for stored in found[save]], store=name, folder=folder)
                unit.why = (
                    f"{len(ids):,} saves against its {keep if keep is not None else '(unread) count'}{past}: its own save "
                    "prunes it, outside raw-lake-monthly, so this step leaves it"
                )
                units.append(unit)
                if past:
                    notes.append(f"{root} holds {len(ids):,} saves against its {keep}; {unit.why.split(': ', 1)[1]}")
                continue
            named: dict[str, str] = {}
            key = f"{HISTORY_PREFIX}/{name}/{pointer}"
            if any(stored.key == key for stored in store.objects):
                try:
                    record = _record(store, key)
                    named = {
                        save: why
                        for save, why in (
                            (record.get("previous_save_id"), "the save before it"),
                            (record.get("save_id"), "current"),
                        )
                        if save
                    }
                except Exception as failure:  # noqa: BLE001 - which save is current is not known
                    problems.append(f"{key} could not be read ({_why(failure)}): which save is current is not known")
                    keep = None
            newest = set(ids[-keep:]) if keep else set(ids)
            for save_id in ids:
                unit = Unit(SAVE, f"{root}{save_id}/", save_id, found[save_id], store=name, folder=folder)
                if save_id in named:
                    unit.why = f"{pointer} names it ({named[save_id]})"
                elif keep is None:
                    unit.why = "not decided: the store's count or pointer could not be read"
                elif save_id in newest:
                    unit.why = f"one of the newest {keep}"
                else:
                    unit.keep = False
                    unit.why = f"beyond the newest {keep}, and {pointer} names it not"
                units.append(unit)
    return units


def _area(stored: Stored) -> str:
    """Where an object no rule decides on sits, for the listing: place()'s area, a step's own folder under steps/."""
    parts = stored.key.split("/")
    if parts[0] == STEPS_PREFIX and len(parts) > 2:
        return "/".join(parts[:2])
    return stored.area


def decide(bucket_url: str, pipelines_dir: str, base_url: str | None, named: dict[str, list[str]]) -> Plan:
    """The rules, over one listing of the bucket. Changes nothing."""
    timings: dict[str, float] = {}
    started = time.monotonic()
    store = open_store(bucket_url, pipelines_dir)
    timings["listing the bucket"] = time.monotonic() - started
    started = time.monotonic()
    served = read_served(base_url, named)
    timings["each environment's latest.json"] = time.monotonic() - started
    problems, notes = [], []
    for found in served.values():
        if found.error:
            problems.append(f"{found.environment}: {found.error}")
        elif not found.known:
            problems.append(
                f"{found.environment}'s latest.json names no raw_run, and no --keep-raw-run {found.environment}=<raw_run> "
                "was given: what it serves is not known, so nothing is deleted"
            )
    pins = decide_pins(store, served, problems)
    units = [*pins, *decide_warehouses(store, served)]
    units += decide_landed(store, pins, pipelines_dir, problems, timings)
    started = time.monotonic()
    units += decide_saves(store, problems, notes)
    timings["the row-history pointers"] = time.monotonic() - started
    decided = {stored.key for unit in units for stored in unit.objects}
    other: dict[str, list[Stored]] = defaultdict(list)
    for stored in store.objects:
        if stored.key not in decided:
            other[_area(stored)].append(stored)
    return Plan(store, served, units, dict(other), problems, notes, timings)


# --- The listing -----------------------------------------------------------------------------------------------------


def _gb(size: int) -> str:
    """Decimal GB, as the totals and the cost lines count them."""
    return f"{size / GB:,.2f} GB"


def _size(size: int) -> str:
    """A unit's or a file's size, in GB, MB or KB, decimal, whichever reads."""
    if size >= GB:
        return _gb(size)
    if size >= 1_000_000:
        return f"{size / 1e6:,.1f} MB"
    return f"{size / 1e3:,.1f} KB"


def _cost(size: int) -> float:
    return max(0.0, size / GB - FREE_GB_MONTH) * PRICE_PER_GB_MONTH


def _objects(number: int) -> str:
    return f"{number:,} object{'' if number == 1 else 's'}"


def _verdict(unit: Unit) -> str:
    if unit.kind == LOAD:
        return "keep" if len(unit.doomed) == 0 else ("delete" if not unit.kept else "keep part")
    return "keep" if unit.keep else "delete"


def totals(plan: Plan) -> list[tuple[str, int, int]]:
    """(row, objects, bytes) for the bucket before, what a delete removes, and the bucket after."""
    doomed = plan.doomed
    gone = sum(stored.size for stored in doomed)
    return [
        ("before", len(plan.store.objects), plan.total),
        ("deleted", len(doomed), gone),
        ("after", len(plan.store.objects) - len(doomed), plan.total - gone),
    ]


def listing(plan: Plan, deleting: bool) -> list[str]:
    """The plan as plain lines for the job's log: keys, names and sizes, never a row of data."""
    lines = [
        f"The raw store's retention step, {'DELETING' if deleting else 'listing only'}: {plan.store.url}, "
        f"{_objects(len(plan.store.objects))}, {_gb(plan.total)}.",
        "",
        "WHAT EACH ENVIRONMENT SERVES",
    ]
    for found in plan.served.values():
        if found.error:
            lines.append(f"   {found.environment}: NOT KNOWN, {found.error}")
            continue
        recorded = f"latest.json names raw_run {found.recorded}" if found.recorded else "latest.json names no raw_run"
        named = f"; --keep-raw-run names {', '.join(found.named)}" if found.named else ""
        serves = ", ".join(found.raw_runs) or "no pin"
        lines.append(f"   {found.environment}: release {found.release or 'none'}, {recorded}{named}: serves {serves}")
    for kind, title in (
        (PIN, f"PINS, {STEPS_PREFIX}/{RAW_INPUTS_PREFIX}/"),
        (WAREHOUSE, f"STORED WAREHOUSES, {STEPS_PREFIX}/{WAREHOUSE_PREFIX}/"),
        (LOAD, f"AS-LANDED FILES, {RAW_STORE_PREFIX}/{LANE}/{AS_LANDED_PREFIX}/"),
        (SAVE, f"ROW-HISTORY SAVES, {HISTORY_PREFIX}/<store>/{SAVES}/ and /{ELEMENTARY_SAVES}/"),
    ):
        units = plan.of(kind)
        doomed = [stored for unit in units for stored in unit.doomed]
        lines += [
            "",
            f"{title}: {len(units):,} in all, {_size(sum(unit.size for unit in units))}; "
            f"{'deleting' if deleting else 'would delete'} {_objects(len(doomed))}, {_size(sum(s.size for s in doomed))}",
        ]
        for unit in units:
            where = f"{unit.environment}/" if unit.environment else (f"{unit.store}/{unit.folder}/" if unit.store else "")
            gone = unit.doomed
            lines.append(
                f"   {_verdict(unit).upper():9} {where}{unit.name}: {_objects(len(unit.objects))}, {_size(unit.size)}"
                + (
                    f", {_objects(len(gone))} ({_size(sum(s.size for s in gone))}) to go"
                    if unit.kind == LOAD and unit.kept and gone
                    else ""
                )
                + f" ({unit.why})"
            )
            if unit.kind == LOAD and unit.kept and gone:
                for stored in gone:
                    lines.append(f"      delete {stored.key.removeprefix(unit.prefix)} ({_size(stored.size)})")
    lines += ["", "EVERYTHING ELSE, never deleted"]
    for area, objects in sorted(plan.other.items()):
        lines.append(f"   {area}: {_objects(len(objects))}, {_size(sum(stored.size for stored in objects))}")
    lines += ["", "TOTALS, at $0.015 per GB-month past the free 10 GB-month"]
    for row, number, size in totals(plan):
        cost = f", ${_cost(size):,.2f} a month" if row != "deleted" else f", ${size / GB * PRICE_PER_GB_MONTH:,.2f} a month less"
        lines.append(f"   {row}: {_objects(number)}, {_gb(size)}{cost}")
    if plan.notes:
        lines += ["", "NOTES"] + [f"   {note}" for note in plan.notes]
    lines += ["", f"REFUSALS: {len(plan.problems):,}"] + [f"   {problem}" for problem in plan.problems]
    lines += ["", "Timings: " + ", ".join(f"{part} {seconds:.1f} s" for part, seconds in plan.timings.items())]
    return lines


def summary(plan: Plan, deleting: bool, verdict: str, deleted: list[str]) -> str:
    """The plan as Markdown for the run's summary page ($GITHUB_STEP_SUMMARY): a row per unit, never a key list."""
    text = ["## Retention step", "", f"**{verdict}**", "", "### What each environment serves", ""]
    text += ["| environment | release | latest.json's raw_run | --keep-raw-run | kept as served |", "|---|---|---|---|---|"]
    for found in plan.served.values():
        if found.error:
            text.append(f"| `{found.environment}` | not known: {found.error} | | | |")
            continue
        text.append(
            f"| `{found.environment}` | `{found.release or 'none'}` | `{found.recorded or 'none'}` | "
            f"{', '.join(f'`{run}`' for run in found.named) or 'none'} | {', '.join(f'`{run}`' for run in found.raw_runs) or 'no pin'} |"
        )
    for kind, title in ((PIN, "Pins"), (WAREHOUSE, "Stored warehouses"), (LOAD, "As-landed loads"), (SAVE, "Row-history saves")):
        units = plan.of(kind)
        if not units:
            continue
        doomed = [stored for unit in units for stored in unit.doomed]
        text += [
            "",
            f"### {title}: {'deleting' if deleting else 'would delete'} {_objects(len(doomed))}, {_size(sum(s.size for s in doomed))}",
            "",
            "| unit | objects | size | verdict | why |",
            "|---|---|---|---|---|",
        ]
        for unit in units:
            where = f"{unit.environment}/" if unit.environment else (f"{unit.store}/{unit.folder}/" if unit.store else "")
            size = _size(unit.size)
            if unit.kind == LOAD and unit.kept and unit.doomed:
                size += f" ({_size(sum(s.size for s in unit.doomed))} to go)"
            text.append(f"| `{where}{unit.name}` | {len(unit.objects):,} | {size} | {_verdict(unit)} | {unit.why} |")
    text += ["", "### Everything else, never deleted", "", "| area | objects | size |", "|---|---|---|"]
    for area, objects in sorted(plan.other.items()):
        text.append(f"| `{area}` | {len(objects):,} | {_size(sum(stored.size for stored in objects))} |")
    text += ["", "### Totals, at $0.015 per GB-month past the free 10 GB-month", "", "| | objects | size | a month |"]
    text.append("|---|---|---|---|")
    for row, number, size in totals(plan):
        cost = f"${_cost(size):,.2f}" if row != "deleted" else f"${size / GB * PRICE_PER_GB_MONTH:,.2f} less"
        text.append(f"| {row} | {number:,} | {_gb(size)} | {cost} |")
    if deleting:
        text += ["", f"{len(deleted):,} objects deleted; each key is in the job's log."]
    if plan.notes:
        text += ["", "### Notes", "", *[f"- {note}" for note in plan.notes]]
    if plan.problems:
        text += ["", f"### Refusals: {len(plan.problems):,}", "", *[f"- {problem}" for problem in plan.problems]]
    return "\n".join(text) + "\n"


# --- The command -----------------------------------------------------------------------------------------------------


def keep_spec(text: str) -> tuple[str, str]:
    """`ENVIRONMENT=RAW_RUN`, for --keep-raw-run: one of SERVING, and an extract run's id."""
    environment, _, raw_run = text.partition("=")
    if environment not in SERVING or not _shaped(raw_run):
        raise argparse.ArgumentTypeError(
            f"{text!r} is not ENVIRONMENT=RAW_RUN, with ENVIRONMENT one of {', '.join(SERVING)} and RAW_RUN an extract "
            "run's id such as 20261008T041936.333353Z"
        )
    return environment, raw_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The raw store's retention step: list, and with --delete delete, what the "
        "raw store no longer needs (this module's docstring)."
    )
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--raw-bucket", help="the private raw bucket's name, as R2_RAW_BUCKET holds it")
    where.add_argument("--bucket-url", help="the bucket's root as a URL: s3://<bucket>, or file:///a/local/store")
    parser.add_argument(
        "--data-base-url",
        help="the public bucket's base URL, where each environment's latest.json is read (DATA_BASE_URL)",
    )
    parser.add_argument(
        "--keep-raw-run",
        type=keep_spec,
        action="append",
        default=[],
        metavar="ENVIRONMENT=RAW_RUN",
        help="a raw_run ENVIRONMENT serves, kept with what it needs as latest.json's own is (repeatable)",
    )
    parser.add_argument("--delete", action="store_true", help="delete what the listing names, unless a refusal stands")
    parser.add_argument("--summary", type=Path, help="append the plan as Markdown to this file ($GITHUB_STEP_SUMMARY)")
    parser.add_argument("--pipelines-dir", help="dlt's working directory (default: a new temporary one)")
    parser.add_argument("--readers", type=int, default=READERS, help=f"objects deleted at once (default {READERS})")
    args = parser.parse_args(argv)
    if args.raw_bucket is not None:
        raw_store_url(args.raw_bucket, LANE)  # refuses anything but a bucket's bare name
        bucket_url = f"s3://{args.raw_bucket}"
    else:
        bucket_url = args.bucket_url
    named: dict[str, list[str]] = defaultdict(list)
    for environment, raw_run in args.keep_raw_run:
        named[environment].append(raw_run)

    with tempfile.TemporaryDirectory() as temporary:
        decided = decide(bucket_url, args.pipelines_dir or str(Path(temporary) / "dlt"), args.data_base_url, named)
    for line in listing(decided, args.delete):
        print(line)

    deleted: list[str] = []
    status = 0
    doomed = decided.doomed
    if decided.problems:
        verdict = (
            f"Not decided: {len(decided.problems):,} refusal{'' if len(decided.problems) == 1 else 's'} above, so nothing "
            f"{'was' if args.delete else 'would be'} deleted."
        )
        print(f"::error title=The retention step could not decide::{verdict}")
        status = 1
    elif not args.delete:
        verdict = (
            f"Listing only, nothing deleted. A dispatch with retention=delete deletes the {_objects(len(doomed))} above, "
            f"{_gb(sum(stored.size for stored in doomed))}."
        )
    else:
        print("")
        print(f"DELETING {_objects(len(doomed))}, every unit's first object before the rest:")
        deleted, problems = delete(decided, args.readers)
        for problem in problems:
            print(f"::error title=A delete did not take::{problem}")
        gone = set(deleted)
        verdict = (
            f"Deleted {len(deleted):,} objects, {_gb(sum(s.size for s in doomed if s.key in gone))}; {len(problems):,} problems."
        )
        status = 1 if problems else 0
    print("")
    print(verdict)
    if args.summary is not None:
        with args.summary.open("a", encoding="utf-8") as handle:
            handle.write(summary(decided, args.delete, verdict, deleted))
    return status


if __name__ == "__main__":
    sys.exit(main())
