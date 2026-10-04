"""Run one lane: change checks, extract, normalize, the run check, load, the after-run check, the run log.

Usage: python -m extract._run --lane monthly --bucket-url file:///path/to/raw-store
       python -m extract._run --lane conditions_ua --raw-bucket our-hike-raw \\
           --warehouse data/warehouse.duckdb --summary "$GITHUB_STEP_SUMMARY"
       python -m extract._run --lane monthly --only raw_registry__sources \\
           --bucket-url file:///tmp/registry-store --warehouse data/warehouse.duckdb

A lane is one scheduled extract job and the cadences it carries (LANES):
`monthly`, or `hourly`, which also runs daily resources when due. A leg
(LEGS) is one job's share of the hourly lane for one data environment, as a
dlt pipeline of its own: a conditions leg reads the upstreams that stay
hourly (HOURLY_JOB_TABLES), a notices leg every other club's and agency's
notices, every 4 hours (decision 61, job_of()). `--help` describes each
flag; `--summary` is written on a refused run too.

The steps, as pipeline/ELT.md designs them in "Change checks, verdicts and
`_loaded_at`" and "A full reload that cannot empty a safety table" (#1793 —
Rebuild the data platform as dlt → dbt: seven contracted marts, a monthly
refresh, published docs, and lighter phone downloads):

1. Each resource's change check, before dlt, compares the upstream's change
   marker (an ETag, a newest edit date), where it has one, with the one its
   last committed load recorded. FRESH leaves the resource out, so its table
   keeps its rows; STALE and UNKNOWN both read it whole.
2. dlt extracts and normalizes what is left, every table `replace`.
3. The run check (run_check()): each table present, non-empty unless its
   type may be empty and the upstream's own count says zero, not shorter than
   that count, and not below COLLAPSE_FLOOR of its last loaded size. A
   failure aborts the package, so nothing lands and no marker advances.
4. The load, then the after-run check (committed()): the load committed, and
   the rows on disk are the rows normalized. A failure logs `unverified`, and
   extract/_warehouse.py refuses to read the tables.
5. One `_extract_runs` row per resource per run, skipped ones included.

A leg, and the monthly lane (ISOLATING_LANES), isolates each upstream
(_extract_and_load()): one that fails or is refused is left out while the
rest load, and the run exits PARTIAL_EXIT (3) so its job still goes red,
unless every one refused has a sources.json row saying reaches_hikers false
(exit_status()). OurHike's own Postgres rows still stop the whole leg
(stops_the_leg()). A leg takes on at most NEW_TABLES_PER_LEG_RUN tables it
has never loaded per run, so a batch of new sources comes on over several
runs rather than overrunning one.

Not built yet, and designed in ELT.md: the as-sent copy beside dlt's
normalized one (`_source_path`), the raw lake (DuckLake) for the monthly
lane, and a lane for `weekly` resources.

THE AS-LANDED COPY (--as-landed, refresh-reference.yml's monthly run) stands
in for the as-sent copy so parity.py, for ELT.md's go/no-go gate, can run
today's exporters on exactly the rows dbt read (decision 30). Each ArcGIS,
Socrata and opentrail resource that ran is written back out as its fetcher's
GeoJSON file (as_landed_path()) and uploaded to
`<bucket-url>/as_landed/<load_id>/` after the load commits and the run log is
written. It is not the upstream's bytes (person fields were never asked for,
and an ArcGIS feature's GeoJSON `id` is not landed: ELT.md's ledger row TL05),
so it tests today's exporters against dbt, not today's fetchers against the
dlt resources, which tests/test_extract_run.py and the run check hold.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import pickle
import queue
import shutil
import sys
import tempfile
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlsplit

# Set before dlt is imported, and in .dlt/config.toml too, so a run from any
# directory has both. dlt's telemetry is on by default, to
# telemetry.scalevector.ai, from jobs holding R2 write keys; dlt's default
# naming turns `GlobalID` into `global_id` where 16 staging models read
# `globalid` (ELT.md, "dlt configuration requirements").
os.environ.setdefault("RUNTIME__DLTHUB_TELEMETRY", "false")
os.environ.setdefault("SCHEMA__NAMING", "sql_ci_v1")

import dlt  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from dlt.common.schema.exceptions import DataValidationError  # noqa: E402
from dlt.common.storages.fsspec_filesystem import glob_files  # noqa: E402
from dlt.pipeline.exceptions import PipelineStepFailed  # noqa: E402

from extract import _kinds  # noqa: E402
from extract._contract import (  # noqa: E402
    CADENCES,
    Carried,
    Incomplete,
    Resource,
    Unavailable,
    all_resources,
    discover,
    discover_shared,
)
from extract._kinds import (  # noqa: E402
    ORGS_TABLE,
    ArcgisLayer,
    ConditionsQuery,
    OpentrailFeed,
    SocrataDataset,
    registry_entry,
)
from lib.freshness_state import Freshness  # noqa: E402
from lib.source_registry import is_arcgis_feature_layer, is_external_source  # noqa: E402

# Which cadences each lane carries. A daily resource rides the hourly lane and
# runs when due (DUE_AFTER). No resource is weekly yet, so no lane carries
# `weekly` and tests/test_extract_layout.py refuses a resource that is.
LANES = {"monthly": ("monthly",), "hourly": ("hourly", "daily")}

# THE HOURLY LANE IS READ BY TWO JOBS (decision 61, the maintainer by poll,
# 2026-10-04): the conditions job, publish-conditions.yml, hourly, and the
# notices job, extract-notices.yml, every 4 hours with up to an hour to read.
# A resource's job is job_of(): the conditions job keeps HOURLY_JOB_TABLES,
# the upstreams the conditions bake published before decision 53, and the
# notices job takes every other hourly or daily resource, so a club source
# wired later goes to the notices job without being named anywhere.
# tests/test_extract_layout.py holds the split against discover().
CONDITIONS_JOB, NOTICES_JOB = "conditions", "notices"
JOBS = (CONDITIONS_JOB, NOTICES_JOB)


@dataclass(frozen=True)
class Leg:
    """One job's read of a lane for one data environment: the lane whose cadences it carries, and the job whose
    resources it reads (job_of())."""

    lane: str
    job: str


# THE LEGS. Each job runs once per data environment, and each leg is its own
# dlt pipeline (own raw-store prefix, markers and `_extract_runs`). The
# conditions legs are split by environment because each reads its own
# environment's Postgres (CONDITIONS_DATABASE_URL), and one pipeline would
# swap production's closures table for UA's every hour (ELT.md, "The hourly
# lanes"). A prefix per leg, rather than ELT.md's `raw_ourhike_production__*`
# table names, keeps every dbt source unchanged (Reasoned). The notices legs
# read no database, and are split by environment anyway so that each
# environment's hourly build reads a store only its own legs write, as
# publish-conditions.yml's legs do. Not in LANES, so fixture mode, which runs
# the lanes, does not run the hourly resources more than once.
LEGS = {
    "conditions_production": Leg("hourly", CONDITIONS_JOB),
    "conditions_ua": Leg("hourly", CONDITIONS_JOB),
    "notices_production": Leg("hourly", NOTICES_JOB),
    "notices_ua": Leg("hourly", NOTICES_JOB),
}

#: THE CONDITIONS JOB'S OWN UPSTREAMS, by raw table, each with why it stays
#: hourly. Exactly what the conditions legs read at 52835a44 that the bake had
#: published before decision 53 (every other hourly resource there was a
#: decision 53 phase B layer, landed 2026-10-03), and the seven sources
#: int_closures__gate types by hand. Decision 61 keeps these in the short
#: hourly job because what a storm or a moderator's closure turns on cannot
#: wait four hours: most severe thunderstorm warnings last less than that, and
#: a verified closure would take up to about 5 hours to reach a phone.
#: Anything not named here is the notices job's.
HOURLY_JOB_TABLES: dict[str, str] = {
    "raw_nws__alerts": "NWS's active alerts: a warning shorter than about 4 hours would expire unseen on a 4-hourly read",
    "raw_ourhike__closures": "OurHike's own moderator-verified closures, which reach a phone within the hour",
    "raw_ourhike__reports": "OurHike's own verified reports, moderated as the closures are",
    "raw_ourhike__notes": "OurHike's own field notes, read by the same queries as the closures",
    "raw_ourhike__disputes": "OurHike's own disputes, read by the same queries as the closures",
    "raw_ourhike__work_projects": "the reviewed volunteer work projects (#760), a file in git the bake has published since",
    "raw_atc__atc_updates": "ATC's reviewed trail updates file, reference/atc_updates.json (#460)",
    "raw_atc__atc_trail_updates": "ATC's reviewed trail updates, one row per update (#460)",
    "raw_atc__atc_trail_updates_pages": "what ATC's site shows since the review, which the bake has published since #963",
    "raw_nynjtc__nynjtc_trail_alerts": "NYNJTC's trail alerts (#1078), published by the bake before decision 53",
    "raw_nynjtc__nynjtc_trail_alerts_terms": "NYNJTC's alert taxonomy terms, daily, which place NYNJTC's alerts",
    "raw_nysparks__oprhp_trail_closures": (
        "OPRHP's temporary trail closures (#1152 - Move OPRHP's temporary closures onto the conditions clock, "
        "where a safety layer belongs)"
    ),
}


def job_of(resource: Resource) -> str:
    """Which job reads this hourly-lane resource (decision 61): CONDITIONS_JOB for HOURLY_JOB_TABLES, else NOTICES_JOB."""
    return CONDITIONS_JOB if resource.table in HOURLY_JOB_TABLES else NOTICES_JOB


# A LEG TAKES ON AT MOST THIS MANY TABLES IT HAS NEVER LOADED IN ONE RUN, after
# every table it has (take_on_new_tables()); the rest wait, logged
# INCOMPLETE as "not yet loaded", and come on over the next runs. One number
# per job, because the two jobs have different budgets.
#
# The conditions job's 10: soak run 506 (publish-conditions.yml 37154645937,
# 2026-10-03) met 70 new hourly layers at once: 85 resources to read, the
# 150 s read budget spent, and the extract step killed at its 4-minute cap
# during dlt's load, so nothing committed and the next run would have met the
# same 85. Run 505, an hour earlier, read 13 and loaded them inside 58 s. 10
# is @unvalidated: it keeps a run near 505's size plus ten. Since decision 61
# a conditions leg carries twelve tables, so the limit bites only on a new
# store's first two runs, or when a source joins HOURLY_JOB_TABLES.
#
# The notices job's 150, Reasoned from run 506 and @unvalidated. In 506 the
# read budget ended at 21:22:23Z and the step was killed at 21:23:42Z, and in
# those 78 s dlt normalized and loaded the 83 tables it had read (68 of them
# new), the after-run check and the run log committed, and the warehouse read
# had begun: at most 0.94 s a table. extract-notices.yml's extract step has
# 50 minutes: up to 10 for the change checks (LEG_CHECK_SECONDS) and 30 for
# the reads, so about 9 are left for the sync and the load, and 150 new
# tables at that rate take about 2.4 of them. At 150 a run, the 80 layers
# decision 61 moved here and phase B's 181 page, feed and WordPress sources
# come on in two runs, where 10 a run would take 27. What would settle it:
# the "Seconds:" line of the first two notices runs' summaries, against the
# tables each took on.
NEW_TABLES_PER_LEG_RUN = {CONDITIONS_JOB: 10, NOTICES_JOB: 150}
# A LEG'S CHANGE CHECKS END AFTER THIS MANY SECONDS, as its reads do after
# --read-seconds (by_folder()). A check still out is refused on its own: its
# last committed table stands and it is not read this run. One number per
# job, because the notices job's folders are far slower to check.
#
# The conditions job's 45: soak run 512 (publish-conditions.yml 37179583519)
# waited 2 m 12 s on one change check, dnrmaps.wi.gov refusing connections (a
# 30 s connect timeout, three attempts, 5 and 30 s apart), and the 150 s read
# budget that followed ran past the extract step's 4-minute cap. Run 510's 89
# checks, a folder per thread, took well under this (Reasoned from its 2 m
# 49 s whole step). 45 is @unvalidated: the step summary's "change checks"
# timing settles whether it is too tight. Its twelve tables since decision 61
# hold no page behind a Crawl-delay.
#
# The notices job's 600, Reasoned from the registry at 377e981a and
# @unvalidated. A page or feed notice's change check IS its one request a run
# (extract/_notices.py: the read reuses what the check fetched), and a
# folder's checks run one after another behind its host's Crawl-delay, so a
# folder's pass costs at least its pages' gaps: buckeyetrail.org's 26 pages
# and blm.gov's 26 at 2 s are 50 s each, hike-mst.org's 23 are 44 s, and
# bmta's 2 pages behind a 60 s Crawl-delay are 60 s, before any request's own
# time. 45 would refuse all four every run. 600 covers the slowest of them
# several times over, and one request that runs lib/http_retry.py's whole
# ladder (3 attempts of 60 s with 5 and 30 s between, 215 s; more under a
# Retry-After) on top. It is ten minutes of extract-notices.yml's 50-minute
# step, whose read budget is 30 (1800 s): the reads that follow a page's check
# reuse its answer, so most of a notices run's waiting is here. The
# "change checks" timing of the first notices runs settles it.
LEG_CHECK_SECONDS = {CONDITIONS_JOB: 45, NOTICES_JOB: 600}
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
# The outcome of a carrying resource whose read ran out of budget before it
# had every row (extract/_contract.py's Incomplete): left out of the run, its
# last committed table standing (on a first run, not yet loaded).
INCOMPLETE = "incomplete"
# What an incomplete read had read, kept for the next run to carry on from and
# never read as data: one row per row read, `row_json` as the resource yielded
# it. Replaced whole in the run log's own load, which every run commits, so it
# survives a run whose other tables were refused. extract/_warehouse.py loads
# only tables `_extract_runs` names, which this never is.
PROGRESS_TABLE = "_extract_progress"

#: Other lanes' resources a lane also lands in its own raw store with
#: `cross_lane=True` (--cross-lane-inputs, refresh-reference.yml), each with
#: the reason. A dbt node is built by one lane (build_marts.py --lane), so the
#: lane lands its own copy of every table its nodes read, and its pinned
#: raw_run (extract/_warehouse.py) freezes them. Never in fixture mode, whose
#: lanes share one store.
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

#: THE MONTHLY LANE ISOLATES EACH UPSTREAM, as a leg does (_extract_and_load()).
#: Monthly runs 10, 11, 12, 14 and 15 (refresh-reference.yml, 2026-10-03/04)
#: each stopped on one layer of about 480, and took every other layer's month
#: with it: run 14 on Oregon Metro's rate limit twelve minutes in, run 15 two
#: minutes in on MassGIS's open-space layer answering its metadata 403. The
#: plain `hourly` lane, which no workflow runs (the legs read its resources),
#: keeps one refusal refusing the run.
ISOLATING_LANES = frozenset({"monthly"})

#: How many extract folders the monthly lane reads at once, before dlt
#: (read_each()). A folder's resources are still read one after another, so
#: no host a folder asks is asked twice at once. @unvalidated: run 13
#: (refresh-reference.yml 37182708502) read its layers one at a time in about
#: 50 minutes, 484 s of it USFS's trails, and 4 is the runner's vCPU count,
#: not a measurement of what the upstreams tolerate. The first run's "read"
#: timing, and any rate-limit waits lib/arcgis.py logs, would settle it.
MONTHLY_READERS = 4

#: dlt's normalize processes for refresh-reference.yml's monthly run, which
#: passes it as --normalize-workers. Run 13's normalize was about 103 of its
#: extract step's 161 minutes (Reasoned from its log: its last layer was read
#: at 07:16:26Z and normalize's schema warnings closed at 08:59:37Z), in one
#: process on a 4-vCPU runner. dlt gives each worker whole tables (its
#: group_worker_files()), so USFS's 1,072,508,650 bytes of trails stay one
#: worker's. Everything else normalizes in one process, the default: fixture
#: mode under pipeline-tests.yml's pytest job, on Python 3.14, lost a worker
#: of a 4-process pool (BrokenProcessPool, "terminated abruptly", run
#: 37214263752 on 3a408a41), which the same build on 3.13 here did not.
#: Why is unmeasured; a leg normalizes in seconds and gains nothing from it.
MONTHLY_NORMALIZE_WORKERS = 4


def isolates(lane: str) -> bool:
    """Whether the lane, or leg, leaves an upstream that fails out on its own while the rest load."""
    return lane in LEGS or lane in ISOLATING_LANES


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
    # A carrying resource's last committed rows and kept progress (carried_for()), handed to its read.
    carried: Carried | None = None


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
    # Each table's column hints, as read_each() or to_dlt read them. Kept in the
    # run log only where the warehouse may create the table from them: a proven
    # zero, and a table refused or incomplete on its own (write_run_log()).
    hints: dict[str, dict] = field(default_factory=dict)
    # Resources whose change check raised Unavailable, by name: why each was left out.
    unavailable: dict[str, str] = field(default_factory=dict)
    # Seconds each timed() part took, in the order they ran (sync, change
    # checks, read, extract, normalize, load, after-run check, run log,
    # warehouse). A part a run did not reach is absent.
    timings: dict[str, float] = field(default_factory=dict)
    # A leg or an isolating lane only (isolates()): resources refused on their own while the rest
    # loaded, by name, with why. Each keeps its last committed table, is logged
    # ISOLATED_OUTCOME, and makes the command line exit PARTIAL_EXIT.
    isolated: dict[str, str] = field(default_factory=dict)
    # {table: path under data/raw/} of the as-landed files this run uploaded under
    # `as_landed/<load_id>/`; empty unless run_pipeline(as_landed=True).
    as_landed: dict[str, str] = field(default_factory=dict)
    # Carrying resources whose read ran out of budget (INCOMPLETE), by name,
    # with how far it got. Not a refusal, so the exit stays 0; a read that fit
    # no page at all raises instead, and is isolated.
    incomplete: dict[str, str] = field(default_factory=dict)
    # A leg only: resources whose table has never loaded and that
    # this run did not take on (take_on_new_tables()), by name, with why. They
    # are logged INCOMPLETE with no column hints, so nothing lands, no marker
    # moves and no metadata is asked for; not a refusal, so the exit stays 0.
    waiting: dict[str, str] = field(default_factory=dict)
    # Isolated resources whose sources.json row says reaches_hikers false, by
    # name (quiet_refusals()): listed as refused, but they leave the exit 0,
    # because nothing a hiker sees is held back by them.
    quiet: set[str] = field(default_factory=set)
    # What each incomplete read had read, by name, which write_run_log keeps
    # in PROGRESS_TABLE for the next run.
    progress: dict[str, list[dict]] = field(default_factory=dict)
    # `_extract_runs` as this run left it, so --warehouse does not read every file again.
    run_log: list[dict] | None = field(default=None, repr=False)


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
    """The cadences a lane, or a leg's lane, carries."""
    if lane in LEGS:
        return LANES[LEGS[lane].lane]
    if lane not in LANES:
        raise ValueError(f"no lane {lane!r}; lanes are {sorted(LANES)} and legs {sorted(LEGS)}")
    return LANES[lane]


