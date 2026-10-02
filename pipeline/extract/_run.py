"""Run one lane: change checks, extract, normalize, the run check, load, the after-run check, the run log.

Usage: python -m extract._run --lane monthly --bucket-url file:///path/to/raw-store

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

THE AS-LANDED COPY (--as-landed, the monthly lane's refresh-reference.yml):
a stand-in for the as-sent copy, built so the go/no-go gate's parity can run
today's exporters on exactly the rows the dbt side read (decision 30, "the
same frozen inputs run through the old and the new pipeline"). For each
ArcGIS, Socrata and opentrail resource that ran, the rows it yielded are
written back out as the GeoJSON file today's fetcher would have written, at
the fetcher's own path under data/raw/ (`as_landed_path`), and uploaded to
`<bucket-url>/as_landed/<load_id>/` once the load has committed and the run
log is written. It is NOT the upstream's bytes, in two ways: person fields
are already left out (the resource never asked for them), and an ArcGIS
feature's GeoJSON `id` member is gone, because the resource does not land it
(TL05's ledger row). So parity on it compares today's exporters with dbt on
one input; it says nothing about today's fetchers against the dlt resources,
which tests/test_extract_run.py and the run check hold instead.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlsplit

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
from extract._kinds import ORGS_TABLE, ArcgisLayer, OpentrailFeed, SocrataDataset, registry_entry  # noqa: E402
from lib.freshness_state import Freshness  # noqa: E402
from lib.source_registry import is_arcgis_feature_layer, is_external_source  # noqa: E402

# Which cadences each lane carries. Daily and weekly resources would ride the
# hourly pipeline when due (ELT.md); none of the folders extracted so far has
# one, so no lane carries them yet and the layout test refuses one.
LANES = {"monthly": ("monthly",), "hourly": ("hourly", "daily")}
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

#: Another lane's resources a lane also reads into its own raw store when run
#: with `cross_lane=True` (--cross-lane-inputs, refresh-reference.yml), each
#: with the reason. A node is built by one lane (build_marts.py --lane); where
#: a node of this lane reads a table another lane lands, this lane lands its
#: own copy at its own time, so its warehouse holds every table its nodes read
#: and its pin freezes it. Never in fixture mode, whose lanes share one store.
ALSO_READS: dict[str, dict[str, str]] = {
    "monthly": {
        "raw_nysparks__oprhp_trail_closures": (
            "OPRHP's temporary closures land on the hourly lane (nysparks/closures.py; #1152 - Move OPRHP's "
            "temporary closures onto the conditions clock, where a safety layer belongs), and the monthly "
            "nearby_trails.geojson still reads them for apply_area_closures()' tape through "
            "stg_oprhp__trail_closures (tl-net, 2a65c736). Read again here, at the monthly build's own time, "
            "as publish-vector-data.yml's build reads them today; found 2026-10-02 as the one hourly-lane "
            "table a monthly-lane dbt source reads, in this branch's manifest"
        ),
    },
}

# @unvalidated: a table whose type may not be empty fails the run when it
# lands below this share of its last loaded size. 0.5 is fetch_opentrail.py's
# MAX_FEATURE_DROP_RATIO, the one precedent here; six monthly runs of
# _extract_runs give the smallest legitimate ratio per type, which is what
# would settle it. Closures and warnings have no floor: every closure lifted
# is exactly what a closures layer emptying looks like.
COLLAPSE_FLOOR = 0.5


class ExtractRefused(RuntimeError):
    """The run check or the after-run check failed. Nothing this run loaded may be read."""


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
    # {table: path under data/raw/} of the as-landed files this run uploaded under
    # `as_landed/<load_id>/`; empty unless run_pipeline(as_landed=True).
    as_landed: dict[str, str] = field(default_factory=dict)


def utc_now_naive() -> datetime:
    """Naive UTC, load_raw.py's convention for `_loaded_at`, so a timestamp compares the same in DuckDB and in dbt."""
    return datetime.now(UTC).replace(tzinfo=None)


def lane_resources(lane: str, resources: list[Resource]) -> list[Resource]:
    return [resource for resource in resources if resource.cadence in LANES[lane]]


