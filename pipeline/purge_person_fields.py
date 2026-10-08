"""purge_person_fields: decision 56's purge. Prove the raw store's current tables hold no person field, list every
other stored object that still holds one, and with --delete delete exactly those.

    python purge_person_fields.py --raw-bucket NAME [--delete] [--summary FILE]
    python purge_person_fields.py --bucket-url file:///a/local/store [--delete]

purge-person-fields.yml runs it on the extract's own venv (requirements-extract.txt: dlt with s3fs, pyarrow and
duckdb), with the raw store's key, which only a workflow holds (pipeline/ELT.md, decision 43). The tests run it on a
local `file://` store (tests/test_purge_person_fields.py).

WHY. pipeline/ELT.md, decision 56: 15 loaded layers carried staff names in `Creator`, `Editor`, `created_user` and
`last_edited_user`, and Alaska Trails' `DataOwner` held a person's e-mail address on 31 rows, until the extract stopped
reading them (aafa7296, 2026-10-03). The maintainer decided the purge runs after the monthly lane had re-read every
layer without them. The method is ELT.md's "Purging a field that should never have loaded" and the dlt skill's "A
field that should never have loaded": on the plain-file tiers, every stored copy that holds the field is DELETED,
never edited, because a pin and a served copy are write-once and a DuckDB file's free pages keep a dropped value.
ELT.md's as-sent copies under `current/` and `snapshots/` are not built, but for OSM's Geofabrik mirror under the
monthly lane's `current/`; what holds those rows today is the as-landed copy, `as_landed/<load_id>/`, which is read
here like everything else in the bucket.

THE FIELD LIST is the extract's own, named where the extract names it and never restated here (FieldRules):
  - PERSON_FIELDS (extract/_kinds.py), for every table: Forest Ranger Contact's six, the Central Iowa Trail
    Association's `updateByDisplay`, and ArcGIS editor tracking's `Creator`, `Editor`, `created_user` and
    `last_edited_user`;
  - the table's own sources.json row's `person_fields`, which is where the code records a layer's editFieldsInfo
    names (the NPS trails' `CREATEUSER` and `EDITUSER`, for one), Alaska Trails' `DataOwner`, and every other field
    a person read and found carrying somebody;
  - the podcast readers' PERSON_TAGS, as the columns PodcastFeed would have named them, and the conditions queries'
    WITHHELD_COLUMNS, each for its own reader's tables.
Names are compared as the extract compares them (extract/_kinds.py's _named_in(): lower-cased, or as dlt lands
them), so `Creator` in an as-landed GeoJSON file and `creator` in a Parquet file are one field. The person-shaped
backstop (PERSON_SHAPED) is a pattern, not a name, and is not used: a stored copy has no ArcGIS field type to tell
`last_edited_date` from `last_edited_user` with, so on a current table it would refuse every purge over a date.

IN THIS ORDER, AND NOTHING DELETED BEFORE ALL OF IT HAS RUN:
  1. THE CURRENT TABLES. Each lane's newest committed load of each table (extract/_warehouse.py's
     committed_tables(); for a notices or conditions leg, only the tables its job reads now, leg_tables()), which
     every build and every new pin reads. Each file's own schema is read, and every listed field in it is counted:
     its rows, and how many carry a value. Never a value. If a value is in one, --delete refuses and deletes
     nothing, since a pin made tomorrow would copy it again: the lane's next read of that table lands it without
     the field, and the purge runs after that.
  2. EVERY OTHER OBJECT IN THE BUCKET, read by its own schema or keys and never judged by its date: a Parquet
     file's schema, a DuckDB file's catalog (downloaded, attached read-only), a JSON file's keys (streamed, each key
     found by a byte pattern, and of each value only whether it is empty). What holds a field is listed with each
     field's counts.
  3. WITH --delete, exactly what step 2 listed, each key printed as it goes. Then the bucket is listed again and
     every deleted key checked gone.

A UNIT GOES WHOLE. A pin (`steps/raw_inputs/<raw_run>/`), a stored warehouse (`steps/dbt_warehouse/<env>/<raw_run>/`),
a notices leg's served copy (`raw/dlt/<leg>/served/<run_id>/`) and a row-history save (`history/<store>/saves/<id>/`)
are each written and read as one: half a pin still answers has_pin() and then fails its build on a missing file. So
a unit with one holding object is deleted whole, its record first (a pin's raw_inputs.json, a served copy's
manifest.json, a stored warehouse's own file), so a delete cut short leaves nothing that reads as finished. Its other
objects are not read: they go with it either way. Every other object stands alone: an as-landed file under
`raw/dlt/<lane>/as_landed/<load_id>/`, an older or uncommitted file in a lane's dataset, a frozen table a leg no
longer reads.

WHAT HOLDS ONE. An object with a value in a listed field: anything but a null or an empty string, in a column its
schema names or under a key its rows carry. A column with no value in it is not a copy of anybody, and it is what
every re-read table has: dlt keeps each column its schema has seen, so a table read again without a field still
writes that field's column, empty (Measured on dlt 1.30.0, 2026-10-08: tests/test_purge_person_fields.py's re-read
month lands `ranger` and `dataowner` with no value in any row), and every pin made since copies it. Those are
counted, named in the listing, and kept.

A pinned as-landed file whose pin records the same sha256 as one already read is not read again: each pin hashed its
copy as it wrote it (its raw_inputs.json), and nothing rewrites a pin, so the two hold the same bytes (Reasoned from
pin_raw_inputs()'s write-once rule, which every build checks again: _warehouse._verified() refuses a pinned file
whose sha256 moved).

WHAT IS NOT READ, and why each may be left:
  - dlt's own bookkeeping in a lane's dataset (`_dlt_loads`, `_dlt_pipeline_state`, `_dlt_version`, `init`): column
    names, load ids and change markers, never a row (Reasoned from what dlt 1.30.0 writes there), and deleting any
    of it would break the lane;
  - the records that name a unit's files, sizes and digests (a pin's raw_inputs.json, a served copy's
    manifest.json, an as-landed index.json, the Geofabrik mirror's current/index.json, row_history's two pointers,
    and dbt's manifest.json and run_results.json beside a warehouse), which hold column names at most;
  - any other format, such as the Geofabrik mirror's `.pbf` extracts: listed by key under "not read", for a person
    to judge.
An object that could not be read is listed, the run ends 1, and --delete deletes nothing: an answer about part of the
bucket is not an answer about the bucket. One deleted between the listing and its read is counted as gone instead:
the hourly legs run outside the monthly lane's group, and their own runs trim old served copies and replace table
files under a purge (Reasoned from extract/_warehouse.py's purge_served() and dlt's `replace`).

AFTER A DELETE, a pin that held a field is gone, so build-reference.yml cannot build from that raw_run again and the
release train cannot promote it. If the raw_run UA serves is one of them, the next promotion needs a fresh UA build:
a refresh-reference.yml run, whose new pin holds no value in any listed field. The listing names every pin it deletes
and the newest pin it keeps.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from extract import _kinds
from extract._contract import all_resources, discover, discover_shared
from extract._geofabrik import CURRENT_PREFIX
from extract._geofabrik import INDEX_NAME as CURRENT_INDEX
from extract._run import (
    AS_LANDED_INDEX,
    AS_LANDED_PREFIX,
    DATASET,
    LANES,
    LEGS,
    RAW_STORE_PREFIX,
    _client,
    _load_of,
    committed_load_ids,
    fs_path,
    leg_run_log_rows,
    leg_tables,
    make_pipeline,
    raw_store_url,
    run_log_rows,
)
from extract._warehouse import PIN_MANIFEST, RAW_INPUTS_PREFIX, SERVED_MANIFEST, SERVED_PREFIX, committed_tables
from row_history import ELEMENTARY_POINTER, ELEMENTARY_SAVES, POINTER, SAVES

#: Where the workflows keep each store in the raw bucket, beside dlt's own prefix (RAW_STORE_PREFIX):
#: refresh-reference.yml and build-reference.yml pass `--steps-url "s3://$R2_RAW_BUCKET/steps"`, build-reference.yml
#: stores the warehouse under `--key "dbt_warehouse/ua/$RAW_RUN"`, and each lane's row history sits at
#: `s3://$R2_RAW_BUCKET/history/<store>`. tests/test_purge_person_fields.py holds these to the workflow files.
STEPS_PREFIX = "steps"
WAREHOUSE_PREFIX = "dbt_warehouse"
HISTORY_PREFIX = "history"
#: The warehouse file build-reference.yml stores: its unit's rows, deleted before the records that describe it.
WAREHOUSE_FILE = "warehouse.duckdb"

#: dlt's own tables in a lane's dataset (the module docstring, "WHAT IS NOT READ").
DLT_TABLES = frozenset({"_dlt_loads", "_dlt_pipeline_state", "_dlt_version"})
#: dbt's records stored beside a warehouse (build-reference.yml's "Store the warehouse and its manifest" step).
DBT_RECORDS = frozenset({"manifest.json", "run_results.json"})

#: How each object is read: a Parquet schema, a DuckDB catalog, a JSON file's keys, or not at all (a record, dlt's
#: bookkeeping, or a format this script does not read).
PARQUET, DUCKDB, JSON_ROWS, RECORD, DLT, UNREAD = "parquet", "duckdb", "json", "record", "dlt", "unread"
JSON_SUFFIXES = (".json", ".geojson", ".jsonl", ".ndjson")

#: Every key in a JSON byte stream, and whether its value is empty. A quoted string followed by a colon is a key by
#: JSON's grammar; `n` is the only first byte a null can have, and `""` is the empty string. An escaped quote is
#: consumed with its backslash, so a string value holding JSON text never yields its inner keys. Whitespace is bounded
#: so that no match is longer than JSON_OVERLAP, which lets a stream be read in chunks without losing a key at a
#: chunk's edge. A key longer than 256 characters is not seen; no listed name comes near that.
JSON_KEY = re.compile(rb'"((?:[^"\\]|\\.){0,256})"[ \t\r\n]{0,16}:[ \t\r\n]{0,16}(n|""|)')
#: What JSON_KEY's second group holds for a value that is no value.
JSON_EMPTY = (b"n", b'""')
JSON_CHUNK = 16 << 20
JSON_OVERLAP = 4096
#: Objects read at once. The JSON pattern runs under the GIL, so threads past one overlap only the downloads.
#: 8 is @unvalidated: the timings the first dispatch prints settle it. On a synthetic as-landed file of 116 MB the
#: pattern ran at 48 to 69 MB/s in a web sandbox (measured 2026-10-08); a line layer has fewer keys per byte than
#: that file, so it reads faster.
READERS = 8
#: How much the Parquet reader asks for at a time: a footer is a few KiB, and s3fs's own default block is far larger.
PARQUET_BLOCK = 1 << 20
#: How much of an error's message the listing prints: enough to name the key, type or column at fault, on one line.
#: The reads here are footers, catalogs, keys and counts, so no message of theirs is built from a row's value
#: (Reasoned from the calls each makes); the cut is a second line behind that.
ERROR_CHARS = 300


# --- The field list -------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldRule:
    """The names one table's stored copies may not hold, each list under the name the listing gives it."""

    lists: tuple[tuple[str, frozenset[str]], ...]

    def listed_by(self, name: str) -> str | None:
        """The list naming `name`, compared as the extract compares names (_kinds._named_in()), or None."""
        for list_name, names in self.lists:
            if names and _kinds._named_in(name, names):
                return list_name
        return None


