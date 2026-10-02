"""Run one lane: change checks, extract, normalize, the run check, load, the after-run check, the run log.

Usage: python -m extract._run --lane monthly --bucket-url file:///path/to/raw-store
       python -m extract._run --lane conditions_ua --raw-bucket our-hike-raw \\
           --warehouse data/warehouse.duckdb --summary "$GITHUB_STEP_SUMMARY"
       python -m extract._run --lane monthly --only raw_registry__sources \\
           --bucket-url file:///tmp/registry-store --warehouse data/warehouse.duckdb

`--lane` is a lane (`monthly`, `hourly`) or a conditions leg
(`conditions_production`, `conditions_ua`: the hourly lane for one data
environment, in a dlt pipeline of its own; LEGS below). `--raw-bucket` names
the private raw bucket and puts the run at its pipeline's own prefix
(raw_store_url); `--bucket-url` gives the whole URL instead. `--only` keeps
the named tables of the lane and nothing else. `--warehouse` loads every
table the run's pipeline has committed into that DuckDB file's `raw` schema
afterwards (extract/_warehouse.py's committed-file read). `--summary` appends
the run's evidence, as Markdown, to a file: rows and the upstream's own
count per table, every refusal and unavailable resource, and how long each
part took. It is written on a refused run too, before the exit.

A conditions leg isolates each upstream: it reads every resource on its own
first, within `--read-seconds`, and one whose read fails, runs out of time or
is refused by the run check is left out while the rest load, its last
committed table standing. OurHike's own Postgres rows still stop the whole
leg (stops_the_leg). A leg that left something out exits PARTIAL_EXIT (3),
so its job still goes red after it has published what did load.

pipeline/ELT.md, "Change checks, verdicts and `_loaded_at`" and "A full reload
that cannot empty a safety table", is the design (#1793 — Rebuild the data
platform as dlt → dbt: seven contracted marts, a monthly refresh, published
docs, and lighter phone downloads). In order:

1. Each resource's change check runs, before dlt. FRESH leaves the resource
   out of the run, so its table keeps the rows it has; STALE and UNKNOWN both
   read it whole.
2. dlt extracts and normalizes what is left, every table `replace`.
3. The run check: each table present, non-empty unless its type may be empty
   and the upstream's own count says zero, not shorter than that count, and
   not collapsed below half its last loaded size. A failure aborts the
   package, so nothing lands and no change marker advances.
4. The load, then the after-run check: the load committed, and the rows on
   disk are the rows normalized. A failure records `unverified`, and the
   warehouse step refuses to read the tables (extract/_warehouse.py).
5. One `_extract_runs` row per resource per run, skipped ones included.

What is not built yet, and ELT.md designs: the as-sent copy beside dlt's
normalized one (`_source_path`), the raw lake (DuckLake) for the monthly lane,
the daily and weekly lanes, and fixture mode for CI's dbt job.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Before dlt is imported, and here as well as in .dlt/config.toml, so a run
# started from any directory has both: telemetry is on by default, to
# telemetry.scalevector.ai, from a job holding R2 write keys; and `snake_case`,
# dlt's default naming, turns `GlobalID` into `global_id` where 16 staging
# models read `globalid` (ELT.md, "dlt configuration requirements").
os.environ.setdefault("RUNTIME__DLTHUB_TELEMETRY", "false")
os.environ.setdefault("SCHEMA__NAMING", "sql_ci_v1")

import dlt  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from extract._contract import CADENCES, Resource, Unavailable, all_resources, discover, discover_shared  # noqa: E402
from extract._kinds import ORGS_TABLE, ConditionsQuery  # noqa: E402
from lib.freshness_state import Freshness  # noqa: E402

# Which cadences each lane carries. Daily and weekly resources would ride the
# hourly pipeline when due (ELT.md); none of the folders extracted so far has
# one, so no lane carries them yet and the layout test refuses one.
LANES = {"monthly": ("monthly",), "hourly": ("hourly", "daily")}
# The conditions legs: publish-conditions.yml runs the hourly lane once per
# data environment, and each leg is a dlt pipeline of its own, so each has its
# own prefix in the raw store, its own markers and its own `_extract_runs`.
# OurHike's Postgres rows are why: each leg reads its own environment's
# database (ConditionsQuery's CONDITIONS_DATABASE_URL), and one pipeline for
# both would replace production's closures table with UA's and back again
# every hour, which the workflow's matrix exists to prevent (ELT.md, "The
# hourly lanes"). ELT.md names per-environment raw tables for that
# (`raw_ourhike_production__*`); a pipeline per leg separates them by prefix
# instead and leaves every table name, and so every dbt source, as it is
# (Reasoned). Not in LANES, so fixture mode, which runs each lane of LANES,
# does not run the hourly resources three times.
LEGS = {"conditions_production": "hourly", "conditions_ua": "hourly"}
# A daily resource has no job of its own: it rides the hourly lane and runs
# when its last good check is a day old, so no second job writes the hourly
# lane's raw store (ELT.md, "Every node carries its cadence"). NYNJTC's alert
# taxonomy terms are the one daily resource; a renamed term moves no post's
# `modified`, so the posts' own marker cannot see it (Reasoned).
DUE_AFTER = {"daily": timedelta(hours=24)}
DATASET = "raw"
SOURCE_NAME = "extract"
RUNS_TABLE = "_extract_runs"
# The verdict and outcome a resource is logged with when its change check
# raised Unavailable: left out of the run, and withdrawn from the warehouse.
UNAVAILABLE = "unavailable"

# @unvalidated: a table whose type may not be empty fails the run when it
# lands below this share of its last loaded size. 0.5 is fetch_opentrail.py's
# MAX_FEATURE_DROP_RATIO, the one precedent here; six monthly runs of
# _extract_runs give the smallest legitimate ratio per type, which is what
# would settle it. Closures and warnings have no floor: every closure lifted
# is exactly what a closures layer emptying looks like.
COLLAPSE_FLOOR = 0.5


class ExtractRefused(RuntimeError):
    """The run check or the after-run check failed. Nothing this run loaded may be read.

    `report` is the refused run's RunReport, so the command line can still
    write its summary: which tables, which counts, and why."""

    def __init__(self, message: str, report: RunReport | None = None):
        super().__init__(message)
        self.report = report


@dataclass
class Planned:
    resource: Resource
    verdict: Freshness
    recorded: dict | None
    marker: dict | None


@dataclass
class RunReport:
    run_id: str
    lane: str
    outcome: str
    load_id: str | None = None
    rows: dict[str, int] = field(default_factory=dict)
    proofs: dict[str, int] = field(default_factory=dict)
    verdicts: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    # Each table's column hints, as to_dlt handed them to dlt. Kept in the run
    # log only for a proven zero, which is the one case the warehouse needs them.
    hints: dict[str, dict] = field(default_factory=dict)
    # Resources whose change check raised Unavailable, by name: why each was left out.
    unavailable: dict[str, str] = field(default_factory=dict)
    # Seconds each part of the run took, in the order they ran: the change
    # checks, extract, normalize, load, the run log. A part a run did not
    # reach is absent.
    timings: dict[str, float] = field(default_factory=dict)
    # A conditions leg only: resources refused on their own while the rest
    # loaded, by name, with why. Each keeps its last committed table and is
    # logged `refused` (ISOLATED_OUTCOME); the command line then exits
    # PARTIAL_EXIT, so the run still goes red.
    isolated: dict[str, str] = field(default_factory=dict)


@contextmanager
def timed(report: RunReport, part: str):
    """Add the seconds the block took to `report.timings[part]`, even when it raises."""
    started = time.monotonic()
    try:
        yield
    finally:
        report.timings[part] = report.timings.get(part, 0.0) + time.monotonic() - started


def utc_now_naive() -> datetime:
    """Naive UTC, load_raw.py's convention for `_loaded_at`, so a timestamp compares the same in DuckDB and in dbt."""
    return datetime.now(UTC).replace(tzinfo=None)