def lane_resources(lane: str, resources: list[Resource]) -> list[Resource]:
    """The resources a lane runs: those of its cadences, and on a leg only those of the leg's job (job_of())."""
    leg = LEGS.get(lane)
    return [
        resource
        for resource in resources
        if resource.cadence in cadences_of(lane) and (leg is None or job_of(resource) == leg.job)
    ]


def leg_tables(leg: str, resources: list[Resource]) -> set[str]:
    """The raw tables a leg's job reads now: what a build may take from that leg's store, and nothing else in it."""
    if leg not in LEGS:
        raise ValueError(f"no leg {leg!r}; legs are {sorted(LEGS)}")
    return {resource.table for resource in lane_resources(leg, resources)}


def cross_lane_resources(lane: str, resources: list[Resource], own: list[Resource]) -> list[Resource]:
    """The other lanes' resources ALSO_READS names for `lane`. Refuses a name no resource carries, rather than reading less."""
    wanted = ALSO_READS.get(lane, {})
    found = [resource for resource in resources if resource.name in wanted and resource not in own]
    if missing := sorted(set(wanted) - {resource.name for resource in found} - {resource.name for resource in own}):
        raise ValueError(f"ALSO_READS names no resource called {', '.join(missing)} for the {lane} lane")
    return found


#: The raw store's prefix for dlt's files, inside the private bucket: raw
#: under `raw/` (ELT.md decision 43) and one prefix per dlt pipeline (ELT.md,
#: "Storage tiers": `dlt/<pipeline>/raw/<table>/…`), where dlt itself adds
#: the dataset, `raw`, and the table.
RAW_STORE_PREFIX = "raw/dlt"