class FieldRules:
    """The FieldRule for a table, from the extract's own lists (the module docstring, "THE FIELD LIST").

    `resources` are discover()'s. A table no resource lands any more is ruled by its sources.json row when its name,
    `raw_<folder>__<key>`, leads to one, and by PERSON_FIELDS alone otherwise. A table of None, a dbt model or a pin's
    extra file, is PERSON_FIELDS alone: a model carries only what a raw table in the same file carried, and that
    table is judged by its own row.
    """

    def __init__(self, resources: list):
        self.resources: dict = {}
        for resource in resources:
            self.resources.setdefault(resource.table, resource)
        self._rules: dict[str | None, FieldRule] = {}

    def __call__(self, table: str | None) -> FieldRule:
        if table not in self._rules:
            self._rules[table] = self._rule(table)
        return self._rules[table]

    def _rule(self, table: str | None) -> FieldRule:
        lists = [("PERSON_FIELDS", _kinds.PERSON_FIELDS)]
        if table is None:
            return FieldRule(tuple(lists))
        resource = self.resources.get(table)
        entry = _registry_row(resource.key if resource is not None else _key_of(table))
        if entry is not None:
            names = frozenset(str(name).lower() for name in entry.get("person_fields") or ())
            lists.append((f"{entry['key']}'s person_fields", names))
        if isinstance(resource, _kinds.PodcastFeed):
            lists.append(("PERSON_TAGS", frozenset(_kinds._feed_column(tag).lower() for tag in _kinds.PERSON_TAGS)))
        if isinstance(resource, _kinds.ConditionsQuery):
            lists.append(("WITHHELD_COLUMNS", _kinds.WITHHELD_COLUMNS))
        return FieldRule(tuple(lists))