def cadences_of(lane: str) -> tuple[str, ...]:
    """The cadences a lane, or a conditions leg's lane, carries."""
    if lane in LEGS:
        return LANES[LEGS[lane]]
    if lane not in LANES:
        raise ValueError(f"no lane {lane!r}; lanes are {sorted(LANES)} and legs {sorted(LEGS)}")
    return LANES[lane]


def lane_resources(lane: str, resources: list[Resource]) -> list[Resource]:
    return [resource for resource in resources if resource.cadence in cadences_of(lane)]


#: The raw store's prefix for dlt's files, inside the private bucket: raw
#: under `raw/` (decision 43) and one prefix per dlt pipeline (ELT.md,
#: "Storage tiers": `dlt/<pipeline>/raw/<table>/…`), where dlt itself adds
#: the dataset, `raw`, and the table.
RAW_STORE_PREFIX = "raw/dlt"


def raw_store_url(bucket: str, lane: str) -> str:
    """`s3://<bucket>/raw/dlt/ourhike_<lane>`: one lane's, or one leg's, own prefix in the raw store.

    The prefix is the dlt pipeline's name, so two legs never share a table
    file, a marker or a run log. dlt reads the endpoint and the keys from
    `DESTINATION__FILESYSTEM__CREDENTIALS__*`, never from here.
    """
    cadences_of(lane)  # refuses an unknown lane before any URL is made
    if not bucket or "/" in bucket or ":" in bucket:
        raise ValueError(f"{bucket!r} is not a bucket name; pass the bucket alone, as R2_RAW_BUCKET holds it")
    return f"s3://{bucket}/{RAW_STORE_PREFIX}/ourhike_{lane}"