def raw_store_url(bucket: str, lane: str) -> str:
    """`s3://<bucket>/raw/dlt/<lane>`: one lane's, or one leg's, own prefix in the raw store.

    Named for the lane as ELT.md's "Storage tiers" writes it (`dlt/monthly/`,
    the prefix refresh-reference.yml's monthly run writes), and for each leg by
    its own name, so no two lanes or legs share a table file, a marker or a run
    log. dlt reads the endpoint and keys from
    `DESTINATION__FILESYSTEM__CREDENTIALS__*`, never from here.
    """
    cadences_of(lane)  # refuses an unknown lane before any URL is made
    if not bucket or "/" in bucket or ":" in bucket:
        raise ValueError(f"{bucket!r} is not a bucket name; pass the bucket alone, as R2_RAW_BUCKET holds it")
    return f"s3://{bucket}/{RAW_STORE_PREFIX}/{lane}"


#: The exit status of a leg or an isolating lane that loaded, and left at least one
#: resource out as refused: not 0, so the job goes red, and not 1, so the
#: workflow can tell "the rest loaded" from "nothing loaded" and still build
#: and publish what did. 2 is argparse's own.
PARTIAL_EXIT = 3
ISOLATED_OUTCOME = "refused"


def stops_the_leg(resource: Resource) -> bool:
    """Whether a refused or failed read of this resource stops the whole leg, rather than only itself.

    OurHike's own Postgres rows (ConditionsQuery) do, as they stop
    export_conditions.py today (extract/_shared/ourhike/closures.py): it
    publishes nothing when it cannot read the database, and a phone keeps the
    last file with its true age. Every other upstream is somebody else's site
    and fails on its own: the leg leaves it out and its last committed table
    stands, as publish-conditions.yml's fetch steps carry ATC's and NYNJTC's
    previous cache forward when either is unreachable.
    """
    return isinstance(resource, ConditionsQuery)


def take_on_new_tables(report: RunReport, to_run: list[Planned], current: dict, log: list[dict], limit: int) -> list[Planned]:
    """`to_run` less the never-loaded resources past `limit`, which go in `report.waiting`.

    Every resource whose table has a logged, committed load (`current`) runs
    as before. Of the rest, those never tried come first, then those refused
    longest ago, so a layer that fails every run goes to the back each time
    and cannot hold the others out; ties go by name.
    """
    new = [item for item in to_run if item.resource.table not in current]
    if len(new) <= limit:
        return to_run
    tried: dict[str, str] = {}
    for row in log:
        if row.get("outcome") == ISOLATED_OUTCOME:
            name = row["resource_name"]
            tried[name] = max(tried.get(name, ""), row["run_id"])
    new.sort(key=lambda item: (tried.get(item.resource.name, ""), item.resource.name))
    waiting = new[limit:]
    for item in waiting:
        report.waiting[item.resource.name] = (
            f"not yet loaded: a leg takes on {limit} tables it has never loaded per run, and {len(new)} were due"
        )
    print(f"::notice title={len(waiting)} new tables wait their turn::{', '.join(sorted(report.waiting))}")
    left_out = {item.resource.name for item in waiting}
    return [item for item in to_run if item.resource.name not in left_out]