def _key_of(table: str) -> str | None:
    """The sources.json key in `raw_<folder>__<key>`, for a table no resource lands any more, or None."""
    if not table.startswith("raw_") or "__" not in table:
        return None
    return table.split("__", 1)[1]


def _registry_row(key: str | None) -> dict | None:
    if not key:
        return None
    try:
        return _kinds.registry_entry(key)
    except KeyError:
        return None


# --- The bucket, object by object -----------------------------------------------------------------------------------


@dataclass
class Holding:
    """One listed field found in an object: the list naming it, its rows (a JSON file's occurrences of the key), and
    how many of those carry a value, which is anything but a null or an empty string. Counts only: nothing here ever
    holds a value."""

    listed_by: str
    rows: int
    with_value: int


@dataclass
class Stored:
    """One object in the raw bucket: where it sits, how it is read, and what reading it found."""

    key: str  # relative to the bucket's root, as the listing prints it
    path: str  # as the bucket's filesystem client names it
    size: int
    kind: str  # PARQUET, DUCKDB, JSON_ROWS, RECORD, DLT or UNREAD
    area: str  # where it sits, for the listing's counts
    unit: str | None = None  # the prefix it is deleted with, or None when it stands alone
    first: bool = False  # deleted before the rest of its unit
    table: str | None = None  # the raw table whose rule it is read under
    lane: str | None = None  # the lane whose dataset holds it
    load_id: str | None = None  # a dataset file's load
    digest: str | None = None  # a pinned as-landed file's sha256, as its pin recorded it
    current: bool = False  # a file of a table's current load, which every build reads (step 1)
    fields: dict[str, Holding] = field(default_factory=dict)  # every listed field found, with or without a value
    read: bool = False
    error: str | None = None
    gone: bool = False  # deleted between the listing and its read: a leg's own run replaced or trimmed it
    copy_of: str | None = None  # the pinned as-landed file with the same recorded sha256 that was read in its place

    @property
    def holds(self) -> bool:
        """Whether a row of it has a value in a listed field (the module docstring, "WHAT HOLDS ONE")."""
        return any(holding.with_value for holding in self.fields.values())

    @property
    def empty_columns(self) -> bool:
        """Whether it has a listed field with no value in any row: kept, and counted."""
        return any(not holding.with_value for holding in self.fields.values())


def _kind(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".parquet"):
        return PARQUET
    if lower.endswith(".duckdb"):
        return DUCKDB
    if lower.endswith(JSON_SUFFIXES):
        return JSON_ROWS
    return UNREAD


def place(key: str, path: str, size: int) -> Stored:
    """Where `key` sits in the bucket: how it is read, the unit it goes with and, where its place says, its table."""
    parts = key.split("/")
    name = parts[-1]
    stored = Stored(key=key, path=path, size=size, kind=_kind(name), area=parts[0] if len(parts) > 1 else "(root)")
    lane_root = RAW_STORE_PREFIX.split("/")
    depth = len(lane_root)
    if parts[:depth] == lane_root and len(parts) > depth + 2:
        lane, where, rest = parts[depth], parts[depth + 1], parts[depth + 2 :]
        stored.area = "/".join(parts[: depth + 2])
        if where == DATASET:
            stored.lane = lane
            if len(rest) == 1 or rest[0] in DLT_TABLES:
                stored.kind = DLT
            else:
                stored.table = rest[0]
                if stored.kind == PARQUET:
                    stored.load_id = _load_of(name)
        elif where == AS_LANDED_PREFIX and rest[1:] == [AS_LANDED_INDEX]:
            stored.kind = RECORD
        elif where == SERVED_PREFIX and len(rest) >= 2:
            stored.unit = "/".join(parts[: depth + 3]) + "/"
            if rest[1:] == [SERVED_MANIFEST]:
                stored.kind, stored.first = RECORD, True
            elif rest[1] == "tables" and stored.kind == PARQUET:
                stored.table = Path(name).stem
        elif where == CURRENT_PREFIX and rest == [CURRENT_INDEX]:
            stored.kind = RECORD
    elif parts[0] == STEPS_PREFIX and len(parts) >= 4 and parts[1] == RAW_INPUTS_PREFIX:
        stored.area = f"{STEPS_PREFIX}/{RAW_INPUTS_PREFIX}"
        stored.unit = "/".join(parts[:3]) + "/"
        if parts[3:] == [PIN_MANIFEST]:
            stored.kind, stored.first = RECORD, True
        elif parts[3] == "tables" and stored.kind == PARQUET:
            stored.table = Path(name).stem
    elif parts[0] == STEPS_PREFIX and len(parts) >= 5 and parts[1] == WAREHOUSE_PREFIX:
        stored.area = f"{STEPS_PREFIX}/{WAREHOUSE_PREFIX}"
        stored.unit = "/".join(parts[:4]) + "/"
        if name in DBT_RECORDS:
            stored.kind = RECORD
        stored.first = name == WAREHOUSE_FILE
    elif parts[0] == HISTORY_PREFIX and len(parts) >= 3:
        stored.area = "/".join(parts[:2])
        if parts[2:] in ([POINTER], [ELEMENTARY_POINTER]):
            stored.kind = RECORD
        elif parts[2] in (SAVES, ELEMENTARY_SAVES) and len(parts) >= 5:
            stored.unit = "/".join(parts[:4]) + "/"
    return stored