def cross_lane_resources(lane: str, resources: list[Resource], own: list[Resource]) -> list[Resource]:
    """The other lanes' resources ALSO_READS names for `lane`. Refuses a name no resource carries, rather than reading less."""
    wanted = ALSO_READS.get(lane, {})
    found = [resource for resource in resources if resource.name in wanted and resource not in own]
    if missing := sorted(set(wanted) - {resource.name for resource in found} - {resource.name for resource in own}):
        raise ValueError(f"ALSO_READS names no resource called {', '.join(missing)} for the {lane} lane")
    return found


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


def to_dlt(resource: Resource, marker: dict | None, proofs: dict[str, int], loaded_at: datetime, hints=None, as_landed=None):
    """Wrap one Resource in the dlt settings every resource shares. `hints` collects each table's column hints;
    `as_landed`, an AsLanded, copies each row it yields (the module docstring)."""
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
        for row in resource.rows(proofs):
            if as_landed is not None:
                as_landed.add(resource, row)  # before _loaded_at, which no fetcher writes
            row["_loaded_at"] = loaded_at
            yield row

    return rows


# --- The as-landed copy (the module docstring says what it is and is not) ---

#: Under the lane's own bucket URL, beside dlt's `raw/` dataset:
#: `<bucket-url>/as_landed/<load_id>/<path under data/raw/>`, plus an
#: `index.json` naming each table's file. Write-once per load, so the files a
#: pinned raw_run names (extract/_warehouse.py's pin) never change under it.
AS_LANDED_PREFIX = "as_landed"
AS_LANDED_INDEX = "index.json"
#: fetch_opentrail.py's OUT_PATH, relative to data/raw/. Spelled here rather
#: than imported because fetch_opentrail.py's module path is fixed to this
#: checkout's data/raw/, and what is wanted is the name under it.
OPENTRAIL_RAW_NAME = "opentrail_at.geojson"


def as_landed_path(resource: Resource) -> str | None:
    """Where today's fetcher writes this resource's layer, relative to data/raw/, or None for a kind it has no file for.

    fetch_all.py writes each `is_arcgis_feature_layer` entry to
    data/raw/<key>.geojson (its RAW_DIR, `out_path = RAW_DIR / f"{key}.geojson"`);
    fetch_external_layers.py writes every other organization's layer, ArcGIS or
    Socrata, to data/raw/external/<key>.geojson; fetch_opentrail.py writes
    OPENTRAIL_RAW_NAME. Those are the paths extract/_fixtures.py's
    fixture_file() reads back, and every exporter parity.py runs reads.
    """
    if isinstance(resource, OpentrailFeed):
        return OPENTRAIL_RAW_NAME
    if not isinstance(resource, ArcgisLayer | SocrataDataset):
        return None
    entry = registry_entry(resource.key)
    if is_external_source(entry):
        return f"external/{resource.key}.geojson"
    if is_arcgis_feature_layer(entry):
        return f"{resource.key}.geojson"
    return None


def as_landed_feature(resource: Resource, row: dict) -> dict:
    """One yielded row as the GeoJSON feature it was read from: `geometry` back out, the server's id back in its place."""
    properties = dict(row)
    geometry = properties.pop("geometry", None)
    if isinstance(geometry, str):
        geometry = json.loads(geometry)
    feature = {"type": "Feature"}
    # Socrata's `:id` and opentrail's feature id are landed as columns, so they
    # go back where the fetchers' files hold them; an ArcGIS layer's is not landed.
    for column in ("_socrata_id", "feature_id"):
        if column in properties and isinstance(resource, SocrataDataset | OpentrailFeed):
            value = properties.pop(column)
            if value is not None:
                feature["id"] = value
    feature["geometry"] = geometry
    feature["properties"] = properties
    return feature