def quiet_refusals(report: RunReport, resources: list[Resource]) -> set[str]:
    """The isolated resources whose sources.json row says reaches_hikers false.

    A key with no registry row, or a row that does not say false, is not
    quiet: an unknown is held to the stricter rule.
    """
    by_name = {resource.name: resource for resource in resources}
    quiet = set()
    for name in report.isolated:
        resource = by_name.get(name)
        try:
            row = _kinds.registry_entry(resource.key) if resource is not None else None
        except KeyError:
            row = None
        if row is not None and row.get("reaches_hikers") is False:
            quiet.add(name)
    return quiet


class CheckTimedOut(Exception):
    """A change check by_folder() stopped waiting for: the leg's job's LEG_CHECK_SECONDS ran out first."""


def by_folder(resources: list[Resource], work: Callable, seconds: float | None = None) -> list:
    """`work(resource)` for each resource, in order, one thread per extract folder.

    A folder's resources are asked one after another, so no host is asked
    twice at once, the rule read_each() keeps. Each answer is what `work`
    returned, or the exception it raised, for the caller to handle in order.
    Soak run 508 (publish-conditions.yml 37158027469) spent 29 s asking 89
    upstreams one at a time, with 190 more notice sources being wired.

    `seconds` bounds the whole wait, as read_each()'s budget does: a resource
    with no answer by then gets a CheckTimedOut, and its daemon thread is
    abandoned, so a host that never answers holds no other club back.
    """
    answers: dict[int, object] = {}

    def run(items: list[tuple[int, Resource]]) -> None:
        for index, resource in items:
            try:
                answers[index] = work(resource)
            except BaseException as failure:  # noqa: BLE001 - handed back to the caller, which re-raises it
                answers[index] = failure

    groups: dict[str | None, list[tuple[int, Resource]]] = defaultdict(list)
    for index, resource in enumerate(resources):
        groups[resource.club].append((index, resource))
    threads = [threading.Thread(target=run, args=(items,), name=f"check {club}", daemon=True) for club, items in groups.items()]
    deadline = None if seconds is None else time.monotonic() + seconds
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(None if deadline is None else max(0.0, deadline - time.monotonic()))
    answered = dict(answers)  # a thread that finishes after the deadline changes nothing below
    late = CheckTimedOut(f"no answer within the leg's {seconds:g} s change-check budget") if seconds is not None else None
    return [answered.get(index, late) for index in range(len(resources))]


def exit_status(report: RunReport) -> int:
    """The command line's exit after a run that loaded: PARTIAL_EXIT when a resource that may reach a hiker was refused."""
    return PARTIAL_EXIT if set(report.isolated) - report.quiet else 0


class Spool:
    """One resource's rows, read before dlt runs and kept on disk until the run ends (read_each()).

    The monthly lane's layers are too large to hold: run 13 spooled
    5,122,690,216 bytes of ArcGIS features, 1,072,508,650 of them USFS's
    trails. Each row is pickled, so dlt is handed exactly the objects the
    reader made, and the file is gzip at level 1. Iterating reads the file
    again from the start, so a table re-extracted after another's refusal
    gets the same rows."""

    def __init__(self, path: Path):
        self.path = path
        self.count = 0

    def write(self, rows) -> Spool:
        try:
            with gzip.open(self.path, "wb", compresslevel=1) as out:
                for row in rows:
                    pickle.dump(row, out, protocol=pickle.HIGHEST_PROTOCOL)
                    self.count += 1
        except BaseException:
            self.path.unlink(missing_ok=True)
            raise
        return self

    def __iter__(self):
        with gzip.open(self.path, "rb") as source:
            while True:
                try:
                    yield pickle.load(source)
                except EOFError:
                    return

    def __len__(self) -> int:
        return self.count


def read_each(
    report: RunReport,
    to_run: list[Planned],
    seconds: float | None,
    *,
    spool: Path | None = None,
    readers: int | None = None,
) -> tuple[list[Planned], dict]:
    """Read every resource's rows before dlt runs, so one upstream's failure, or its slowness, is its own.

    A club's resources are read one after another, one folder to a thread, so
    no host is asked twice at once: every folder at once, or `readers` folders
    at a time (MONTHLY_READERS). With `spool`, a directory, each resource's
    rows go to a Spool there rather than a list. `seconds` is the whole read's
    budget: a folder still reading at the end leaves its unread resources out
    of this run, and its daemon thread is abandoned. No host's Crawl-delay is
    shortened to fit (lib/http_retry.py's throttle is the resource's own).
    A carrying resource (Resource.carries) gets what is left of the budget, so
    it can stop in time: it answers Incomplete and goes in `report.incomplete`
    (what it read in `report.progress`) rather than being refused.

    Returns the resources that answered, and {name: rows}. One whose read
    failed or ran out of time goes in `report.isolated`, or is re-raised where
    stops_the_leg() says so. Column hints are read here too, first, because
    ArcGIS's ask the layer's metadata again; they go in `report.hints`.
    """
    results: dict[str, object] = {}
    hints: dict[str, dict] = {}
    files = {item.resource.name: None if spool is None else spool / f"{index}.pickle.gz" for index, item in enumerate(to_run)}

    def read(items: list[Planned]) -> None:
        for item in items:
            proofs: dict[str, int] = {}
            try:
                hints[item.resource.table] = item.resource.column_hints()
                if item.resource.carries:
                    left = None if deadline is None else max(0.0, deadline - time.monotonic())
                    answer = item.resource.rows_carried(proofs, replace(item.carried or Carried(), seconds=left))
                else:
                    answer = item.resource.rows(proofs)
                path = files[item.resource.name]
                rows = list(answer) if path is None else Spool(path).write(answer)
            except Exception as failure:  # noqa: BLE001 - every failure is recorded, and re-raised where it stops the leg
                results[item.resource.name] = failure
            else:
                results[item.resource.name] = (rows, proofs)

    folders: queue.SimpleQueue[list[Planned]] = queue.SimpleQueue()
    by_folder: dict[str | None, list[Planned]] = defaultdict(list)
    for item in to_run:
        by_folder[item.resource.club].append(item)
    for items in by_folder.values():
        folders.put(items)

    def reader() -> None:
        while True:
            try:
                items = folders.get_nowait()
            except queue.Empty:
                return
            read(items)

    count = len(by_folder) if readers is None else max(1, min(readers, len(by_folder)))
    threads = [threading.Thread(target=reader, name=f"read {index}", daemon=True) for index in range(count)]
    deadline = None if seconds is None else time.monotonic() + seconds
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(None if deadline is None else max(0.0, deadline - time.monotonic()))
    answered = dict(results)  # a thread that finishes after the deadline changes nothing below
    report.hints.update(hints)

    kept, read_rows = [], {}
    for item in to_run:
        name = item.resource.name
        outcome = answered.get(name)
        if outcome is None:
            failure: BaseException = TimeoutError(f"no answer within the leg's {seconds:g} s read budget")
        elif isinstance(outcome, Incomplete):
            loaded_before = bool(item.carried and item.carried.committed)
            report.incomplete[name] = f"{outcome}; {'its last committed table stands' if loaded_before else 'not yet loaded'}"
            report.progress[name] = outcome.progress
            print(f"::warning title={name} {'incomplete' if loaded_before else 'not yet loaded'}::{report.incomplete[name]}")
            continue
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


def contract_breach(failure: BaseException) -> DataValidationError | None:
    """The schema-contract refusal behind a failed dlt step, or None. A retyped ArcGIS field raises one at extract."""
    seen = set()
    while failure is not None and id(failure) not in seen:
        if isinstance(failure, DataValidationError):
            return failure
        seen.add(id(failure))
        failure = failure.__cause__ or failure.__context__
    return None


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


#: R2 refuses a multipart upload whose parts are not all one length ("All
#: non-trailing parts must have the same length"), and s3fs only guarantees
#: that with fixed_upload_size. Monthly run 37088620131's pin failed on it
#: (2026-10-03), writing a large file through fs.open().
S3_KWARGS = {"fixed_upload_size": True}


def make_pipeline(lane: str, bucket_url: str, pipelines_dir: str | None = None):
    kwargs = S3_KWARGS if bucket_url.startswith("s3://") else None
    return dlt.pipeline(
        pipeline_name=f"ourhike_{lane}",
        destination=dlt.destinations.filesystem(bucket_url, kwargs=kwargs),
        dataset_name=DATASET,
        pipelines_dir=pipelines_dir,
    )