def _unit_name(unit: str) -> str:
    if unit.startswith(f"{STEPS_PREFIX}/{RAW_INPUTS_PREFIX}/"):
        return "a pin"
    if unit.startswith(f"{STEPS_PREFIX}/{WAREHOUSE_PREFIX}/"):
        return "a stored warehouse"
    if unit.startswith(f"{HISTORY_PREFIX}/"):
        return "a row-history save"
    return "a served copy"


@dataclass
class Store:
    """The raw bucket, listed once: its URL, its filesystem client and root as that client names it, every object."""

    url: str
    fs: object
    root: str
    objects: list[Stored]
    pipelines_dir: str

    def lane_url(self, lane: str) -> str:
        return f"{self.url}/{RAW_STORE_PREFIX}/{lane}"


def open_store(bucket_url: str, pipelines_dir: str) -> Store:
    """The bucket at `bucket_url`, through the client dlt makes from DESTINATION__FILESYSTEM__CREDENTIALS__*."""
    bucket_url = bucket_url.rstrip("/")
    probe = make_pipeline("monthly", f"{bucket_url}/{RAW_STORE_PREFIX}/monthly", pipelines_dir)
    store = Store(url=bucket_url, fs=_client(probe).fs_client, root=fs_path(bucket_url), objects=[], pipelines_dir=pipelines_dir)
    store.objects = list_bucket(store)
    return store


def list_bucket(store: Store) -> list[Stored]:
    """Every object under the bucket's root, placed (place()), in key order. Asked of the store each time: s3fs keeps
    a listings cache, which would answer a second listing with what the first one saw."""
    store.fs.invalidate_cache()
    try:
        found = store.fs.find(store.root, detail=True)
    except FileNotFoundError:
        return []
    objects = []
    for path, info in found.items():
        if info.get("type", "file") != "file":
            continue
        objects.append(place(path[len(store.root) :].lstrip("/"), path, int(info.get("size") or 0)))
    return sorted(objects, key=lambda stored: stored.key)


# --- Step 1: the current tables --------------------------------------------------------------------------------------


@dataclass
class Lane:
    """One lane's or leg's dataset: the load of each table a build reads now, or why that could not be told."""

    name: str
    current: dict[str, str]  # table -> the load id a build reads it from
    reads: str  # what "current" means for this lane, for the listing
    error: str | None = None


def lanes_in(store: Store, resources: list) -> list[Lane]:
    """Every lane or leg with a dataset in the bucket, and its current loads (the module docstring, step 1). Marks each
    current file `current`."""
    lanes = []
    for name in sorted({stored.lane for stored in store.objects if stored.lane}):
        if name not in LANES and name not in LEGS:
            lanes.append(Lane(name, {}, "no workflow runs this lane, so no build reads its tables"))
            continue
        loads = f"{RAW_STORE_PREFIX}/{name}/{DATASET}/_dlt_loads/"
        if not any(stored.key.startswith(loads) for stored in store.objects):
            lanes.append(Lane(name, {}, "no load of it has committed, so no build reads its tables"))
            continue
        try:
            pipeline = make_pipeline(name, store.lane_url(name), store.pipelines_dir)
            complete = committed_load_ids(pipeline)
            log = leg_run_log_rows(pipeline, complete) if name in LEGS else run_log_rows(pipeline)
            current = committed_tables(pipeline, log=log, complete=complete)
        except Exception as failure:  # noqa: BLE001 - a lane that cannot be read is unknown, and refuses the delete
            lanes.append(Lane(name, {}, "", error=f"its run log could not be read ({_why(failure)})"))
            continue
        if name in LEGS:
            read_now = leg_tables(name, resources)
            current = {table: load_id for table, load_id in current.items() if table in read_now}
            reads = "each table its job reads now, at its newest committed load"
        else:
            reads = "each table, at its newest committed load"
        lanes.append(Lane(name, current, reads))
    by_name = {lane.name: lane for lane in lanes}
    for stored in store.objects:
        lane = by_name.get(stored.lane)
        if lane is not None and stored.kind == PARQUET and lane.current.get(stored.table) == stored.load_id:
            stored.current = True
    return lanes


# --- Step 2: reading each object ------------------------------------------------------------------------------------


def read_parquet(store: Store, stored: Stored, rule: FieldRule) -> None:
    """The listed fields in a Parquet file's schema, each with its rows and how many carry a value."""
    with store.fs.open(stored.path, "rb", block_size=PARQUET_BLOCK) as handle:
        parquet = pq.ParquetFile(handle)
        held = {name: rule.listed_by(name) for name in parquet.schema_arrow.names}
        held = {name: listed for name, listed in held.items() if listed}
        if held:
            columns = parquet.read(columns=sorted(held))
            for name, listed in held.items():
                stored.fields[name] = Holding(listed, columns.num_rows, _values(columns.column(name)))


def _values(column) -> int:
    """How many of a column's rows carry a value: not null, and for text not the empty string."""
    if pa.types.is_string(column.type) or pa.types.is_large_string(column.type) or pa.types.is_string_view(column.type):
        return pc.sum(pc.fill_null(pc.not_equal(column, ""), False)).as_py() or 0
    return len(column) - column.null_count


def json_keys(handle) -> Counter:
    """{(key, the value's first bytes if it is empty, else b""): occurrences} for every key in a JSON stream, read
    JSON_CHUNK at a time (JSON_KEY)."""
    counts: Counter = Counter()
    carry = b""
    while True:
        chunk = handle.read(JSON_CHUNK)
        data = carry + chunk
        # A match starting before `limit` ends inside `data`; one starting at or after it is found again from the carry.
        limit = len(data) if not chunk else max(0, len(data) - JSON_OVERLAP)
        resume, found = 0, []
        for match in JSON_KEY.finditer(data):
            if match.start() >= limit:
                break
            found.append(match.group(1, 2))
            resume = match.end()
        counts.update(found)
        if not chunk:
            return counts
        carry = data[max(resume, limit) :]