#: The exit status of a conditions leg that loaded, and left at least one
#: resource out as refused: not 0, so the job goes red, and not 1, so the
#: workflow can tell "the rest loaded" from "nothing loaded" and still build
#: and publish what did. 2 is argparse's own.
PARTIAL_EXIT = 3
ISOLATED_OUTCOME = "refused"


def stops_the_leg(resource: Resource) -> bool:
    """Whether a refused or failed read of this resource stops the whole leg, rather than only itself.

    OurHike's own conditions rows do (ConditionsQuery): their reader's problem
    "stops the lane, as it stops the bake" (extract/_shared/ourhike/closures.py),
    because export_conditions.py today publishes nothing when it cannot read
    the database, and a phone then keeps the last file with its true age.
    Every other upstream is somebody else's site, and its failure is its own:
    the leg leaves it out and its last committed table stands, as today's bake
    carries ATC's and NYNJTC's previous cache forward when either is
    unreachable (publish-conditions.yml's fetch steps).
    """
    return isinstance(resource, ConditionsQuery)


def read_each(report: RunReport, to_run: list[Planned], seconds: float | None) -> tuple[list[Planned], dict]:
    """Read every resource's rows before dlt runs, so one upstream's failure, or its slowness, is its own.

    One thread per extract folder, so a club's own resources are asked one
    after another, as they would be in one run, and no host is asked twice at
    once; the folders run side by side. `seconds` is the whole read's budget:
    a folder still reading when it runs out leaves its unread resources out
    of this run. Nothing waits on them, and nothing shortens a host's
    Crawl-delay to fit (lib/http_retry.py's throttle is the resource's own);
    a daemon thread is abandoned, and dies with the process.

    Returns the resources that answered, and {name: rows}. A resource whose
    read failed, or ran out of time, is in `report.isolated`, or, where
    stops_the_leg() says so, re-raised.
    """
    results: dict[str, object] = {}

    def read(items: list[Planned]) -> None:
        for item in items:
            proofs: dict[str, int] = {}
            try:
                rows = list(item.resource.rows(proofs))
            except Exception as failure:  # noqa: BLE001 - every failure is recorded, and re-raised where it stops the leg
                results[item.resource.name] = failure
            else:
                results[item.resource.name] = (rows, proofs)

    by_folder: dict[str | None, list[Planned]] = defaultdict(list)
    for item in to_run:
        by_folder[item.resource.club].append(item)
    threads = [
        threading.Thread(target=read, args=(items,), name=f"read {folder}", daemon=True) for folder, items in by_folder.items()
    ]
    deadline = None if seconds is None else time.monotonic() + seconds
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(None if deadline is None else max(0.0, deadline - time.monotonic()))
    answered = dict(results)  # a thread that finishes after the deadline changes nothing below

    kept, read_rows = [], {}
    for item in to_run:
        name = item.resource.name
        outcome = answered.get(name)
        if outcome is None:
            failure: BaseException = TimeoutError(f"no answer within the leg's {seconds:g} s read budget")
        elif isinstance(outcome, BaseException):
            failure = outcome
        else:
            rows, proofs = outcome
            report.proofs.update(proofs)
            read_rows[name] = rows
            kept.append(item)
            continue
        if stops_the_leg(item.resource):
            raise failure
        report.isolated[name] = f"read failed: {type(failure).__name__}: {failure}"
        print(f"::error title={name} refused::{report.isolated[name]}; its last committed table stands")
    return kept, read_rows


def only_tables(resources: list[Resource], tables: list[str], lane: str) -> list[Resource]:
    """The lane's resources whose table is one of `tables`. Refuses a table the lane does not carry."""
    on_lane = {resource.table for resource in lane_resources(lane, resources)}
    missing = sorted(set(tables) - on_lane)
    if missing:
        raise ValueError(f"{', '.join(missing)}: not a table the {lane} lane carries, so --only cannot keep it")
    return [resource for resource in resources if resource.table in tables]


def _naive_utc(stamp: datetime) -> datetime:
    return stamp.astimezone(UTC).replace(tzinfo=None) if stamp.tzinfo else stamp