def store_schema(pipeline) -> dlt.Schema:
    """The one dlt schema everything a lane writes goes into: the store's default, or SOURCE_NAME's in a store with none.

    dlt puts its own state in the default schema's load package, so a second
    schema makes a second package, which _extract_and_load refuses ("one load
    expected from this run, and 2 committed": refresh-reference.yml's monthly
    run 37070628933, after 37058045092 was refused before its load).
    tests/test_extract_run.py reproduces it: a refused run's log, a bare
    resource, makes `ourhike_<lane>` the store's default schema, and the next
    run's `extract` schema is a second one. Reasoned from that reproduction;
    the R2 store's own schema list was not read.
    """
    if pipeline.default_schema_name:
        return pipeline.default_schema
    return dlt.Schema(SOURCE_NAME)


#: The key under which each stored marker also carries its resource's definition_digest().
DEFINITION_KEY = "_definition"


def definition_digest(resource: Resource) -> str:
    """A sha256 of what decides a resource's rows on our side: its own fields, the fields every read drops, its `where`.

    Kept in its marker, so a fix to the resource, such as a field added to
    PERSON_FIELDS or to an ArcGIS row's `person_fields`, reads an upstream
    that has not moved again once.
    """
    definition = {
        "resource": repr(resource),
        "person_fields": sorted(_kinds.PERSON_FIELDS),
        "person_shaped": _kinds.PERSON_SHAPED.pattern,
        "field_rules": getattr(resource, "field_rules", None),
        "wordpress_dropped": sorted(_kinds.WP_DROPPED),
        "withheld_columns": sorted(_kinds.WITHHELD_COLUMNS),
        "where": getattr(resource, "where", None),
    }
    # Only when on, so every digest recorded before return_z existed still matches:
    # turning it on changes the geometry a read lands, so the layer is read once more.
    if getattr(resource, "return_z", False):
        definition["return_z"] = True
    return hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()


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


def to_dlt(
    resource: Resource,
    marker: dict | None,
    proofs: dict[str, int],
    loaded_at: datetime,
    hints=None,
    read=None,
    carried: Carried | None = None,
    as_landed=None,
):
    """Wrap one Resource in the dlt settings every resource shares. `hints` collects each table's column hints.

    `read` is the resource's rows already read (a leg reads each
    upstream on its own first, read_each()); None reads them here, through
    rows_carried() with `carried` and no budget for a resource that carries.
    `as_landed`, an AsLanded, copies each row it yields, read here or before
    (the module docstring). Hints already in `hints` are used as they are."""
    columns = None if hints is None else hints.get(resource.table)
    if columns is None:
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
        if read is not None:
            answer = (dict(row) for row in read)
        elif resource.carries:
            answer = resource.rows_carried(proofs, replace(carried or Carried(), seconds=None))
        else:
            answer = resource.rows(proofs)
        for row in answer:
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
    data/raw/<key>.geojson; fetch_external_layers.py writes every other
    organization's layer, ArcGIS or Socrata, to data/raw/external/<key>.geojson;
    fetch_opentrail.py writes OPENTRAIL_RAW_NAME. extract/_fixtures.py's
    fixture_file() and every exporter parity.py runs read those paths.
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

    def reset(self) -> None:
        """Forget every staged file: a leg that refused a table on its own extracts what is left again
        (_extract_and_load), and the copy starts again with that extract, so no row is copied twice."""
        for handle in self._open.values():
            handle.close()
        self._open.clear()
        for path in self.paths.values():
            (self.staging / path).unlink(missing_ok=True)
        self.paths.clear()

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


def as_landed_index(fs, bucket_url: str, load_id: str, cache: dict) -> dict[str, str]:
    """{table: path under data/raw/} for one load's as-landed files; empty for a load that wrote none."""
    if load_id not in cache:
        path = f"{fs_path(bucket_url)}/{AS_LANDED_PREFIX}/{load_id}/{AS_LANDED_INDEX}"
        if fs.exists(path):
            with fs.open(path, "r") as index:
                cache[load_id] = json.load(index)
        else:
            cache[load_id] = {}
    return cache[load_id]


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
        elif resource.exact_proof and landed != proof:
            # Rows built from the very answer the count is read from: more rows than it counts is a row twice, or
            # a carried row the upstream no longer lists, and no count at all is a read that skipped its proof.
            problems.append(
                f"{table}: {landed} rows, and the upstream counts {proof}, which must be exactly the rows this table holds"
            )
        elif proof is None and resource.may_be_empty:
            # A table that may empty has no shrink floor, so it may shrink only
            # beside the same proof a zero needs.
            problems.append(
                f"{table}: {landed} rows and no upstream count read this run; a {resource.type} table has no "
                "shrink floor, so a read cut short would pass as rows removed"
            )
        prior = previous.get(table)
        if not resource.may_be_empty and prior and landed < COLLAPSE_FLOOR * prior:
            problems.append(f"{table}: {landed} rows against {prior} last time, below the {COLLAPSE_FLOOR:.0%} floor")
    return problems


def _client(pipeline):
    return pipeline.destination_client()


def committed_load_ids(pipeline) -> set[str]:
    """Load ids `_dlt_loads` records as complete, from its file names: one listing, no file read.

    dlt 1.30.0's filesystem destination writes one `<schema>__<load_id>.jsonl`
    per complete load, always with status 0 (FilesystemClient._store_load()),
    and writes it last, so a load cut short has none.
    """
    ids = set()
    for path in _client(pipeline).list_table_files("_dlt_loads"):
        name = os.path.basename(path)
        if name.endswith(".jsonl") and "__" in name:
            ids.add(name.removesuffix(".jsonl").rsplit("__", 1)[1])
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


def table_listing(pipeline, tables: list[str]) -> dict[str, list[str]]:
    """{table: its Parquet files} for each of `tables`, from one listing of the dataset rather than one per table.

    The same files table_files() lists: dlt 1.30.0's list_table_files() globs
    the table's directory and keeps the paths under the table's own prefix,
    and this keeps the paths under each prefix from one glob of the dataset.
    tests/test_extract_run.py holds the two equal. A store with nothing in it
    yet lists nothing.
    """
    client = _client(pipeline)
    root = client.pathlib.join(client.dataset_path, "")
    try:
        found = [
            client.pathlib.join(root, details["relative_path"])
            for details in glob_files(client.fs_client, client.make_remote_url(root), "**")
        ]
    except FileNotFoundError:
        return {}
    found = sorted(path for path in found if path.endswith(".parquet"))
    return {table: [path for path in found if path.startswith(client.get_table_prefix(table))] for table in tables}


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
    return _read_rows(pipeline, table_files(pipeline, RUNS_TABLE))


def _read_rows(pipeline, files: list[str]) -> list[dict]:
    client = _client(pipeline)
    rows = []
    for path in files:
        rows.extend(pq.read_table(client.fs_client.open(path)).to_pylist())
    return rows


def readable_tables(pipeline, log: list[dict], complete: set[str]) -> dict[str, str]:
    """{table: the load a build reads it from}: extract/_warehouse.py's committed_tables(), imported here for committed_rows()' reason."""
    from extract._warehouse import committed_tables

    return committed_tables(pipeline, log=log, complete=complete)


def fresh_but_unserved(
    pipeline, resource: Resource, load_id: str | None, row: dict, landed=None, files: list[str] | None = None
) -> str | None:
    """Why a FRESH verdict cannot stand, or None. `landed`, in an --as-landed run, gives a load's as-landed index.

    FRESH keeps the served load, so that load must still have its files, and,
    in an --as-landed run, the as-landed file the pin copies: an upload that
    failed after the run log leaves a logged load with none.
    """
    if not load_id or not served_files_intact(pipeline, resource.table, load_id, row, files=files):
        return f"the files of load {load_id} are gone"
    if landed is not None and as_landed_path(resource) is not None and resource.table not in landed(load_id):
        return f"load {load_id} wrote no as-landed file"
    return None