def _decoded(key: bytes) -> str:
    """A key's text, its JSON escapes undone (a `\\u00e9` is the letter it stands for)."""
    try:
        return json.loads(b'"' + key + b'"')
    except ValueError:
        return key.decode("utf-8", "replace")


def read_json(store: Store, stored: Stored, rule: FieldRule) -> None:
    """The listed fields among a JSON file's keys, each with its occurrences and how many carry a value."""
    with store.fs.open(stored.path, "rb", block_size=JSON_CHUNK) as handle:
        counts = json_keys(handle)
    per_key: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (raw, empty), occurrences in counts.items():
        tally = per_key[_decoded(raw)]
        tally[0] += occurrences
        if empty not in JSON_EMPTY:
            tally[1] += occurrences
    for name, (occurrences, with_value) in per_key.items():
        if listed := rule.listed_by(name):
            stored.fields[name] = Holding(listed, occurrences, with_value)


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def read_duckdb(store: Store, stored: Stored, rules: FieldRules, scratch: Path) -> None:
    """The listed fields in a DuckDB file's tables: downloaded whole, attached read-only, its catalog read.

    A table in the `raw` schema is judged by its own table's rule, every other table by PERSON_FIELDS (FieldRules).
    A view stores no rows, so only base tables are read. The download is deleted before the next one starts.
    """
    handle, name = tempfile.mkstemp(suffix=".duckdb", dir=scratch)
    os.close(handle)
    local = Path(name)
    try:
        store.fs.get_file(stored.path, str(local))
        with duckdb.connect() as con:
            con.execute(f"ATTACH {_literal(str(local))} AS stored (READ_ONLY)")
            columns = con.execute(
                "select c.schema_name, c.table_name, c.column_name from duckdb_columns() c "
                "join duckdb_tables() t using (database_name, schema_name, table_name) "
                "where c.database_name = 'stored' order by all"
            ).fetchall()
            for schema, table, column in columns:
                listed = rules(table if schema == "raw" else None).listed_by(column)
                if listed:
                    rows, with_value = con.execute(
                        f"select count(*), count(nullif(cast({_quoted(column)} as varchar), '')) "
                        f"from stored.{_quoted(schema)}.{_quoted(table)}"
                    ).fetchone()
                    stored.fields[f"{schema}.{table}.{column}"] = Holding(listed, rows, with_value)
    finally:
        local.unlink(missing_ok=True)
        local.with_name(local.name + ".wal").unlink(missing_ok=True)


def _json_record(store: Store, path: str) -> dict:
    with store.fs.open(path, "r") as handle:
        return json.load(handle)


def name_the_landed_files(store: Store) -> list[str]:
    """Give each as-landed file the table its record names: a lane load's index.json, or a pin's raw_inputs.json,
    which also records each pinned file's sha256. Returns the records that could not be read, each with why."""
    problems = []
    lane_root = RAW_STORE_PREFIX.split("/")
    depth = len(lane_root)
    by_key = {stored.key: stored for stored in store.objects}
    for record in [stored for stored in store.objects if stored.kind == RECORD]:
        parts = record.key.split("/")
        try:
            if parts[:depth] == lane_root and len(parts) == depth + 4 and parts[depth + 1] == AS_LANDED_PREFIX:
                folder = "/".join(parts[:-1])
                for table, path in _json_record(store, record.path).items():
                    if (landed := by_key.get(f"{folder}/{path}")) is not None:
                        landed.table = table
            elif parts[0] == STEPS_PREFIX and parts[1:2] == [RAW_INPUTS_PREFIX] and parts[3:] == [PIN_MANIFEST]:
                folder = "/".join(parts[:3])
                for path, entry in (_json_record(store, record.path).get("as_landed") or {}).items():
                    if (landed := by_key.get(f"{folder}/{AS_LANDED_PREFIX}/{path}")) is not None:
                        landed.table, landed.digest = entry.get("table"), entry.get("sha256")
        except Exception as failure:  # noqa: BLE001 - its files are then read on PERSON_FIELDS alone, and this is said
            problems.append(f"{record.key}: {_why(failure)}")
    return problems


def _read_one(store: Store, stored: Stored, rules: FieldRules, scratch: Path) -> None:
    try:
        if stored.kind == PARQUET:
            read_parquet(store, stored, rules(stored.table))
        elif stored.kind == JSON_ROWS:
            read_json(store, stored, rules(stored.table))
        elif stored.kind == DUCKDB:
            read_duckdb(store, stored, rules, scratch)
        stored.read = True
    except FileNotFoundError:
        # The hourly legs are not in raw-lake-monthly: a notices run trims its served copies and a load replaces its
        # tables while this reads. What is gone holds nothing, and what replaced it is a run under today's rule.
        stored.gone = True
    except Exception as failure:  # noqa: BLE001 - an object that cannot be read is listed, never taken as clean
        stored.error = _why(failure)


def _why(failure: Exception) -> str:
    """An error's type and the start of its message, on one line (ERROR_CHARS)."""
    message = " ".join(str(failure).split())
    return f"{type(failure).__name__}: {message[:ERROR_CHARS]}{'...' if len(message) > ERROR_CHARS else ''}"


def held_units(objects: list[Stored]) -> set[str]:
    """Every unit with an object that holds a listed field: each is deleted whole."""
    return {stored.unit for stored in objects if stored.unit and stored.holds}