def due(resources: list[Resource], log: list[dict], now: datetime) -> list[Resource]:
    """The resources this run should check: all of them, less any slower one checked within its interval.

    A check counts when its run loaded or found the resource fresh; a refused
    run's check does not, so a daily resource whose last run was refused is
    due again on the next hourly firing. A resource left out keeps its last
    committed rows, exactly as a FRESH one does.
    """
    last: dict[str, datetime] = {}
    for row in log:
        if row.get("outcome") in ("loaded", "skipped") and row.get("checked_at") is not None:
            stamp = _naive_utc(row["checked_at"])
            name = row["resource_name"]
            last[name] = max(last.get(name, stamp), stamp)
    return [
        resource
        for resource in resources
        if resource.cadence not in DUE_AFTER
        or resource.name not in last
        or now - last[resource.name] >= DUE_AFTER[resource.cadence]
    ]


def make_pipeline(lane: str, bucket_url: str, pipelines_dir: str | None = None):
    return dlt.pipeline(
        pipeline_name=f"ourhike_{lane}",
        destination=dlt.destinations.filesystem(bucket_url),
        dataset_name=DATASET,
        pipelines_dir=pipelines_dir,
    )


def recorded_markers(pipeline) -> dict[str, dict | None]:
    """Each resource's marker from the last load that committed, by resource name.

    Markers live in dlt resource state, which the filesystem destination keeps
    in the raw store, so `sync_destination()` gives a fresh runner the same
    markers. A marker set during a run that was refused is gone after
    `abort_packages()` (measured 2026-10-01, ELT.md), which is what keeps a
    degraded response from advancing it.
    """
    resources = pipeline.state.get("sources", {}).get(SOURCE_NAME, {}).get("resources", {})
    return {name: state.get("marker") for name, state in resources.items()}


def to_dlt(resource: Resource, marker: dict | None, proofs: dict[str, int], loaded_at: datetime, hints=None, read=None):
    """Wrap one Resource in the dlt settings every resource shares. `hints` collects each table's column hints.

    `read` is the resource's rows already read (a conditions leg reads each
    upstream on its own first, read_each()); None reads them here."""
    columns = resource.column_hints()
    if hints is not None:
        hints[resource.table] = columns

    @dlt.resource(
        name=resource.name,
        table_name=resource.table,
        write_disposition="replace",
        # Nested values stay JSON in one column; dlt's default unnests a list
        # into a child table, which is how the A.T. centerline once became
        # 2,072,165 rows in 4 tables and reported LOADED (#1363's spike).
        max_table_nesting=0,
        columns=columns,
        schema_contract=resource.schema_contract,
        file_format="parquet",
    )
    def rows():
        dlt.current.resource_state()["marker"] = marker
        for row in resource.rows(proofs) if read is None else (dict(row) for row in read):
            row["_loaded_at"] = loaded_at
            yield row

    return rows


def run_check(planned: list[Planned], rows: dict[str, int], proofs: dict[str, int], previous: dict[str, int]) -> list[str]:
    """Why this run's normalized tables may not load, or [] when they may. Runs between normalize and load."""
    by_table: dict[str, list[Planned]] = defaultdict(list)
    for item in planned:
        by_table[item.resource.table].append(item)
    problems = []
    for table, items in by_table.items():
        if all(item.verdict is Freshness.FRESH for item in items):
            continue
        resource = items[0].resource
        # dlt records no count for a table that has never held a row, so an
        # absent count is a zero, never a pass.
        landed = rows.get(table, 0)
        if table == ORGS_TABLE:
            if landed != len(items):
                problems.append(f"{table}: {landed} rows for {len(items)} club folders; each org.py is exactly one")
            continue
        proof = proofs.get(table)
        if landed == 0:
            if not resource.may_be_empty:
                problems.append(f"{table}: 0 rows, and a {resource.type} table may not be empty")
            elif proof is None:
                problems.append(
                    f"{table}: 0 rows and no upstream count read this run to prove it; "
                    "an empty answer from a failed fetch looks exactly like a quiet trail"
                )
            elif proof > 0:
                problems.append(f"{table}: 0 rows, and the upstream counts {proof}")
            continue
        if proof is not None and landed < proof:
            problems.append(f"{table}: {landed} rows, and the upstream counts {proof}")
        prior = previous.get(table)
        if not resource.may_be_empty and prior and landed < COLLAPSE_FLOOR * prior:
            problems.append(f"{table}: {landed} rows against {prior} last time, below the {COLLAPSE_FLOOR:.0%} floor")
    return problems


def _client(pipeline):
    return pipeline.destination_client()


def committed_load_ids(pipeline) -> set[str]:
    """Load ids `_dlt_loads` records as complete (status 0). dlt writes that row last, so a load cut short has none."""
    client = _client(pipeline)
    ids = set()
    for path in client.list_table_files("_dlt_loads"):
        for line in client.read_text(path).splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("status") == 0:
                    ids.add(row["load_id"])
    return ids