def proven_zero(row: dict) -> bool:
    """Whether a run log row is a load of 0 rows beside the upstream's own 0, with the hints to create the table empty."""
    return row.get("rows") == 0 and row.get("count_proof") == 0 and row.get("column_hints") is not None


def served_files_intact(pipeline, table: str, load_id: str, row: dict, files: list[str] | None = None) -> bool:
    """Whether the table's files are still those of `load_id`, the load a build serves it from.

    A later load's `replace` deletes them, and that load's marker can reach
    dlt state with no `_extract_runs` row: dlt 1.30.0's filesystem
    complete_load() stores the state before the `_dlt_loads` row. A first-run
    proven zero has no file at all.
    """
    files = table_files(pipeline, table) if files is None else files
    if any(not os.path.basename(path).startswith(f"{load_id}.") for path in files):
        return False
    return bool(files) or proven_zero(row)


def committed_rows(pipeline, table: str, *, log: list[dict] | None = None, complete: set[str] | None = None) -> tuple[dict, ...]:
    """The table's rows as its last committed load left them, dlt's own columns dropped; () where it has none.

    The load is the one extract/_warehouse.py's committed_tables() serves, and
    its files are listed by that load id, never globbed, so nothing an
    uncommitted package left behind is carried. Imported here rather than at
    the top, because that module imports this one.
    """
    from extract._warehouse import committed_tables

    load_id = committed_tables(pipeline, log=log, complete=complete).get(table)
    if load_id is None:
        return ()
    rows = _read_rows(pipeline, table_files(pipeline, table, load_id))
    return tuple({name: value for name, value in row.items() if not name.startswith("_dlt_")} for row in rows)


def stored_progress(pipeline, complete: set[str] | None = None) -> dict[str, list[dict]]:
    """What earlier incomplete reads kept (PROGRESS_TABLE), by resource name: the newest committed load's rows.

    The load is the newest that `_dlt_loads` records complete and that wrote
    this table, found by the load id in each file's name. A `replace` load
    deletes the files before it, so that is the one snapshot; a load cut
    short never commits, and is passed over for the last that did.
    """
    files = table_files(pipeline, PROGRESS_TABLE)
    if not files:
        return {}
    complete = committed_load_ids(pipeline) if complete is None else complete
    loads = {load_id: [path for path in files if os.path.basename(path).startswith(f"{load_id}.")] for load_id in complete}
    written = sorted((load_id for load_id, paths in loads.items() if paths), key=float)
    if not written:
        return {}
    kept: dict[str, list[dict]] = defaultdict(list)
    for row in _read_rows(pipeline, loads[written[-1]]):
        kept[row["resource_name"]].append(json.loads(row["row_json"]))
    return dict(kept)


def carried_for(pipeline, items: list[Planned], kept: dict[str, list[dict]], log: list[dict], complete: set[str]) -> None:
    """Hand each carrying resource about to be read its last committed rows and its kept progress (Planned.carried)."""
    for item in items:
        if item.resource.carries:
            item.carried = Carried(
                committed=committed_rows(pipeline, item.resource.table, log=log, complete=complete),
                progress=tuple(kept.get(item.resource.name, ())),
            )


def progress_after(kept: dict[str, list[dict]], report: RunReport, loaded: set[str]) -> dict[str, list[dict]]:
    """What PROGRESS_TABLE holds after this run: a read that loaded drops its own, an incomplete one replaces it.

    Anything else, a resource refused, isolated, not due or not read at all,
    keeps what it had, so a run whose other tables were refused costs a
    first run nothing it had already read.
    """
    after = {name: rows for name, rows in kept.items() if name not in loaded}
    after.update(report.progress)
    return {name: rows for name, rows in after.items() if rows}


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


# PROGRESS_TABLE's columns: whose progress, the run that wrote this snapshot, and the row as JSON text.
PROGRESS_COLUMNS = {
    "resource_name": {"data_type": "text", "nullable": False},
    "run_id": {"data_type": "text", "nullable": False},
    "row_json": {"data_type": "text", "nullable": False},
}


def write_run_log(
    pipeline,
    report: RunReport,
    planned: list[Planned],
    checked_at: datetime,
    unavailable: list[Resource] = (),
    progress: dict[str, list[dict]] | None = None,
) -> list[str]:
    """Append one `_extract_runs` row per planned resource, and per unavailable one. INCREMENTAL.md's log.json, as one append-only table.

    Returns the ids of the loads that wrote it.

    `progress`, where the run has a carrying resource or kept progress
    (progress_after()), replaces PROGRESS_TABLE in the same load, so what an
    incomplete read fetched commits with the run log whatever else the run did.
    """
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
        # An isolated resource (refused on its own by a leg) and an incomplete
        # read leave what a FRESH one leaves, no rows and no load, and are
        # logged `refused` or `incomplete`, so committed_tables() keeps serving
        # the last committed load and due() does not count the check. Both keep
        # their column hints, so the warehouse can create a table not yet
        # loaded, empty, rather than refuse the build (not_yet_loaded()).
        isolated = resource.name in report.isolated
        waiting = resource.name in report.waiting
        incomplete = resource.name in report.incomplete or waiting
        skipped = item.verdict is Freshness.FRESH or isolated or incomplete
        outcome = ISOLATED_OUTCOME if isolated else INCOMPLETE if incomplete else "skipped" if skipped else report.outcome
        if waiting:
            hints = None  # never read this run, and column_hints() would ask the server for its metadata
        elif incomplete:
            hints = report.hints.get(resource.table) or resource.column_hints()
        elif isolated:
            hints = report.hints.get(resource.table)  # None where the read failed before its hints
        elif outcome == "loaded" and report.rows.get(resource.table, 0) == 0:
            # A proven zero writes no file on a table's first load (dlt keeps no
            # schema for a table that never held a row, measured 2026-10-01), so
            # its hints are what lets the warehouse create it empty.
            hints = report.hints.get(resource.table)
        else:
            hints = None
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
                "outcome": outcome,
                "checked_at": checked_at,
                "column_hints": None if hints is None else json.dumps(hints, sort_keys=True),
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

    if progress is None:
        return pipeline.run(runs(), schema=store_schema(pipeline)).loads_ids

    @dlt.resource(
        name=PROGRESS_TABLE,
        table_name=PROGRESS_TABLE,
        write_disposition="replace",
        file_format="parquet",
        columns=PROGRESS_COLUMNS,
    )
    def kept():
        yield [
            {"resource_name": name, "run_id": report.run_id, "row_json": json.dumps(row, sort_keys=True)}
            for name, rows in sorted(progress.items())
            for row in rows
        ]

    return pipeline.run([runs(), kept()], schema=store_schema(pipeline)).loads_ids