def read_everything(store: Store, rules: FieldRules, scratch: Path, readers: int, timings: dict[str, float]) -> None:
    """Every Parquet file first, since each costs a footer and they decide most units; then every JSON file outside the
    units those decided, a pinned as-landed file once per recorded sha256; then every DuckDB file left, one at a time."""
    started = time.monotonic()
    with ThreadPoolExecutor(readers) as pool:
        list(pool.map(lambda stored: _read_one(store, stored, rules, scratch), [s for s in store.objects if s.kind == PARQUET]))
    timings["Parquet schemas"] = time.monotonic() - started

    started = time.monotonic()
    held = held_units(store.objects)
    waiting = [stored for stored in store.objects if stored.kind == JSON_ROWS and stored.unit not in held]
    first_of: dict[str, Stored] = {}
    for stored in waiting:
        if stored.digest and stored.digest in first_of:
            stored.copy_of = first_of[stored.digest].key
        elif stored.digest:
            first_of[stored.digest] = stored
    with ThreadPoolExecutor(readers) as pool:
        list(pool.map(lambda stored: _read_one(store, stored, rules, scratch), [s for s in waiting if s.copy_of is None]))
    # A copy takes its twin's answer only when the twin was read; one whose twin was gone or would not read is read
    # itself, so that no object is kept on an answer nobody got.
    unanswered = []
    for stored in waiting:
        if stored.copy_of is not None:
            source = first_of[stored.digest]
            if source.read:
                stored.fields, stored.read = dict(source.fields), True
            else:
                stored.copy_of = None
                unanswered.append(stored)
    with ThreadPoolExecutor(readers) as pool:
        list(pool.map(lambda stored: _read_one(store, stored, rules, scratch), unanswered))
    timings["JSON keys"] = time.monotonic() - started

    started = time.monotonic()
    held = held_units(store.objects)
    for stored in store.objects:
        if stored.kind == DUCKDB and stored.unit not in held:
            _read_one(store, stored, rules, scratch)
    timings["DuckDB catalogs"] = time.monotonic() - started


# --- The answer -----------------------------------------------------------------------------------------------------


@dataclass
class Answer:
    """What steps 1 and 2 found: the lanes, every object, and from those what a delete removes and what refuses it."""

    store: Store
    rules: FieldRules
    lanes: list[Lane]
    record_problems: list[str]
    timings: dict[str, float]

    @cached_property
    def held(self) -> set[str]:
        return held_units(self.store.objects)

    @property
    def doomed(self) -> list[Stored]:
        """Every object a delete removes: each holding object that stands alone, and every object of a held unit."""
        held = self.held
        return [
            stored
            for stored in self.store.objects
            if not stored.current and not stored.gone and (stored.unit in held or (stored.unit is None and stored.holds))
        ]

    @property
    def current_holders(self) -> list[Stored]:
        return [stored for stored in self.store.objects if stored.current and stored.holds]

    @property
    def unreadable(self) -> list[Stored]:
        """Objects that could not be read, outside every unit that goes whole anyway."""
        held = self.held
        return [stored for stored in self.store.objects if stored.error and stored.unit not in held]

    @property
    def complete(self) -> bool:
        return not self.unreadable and not self.record_problems and not any(lane.error for lane in self.lanes)

    @property
    def clean_now(self) -> bool:
        return not self.current_holders


def find(bucket_url: str, pipelines_dir: str, scratch: Path, readers: int = READERS, resources: list | None = None) -> Answer:
    """Steps 1 and 2 of the module docstring. Changes nothing. `resources` are discover()'s unless a test hands its own."""
    timings: dict[str, float] = {}
    started = time.monotonic()
    store = open_store(bucket_url, pipelines_dir)
    timings["listing the bucket"] = time.monotonic() - started
    if resources is None:
        resources = all_resources(discover() + discover_shared())
    rules = FieldRules(resources)
    started = time.monotonic()
    lanes = lanes_in(store, resources)
    timings["the lanes' run logs"] = time.monotonic() - started
    record_problems = name_the_landed_files(store)
    read_everything(store, rules, scratch, readers, timings)
    return Answer(store, rules, lanes, record_problems, timings)


# --- The listing ----------------------------------------------------------------------------------------------------


def _count(number: int, one: str, many: str | None = None) -> str:
    return f"{number:,} {one if number == 1 else (many or one + 's')}"


def _size(size: int) -> str:
    if size >= 1_000_000:
        return f"{size / 1e6:,.1f} MB"
    return f"{size / 1e3:,.1f} KB" if size >= 1_000 else f"{size:,} bytes"


def _fields(fields: dict[str, Holding], unit: str = "rows") -> str:
    return "; ".join(
        f"{name} ({holding.listed_by}): {holding.with_value:,} of {holding.rows:,} {unit} with a value"
        for name, holding in sorted(fields.items())
    )


def _of(stored: Stored) -> str:
    return _fields(stored.fields, "occurrences" if stored.kind == JSON_ROWS else "rows")


def pins(answer: Answer) -> tuple[list[str], list[str]]:
    """(the pins a delete removes, the pins it keeps), each oldest first: a raw_run sorts in time order."""
    every = sorted({stored.unit for stored in answer.store.objects if stored.area == f"{STEPS_PREFIX}/{RAW_INPUTS_PREFIX}"})
    held = answer.held
    return [unit for unit in every if unit in held], [unit for unit in every if unit not in held]