def table_files(pipeline, table: str, load_id: str | None = None) -> list[str]:
    """The table's Parquet files, optionally only those of one load.

    The load id is read from the FILE NAME, `<load_id>.<file_id>.parquet`,
    because a zero-row file has no `_dlt_load_id` value to read (ELT.md, "A
    full reload that cannot empty a safety table"). An explicit list, never a
    glob: a glob also reads a file an uncommitted load left behind.
    """
    client = _client(pipeline)
    try:
        files = client.list_table_files(table)
    except FileNotFoundError:
        return []
    files = [path for path in files if path.endswith(".parquet")]
    if load_id is not None:
        files = [path for path in files if os.path.basename(path).startswith(f"{load_id}.")]
    return sorted(files)


def rows_on_disk(pipeline, files: list[str]) -> int:
    client = _client(pipeline)
    return sum(pq.ParquetFile(client.fs_client.open(path)).metadata.num_rows for path in files)


def committed(pipeline, load_id: str, rows: dict[str, int], planned: list[Planned]) -> list[str]:
    """The after-run check: the load committed, and every loaded table holds on disk what was normalized."""
    problems = []
    if load_id not in committed_load_ids(pipeline):
        problems.append(f"load {load_id} is not recorded as complete in _dlt_loads")
    for table in {item.resource.table for item in planned if item.verdict is not Freshness.FRESH}:
        expected = rows.get(table)
        if expected is None:
            continue  # never held a row, so dlt wrote no file; the run check already ruled on the zero
        landed = rows_on_disk(pipeline, table_files(pipeline, table, load_id))
        if landed != expected:
            problems.append(f"{table}: {landed} rows landed, {expected} normalized")
    return problems


def run_log_rows(pipeline) -> list[dict]:
    files = table_files(pipeline, RUNS_TABLE)
    if not files:
        return []
    client = _client(pipeline)
    rows = []
    for path in files:
        rows.extend(pq.read_table(client.fs_client.open(path)).to_pylist())
    return rows


def last_loaded_counts(log: list[dict]) -> dict[str, int]:
    """Each table's row count on its most recent `loaded` run: the run check's "no collapse" baseline."""
    latest: dict[str, tuple[str, int]] = {}
    for row in log:
        if row.get("outcome") != "loaded" or row.get("rows") is None:
            continue
        previous = latest.get(row["table_name"])
        if previous is None or row["run_id"] > previous[0]:
            latest[row["table_name"]] = (row["run_id"], row["rows"])
    return {table: count for table, (_, count) in latest.items()}


# Typed up front, so a column that is null on every row of one run (no marker
# recorded yet, no count readable) still exists and keeps one type across runs.
RUNS_COLUMNS = {
    "run_id": {"data_type": "text", "nullable": False},
    "pipeline": {"data_type": "text", "nullable": False},
    "cadence": {"data_type": "text"},
    "club": {"data_type": "text"},
    "type": {"data_type": "text"},
    "resource_name": {"data_type": "text"},
    "table_name": {"data_type": "text", "nullable": False},
    "verdict": {"data_type": "text", "nullable": False},
    "recorded_marker": {"data_type": "text"},
    "upstream_marker": {"data_type": "text"},
    "rows": {"data_type": "bigint"},
    "count_proof": {"data_type": "bigint"},
    "load_id": {"data_type": "text"},
    "outcome": {"data_type": "text", "nullable": False},
    "checked_at": {"data_type": "timestamp"},
    "column_hints": {"data_type": "text"},
}