def run_pipeline(
    lane: str,
    bucket_url: str,
    *,
    resources: list[Resource] | None = None,
    pipelines_dir: str | None = None,
    read_seconds: float | None = None,
    as_landed: bool = False,
    cross_lane: bool = False,
    normalize_workers: int = 1,
) -> RunReport:
    """One lane, or one leg, end to end. Raises ExtractRefused, after logging, when either check fails.

    Whatever it raises carries the run's RunReport as `.report` where the
    exception takes one, so a caller can say how far the run got.
    `read_seconds` is a leg's read budget (read_each()); the lanes
    ignore it. `as_landed` also writes the as-landed copy (the module
    docstring). `cross_lane` also reads ALSO_READS' resources for this lane.
    """
    cadences_of(lane)
    if resources is None:
        resources = all_resources(discover() + discover_shared())
    plan_resources = lane_resources(lane, resources)
    if cross_lane:
        plan_resources += cross_lane_resources(lane, resources, plan_resources)
    checked_at = utc_now_naive()
    report = RunReport(run_id=checked_at.strftime("%Y%m%dT%H%M%S.%fZ"), lane=lane, outcome="loaded")
    try:
        _run(report, lane, bucket_url, plan_resources, pipelines_dir, checked_at, read_seconds, as_landed, normalize_workers)
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
    as_landed: bool = False,
    normalize_workers: int = 1,
) -> None:
    pipeline = make_pipeline(lane, bucket_url, pipelines_dir)
    # Drop a package a dead run left pending, then sync, so the committed
    # marker comes back. Kept, the next run reads the dead run's uncommitted
    # marker and answers FRESH for a change it never loaded, and the run log's
    # pipeline.run() commits the dead package with no `_extract_runs` row
    # (measured 2026-10-01, tests/test_extract_run.py's
    # test_a_load_that_dies_before_it_commits...). CI's runners start with no
    # working directory; a laptop or a cached runner may not.
    with timed(report, "sync"):
        if pipeline.has_pending_data:
            print(f"::warning title={lane} dropped an uncommitted load::a previous run died before its load committed")
            pipeline.abort_packages()
        pipeline.sync_destination()
        recorded = recorded_markers(pipeline)
        # Read once: every run log file is a read of its own, and nothing writes the log before the run's end.
        log = run_log_rows(pipeline)
        complete = committed_load_ids(pipeline)
        current = readable_tables(pipeline, log, complete)
        served = {(row["table_name"], row.get("load_id")): row for row in log}
        indexes: dict[str, dict] = {}

        def landed(load_id: str) -> dict[str, str]:
            return as_landed_index(_client(pipeline).fs_client, bucket_url, load_id, indexes)

        plan_resources = due(plan_resources, log, checked_at)
        # One listing of the store for every FRESH verdict's served-files check,
        # not one per table: each was a request to R2.
        listing = table_listing(pipeline, [resource.table for resource in plan_resources])
    planned, unavailable = [], []
    with timed(report, "change checks"):

        def ask(resource: Resource):
            # A MARKER COUNTS ONLY BESIDE ROWS A BUILD CAN READ. With no logged,
            # committed load (`current`) it is read as none: refresh-reference.yml's
            # monthly run 37070628933 committed with no `_extract_runs` row, and
            # 37081046157 then answered 53 resources FRESH whose rows no build
            # could see.
            stored = recorded.get(resource.name) if resource.table in current else None
            # A marker of another definition of the resource, or of none, is no marker (definition_digest()).
            definition = definition_digest(resource)
            if stored and stored.get(DEFINITION_KEY) == definition:
                before = {name: value for name, value in stored.items() if name != DEFINITION_KEY}
            else:
                before = None
            verdict, marker = resource.change_check(before)
            return stored, verdict, {**marker, DEFINITION_KEY: definition} if marker else None

        # The upstreams are asked one folder per thread (by_folder()), and
        # everything that touches the store or the report happens here, in order.
        budget = LEG_CHECK_SECONDS[LEGS[lane].job] if lane in LEGS else None
        for resource, outcome in zip(plan_resources, by_folder(plan_resources, ask, budget)):
            if isinstance(outcome, CheckTimedOut):
                # Refused on its own, as a read that ran out of time is (read_each()): its last
                # committed table stands, it is not read this run, and it is logged `refused`.
                report.isolated[resource.name] = f"change check: {outcome}"
                print(f"::error title={resource.name} refused::{report.isolated[resource.name]}; its last committed table stands")
                stored = recorded.get(resource.name) if resource.table in current else None
                planned.append(Planned(resource, Freshness.UNKNOWN, stored, None))
                report.verdicts[resource.name] = Freshness.UNKNOWN.value
                continue
            if isinstance(outcome, Unavailable):
                # An annotation, so the gap reaches the run summary rather than only the step log.
                print(f"::warning title={resource.name} is unavailable::{outcome}")
                unavailable.append(resource)
                report.unavailable[resource.name] = str(outcome)
                report.verdicts[resource.name] = UNAVAILABLE
                continue
            if isinstance(outcome, BaseException):
                raise outcome
            stored, verdict, marker = outcome
            if verdict is Freshness.FRESH:
                # A FRESH verdict is UNKNOWN when the served load cannot give a build what it needs.
                load_id = current.get(resource.table)
                row = served.get((resource.table, load_id), {})
                files = listing.get(resource.table, [])
                if gap := fresh_but_unserved(pipeline, resource, load_id, row, landed if as_landed else None, files=files):
                    print(f"  {resource.name}: fresh, but {gap}; reading it again")
                    verdict = Freshness.UNKNOWN
            planned.append(Planned(resource, verdict, stored, marker))
            report.verdicts[resource.name] = verdict.value
    to_run = [item for item in planned if item.verdict is not Freshness.FRESH and item.resource.name not in report.isolated]
    print(
        f"{lane}: {len(planned) + len(unavailable)} resources, {len(to_run)} to read, "
        f"{len(planned) - len(to_run)} fresh, {len(unavailable)} unavailable"
    )
    if lane in LEGS:
        to_run = take_on_new_tables(report, to_run, current, log, NEW_TABLES_PER_LEG_RUN[LEGS[lane].job])
    # A resource that reads only what moved (Resource.carries) is handed its
    # last committed rows and what an earlier incomplete read kept, and every
    # run log written below carries PROGRESS_TABLE forward: unchanged where the
    # run refused, dropped for a read that loaded, replaced for one that ran out.
    carrying = any(item.resource.carries for item in planned)
    kept = {}
    if carrying:
        kept = stored_progress(pipeline, complete)
        carried_for(pipeline, to_run, kept, log, complete)

    def progress(loaded: set[str] = frozenset()) -> dict[str, list[dict]] | None:
        return progress_after(kept, report, loaded) if carrying else None

    copy = AsLanded(Path(tempfile.mkdtemp(prefix="as_landed_"))) if as_landed and to_run else None
    # An isolating lane's rows wait on disk between the read and the load (Spool); a leg's are few, and held.
    spool = Path(tempfile.mkdtemp(prefix="read_")) if lane in ISOLATING_LANES and to_run else None
    try:
        _extract_and_load(
            pipeline,
            report,
            lane,
            planned,
            to_run,
            unavailable,
            checked_at,
            read_seconds,
            copy,
            progress,
            log,
            spool,
            normalize_workers,
        )
        # After the run log, so a failed upload leaves a committed, logged load
        # and a red job, and the next --as-landed run reads the layer again
        # (fresh_but_unserved()).
        if copy is not None and report.load_id is not None:
            report.as_landed = upload_as_landed(pipeline, bucket_url, report.load_id, copy)
    finally:
        if copy is not None:
            shutil.rmtree(copy.staging, ignore_errors=True)
        if spool is not None:
            shutil.rmtree(spool, ignore_errors=True)