def listing(answer: Answer, deleting: bool) -> list[str]:
    """The answer as plain lines for the job's log: keys, field names and counts, never a value."""
    store, lines = answer.store, []
    lines.append(
        f"Decision 56's purge of person fields, {'DELETING' if deleting else 'listing only'}: {store.url}, "
        f"{_count(len(store.objects), 'object')}, {_size(sum(s.size for s in store.objects))}. "
        "Field names and counts only, never a value."
    )

    lines += ["", "1. THE CURRENT TABLES, which every build and every new pin reads"]
    for lane in answer.lanes:
        if lane.error:
            lines.append(f"   {lane.name}: NOT KNOWN, {lane.error}")
            continue
        files = [stored for stored in store.objects if stored.lane == lane.name and stored.current]
        found_in: dict[str, dict[str, Holding]] = defaultdict(dict)
        for stored in files:
            for name, found in stored.fields.items():
                total = found_in[stored.table].setdefault(name, Holding(found.listed_by, 0, 0))
                total.rows += found.rows
                total.with_value += found.with_value
        holding = {table: fields for table, fields in found_in.items() if any(h.with_value for h in fields.values())}
        empty = sorted(set(found_in) - set(holding))
        verdict = "none holds a person field" if not holding else f"{_count(len(holding), 'table')} HOLD a person field"
        lines.append(
            f"   {lane.name}: {_count(len(lane.current), 'table')} ({lane.reads}), {_count(len(files), 'file')} read: {verdict}"
        )
        if empty:
            lines.append(
                f"     {_count(len(empty), 'table')} keep a listed field's column with no value in any row, as dlt keeps "
                f"every column its schema has seen; nothing to delete: {', '.join(empty)}"
            )
        for table, fields in sorted(holding.items()):
            reread = (
                "a resource still lands it, and lands it without the field when it next reads it"
                if table in answer.rules.resources
                else "NO RESOURCE LANDS IT ANY MORE, so nothing will read it again"
            )
            lines.append(f"     {table}: {_fields(fields)}; {reread}")
    if not answer.clean_now:
        lines.append("   A delete refuses while a current table holds one, and deletes nothing.")
    elif not any(lane.error for lane in answer.lanes):
        lines.append("   Clean: no current table holds a person field.")

    doomed = answer.doomed
    held = sorted(answer.held)
    alone = [stored for stored in doomed if stored.unit is None]
    lines += [
        "",
        f"2. EVERY OTHER STORED OBJECT THAT HOLDS ONE: {_count(len(doomed), 'object')}, "
        f"{_size(sum(stored.size for stored in doomed))}: {_count(len(held), 'unit')} deleted whole and "
        f"{_count(len(alone), 'object')} on {'its' if len(alone) == 1 else 'their'} own",
    ]
    for unit in held:
        members = [stored for stored in store.objects if stored.unit == unit]
        first = [stored.key.removeprefix(unit) for stored in members if stored.first]
        lines.append(
            f"   {unit} ({_unit_name(unit)}, {_count(len(members), 'object')}, {_size(sum(s.size for s in members))}"
            + (f"; {', '.join(first)} deleted first" if first else "")
            + ")"
        )
        holders = [stored for stored in members if stored.holds]
        for stored in holders:
            lines.append(f"     {stored.key.removeprefix(unit)}: {_of(stored)}")
        if len(members) > len(holders):
            lines.append(f"     and {_count(len(members) - len(holders), 'other object')} of this unit, deleted with it")
    for stored in alone:
        lines.append(f"   {stored.key}: {_of(stored)}")
    gone, kept = pins(answer)
    lines.append(
        f"   Pins: {len(gone):,} {'deleted' if deleting else 'to delete'}, {len(kept):,} kept"
        + (f", the newest kept {kept[-1]}" if kept else "")
        + ". If the raw_run UA serves is among those deleted, the next promotion needs a fresh UA build "
        "(a refresh-reference.yml run)."
    )

    unread = [stored for stored in store.objects if stored.kind == UNREAD and stored.unit not in answer.held]
    lines += ["", f"3. NOT READ: {_count(len(unread), 'object')} in formats this script does not read"]
    for stored in unread:
        lines.append(f"   {stored.key} ({_size(stored.size)})")

    clean = [stored for stored in store.objects if stored.read and not stored.holds and not stored.current]
    copies = sum(1 for stored in clean if stored.copy_of is not None)
    hollow = sum(1 for stored in clean if stored.empty_columns)
    skipped = sum(1 for stored in store.objects if stored.unit in answer.held and not stored.read)
    records = sum(1 for stored in store.objects if stored.kind in (RECORD, DLT) and stored.unit not in answer.held)
    lines += ["", f"4. READ, AND HOLDING NONE: {_count(len(clean), 'object')}"]
    for area, number in sorted(Counter(stored.area for stored in clean).items()):
        lines.append(f"   {area}: {number:,}")
    if hollow:
        lines.append(f"   ({_count(hollow, 'object')} of these keep a listed field's column with no value in any row)")
    if copies:
        lines.append(f"   ({_count(copies, 'pinned as-landed file')} judged by the copy whose recorded sha256 it shares)")
    lines.append(
        f"   Not read: {skipped:,} more objects of the units that go whole, and {records:,} records and dlt bookkeeping "
        "files, which hold no rows."
    )
    if gone := sum(1 for stored in store.objects if stored.gone):
        lines.append(f"   Gone before they were read: {_count(gone, 'object')}, replaced or trimmed by a lane's own run.")

    lines += ["", f"5. COULD NOT BE READ: {_count(len(answer.unreadable) + len(answer.record_problems), 'object')}"]
    lines += [f"   {stored.key}: {stored.error}" for stored in answer.unreadable]
    lines += [f"   {problem}" for problem in answer.record_problems]
    lines += ["", "Timings: " + ", ".join(f"{part} {seconds:.1f} s" for part, seconds in answer.timings.items())]
    return lines


#: The most lines one list on the summary page holds. GitHub refuses a step summary over 1 MiB, and the job's log
#: keeps every key whatever this cuts.
SUMMARY_LINES = 400


def _capped(lines: list[str]) -> list[str]:
    if len(lines) <= SUMMARY_LINES:
        return lines
    return [*lines[:SUMMARY_LINES], f"- and {len(lines) - SUMMARY_LINES:,} more, every one of them in the job's log"]