class AsLanded:
    """Each resource's rows, streamed to a local FeatureCollection as dlt extracts them, uploaded only after the load commits."""

    def __init__(self, staging: Path):
        self.staging = staging
        self.paths: dict[str, str] = {}  # table -> path under data/raw/
        self._open: dict[str, object] = {}

    def add(self, resource: Resource, row: dict) -> None:
        path = as_landed_path(resource)
        if path is None:
            return
        handle = self._open.get(resource.table)
        if handle is None:
            target = self.staging / path
            target.parent.mkdir(parents=True, exist_ok=True)
            handle = target.open("w", encoding="utf-8")
            handle.write('{"type":"FeatureCollection","features":[')
            self._open[resource.table] = handle
            self.paths[resource.table] = path
        else:
            handle.write(",")
        handle.write(json.dumps(as_landed_feature(resource, row), separators=(",", ":"), default=str))

    def close(self, planned: list[Planned]) -> None:
        for handle in self._open.values():
            handle.write("]}")
            handle.close()
        self._open.clear()
        # A layer that ran and yielded no row is an empty FeatureCollection,
        # the file fetch_external_layers.py writes for a legitimately empty layer.
        for item in planned:
            resource = item.resource
            path = as_landed_path(resource)
            if item.verdict is Freshness.FRESH or path is None or resource.table in self.paths:
                continue
            target = self.staging / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
            self.paths[resource.table] = path


def fs_path(url: str) -> str:
    """A bucket URL as the fsspec path its filesystem client takes: a local path for file://, `bucket/key` for s3://."""
    parts = urlsplit(url)
    if parts.scheme in ("", "file"):
        return unquote(parts.path).rstrip("/")
    return f"{parts.netloc}{unquote(parts.path)}".rstrip("/")


def upload_as_landed(pipeline, bucket_url: str, load_id: str, as_landed: AsLanded) -> dict[str, str]:
    """Put this load's as-landed files under `<bucket-url>/as_landed/<load_id>/`, the index last. Returns {table: path}."""
    if not as_landed.paths:
        return {}
    fs = _client(pipeline).fs_client
    root = f"{fs_path(bucket_url)}/{AS_LANDED_PREFIX}/{load_id}"
    for table, path in sorted(as_landed.paths.items()):
        fs.makedirs(os.path.dirname(f"{root}/{path}"), exist_ok=True)
        fs.put_file(str(as_landed.staging / path), f"{root}/{path}")
    with fs.open(f"{root}/{AS_LANDED_INDEX}", "w") as index:
        index.write(json.dumps(as_landed.paths, indent=2, sort_keys=True))
    return dict(as_landed.paths)


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
        skipped = item.verdict is Freshness.FRESH
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
                "outcome": "skipped" if skipped else report.outcome,
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
    as_landed: bool = False,
    cross_lane: bool = False,
) -> RunReport:
    """One lane, end to end. Raises ExtractRefused, after logging, when either check fails.

    `as_landed` also writes the as-landed copy (the module docstring) for every
    resource that ran, after the load commits and the run log is written.
    `cross_lane` also reads the other lanes' resources ALSO_READS names for this lane.
    """
    if lane not in LANES:
        raise ValueError(f"no lane {lane!r}; lanes are {sorted(LANES)}")
    if resources is None:
        resources = all_resources(discover() + discover_shared())
    plan_resources = lane_resources(lane, resources)
    if cross_lane:
        plan_resources += cross_lane_resources(lane, resources, plan_resources)
    checked_at = utc_now_naive()
    report = RunReport(run_id=checked_at.strftime("%Y%m%dT%H%M%S.%fZ"), lane=lane, outcome="loaded")

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
    if pipeline.has_pending_data:
        print(f"::warning title={lane} dropped an uncommitted load::a previous run died before its load committed")
        pipeline.abort_packages()
    pipeline.sync_destination()
    recorded = recorded_markers(pipeline)
    plan_resources = due(plan_resources, run_log_rows(pipeline), checked_at)
    planned, unavailable = [], []
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

    copy = AsLanded(Path(tempfile.mkdtemp(prefix="as_landed_"))) if as_landed and to_run else None
    try:
        _extract_and_load(pipeline, report, planned, to_run, unavailable, checked_at, copy)
        # After the run log, so a failed upload leaves a committed, logged load
        # and a red job rather than a load the warehouse cannot see.
        if copy is not None and report.load_id is not None:
            report.as_landed = upload_as_landed(pipeline, bucket_url, report.load_id, copy)
    finally:
        if copy is not None:
            shutil.rmtree(copy.staging, ignore_errors=True)
    return report