def write_run_log(
    pipeline, report: RunReport, planned: list[Planned], checked_at: datetime, unavailable: list[Resource] = ()
) -> None:
    """Append one `_extract_runs` row per planned resource, and per unavailable one. INCREMENTAL.md's log.json, as one append-only table."""
    log = [
        {
            "run_id": report.run_id,
            "pipeline": report.lane,
            "cadence": resource.cadence,
            "club": resource.club,
            "type": resource.type,
            "resource_name": resource.name,
            "table_name": resource.table,
            "verdict": UNAVAILABLE,
            "recorded_marker": None,
            "upstream_marker": None,
            "rows": None,
            "count_proof": None,
            "load_id": None,
            "outcome": UNAVAILABLE,
            "checked_at": checked_at,
            "column_hints": None,
        }
        for resource in unavailable
    ]
    for item in planned:
        resource = item.resource
        # An isolated resource (a conditions leg's, refused on its own) is
        # logged like a FRESH one in what it leaves behind, no rows and no
        # load, and as refused in its outcome: committed_tables() then keeps
        # reading its last committed load, and due() does not count the check.
        isolated = resource.name in report.isolated
        skipped = item.verdict is Freshness.FRESH or isolated
        log.append(
            {
                "run_id": report.run_id,
                "pipeline": report.lane,
                "cadence": resource.cadence,
                "club": resource.club,
                "type": resource.type,
                "resource_name": resource.name,
                "table_name": resource.table,
                "verdict": item.verdict.value,
                "recorded_marker": json.dumps(item.recorded, sort_keys=True) if item.recorded else None,
                "upstream_marker": json.dumps(item.marker, sort_keys=True) if item.marker else None,
                "rows": None if skipped else report.rows.get(resource.table, 0),
                "count_proof": report.proofs.get(resource.table),
                "load_id": None if skipped else report.load_id,
                "outcome": ISOLATED_OUTCOME if isolated else "skipped" if skipped else report.outcome,
                "checked_at": checked_at,
                # A proven zero writes no file on a table's first load (dlt keeps no
                # schema for a table that never held a row, measured 2026-10-01), so
                # its hints are what lets the warehouse create it empty.
                "column_hints": json.dumps(report.hints[resource.table], sort_keys=True)
                if not skipped and report.rows.get(resource.table, 0) == 0 and resource.table in report.hints
                else None,
            }
        )

    @dlt.resource(
        name=RUNS_TABLE,
        table_name=RUNS_TABLE,
        write_disposition="append",
        file_format="parquet",
        columns=RUNS_COLUMNS,
    )
    def runs():
        yield log

    pipeline.run(runs())


def run_pipeline(
    lane: str,
    bucket_url: str,
    *,
    resources: list[Resource] | None = None,
    pipelines_dir: str | None = None,
    read_seconds: float | None = None,
) -> RunReport:
    """One lane, or one conditions leg, end to end. Raises ExtractRefused, after logging, when either check fails.

    Whatever it raises carries the run's RunReport as `.report` where the
    exception will take one, so a caller can say what the run got to.
    `read_seconds` is a conditions leg's budget for reading its upstreams
    (read_each()); the lanes ignore it."""
    cadences_of(lane)
    if resources is None:
        resources = all_resources(discover() + discover_shared())
    checked_at = utc_now_naive()
    report = RunReport(run_id=checked_at.strftime("%Y%m%dT%H%M%S.%fZ"), lane=lane, outcome="loaded")
    try:
        _run(report, lane, bucket_url, lane_resources(lane, resources), pipelines_dir, checked_at, read_seconds)
    except Exception as failure:
        if getattr(failure, "report", None) is None:
            try:
                failure.report = report
            except AttributeError:
                pass  # an exception type that keeps no attributes; the caller reports without it
        raise
    return report