def summary(answer: Answer, deleting: bool, verdict: str, deleted: list[str]) -> str:
    """The answer as Markdown for the run's summary page: what each step found, by unit and key, never a value. Each
    deleted key is in the job's log; here the units and objects they made up, so the page stays under GitHub's cap."""
    rows = []
    for lane in answer.lanes:
        tables = sorted({stored.table for stored in answer.current_holders if stored.lane == lane.name})
        if lane.error:
            state = f"not known: {lane.error}"
        elif tables:
            state = "holds a person field: " + ", ".join(f"`{table}`" for table in tables)
        else:
            state = "clean"
        rows.append(f"| `{lane.name}` | {len(lane.current):,} | {state} |")
    doomed = answer.doomed
    gone, kept = pins(answer)
    found = [f"- `{unit}` ({_unit_name(unit)}, whole)" for unit in sorted(answer.held)]
    found += [f"- `{stored.key}`" for stored in doomed if stored.unit is None]
    text = [
        "## Purge of person fields (decision 56)",
        "",
        f"**{verdict}**",
        "",
        "### 1. The current tables",
        "",
        "| lane | tables | person fields |",
        "|---|---|---|",
        *rows,
        "",
        f"### 2. Stored objects holding one: {len(doomed):,}, {_size(sum(s.size for s in doomed))}"
        + (f", {len(deleted):,} deleted" if deleting else ""),
        "",
        *_capped(found),
        "",
        f"Pins: {len(gone):,} {'deleted' if deleting else 'to delete'}, {len(kept):,} kept"
        + (f", the newest kept `{kept[-1]}`." if kept else "."),
    ]
    unread = [stored for stored in answer.store.objects if stored.kind == UNREAD and stored.unit not in answer.held]
    if unread:
        text += ["", f"### Not read: {len(unread):,}", "", *_capped([f"- `{stored.key}`" for stored in unread])]
    problems = [f"- `{stored.key}`: {stored.error}" for stored in answer.unreadable]
    problems += [f"- {problem}" for problem in answer.record_problems]
    if problems:
        text += ["", f"### Could not be read: {len(problems):,}", "", *_capped(problems)]
    return "\n".join(text) + "\n"


# --- Step 3: the delete ---------------------------------------------------------------------------------------------


def _delete_one(store: Store, stored: Stored) -> str | None:
    """Delete one object; None when it is gone, or why it is not."""
    try:
        store.fs.rm_file(stored.path)
    except FileNotFoundError:
        return None  # gone already: a notices run's own trim of its served copies, say
    except Exception as failure:  # noqa: BLE001 - reported by key, and the run ends 1
        return _why(failure)
    return None


def delete(answer: Answer, readers: int = READERS) -> tuple[list[str], list[str]]:
    """Delete exactly answer.doomed, every unit's first objects before any other, printing each key as it goes. Then
    list the bucket again and check every deleted key gone. Returns (the keys deleted, the problems)."""
    store, doomed = answer.store, answer.doomed
    deleted, problems = [], []
    for batch in ([stored for stored in doomed if stored.first], [stored for stored in doomed if not stored.first]):
        with ThreadPoolExecutor(readers) as pool:
            for stored, problem in zip(batch, pool.map(lambda stored: _delete_one(store, stored), batch), strict=True):
                if problem is None:
                    deleted.append(stored.key)
                    print(f"deleted {stored.key}")
                else:
                    problems.append(f"{stored.key}: not deleted ({problem})")
    remaining = {stored.key for stored in list_bucket(store)} & set(deleted)
    problems += [f"{key}: deleted, and listed again afterwards" for key in sorted(remaining)]
    return deleted, problems


# --- The command ----------------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None, resources: list | None = None) -> int:
    """The command line. `resources` are discover()'s unless a test hands its own (find())."""
    parser = argparse.ArgumentParser(
        description="Decision 56's purge: list, and with --delete delete, every stored copy of a person field "
        "(this module's docstring)."
    )
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--raw-bucket", help="the private raw bucket's name, as R2_RAW_BUCKET holds it")
    where.add_argument("--bucket-url", help="the bucket's root as a URL: s3://<bucket>, or file:///a/local/store")
    parser.add_argument(
        "--delete", action="store_true", help="delete what the listing names, unless a current table still holds a field"
    )
    parser.add_argument("--summary", type=Path, help="append the answer as Markdown to this file ($GITHUB_STEP_SUMMARY)")
    parser.add_argument("--pipelines-dir", help="dlt's working directory (default: a new temporary one)")
    parser.add_argument("--scratch", type=Path, help="where a DuckDB file is downloaded to read (default: a temporary one)")
    parser.add_argument("--readers", type=int, default=READERS, help=f"objects read at once (default {READERS})")
    args = parser.parse_args(argv)
    if args.raw_bucket is not None:
        raw_store_url(args.raw_bucket, "monthly")  # refuses anything but a bucket's bare name
        bucket_url = f"s3://{args.raw_bucket}"
    else:
        bucket_url = args.bucket_url

    with tempfile.TemporaryDirectory() as temporary:
        scratch = args.scratch or Path(temporary)
        scratch.mkdir(parents=True, exist_ok=True)
        answer = find(bucket_url, args.pipelines_dir or str(Path(temporary) / "dlt"), scratch, args.readers, resources)
    for line in listing(answer, args.delete):
        print(line)

    deleted: list[str] = []
    status = 0
    if not answer.complete:
        verdict = "Incomplete: an object or a run log could not be read (section 5), so nothing was deleted."
        print(f"::error title=The purge could not read everything::{verdict}")
        status = 1
    elif not answer.clean_now and args.delete:
        verdict = "Refused: a current table still holds a person field (section 1), so nothing was deleted."
        print(f"::error title=A current table still holds a person field::{verdict}")
        status = 1
    elif not args.delete:
        verdict = (
            f"Listing only, nothing deleted. A dispatch with delete=true deletes the {len(answer.doomed):,} objects in section 2."
        )
        if not answer.clean_now:
            verdict = (
                "Listing only, nothing deleted. A dispatch with delete=true would refuse: a current table still holds a "
                "person field (section 1)."
            )
            print(f"::warning title=A current table still holds a person field::{verdict}")
    else:
        print("")
        print(f"DELETING {len(answer.doomed):,} objects, every unit's record first:")
        deleted, problems = delete(answer, args.readers)
        for problem in problems:
            print(f"::error title=A delete did not take::{problem}")
        verdict = f"Deleted {len(deleted):,} objects; {len(problems):,} problems."
        status = 1 if problems else 0
    print("")
    print(verdict)
    if args.summary is not None:
        with args.summary.open("a", encoding="utf-8") as handle:
            handle.write(summary(answer, args.delete, verdict, deleted))
    return status


if __name__ == "__main__":
    sys.exit(main())