def _extract_and_load(pipeline, report: RunReport, planned, to_run, unavailable, checked_at, as_landed: AsLanded | None):
    """run_pipeline's extract, checks, load and run log; ExtractRefused, after logging, when either check fails."""
    if to_run:
        source = dlt.source(
            lambda: [to_dlt(item.resource, item.marker, report.proofs, checked_at, report.hints, as_landed) for item in to_run],
            name=SOURCE_NAME,
        )
        pipeline.extract(source(), loader_file_format="parquet")
        if as_landed is not None:
            as_landed.close(planned)
        pipeline.normalize()
        report.rows = {
            table: count
            for table, count in pipeline.last_trace.last_normalize_info.row_counts.items()
            if not table.startswith("_dlt")
        }
        report.problems = run_check(planned, report.rows, report.proofs, last_loaded_counts(run_log_rows(pipeline)))
        if report.problems:
            pipeline.abort_packages()
            report.outcome = "refused"
            write_run_log(pipeline, report, planned, checked_at, unavailable)
            raise ExtractRefused("Extract run check:\n  " + "\n  ".join(report.problems))
        loads = pipeline.load().loads_ids
        if len(loads) != 1:
            raise ExtractRefused(f"one load expected from this run, and {len(loads)} committed: {loads}")
        report.load_id = loads[0]
        report.problems = committed(pipeline, report.load_id, report.rows, planned)
        if report.problems:
            report.outcome = "unverified"
            write_run_log(pipeline, report, planned, checked_at, unavailable)
            raise ExtractRefused("Extract after-run check:\n  " + "\n  ".join(report.problems))
    write_run_log(pipeline, report, planned, checked_at, unavailable)


def report_document(report: RunReport) -> dict:
    """What --report-json writes: the run's identity and outcome, which a workflow reads `run_id` (the raw_run) from."""
    return {
        "run_id": report.run_id,
        "lane": report.lane,
        "outcome": report.outcome,
        "load_id": report.load_id,
        "rows": report.rows,
        "proofs": report.proofs,
        "verdicts": report.verdicts,
        "unavailable": report.unavailable,
        "as_landed": report.as_landed,
        "problems": report.problems,
    }


def main(argv: list[str] | None = None) -> RunReport:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--lane", required=True, choices=sorted(LANES))
    parser.add_argument("--bucket-url", required=True, help="the raw store: file:///… locally, s3://… for R2")
    parser.add_argument(
        "--as-landed",
        action="store_true",
        help="also upload each ArcGIS, Socrata and opentrail layer as today's fetcher's file (the module docstring)",
    )
    parser.add_argument("--pipelines-dir", help="dlt's working directory (default: dlt's own)")
    parser.add_argument(
        "--cross-lane-inputs",
        action="store_true",
        help="also read the other lanes' resources this lane's dbt nodes read (ALSO_READS); never in fixture mode",
    )
    parser.add_argument(
        "--report-json", type=Path, help="write the run's id, outcome and counts here, refused or not (refresh-reference.yml)"
    )
    args = parser.parse_args(argv)
    try:
        report = run_pipeline(
            args.lane,
            args.bucket_url,
            pipelines_dir=args.pipelines_dir,
            as_landed=args.as_landed,
            cross_lane=args.cross_lane_inputs,
        )
    except ExtractRefused as refused:
        if args.report_json:
            args.report_json.write_text(
                json.dumps({"lane": args.lane, "outcome": "refused", "problems": str(refused).splitlines()}, indent=2)
            )
        raise
    if args.report_json:
        args.report_json.write_text(json.dumps(report_document(report), indent=2, sort_keys=True, default=str))
    for name, verdict in sorted(report.verdicts.items()):
        print(f"  {name}: {verdict}")
    return report


assert set(cadence for cadences in LANES.values() for cadence in cadences) <= set(CADENCES)

if __name__ == "__main__":
    try:
        main()
    except ExtractRefused as refused:
        print(refused, file=sys.stderr)
        sys.exit(1)