def _run(
    report: RunReport,
    lane: str,
    bucket_url: str,
    plan_resources: list[Resource],
    pipelines_dir: str | None,
    checked_at: datetime,
    read_seconds: float | None = None,
) -> None:
    pipeline = make_pipeline(lane, bucket_url, pipelines_dir)
    # A run that died after its extract and before its load committed leaves
    # its package pending in the working directory, and its resource state
    # with it. Kept, the next run reads that uncommitted marker as recorded and
    # answers FRESH for a change it never loaded, and the run log's own
    # pipeline.run() commits the dead package without an `_extract_runs` row
    # (measured 2026-10-01: tests/test_extract_run.py's
    # test_a_load_that_dies_before_it_commits...). Dropped first, then synced,
    # the committed marker comes back (the dlt skill, "A marker advances only
    # when a load commits"). CI's runners start with no working directory, so
    # this bites a reused one: a laptop, a cached runner.
    with timed(report, "sync"):
        if pipeline.has_pending_data:
            print(f"::warning title={lane} dropped an uncommitted load::a previous run died before its load committed")
            pipeline.abort_packages()
        pipeline.sync_destination()
        recorded = recorded_markers(pipeline)
        plan_resources = due(plan_resources, run_log_rows(pipeline), checked_at)
    planned, unavailable = [], []
    with timed(report, "change checks"):
        for resource in plan_resources:
            before = recorded.get(resource.name)
            try:
                verdict, marker = resource.change_check(before)
            except Unavailable as reason:
                # An annotation, so the gap reaches the run summary rather than only the step log.
                print(f"::warning title={resource.name} is unavailable::{reason}")
                unavailable.append(resource)
                report.unavailable[resource.name] = str(reason)
                report.verdicts[resource.name] = UNAVAILABLE
                continue
            planned.append(Planned(resource, verdict, before, marker))
            report.verdicts[resource.name] = verdict.value
    to_run = [item for item in planned if item.verdict is not Freshness.FRESH]
    print(
        f"{lane}: {len(planned) + len(unavailable)} resources, {len(to_run)} to read, "
        f"{len(planned) - len(to_run)} fresh, {len(unavailable)} unavailable"
    )

    # A CONDITIONS LEG ISOLATES EACH UPSTREAM. One club's failure must not hold
    # back another club's closures, so a leg reads every resource on its own
    # first (read_each), and a resource whose read fails, runs out of time or
    # is refused by the run check is left out of this run, as a FRESH one is:
    # its last committed table stands, it is logged `refused`, and the rest
    # load. OurHike's own rows are the exception (stops_the_leg). ELT.md's "A
    # full reload that cannot empty a safety table" reasoned that a refusal
    # costs the whole leg an hour; this is the change that stops it doing so.
    # The monthly and hourly lanes are unchanged: one refusal refuses the run.
    read = None
    if to_run and lane in LEGS:
        with timed(report, "read"):
            to_run, read = read_each(report, to_run, read_seconds)
    previous = last_loaded_counts(run_log_rows(pipeline)) if to_run else {}
    while to_run:

        def resources(items=tuple(to_run)):
            return [
                to_dlt(
                    item.resource,
                    item.marker,
                    report.proofs,
                    checked_at,
                    report.hints,
                    None if read is None else read[item.resource.name],
                )
                for item in items
            ]

        with timed(report, "extract"):
            pipeline.extract(dlt.source(resources, name=SOURCE_NAME)(), loader_file_format="parquet")
        with timed(report, "normalize"):
            pipeline.normalize()
        report.rows = {
            table: count
            for table, count in pipeline.last_trace.last_normalize_info.row_counts.items()
            if not table.startswith("_dlt")
        }
        if read is None:
            report.problems = run_check(planned, report.rows, report.proofs, previous)
            if report.problems:
                pipeline.abort_packages()
                report.outcome = "refused"
                with timed(report, "run log"):
                    write_run_log(pipeline, report, planned, checked_at, unavailable)
                raise ExtractRefused("Extract run check:\n  " + "\n  ".join(report.problems), report)
            break
        refused = {}
        for table in dict.fromkeys(item.resource.table for item in to_run):
            items = [item for item in to_run if item.resource.table == table]
            if problems := run_check(items, report.rows, report.proofs, previous):
                refused[table] = (items, problems)
        if not refused:
            break
        pipeline.abort_packages()
        if any(stops_the_leg(item.resource) for items, _ in refused.values() for item in items):
            report.problems = [problem for _, problems in refused.values() for problem in problems]
            report.outcome = "refused"
            with timed(report, "run log"):
                write_run_log(pipeline, report, planned, checked_at, unavailable)
            raise ExtractRefused("Extract run check:\n  " + "\n  ".join(report.problems), report)
        for table, (items, problems) in refused.items():
            for item in items:
                report.isolated[item.resource.name] = "; ".join(problems)
                print(f"::error title={item.resource.name} refused::{'; '.join(problems)}; its last committed table stands")
        to_run = [item for item in to_run if item.resource.table not in refused]
        report.rows = {}
    if to_run:
        with timed(report, "load"):
            loads = pipeline.load().loads_ids
        if len(loads) != 1:
            raise ExtractRefused(f"one load expected from this run, and {len(loads)} committed: {loads}", report)
        report.load_id = loads[0]
        with timed(report, "after-run check"):
            report.problems = committed(pipeline, report.load_id, report.rows, planned)
        if report.problems:
            report.outcome = "unverified"
            with timed(report, "run log"):
                write_run_log(pipeline, report, planned, checked_at, unavailable)
            raise ExtractRefused("Extract after-run check:\n  " + "\n  ".join(report.problems), report)
    with timed(report, "run log"):
        write_run_log(pipeline, report, planned, checked_at, unavailable)