def _extract_and_load(
    pipeline,
    report: RunReport,
    lane: str,
    planned: list[Planned],
    to_run: list[Planned],
    unavailable: list[Resource],
    checked_at: datetime,
    read_seconds: float | None,
    as_landed: AsLanded | None,
    progress: Callable[..., dict[str, list[dict]] | None] = lambda loaded=frozenset(): None,
    log: list[dict] | None = None,
    spool: Path | None = None,
    normalize_workers: int = 1,
) -> None:
    """run_pipeline's extract, checks, load and run log; ExtractRefused, after logging, when either check fails.

    `progress` is _run()'s: what PROGRESS_TABLE holds after this run, given
    the resources that loaded, which every run log written here carries.
    `spool` is where an isolating lane's rows wait (Spool), and
    `normalize_workers` dlt's normalize processes (MONTHLY_NORMALIZE_WORKERS)."""
    # A LEG, AND THE MONTHLY LANE, ISOLATE EACH UPSTREAM (isolates()), so one
    # club's failure does not hold back another club's closures, or its month.
    # Every resource is read first (read_each), and one whose read fails, runs
    # out of time or is refused by the run check or dlt's schema contract is
    # left out like a FRESH one: its last committed table stands, it is logged
    # `refused`, and the rest load (extracted again after a refusal). OurHike's
    # own rows are the exception (stops_the_leg). On the plain hourly lane one
    # refusal refuses the run.
    read = None
    if to_run and isolates(lane):
        readers = None if lane in LEGS else MONTHLY_READERS
        with timed(report, "read"):
            to_run, read = read_each(report, to_run, read_seconds, spool=spool, readers=readers)
    log = run_log_rows(pipeline) if log is None else log
    previous = last_loaded_counts(log) if to_run else {}
    while to_run:
        if as_landed is not None:
            as_landed.reset()  # a leg's second pass re-extracts what is left, and copies it again

        def resources(items=tuple(to_run)):
            return [
                to_dlt(
                    item.resource,
                    item.marker,
                    report.proofs,
                    checked_at,
                    report.hints,
                    None if read is None else read[item.resource.name],
                    carried=item.carried,
                    as_landed=as_landed,
                )
                for item in items
            ]

        try:
            with timed(report, "extract"):
                pipeline.extract(
                    dlt.source(resources, name=SOURCE_NAME)(), schema=store_schema(pipeline), loader_file_format="parquet"
                )
            if as_landed is not None:
                # What ran: a lane's every non-FRESH resource, a leg's less those read_each() left out.
                as_landed.close(to_run)
            with timed(report, "normalize"):
                pipeline.normalize(workers=normalize_workers)
        except PipelineStepFailed as failure:
            # On a leg, a table dlt's schema contract refuses is left out like one the run check refuses.
            breach = contract_breach(failure) if read is not None else None
            items = [item for item in to_run if breach is not None and item.resource.table == breach.table_name]
            if not items or any(stops_the_leg(item.resource) for item in items):
                raise
            pipeline.abort_packages()
            for item in items:
                report.isolated[item.resource.name] = f"schema contract: {breach}"
                print(f"::error title={item.resource.name} refused::schema contract; its last committed table stands")
            to_run = [item for item in to_run if item not in items]
            continue
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
                    write_run_log(pipeline, report, planned, checked_at, unavailable, progress())
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
                write_run_log(pipeline, report, planned, checked_at, unavailable, progress())
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
                write_run_log(pipeline, report, planned, checked_at, unavailable, progress())
            raise ExtractRefused("Extract after-run check:\n  " + "\n  ".join(report.problems), report)
    with timed(report, "run log"):
        written = write_run_log(
            pipeline, report, planned, checked_at, unavailable, progress({item.resource.name for item in to_run})
        )
    # The log as this run left it: what it read at the start, and the file it just wrote.
    report.run_log = log + _read_rows(pipeline, [path for load in written for path in table_files(pipeline, RUNS_TABLE, load)])


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


def summary_markdown(report: RunReport | None, lane: str, *, failure: BaseException | None = None) -> str:
    """The run's evidence as Markdown, for `$GITHUB_STEP_SUMMARY`: what each table loaded, and why a run stopped.

    One row per resource the run planned: its verdict, the rows it landed, and
    the upstream's own count read in the same run, blank where the platform
    has none and never written as 0. The rows read "kept" for a FRESH resource
    (its last committed table stands), "withdrawn" for an unavailable one, and
    say so for a refused or incomplete one. A run that stopped before
    normalize has no counts, so its rows are blank rather than zero.
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
    if report.incomplete:
        lines += ["**Read incomplete** (ran out of budget; nothing landed, and what it read is kept for the next run):", ""]
        lines += [*[f"- `{name}`: {why}" for name, why in sorted(report.incomplete.items())], ""]
    if report.waiting:
        lines += [f"**Waiting** ({len(report.waiting)} never-loaded tables this run did not take on; not yet loaded):", ""]
        lines += [", ".join(f"`{name}`" for name in sorted(report.waiting)), ""]
    if report.quiet:
        lines += ["**Refused, and reaching no hiker** (`reaches_hikers: false`, so the run's exit is not failed for them):", ""]
        lines += [", ".join(f"`{name}`" for name in sorted(report.quiet)), ""]
    normalized = "normalize" in report.timings and not (stopped and not report.rows)
    if report.verdicts:
        lines += ["| table | verdict | rows | upstream count |", "|---|---|---:|---:|"]
        for name, verdict in sorted(report.verdicts.items()):
            if name in report.isolated:
                rows = "refused, last table stands"
            elif name in report.incomplete:
                rows = "incomplete, nothing landed"
            elif name in report.waiting:
                rows = "waiting, not yet loaded"
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


def load_committed(
    lane: str,
    bucket_url: str,
    warehouse: Path,
    pipelines_dir: str | None = None,
    log: list[dict] | None = None,
    tables: set[str] | None = None,
) -> dict[str, int]:
    """Every table the lane's pipeline has committed, into `warehouse`'s raw schema. Returns {table: rows}.

    extract/_warehouse.py's committed-file read, which refuses a table whose
    recorded load left no file rather than loading it empty. `log` is the run
    log as a run just left it (RunReport.run_log), so it is not read again.
    `tables`, for a leg, is leg_tables(): the store's other tables stay out.
    Imported here rather than at the top, because that module imports this one."""
    import duckdb

    from extract._warehouse import LEG_READERS, load_warehouse

    warehouse.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(warehouse)) as con:
        readers = LEG_READERS if lane in LEGS else 1
        pipeline = make_pipeline(lane, bucket_url, pipelines_dir)
        return load_warehouse(con, pipeline, log=log, readers=readers, tables=tables)


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
        help="a leg's budget for reading its upstreams; one not read in time is refused on its own",
    )
    parser.add_argument(
        "--as-landed",
        action="store_true",
        help="also upload each ArcGIS, Socrata and opentrail layer as today's fetcher's file (the module docstring)",
    )
    parser.add_argument(
        "--cross-lane-inputs",
        action="store_true",
        help="also read the other lanes' resources this lane's dbt nodes read (ALSO_READS); never in fixture mode",
    )
    parser.add_argument(
        "--normalize-workers",
        type=int,
        default=1,
        help=f"dlt's normalize processes (refresh-reference.yml passes {MONTHLY_NORMALIZE_WORKERS}, MONTHLY_NORMALIZE_WORKERS)",
    )
    parser.add_argument(
        "--report-json", type=Path, help="write the run's id, outcome and counts here, refused or not (refresh-reference.yml)"
    )
    args = parser.parse_args(argv)
    if args.only and args.cross_lane_inputs:
        # Otherwise cross_lane_resources() would refuse ALSO_READS' tables,
        # which --only removed, by a name the command line never gave.
        parser.error("--only keeps only the tables it names, so it cannot also read --cross-lane-inputs' tables")
    bucket_url = args.bucket_url or raw_store_url(args.raw_bucket, args.lane)
    discovered = all_resources(discover() + discover_shared())
    resources = only_tables(discovered, args.only, args.lane) if args.only else discovered
    # A leg's warehouse holds its job's tables alone, whatever else its store kept (load_warehouse()'s `tables`).
    keep = leg_tables(args.lane, discovered) if args.lane in LEGS else None
    report = None
    try:
        try:
            report = run_pipeline(
                args.lane,
                bucket_url,
                resources=resources,
                pipelines_dir=args.pipelines_dir,
                read_seconds=args.read_seconds,
                as_landed=args.as_landed,
                cross_lane=args.cross_lane_inputs,
                normalize_workers=args.normalize_workers,
            )
        except ExtractRefused as refused:
            if args.report_json:
                args.report_json.write_text(
                    json.dumps({"lane": args.lane, "outcome": "refused", "problems": str(refused).splitlines()}, indent=2)
                )
            raise
        if args.report_json:
            # The extract's own run, written before --warehouse reads it back.
            args.report_json.write_text(json.dumps(report_document(report), indent=2, sort_keys=True, default=str))
        if args.warehouse is not None:
            with timed(report, "warehouse"):
                loaded = load_committed(args.lane, bucket_url, args.warehouse, args.pipelines_dir, report.run_log, keep)
            print(f"{len(loaded)} tables, {sum(loaded.values())} rows, into {args.warehouse}")
    except Exception as failure:
        if args.summary is not None:
            known = getattr(failure, "report", None) or report  # the warehouse step's refusal carries none
            with open(args.summary, "a", encoding="utf-8") as handle:
                handle.write(summary_markdown(known, args.lane, failure=failure))
        raise
    report.quiet = quiet_refusals(report, resources)
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
    if finished.quiet:
        print(f"{len(finished.quiet)} resource(s) reaching no hiker refused on their own (reaches_hikers false)")
    if exit_status(finished):
        print(f"{len(finished.isolated)} resource(s) refused on their own; the rest loaded", file=sys.stderr)
        sys.exit(PARTIAL_EXIT)