def summary_markdown(report: RunReport | None, lane: str, *, failure: BaseException | None = None) -> str:
    """The run's evidence as Markdown, for `$GITHUB_STEP_SUMMARY`: what each table loaded, and why a run stopped.

    One row per resource the run planned: its verdict, the rows it landed,
    and the upstream's own count read in the same run, blank where the
    platform has none and never written as 0 for it. A FRESH resource lands
    nothing and keeps its last committed table, so its rows read "kept"; an
    unavailable one is withdrawn from the warehouse, and reads "withdrawn".
    A run that stopped before normalize has no counts at all, and its rows
    are left blank rather than written as zero.
    """
    lines = [f"### Extract: `{lane}`", ""]
    if report is None:
        return "\n".join([*lines, f"**Failed before a run began:** `{type(failure).__name__}: {failure}`", ""]) + "\n"
    stopped = failure is not None and not isinstance(failure, ExtractRefused)
    outcome = "failed" if stopped else report.outcome
    head = f"Run `{report.run_id}`, outcome **{outcome}**"
    lines += [head + (f", load `{report.load_id}`" if report.load_id else ""), ""]
    if stopped:
        lines += [f"**Stopped by** `{type(failure).__name__}: {failure}`", ""]
    if report.problems:
        lines += ["**Refused:**", "", *[f"- {problem}" for problem in report.problems], ""]
    if report.isolated:
        lines += ["**Refused on its own** (left out of this run; its last committed table stands):", ""]
        lines += [*[f"- `{name}`: {why}" for name, why in sorted(report.isolated.items())], ""]
    if report.unavailable:
        lines += ["**Unavailable** (left out of the run, and withdrawn from the warehouse):", ""]
        lines += [*[f"- `{name}`: {why}" for name, why in sorted(report.unavailable.items())], ""]
    normalized = "normalize" in report.timings and not (stopped and not report.rows)
    if report.verdicts:
        lines += ["| table | verdict | rows | upstream count |", "|---|---|---:|---:|"]
        for name, verdict in sorted(report.verdicts.items()):
            if name in report.isolated:
                rows = "refused, last table stands"
            elif verdict == Freshness.FRESH.value:
                rows = "kept"
            elif verdict == UNAVAILABLE:
                rows = "withdrawn"
            else:
                rows = str(report.rows.get(name, 0)) if normalized else ""
            proof = report.proofs.get(name)
            lines.append(f"| `{name}` | {verdict} | {rows} | {'' if proof is None else proof} |")
        lines.append("")
    if report.timings:
        lines += ["Seconds: " + ", ".join(f"{part} {seconds:.1f}" for part, seconds in report.timings.items()), ""]
    return "\n".join(lines) + "\n"


def load_committed(lane: str, bucket_url: str, warehouse: Path, pipelines_dir: str | None = None) -> dict[str, int]:
    """Every table the lane's pipeline has committed, into `warehouse`'s raw schema. Returns {table: rows}.

    extract/_warehouse.py's committed-file read, which refuses a table whose
    recorded load left no file rather than loading it empty. Imported here
    rather than at the top, because that module imports this one."""
    import duckdb

    from extract._warehouse import load_warehouse

    warehouse.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(warehouse)) as con:
        return load_warehouse(con, make_pipeline(lane, bucket_url, pipelines_dir))


def main(argv: list[str] | None = None) -> RunReport:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--lane", required=True, choices=sorted(LANES) + sorted(LEGS))
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--bucket-url", help="the raw store: file:///… locally, s3://… for R2")
    where.add_argument("--raw-bucket", help="the private raw bucket's name, as R2_RAW_BUCKET holds it")
    parser.add_argument("--only", action="append", default=[], metavar="TABLE", help="keep only this table of the lane")
    parser.add_argument("--warehouse", type=Path, help="then load every committed table into this DuckDB file")
    parser.add_argument("--summary", type=Path, help="append the run's evidence, as Markdown, to this file")
    parser.add_argument("--pipelines-dir", help="dlt's working directory (default: dlt's own)")
    parser.add_argument(
        "--read-seconds",
        type=float,
        help="a conditions leg's budget for reading its upstreams; one not read in time is refused on its own",
    )
    args = parser.parse_args(argv)
    bucket_url = args.bucket_url or raw_store_url(args.raw_bucket, args.lane)
    resources = all_resources(discover() + discover_shared())
    if args.only:
        resources = only_tables(resources, args.only, args.lane)
    report = None
    try:
        report = run_pipeline(
            args.lane, bucket_url, resources=resources, pipelines_dir=args.pipelines_dir, read_seconds=args.read_seconds
        )
        if args.warehouse is not None:
            with timed(report, "warehouse"):
                loaded = load_committed(args.lane, bucket_url, args.warehouse, args.pipelines_dir)
            print(f"{len(loaded)} tables, {sum(loaded.values())} rows, into {args.warehouse}")
    except Exception as failure:
        if args.summary is not None:
            known = getattr(failure, "report", None) or report  # the warehouse step's refusal carries none
            with open(args.summary, "a", encoding="utf-8") as handle:
                handle.write(summary_markdown(known, args.lane, failure=failure))
        raise
    if args.summary is not None:
        with open(args.summary, "a", encoding="utf-8") as handle:
            handle.write(summary_markdown(report, args.lane))
    for name, verdict in sorted(report.verdicts.items()):
        print(f"  {name}: {verdict}")
    return report


assert set(cadence for cadences in LANES.values() for cadence in cadences) <= set(CADENCES)

if __name__ == "__main__":
    try:
        finished = main()
    except ExtractRefused as refused:
        print(refused, file=sys.stderr)
        sys.exit(1)
    if finished.isolated:
        print(f"{len(finished.isolated)} resource(s) refused on their own; the rest loaded", file=sys.stderr)
        sys.exit(PARTIAL_EXIT)
