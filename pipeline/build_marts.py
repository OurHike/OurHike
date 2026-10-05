"""build_marts: the dbt build in the order the Python steps need, from the seeds to the phone files.

    python build_marts.py --fixtures [--dbt dbt] [--python <interpreter>]
        [--warehouse data/warehouse.duckdb] [--processed-dir data/processed/dbt]
        [--raw-dir data/raw] [--threads N] [--dry-run]
    python build_marts.py --lane monthly ...                 # refresh-reference.yml
    python build_marts.py --lane hourly [--state <dir>] ...  # the hourly conditions lane

The one home of the build order (pipeline/ELT.md, "Python steps, outside dbt"
and "Running it"). CI's dbt job and scripts/test.sh call it with --fixtures.

WHY MORE THAN ONE `dbt build`. A rule that stays Python runs as a step between
dbt invocations: it reads a named intermediate and writes `derived.<table>`,
which dbt reads back as a source (models/staging/derived/). A single
`dbt build` would reach the first stg_derived__ model before any step had
written its table, and fail. So:

1. `dbt seed`;
2. stage A: everything not downstream of a `derived` source, except the pub_
   writers and the evaluator package (CI runs it on its own, at severity
   error);
3. for each STEPS entry, in order: the step, then
   `dbt build -s source:derived.<its table>+`, less what a later step's table
   also feeds, which waits for that step;
4. the pub_ writers LAST (`-s path:models/publish`): `dbt build` tests each
   model after building it, so a writer built beside its parents would write
   its file before a failing test upstream could stop it (ELT.md, "Publish
   (reverse ETL)").

Contracts stay enforced in every invocation. `dbt deps` is not here: CI and
scripts/test.sh run it first, and a sandbox whose proxy cannot fetch the
packages skips it (scripts/test.sh --no-dbt-deps).

A LANE BUILDS ONLY ITS OWN NODES (--lane; ELT.md, "Every node carries its
cadence"). A node's cadence is the fastest `meta.cadence` among the sources
it reads, so `config.meta.cadence:hourly+` selects every node an hourly
source reaches.
- `monthly` (refresh-reference.yml) excludes every node an hourly or daily
  source reaches, writers included: its warehouse holds only the monthly raw
  tables, so those nodes would fail on a missing source or, if built, store
  month-old closures (ELT.md's probe, measured on dbt-oss 2.0.5). A source
  with no `meta.cadence` is built here, so an untagged source lands where
  today's build puts it rather than nowhere.
- `hourly` builds the seeds, every node an hourly or daily source reaches,
  the hourly steps and what they unblock, then those nodes' writers. What
  they read from the monthly lane comes through `--defer --state`; without
  --state the build also takes every parent of those nodes (LANE_PARENTS),
  so the warehouse must hold the monthly raw tables they read (the registry,
  today).
- Each STEPS entry runs in its `lane`. After `dbt seed`, lane_problems()
  refuses a step with no `step_<name>` exposure listing its inputs
  (models/intermediate/*/_*__intermediate.yml) unless it `reads_no_model`, a
  monthly step reading a node an hourly or daily source reaches, and a step
  whose table feeds only the other lane's writers.
- --without-step NAME leaves a step out with everything its table unblocks,
  so those writers keep their last files (publish.py's `kept`): for an input
  a run does not have, such as the weather squares the hourly production leg
  lacks (publish-conditions.yml).
With no --lane every step and node builds, as CI's fixture warehouse, which
holds both lanes' tables, needs.

NOT dbt's `selectors.yml` (ELT.md's shape): dbt documents `--selector` as not
combinable with `-s` or `--exclude`, which every invocation here carries, so a
selector file would need one selector per invocation per lane. A lane is one
more `--exclude` on each, and LANE_EXCLUDES is its one home. That 2.0.6 keeps
dbt's rule is @unvalidated: the one probe (2026-10-02) named an undefined
selector beside `--exclude`, and dbt crashed rather than answering. A probe
with a defined selector beside `--exclude` would settle it.

A NEW STEP IS ONE STEPS ENTRY plus its script; nothing in CI or
scripts/test.sh changes. After `dbt seed`, derived_source_problems() refuses
a `derived` table no step writes, which would leave everything downstream of
it unbuilt without one failing node, and a step writing a table no source
declares.

THE ROW HISTORY IS RESTORED FIRST AND SAVED LAST. The row-history snapshots
(int_<mart>__history, one per mart, decision 57; macros/row_history.sql) are
the only state a build carries from one run to the next, and the warehouse is
rebuilt from raw every
run, so `row_history.py restore` runs before `dbt seed` and `row_history.py
save` after the writers, only when every command before it succeeded. The
store is --history-url, else OURHIKE_HISTORY_URL. A store with no history
yet is a cold start, and cold starts are allowed only:
- under --fixtures with no store named, into a new temporary directory, so
  CI and scripts/test.sh start history in every run and keep none;
- for a store whose name (its URL's last part, `monthly` for
  s3://<bucket>/history/monthly) row_history_stores.toml does not list as
  started: its first run, said in a warning;
- with --history-cold-start, by hand.
Anything else with no history fails before dbt runs, because a silent cold
start would date every row as first seen in this build. Without --fixtures a
store must be named: there is no default that keeps history. The restore and
the save run on --history-python (default: this interpreter), which needs
DuckDB, and s3fs for an s3:// store: the extract's venv in a workflow.
Every dbt command runs with TZ=UTC, so a TIMESTAMPTZ column is hashed in the
same characters on every machine (macros/row_hash.sql), and with
OURHIKE_BUILT_BY, the git commit and workflow run, which each snapshot
version records as `_built_by` (never hashed), so a reader can tell a change
upstream from a change to this project's rules.

--no-history-save restores the history and builds with it, and saves
nothing back: for a build that knows some of its inputs are missing, so that
a row's absence is never recorded as its removal. publish-conditions.yml
passes it when the notices legs' served copy was not the newest
(extract/_warehouse.py, "THE SERVED COPY"), because the closures and
warnings marts then lack, or hold older, notices; saved, the history would
close those rows and reopen them an hour later with a new `_changed_at`.
What it costs is the date of a row that did change: it is dated by the next
build that saves (Reasoned).

--history-on-failure degrade IS THE CONDITIONS LEGS' (the maintainer, by poll,
2026-10-03): closures and warnings must still publish when their history
cannot be restored. Then the restore's failure is printed as an error, every
dbt command runs with OURHIKE_ROW_HISTORY=off and leaves the snapshots out,
so the marts read their final intermediates with both dates null (unknown,
never "new"), nothing is saved, and the build exits DEGRADED_EXIT once
everything else has passed, so the workflow publishes and then goes red. A
command that fails with that code itself is answered with 1, so the workflow
never reads a failed build as a publishable one. The
default, `fail`, is the monthly lane's: a restore that fails stops the build
before dbt runs.

ONE SOURCE OR ONE WRITER NEVER STOPS THE REST (decision 81, the maintainer's
poll of 2026-10-05: "Hold that source and publish the rest"; review finding
ARCH-1 of PR #1805 — dlt → dbt re-platform as one go/no-go change). Five of
the hourly soak's first ten runs published nothing because of one source:
runs 525 to 527 and 530 on a test of one source's rows, run 531 on one
writer's SQL after six other writers had written. Three things now answer
PARTIAL_EXIT instead, once everything else has run, so the workflow publishes
what was written and then turns the run red:
- a test whose `meta` sets `holds_a_source` warned: it names rows that
  int_closures__gate holds their source for (a club's wording in a published
  column, a row outside its region box), and its rows are printed as a failed
  test's are;
- a model of one generated club notice source failed in stage A (a SQL error
  on one source's rows): that source's raw tables are dropped from the
  warehouse and stage A runs once more, so the gate holds the source as "not
  in this warehouse" and it carries its last good rows. Any other failure in
  stage A stops the build, as before;
- some pub_ writers failed and every failure in that dbt run is a writer's
  own (its model, or a test or unit test of it): each failed writer's file is
  removed from the processed directory, so a half-written or untested file
  is never there to publish, and its key keeps the bucket's last copy. The
  log says which files were written. publish.py, told so by
  OURHIKE_BUILD_PARTIAL, keeps a failed writer's key rather than refusing
  the whole publish.
The row history is still saved: the marts passed their tests, and a source
held this way carries its rows rather than losing them (Reasoned).

--dbt and --python differ in CI, where dbt is in the job's
requirements-dbt.txt venv and the steps need requirements.txt's rasterio
($RUNNER_TEMP/pipeline); this file imports only the standard library, so it
runs on either. Every dbt command gets OURHIKE_WAREHOUSE and
OURHIKE_PROCESSED_DIR as absolute paths, so dbt and the steps read one
warehouse.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import tomllib

PIPELINE_DIR = Path(__file__).resolve().parent
DBT_DIR = PIPELINE_DIR / "dbt"
DERIVED_SOURCE = "derived"
# The first run, after which the manifest it wrote is checked against STEPS.
SEED = "dbt seed"
MANIFEST_PATH = DBT_DIR / "target" / "manifest.json"
#: What the dbt run that just ended did, node by node: read for its failed tests, its warnings and its failed writers.
RUN_RESULTS_PATH = DBT_DIR / "target" / "run_results.json"

#: The scheduled lanes (the module docstring, "A LANE BUILDS ONLY ITS OWN NODES").
MONTHLY, HOURLY = "monthly", "hourly"
LANES = (MONTHLY, HOURLY)
#: The cadences faster than monthly. Daily rides the hourly lane when due
#: (extract/_run.py's DUE_AFTER), so its nodes are the hourly lane's too.
FASTER_THAN_MONTHLY = ("hourly", "daily")
#: Every node a faster-than-monthly source reaches, as dbt selects it. Measured
#: 2026-10-02 on dbt 2.0.6 against this project (`dbt ls --resource-type
#: model`): of 247 models, 22 are reached by an hourly source and 9 by a daily
#: one, which leaves 224 to the monthly lane; of the 29 writers, 4 are the
#: hourly lane's.
LANE_EXCLUDES = tuple(f"config.meta.cadence:{cadence}+" for cadence in FASTER_THAN_MONTHLY)
#: The hourly lane's other half when it has no --state to defer to: every
#: parent of a node whose own cadence is hourly or daily (the hourly exposures
#: among them), so the monthly nodes the closures and warnings marts read
#: (int_sources__publication, the registry staging, two seeds) are built in
#: the same warehouse. Selected under `--indirect-selection cautious`: with the
#: default (eager), the relationships tests on points_of_interest,
#: suggested_hikes and int_trail_lines__coded_domains come along and fail on
#: tables an hourly warehouse does not hold. Both measured 2026-10-02 on dbt
#: 2.0.6 against the fixture warehouse: `dbt ls -s +config.meta.cadence:hourly
#: --indirect-selection cautious` selected 30 models and seeds, 11 sources and
#: the 4 pub_conditions_* writers.
LANE_PARENTS = tuple(f"+config.meta.cadence:{cadence}" for cadence in FASTER_THAN_MONTHLY)


@dataclass(frozen=True)
class Step:
    """A Python step: its name, the `derived.<table>` it writes, and how it runs.

    `command` is the script and its arguments, run with --python from
    pipeline/; `fixture_args` are added under --fixtures, and a lane's
    `lane_args` under --lane without --fixtures, where a scheduled build
    reads an input from somewhere a fixture build does not. All may hold
    `{warehouse}` and `{raw_dir}`."""

    name: str
    table: str
    command: tuple[str, ...]
    fixture_args: tuple[str, ...] = ()
    lane_args: tuple[tuple[str, tuple[str, ...]], ...] = ()
    # The lane that runs it under --lane: the lane of the nodes its table
    # unblocks, which lane_problems() holds it to. Without --lane every step runs.
    lane: str = MONTHLY
    # True for a step that reads no dbt node, only a file (step_weather_squares
    # lands squares.json whole): it then needs no step_<name> exposure, and
    # lane_problems() has no input of its to check.
    reads_no_model: bool = False


#: The Python steps, in the order they run (pipeline/ELT.md, "Python steps,
#: outside dbt", has the four planned and why each stays Python).
STEPS: list[Step] = [
    # THE POI STEPS COME FIRST: every table they write reaches the trail_lines
    # mart (points_of_interest -> int_trail_lines__spur_destinations -> the
    # spurs -> int_trail_lines__at_published -> trail_lines), which
    # step_node_lines' int_trail_network__routable and step_dem_sampling's
    # sample points both read.
    # PO36 (a row of pipeline/ELT.md's ledger, as is each code below): NYNJTC's
    # Long Path guide placed as waypoints, from the guide_pages sections and the
    # Long Path layer's lines, both staged; under --fixtures,
    # extract/_fixtures.py serves the pages. Before the water steps, because its
    # records join int_points_of_interest__unioned, upstream of OSM water's
    # distance pass.
    Step(
        name="step_long_path_guide",
        table="long_path_guide",
        command=("step_long_path_guide.py", "--warehouse", "{warehouse}"),
    ),
    # PO07 and PO17: which A.T. shelters and campsites have water a hiker can
    # walk to, fetch_trail_water.py's rule over int_points_of_interest__water_sites.
    # Under --fixtures it reads each site's candidate reaches and the EPQS
    # answers make_dbt_fixtures.py wrote, never the network. The monthly lane
    # lands the site water refresh-reference.yml's build job derived from the
    # Geofabrik extracts the raw store keeps (fetch_trail_water.py --derive,
    # #1652), pinned with the build's raw inputs, or the last landed one.
    Step(
        name="step_site_water",
        table="site_water",
        command=("step_site_water.py", "--warehouse", "{warehouse}"),
        fixture_args=(
            "--candidates",
            "{raw_dir}/site_water/candidates.json",
            "--elevations",
            "{raw_dir}/site_water/epqs_elevations.json",
        ),
        lane_args=((MONTHLY, ("--from-file", "{raw_dir}/derived/trail_water.json")),),
    ),
    # PO03: OSM's water points. Under --fixtures it lands make_dbt_fixtures.py's
    # points; the monthly lane lands the build job's scan of the Geofabrik
    # extracts (fetch_osm_water.py, #1652), pinned with its raw inputs, or the
    # last landed one, and warns when none has ever landed (step_osm_water.py's
    # docstring says how).
    Step(
        name="step_osm_water",
        table="osm_water",
        command=("step_osm_water.py", "--warehouse", "{warehouse}"),
        fixture_args=("--points", "{raw_dir}/osm_water/points.geojson"),
        lane_args=((MONTHLY, ("--landed", "{raw_dir}/derived/osm_water.geojson")),),
        reads_no_model=True,
    ),
    # PO06 and PO07: the grade half of OSM water's reach, over
    # int_points_of_interest__osm_water_reach's distance pass. Under --fixtures
    # it reads the EPQS answers make_dbt_fixtures.py wrote, never the network.
    Step(
        name="step_osm_water_grade",
        table="osm_water_grade",
        command=("step_osm_water_grade.py", "--warehouse", "{warehouse}"),
        fixture_args=("--elevations", "{raw_dir}/osm_water/epqs_elevations.json"),
    ),
    # PO24 and PO38: the photo manifests export_poi.py attaches, a stand-in for
    # the Commons extract kind. Under --fixtures it lands make_dbt_fixtures.py's
    # outcome files and decisions; otherwise the files export_poi.py reads.
    Step(
        name="step_poi_photos",
        table="poi_photos",
        command=("step_poi_photos.py", "--warehouse", "{warehouse}"),
        fixture_args=(
            "--commons",
            "{raw_dir}/poi_photos/poi_images.json",
            "--atc",
            "{raw_dir}/poi_photos/poi_images_atc.json",
            "--decisions",
            "{raw_dir}/poi_photos/photo_screen_decisions.json",
        ),
        reads_no_model=True,
    ),
    # TN04: every routable trail part cut where int_trail_network__cuts says,
    # by build_trail_graph.py's own _split_all, from warehouse inputs alone (so
    # no fixture_args). Before step_dem_sampling, whose input
    # int_elevation__dem_points is downstream of this step's graph_pieces
    # (through int_trail_network__edges and int_elevation__edge_sample_points).
    Step(
        name="step_node_lines",
        table="graph_pieces",
        command=("step_node_lines.py", "--warehouse", "{warehouse}"),
    ),
    # EL06: the DEM's elevation at every int_elevation__sample_points row.
    # Under --fixtures it reads the tile index and synthetic GeoTIFF
    # make_dbt_fixtures.py wrote; otherwise fetch_elevation.py's index, the
    # step's own default.
    Step(
        name="step_dem_sampling",
        table="dem_samples",
        command=("step_dem_sampling.py", "--warehouse", "{warehouse}"),
        fixture_args=("--index", "{raw_dir}/elevation/tile_index.json"),
    ),
    # WN03: the NBM weather squares build_weather_squares.py chose, which the
    # NWS alerts' placement reads. Under --fixtures it reads the squares.json
    # make_dbt_fixtures.py wrote; otherwise the weather job's own file.
    Step(
        name="step_weather_squares",
        table="weather_squares",
        command=("step_weather_squares.py", "--warehouse", "{warehouse}"),
        fixture_args=("--squares", "{raw_dir}/weather/squares.json"),
        lane=HOURLY,
        reads_no_model=True,
    ),
    # SH03, SH06: each Hike Finder hike's route formed from its description,
    # or its published track re-walked, over the junction graph. Last of the
    # steps, because it reads the graph's edges and their climb, which the
    # graph's own step and the network elevation will write ahead of it.
    Step(
        name="step_form_route",
        table="formed_routes",
        command=("step_form_route.py", "--warehouse", "{warehouse}"),
    ),
]


@dataclass(frozen=True)
class Paths:
    warehouse: Path
    processed_dir: Path
    raw_dir: Path


#: The history stores that have been saved to at least once, by name (the store URL's last part), each with the
#: run that started it: an empty one of these is lost history, never a first run (the module docstring, "THE ROW
#: HISTORY IS RESTORED FIRST AND SAVED LAST").
HISTORY_STORES = PIPELINE_DIR / "row_history_stores.toml"
RESTORE_LABEL, SAVE_LABEL = "restore the row history", "save the row history"
#: What --history-on-failure degrade leaves out of every dbt build once the restore has failed: the snapshots,
#: which would otherwise start a history this run cannot keep and the marts must not read.
SNAPSHOTS = "resource_type:snapshot"
#: build_marts.py's exit when a degraded build passed: the marts and their writers are built, with null dates,
#: and nothing was saved. Not 0, so the workflow goes red once it has published; not 1, so it can tell.
DEGRADED_EXIT = 4
HISTORY_ON_FAILURE = ("fail", "degrade")
#: build_marts.py's exit when the build finished with part of it held back (the module docstring, "ONE SOURCE OR ONE
#: WRITER NEVER STOPS THE REST"): every file written may publish, and the workflow goes red once it has. Not 0 and not
#: 1 for DEGRADED_EXIT's reason; and DEGRADED_PARTIAL_EXIT when the build was degraded too, so the workflow can say both.
PARTIAL_EXIT = 5
DEGRADED_PARTIAL_EXIT = 6
#: The exits that mean "built, publish what was written": a dbt command or step that answers one of them itself is
#: answered with 1, so the workflow never reads a failed build as a publishable one.
PUBLISHABLE_EXITS = (DEGRADED_EXIT, PARTIAL_EXIT, DEGRADED_PARTIAL_EXIT)
#: How much older than the writers' run a file may look and still count as written by it: publish.py's
#: WRITER_CLOCK_SLACK_S, for the same filesystems, @unvalidated there.
WRITER_CLOCK_SLACK_S = 2.0
#: The `meta` key of a test whose warning means int_closures__gate held a source for the rows it returns.
HOLDS_A_SOURCE = "holds_a_source"
#: The readers seed: which raw tables are each club notice source's, and which of them are generated.
NOTICE_READERS = DBT_DIR / "seeds" / "notice_readers.csv"


@dataclass(frozen=True)
class History:
    """Where the row-history snapshots are kept between runs, whether an empty store may start them, and the
    interpreter row_history.py runs on."""

    url: str
    cold_start: bool
    python: str


def resolve_history(
    url: str | None, *, fixtures: bool, cold_start: bool, python: str, started: dict[str, str]
) -> tuple[History, str | None]:
    """The store this build restores from and saves to, and a line to print about it.

    Raises ValueError when no store is named outside --fixtures."""
    if not url:
        if not fixtures:
            raise ValueError(
                "no row-history store: pass --history-url or set OURHIKE_HISTORY_URL. Without one every snapshot "
                "would start its history again in a warehouse this run throws away (pipeline/row_history.py)."
            )
        url = tempfile.mkdtemp(prefix="ourhike-history-")
        return History(url, True, python), (
            f"--fixtures with no history store named: a cold start in {url}, a new temporary directory no later run reads"
        )
    if cold_start:
        return History(url, True, python), f"--history-cold-start: an empty {url} starts its history in this build"
    name = history_store_name(url)
    if name not in started:
        return History(url, True, python), (
            f"::warning title=Row history store not started::{name} is not in row_history_stores.toml, so an empty "
            f"{url} starts its history in this build. Once this run has saved, list {name} there, so that from then "
            "on an empty store is refused as lost history."
        )
    return History(url, False, python), None


def built_by(environ: dict[str, str]) -> str:
    """What each snapshot version records as `_built_by`: OURHIKE_BUILT_BY when set, else the commit (GITHUB_SHA,
    else `git rev-parse HEAD`) and, in a workflow, `run <GITHUB_RUN_ID>.<GITHUB_RUN_ATTEMPT>`. Only characters a SQL
    string literal takes as they are (macros/row_history.sql writes it into one)."""
    value = environ.get("OURHIKE_BUILT_BY")
    if not value:
        commit = environ.get("GITHUB_SHA")
        if not commit:
            found = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PIPELINE_DIR, capture_output=True, text=True, check=False)
            commit = found.stdout.strip() if found.returncode == 0 else "unknown"
        value = commit[:12]
        if run_id := environ.get("GITHUB_RUN_ID"):
            value += f" run {run_id}.{environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    return "".join(character for character in value if character.isalnum() or character in " .:/_-")


def history_store_name(url: str) -> str:
    """A store's name in row_history_stores.toml: the last part of its URL."""
    return url.rstrip("/").rsplit("/", 1)[-1]


def started_history_stores(path: Path = HISTORY_STORES) -> dict[str, str]:
    return tomllib.loads(path.read_text(encoding="utf-8"))["started"]


@dataclass(frozen=True)
class Run:
    """One command of the build: what the log calls it, its argv, the directory it runs in, and which of the two dbt
    runs main() answers a failure of differently it is (STAGE_A or WRITERS; the module docstring, "ONE SOURCE OR ONE
    WRITER NEVER STOPS THE REST")."""

    label: str
    argv: tuple[str, ...]
    cwd: Path
    stage: str = ""


#: Run.stage of stage A, and of the pub_ writers' dbt run.
STAGE_A, WRITERS = "stage_a", "writers"


def plan(
    steps: list[Step],
    *,
    dbt: str,
    python: str,
    paths: Paths,
    fixtures: bool,
    threads: int | None = None,
    profiles_dir: str = ".",
    lane: str | None = None,
    state: Path | None = None,
    without: tuple[str, ...] = (),
    history: History | None = None,
    snapshots: bool = True,
    save_history: bool = True,
) -> list[Run]:
    """Every command of the build, in order, for these steps, in `lane` (None: every node), less the steps `without` names,
    between the row history's restore and its save when `history` names a store (the save left out when
    `save_history` is false: --no-history-save), and with no snapshot built when `snapshots` is false (the module
    docstring, "--history-on-failure degrade")."""
    if lane not in (None, *LANES):
        raise ValueError(f"no lane {lane!r}; lanes are {', '.join(LANES)}")
    if state is not None and lane != HOURLY:
        raise ValueError("--state is the hourly lane's: only it defers to another build's nodes")
    if unknown := sorted(set(without) - {step.name for step in steps}):
        raise ValueError(f"--without-step names no entry of STEPS: {', '.join(unknown)}")
    common = ("--profiles-dir", profiles_dir, *(("--threads", str(threads)) if threads else ()))
    fields = {"warehouse": str(paths.warehouse), "raw_dir": str(paths.raw_dir)}
    running = [step for step in steps if step.name not in without and (lane is None or step.lane == lane)]
    # What a step that does not run here would have unblocked: built by no
    # invocation of this build, so its writer keeps its last file.
    held = tuple(f"source:{DERIVED_SOURCE}.{step.table}+" for step in steps if step not in running)
    selection: tuple[str, ...] = ()
    lane_exclude: tuple[str, ...] = ()
    after: tuple[str, ...] = ()  # options every dbt build of the lane carries after its --exclude
    if lane == MONTHLY:
        lane_exclude = LANE_EXCLUDES
    elif lane == HOURLY:
        selection = ("-s", *LANE_EXCLUDES, *(LANE_PARENTS if state is None else ()))
        after = ("--defer", "--state", str(state)) if state is not None else ("--indirect-selection", "cautious")

    runs = [Run(SEED, (dbt, "seed", *common), DBT_DIR)]
    stage_a_exclude = ["package:dbt_project_evaluator", "path:models/publish"]
    if running:
        stage_a_exclude.append(f"source:{DERIVED_SOURCE}+")
    no_snapshots = () if snapshots else (SNAPSHOTS,)
    stage_a_exclude += [*held, *lane_exclude, *no_snapshots]
    label = "stage A: everything no Python step reads back"
    if lane == HOURLY:
        label = "stage A of the hourly lane: every node an hourly or daily source reaches, no step reads back"
    runs.append(Run(label, (dbt, "build", *common, *selection, "--exclude", *stage_a_exclude, *after), DBT_DIR, STAGE_A))
    for position, step in enumerate(running):
        arguments = step.command + (step.fixture_args if fixtures else dict(step.lane_args).get(lane, ()))
        runs.append(Run(step.name, (python, *(argument.format(**fields) for argument in arguments)), PIPELINE_DIR))
        later = [f"source:{DERIVED_SOURCE}.{following.table}+" for following in running[position + 1 :]]
        unblocks = ("-s", f"source:{DERIVED_SOURCE}.{step.table}+", "--exclude", "path:models/publish", *later, *held)
        unblocks += no_snapshots
        runs.append(
            Run(
                f"what {DERIVED_SOURCE}.{step.table} unblocks", (dbt, "build", *common, *unblocks, *lane_exclude, *after), DBT_DIR
            )
        )
    if lane == HOURLY:
        writers = ("-s", *(f"path:models/publish,{selector}" for selector in LANE_EXCLUDES))
        label = "the hourly lane's pub_ writers"
    else:
        writers = ("-s", "path:models/publish")
        label = "the pub_ writers"
    if held or lane_exclude:
        writers += ("--exclude", *lane_exclude, *held)
    runs.append(Run(label, (dbt, "build", *common, *writers, *after), DBT_DIR, WRITERS))
    if history is not None:
        store = ("--url", history.url, "--warehouse", str(paths.warehouse))
        restore = (history.python, "row_history.py", "restore", *store, *(("--cold-start",) if history.cold_start else ()))
        runs.insert(0, Run(RESTORE_LABEL, restore, PIPELINE_DIR))
        if save_history:
            runs.append(Run(SAVE_LABEL, (history.python, "row_history.py", "save", *store), PIPELINE_DIR))
    return runs


def _cadence(source: dict) -> str | None:
    return ((source.get("config") or {}).get("meta") or {}).get("cadence") or (source.get("meta") or {}).get("cadence")


def _reached(manifest: dict, starts: list[str]) -> set[str]:
    """`starts` and every node below them in the manifest's child_map, as dbt's `+` follows it."""
    children = manifest.get("child_map") or {}
    reached: set[str] = set()
    queue = list(starts)
    while queue:
        node = queue.pop()
        if node in reached:
            continue
        reached.add(node)
        queue.extend(children.get(node) or [])
    return reached


def faster_nodes(manifest: dict) -> set[str]:
    """Every node a faster-than-monthly source reaches."""
    sources = manifest.get("sources") or {}
    return _reached(manifest, [uid for uid, source in sources.items() if _cadence(source) in FASTER_THAN_MONTHLY])


def lane_problems(manifest: dict, steps: list[Step], lane: str | None) -> list[str]:
    """What stops a lane's build: a step with no exposure naming its inputs, a monthly step reading a node an
    hourly or daily source reaches, or a step whose lane is not the lane of what its table unblocks."""
    if lane is None:
        return []
    exposures = {exposure.get("name"): exposure for exposure in (manifest.get("exposures") or {}).values()}
    derived = {
        source.get("name"): uid
        for uid, source in (manifest.get("sources") or {}).items()
        if source.get("source_name") == DERIVED_SOURCE
    }
    reached = faster_nodes(manifest)
    problems = []
    for step in steps:
        exposure = exposures.get(step.name)
        if step.reads_no_model:
            if exposure is not None and (exposure.get("depends_on") or {}).get("nodes"):
                problems.append(
                    f"{step.name} says it reads no dbt node (reads_no_model), and its exposure {step.name} lists some"
                )
        elif exposure is None:
            problems.append(
                f"{step.name} has no exposure named {step.name} listing what it reads, so the {lane} lane cannot "
                "check that it builds the step's inputs"
            )
        elif step.lane == MONTHLY:
            for node in (exposure.get("depends_on") or {}).get("nodes") or []:
                if node in reached:
                    problems.append(
                        f"{step.name} reads {node}, which an hourly or daily source reaches: the monthly lane, where "
                        "the step runs, does not build it, so the step would read a stale or missing input"
                    )
        # A step's lane is the lane of the phone files its table ends in: the
        # models between (its own staging, say) are reached by no source with a
        # cadence, and are built by whichever lane runs the step.
        unblocked = _reached(manifest, [derived[step.table]] if step.table in derived else [])
        writers = sorted(node for node in unblocked if _is_writer(node))
        if step.lane == MONTHLY and writers and all(node in reached for node in writers):
            problems.append(
                f"{step.name} runs in the monthly lane, and every writer derived.{step.table} feeds is the hourly "
                f"lane's ({', '.join(writers)}): give its STEPS entry lane=HOURLY"
            )
        if step.lane == HOURLY and (monthly := [node for node in writers if node not in reached]):
            problems.append(
                f"{step.name} runs in the hourly lane, and derived.{step.table} feeds monthly-lane writers "
                f"({', '.join(monthly)}), which no hourly or daily source reaches: the monthly lane leaves out what an "
                "hourly step unblocks, so nothing would write them"
            )
    return problems


def _is_writer(node: str) -> bool:
    """A pub_ writer's unique id, `model.<project>.pub_<file>` (models/publish/; the evaluator holds the prefix)."""
    parts = node.split(".")
    return len(parts) >= 3 and parts[0] == "model" and parts[2].startswith("pub_")


#: How much of a failed test's answer the log shows: rows, and characters a value. Enough to name the source and the
#: row; little enough that a wording test's failure does not copy a club's paragraph into a public log.
FAILED_ROWS_SHOWN = 10
FAILED_VALUE_WIDTH = 120


def _rows_query(result: dict, manifest: dict) -> str:
    """The SQL whose rows show why `result`'s test failed: its compiled SQL, or for dbt_utils' expression_is_true,
    which selects a constant, the rows of the model the test is attached to where the expression does not hold."""
    node = manifest.get("nodes", {}).get(result["unique_id"], {})
    meta = node.get("test_metadata") or {}
    attached = manifest.get("nodes", {}).get(node.get("attached_node") or "", {})
    if meta.get("name") == "expression_is_true" and attached.get("relation_name"):
        where = (node.get("config") or {}).get("where")
        condition = f"not ({meta['kwargs']['expression']})" + (f" and ({where})" if where else "")
        return f"select * from {attached['relation_name']} where {condition}"
    return (result.get("compiled_code") or "").strip().rstrip(";")


def failed_test_rows(
    warehouse: Path,
    since: float,
    results_path: Path | None = None,
    manifest_path: Path | None = None,
    *,
    statuses: tuple[str, ...] = ("fail", "error"),
    only: set[str] | None = None,
) -> list[str]:
    """What each test that failed or errored in the dbt run that just ended returned, as log lines (`statuses` to ask
    for others, such as the warnings of the tests that hold a source; `only` to ask for these unique ids alone).

    dbt 2.0.6 prints a failed test's name and row count and nothing of the rows, and no artifact keeps the
    warehouse, so a failure on data only a live run holds (soak run 525, publish-conditions.yml 37216623795: three
    tests on the first real club notices) could not be read. Each failed test's compiled SQL is asked again, read-only,
    for FAILED_ROWS_SHOWN rows, every value cut at FAILED_VALUE_WIDTH characters (_rows_query(): for
    expression_is_true, the attached model's own failing rows, since soak run 526 printed its constant). `since` is when
    the run started:
    run_results.json older than that is an earlier stage's, and says nothing about this failure."""
    path = results_path or RUN_RESULTS_PATH
    try:
        if path.stat().st_mtime < since:
            return []
        results = json.loads(path.read_text(encoding="utf-8"))["results"]
    except (OSError, ValueError, KeyError):
        return []
    failed = [
        result
        for result in results
        if result.get("unique_id", "").startswith("test.")
        and result.get("status") in statuses
        and (only is None or result.get("unique_id") in only)
    ]
    if not failed:
        return []
    import duckdb

    try:
        manifest = json.loads((manifest_path or MANIFEST_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    lines = []
    with duckdb.connect() as con:
        try:
            con.execute("load spatial")
        except duckdb.Error:
            pass  # a test that needs it says so below
        con.execute(f"attach '{warehouse}' as warehouse (read_only)")
        con.execute("use warehouse")
        for result in failed:
            lines.append(f"::group::{result['unique_id']}: {result.get('failures')} row(s), {result.get('status')}")
            code = _rows_query(result, manifest)
            try:
                if not code:
                    raise ValueError("run_results.json holds no compiled SQL for it")
                cursor = con.execute(f"select * from ({code}) limit {FAILED_ROWS_SHOWN}")
                names = [column[0] for column in cursor.description]
                for row in cursor.fetchall():
                    shown = {name: None if value is None else str(value)[:FAILED_VALUE_WIDTH] for name, value in zip(names, row)}
                    lines.append(json.dumps(shown, ensure_ascii=False))
            except (duckdb.Error, ValueError) as failure:
                lines.append(f"(not asked again: {failure})")
            lines.append("::endgroup::")
    return lines


def read_run_results(since: float, results_path: Path | None = None) -> list[dict] | None:
    """The results of the dbt run that started at `since`, or None when run_results.json is missing, unreadable or an
    earlier run's."""
    path = results_path or RUN_RESULTS_PATH
    try:
        if path.stat().st_mtime < since:
            return None
        return json.loads(path.read_text(encoding="utf-8"))["results"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _node(manifest: dict, unique_id: str) -> dict:
    return (manifest.get("nodes") or {}).get(unique_id) or (manifest.get("unit_tests") or {}).get(unique_id) or {}


def source_holds(results: list[dict], manifest: dict) -> set[str]:
    """The tests that warned in this run and whose `meta` says a warning holds a source (HOLDS_A_SOURCE)."""
    held = set()
    for result in results:
        if result.get("status") != "warn":
            continue
        node = _node(manifest, result.get("unique_id", ""))
        meta = {**(node.get("meta") or {}), **((node.get("config") or {}).get("meta") or {})}
        if meta.get(HOLDS_A_SOURCE):
            held.add(result["unique_id"])
    return held


#: A dbt result that is a failure: a model or snapshot that errored, a test that failed or errored, and a node dbt
#: skipped because something it needs failed.
FAILED_STATUSES = ("error", "fail", "skipped", "runtime error")


def _depends_on(manifest: dict, unique_id: str) -> list[str]:
    node = _node(manifest, unique_id)
    return list((node.get("depends_on") or {}).get("nodes") or []) + (
        [node["attached_node"]] if node.get("attached_node") else []
    )


def failed_writers(results: list[dict], manifest: dict) -> tuple[dict[str, str], list[str]]:
    """The pub_ writers this dbt run failed, each with why, and every other failure in it.

    A writer fails when its own model did not succeed, or when a test or unit test of it failed: dbt builds a model
    before its tests, so a writer whose not_null test failed has already written its file."""
    models: dict[str, str] = {}
    tests: dict[str, str] = {}
    others: list[str] = []
    for result in results:
        unique_id = result.get("unique_id", "")
        status = result.get("status")
        if status not in FAILED_STATUSES:
            continue
        if _is_writer(unique_id):
            models[unique_id] = f"its model finished {status}"
            continue
        tested = [node for node in _depends_on(manifest, unique_id) if _is_writer(node)]
        if tested and unique_id.split(".", 1)[0] in ("test", "unit_test"):
            # A test skipped because its writer failed says nothing the writer's own result does not.
            if status != "skipped":
                for writer in tested:
                    tests.setdefault(writer, f"{unique_id} finished {status}")
            continue
        others.append(unique_id)
    # A failed unit test says more than the writer dbt then skipped; a writer's own error, more than nothing.
    return {**models, **tests}, others


def writer_files(manifest: dict, writers: set[str] | list[str], processed_dir: Path) -> dict[str, Path]:
    """Each writer's file in the processed directory, by its `location` (macros/materializations/phone_file.sql)."""
    files = {}
    for writer in writers:
        location = (_node(manifest, writer).get("config") or {}).get("location")
        if location:
            files[writer] = processed_dir / location
    return files


def notice_readers(path: Path | None = None) -> list[dict[str, str]]:
    with (path or NOTICE_READERS).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _ancestor_sources(manifest: dict, unique_id: str) -> set[str]:
    """Every source node above `unique_id`, by the manifest's parent_map (else each node's depends_on)."""
    parents = manifest.get("parent_map")
    seen: set[str] = set()
    sources: set[str] = set()
    queue = [unique_id]
    while queue:
        node = queue.pop()
        if node in seen:
            continue
        seen.add(node)
        if node.startswith("source."):
            sources.add(node)
            continue
        queue.extend((parents.get(node) or []) if parents is not None else _depends_on(manifest, node))
    return sources


def one_sources_failures(results: list[dict], manifest: dict, readers: list[dict[str, str]]) -> dict[str, list[str]] | None:
    """The generated club notice sources whose own models errored in this dbt run, each with its raw tables, or None
    unless every failure in it is that (the module docstring, "ONE SOURCE OR ONE WRITER NEVER STOPS THE REST").

    A model is one source's own when the only club notice raw tables above it are that one source's, and the source
    is generated (seeds/notice_readers.csv's `staged_by` is a model, never `hand`): its base and staging models read
    an absent table as typed and empty (macros/notices.sql's notice_raw_table), and the gate holds the source with
    that reason. A union of several sources, a hand-staged source's model, any failed test or unit test, and anything
    else is not one source's own, so the build stops on it as before. Skipped nodes are what a failure left unbuilt
    and say nothing of their own."""
    by_table = {row["raw_table"]: row for row in readers}
    tables_of: dict[str, list[str]] = {}
    for row in readers:
        tables_of.setdefault(row["source_key"], []).append(row["raw_table"])
    hand = {row["source_key"] for row in readers if row["staged_by"] == "hand"}
    sources = manifest.get("sources") or {}
    held: dict[str, list[str]] = {}
    for result in results:
        unique_id = result.get("unique_id", "")
        status = result.get("status")
        if status not in FAILED_STATUSES or status == "skipped":
            continue
        if not unique_id.startswith("model.") or status != "error":
            return None
        keys = set()
        for source in _ancestor_sources(manifest, unique_id):
            node = sources.get(source) or {}
            for name in (node.get("identifier"), node.get("name")):
                if name in by_table:
                    keys.add(by_table[name]["source_key"])
        if len(keys) != 1 or keys & hand:
            return None
        (key,) = keys
        held[key] = sorted(set(tables_of[key]))
    return held or None


def drop_raw_tables(warehouse: Path, tables: list[str], schema: str = "raw") -> list[str]:
    """Drop each of `tables` the warehouse holds in `schema`, a table or a view, and return the ones it held."""
    import duckdb

    dropped = []
    with duckdb.connect(str(warehouse)) as con:
        for table in tables:
            found = con.execute(
                "select table_type from information_schema.tables where table_schema = ? and table_name = ?", [schema, table]
            ).fetchone()
            if found is None:
                continue
            kind = "view" if found[0] == "VIEW" else "table"
            con.execute(f'drop {kind} "{schema}"."{table}"')
            dropped.append(table)
    return dropped


def _read_manifest() -> dict:
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _report_writers(results: list[dict], manifest: dict, failed: dict[str, str], processed_dir: Path, since: float) -> str:
    """Remove each failed writer's file and say which files the others wrote: the lines publish-conditions.yml's log
    keeps, and the summary for the build's last line.

    A failed writer's file is removed whatever its age, so nothing it half-wrote, and nothing a test of it refused,
    can be published; its key then keeps the bucket's last copy (publish.py's `kept`)."""
    for writer, path in sorted(writer_files(manifest, failed, processed_dir).items()):
        removed = path.exists()
        path.unlink(missing_ok=True)
        print(
            f"::error title={writer.rsplit('.', 1)[-1]} failed::{failed[writer]}, so {path.name} "
            f"{'is removed' if removed else 'was not written'} and its key keeps the bucket's last copy. Every other "
            "writer's file still publishes, and the run goes red afterwards.",
            flush=True,
        )
    succeeded = [
        result["unique_id"]
        for result in results
        if _is_writer(result.get("unique_id", "")) and result.get("status") == "success" and result["unique_id"] not in failed
    ]
    wrote = sorted(
        path.name
        for path in writer_files(manifest, succeeded, processed_dir).values()
        if path.exists() and path.stat().st_mtime >= since - WRITER_CLOCK_SLACK_S
    )
    print(f"-- build_marts: wrote {len(wrote)} file(s): {', '.join(wrote) or 'none'}", flush=True)
    return f"{len(failed)} writer(s) failed: {', '.join(sorted(name.rsplit('.', 1)[-1] for name in failed))}"


def derived_source_problems(manifest: dict, steps: list[Step]) -> list[str]:
    """What stops the build: a derived table no step writes, or a step writing a table no source declares."""
    declared = {
        source["name"] for source in (manifest.get("sources") or {}).values() if source.get("source_name") == DERIVED_SOURCE
    }
    written = [step.table for step in steps]
    problems = [
        f"source {DERIVED_SOURCE}.{table} is declared and no entry of build_marts.STEPS writes it, so nothing "
        "downstream of it would be built"
        for table in sorted(declared - set(written))
    ]
    problems += [
        f"{step.name} writes {DERIVED_SOURCE}.{step.table}, which no source declares, so dbt would never read it"
        for step in steps
        if step.table not in declared
    ]
    problems += [
        f"{DERIVED_SOURCE}.{table} is written by more than one step"
        for table in sorted({t for t in written if written.count(t) > 1})
    ]
    return problems


def _resolved(value: Path | str | None, variable: str, default: Path) -> Path:
    """An argument, else the variable dbt's own files read, else the default; relative to the directory dbt reads it from."""
    if value is not None:
        return Path(value).resolve()
    if os.environ.get(variable):
        return (DBT_DIR / os.environ[variable]).resolve()
    return default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--fixtures", action="store_true", help="point every step at make_dbt_fixtures.py's inputs")
    parser.add_argument("--dbt", default="dbt", help="the dbt executable (default: dbt, from PATH)")
    parser.add_argument("--python", default=sys.executable, help="the interpreter the Python steps run on")
    parser.add_argument("--warehouse", type=Path, help="default: OURHIKE_WAREHOUSE, else data/warehouse.duckdb")
    parser.add_argument("--processed-dir", type=Path, help="default: OURHIKE_PROCESSED_DIR, else data/processed/dbt")
    parser.add_argument("--raw-dir", type=Path, default=PIPELINE_DIR / "data" / "raw", help="the fixtures' directory")
    parser.add_argument("--threads", type=int, help="passed to every dbt seed and build")
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        help="default: pipeline/dbt, whose profiles.yml CI uses; another one can cap DuckDB's memory on a shared machine",
    )
    parser.add_argument("--lane", choices=LANES, help="build only that lane's nodes (default: every node, as CI's fixtures need)")
    parser.add_argument("--state", type=Path, help="the hourly lane only: defer to the build whose target/ this is")
    parser.add_argument(
        "--without-step",
        action="append",
        default=[],
        metavar="NAME",
        help="leave this STEPS entry out, and everything its derived table unblocks, writers included (repeatable)",
    )
    parser.add_argument(
        "--history-url",
        default=os.environ.get("OURHIKE_HISTORY_URL"),
        help="the row-history store, a directory or s3:// URL (default: OURHIKE_HISTORY_URL; none: --fixtures only)",
    )
    parser.add_argument(
        "--history-cold-start", action="store_true", help="let an empty history store start its history in this build"
    )
    parser.add_argument(
        "--history-python",
        default=sys.executable,
        help="the interpreter row_history.py runs on: DuckDB, and s3fs for an s3:// store (default: this one)",
    )
    parser.add_argument(
        "--history-on-failure",
        choices=HISTORY_ON_FAILURE,
        default="fail",
        help="degrade: a failed restore builds and publishes with null row dates and exits DEGRADED_EXIT (conditions legs)",
    )
    parser.add_argument(
        "--no-history-save",
        action="store_true",
        help="restore the row history and build with it, but save nothing back: some of this build's inputs are missing",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the commands and run none")
    args = parser.parse_args(argv)

    paths = Paths(
        warehouse=_resolved(args.warehouse, "OURHIKE_WAREHOUSE", PIPELINE_DIR / "data" / "warehouse.duckdb"),
        processed_dir=_resolved(args.processed_dir, "OURHIKE_PROCESSED_DIR", PIPELINE_DIR / "data" / "processed" / "dbt"),
        raw_dir=args.raw_dir.resolve(),
    )
    try:
        history, notice = resolve_history(
            args.history_url,
            fixtures=args.fixtures,
            cold_start=args.history_cold_start,
            python=args.history_python,
            started=started_history_stores(),
        )
        options = {
            "dbt": args.dbt,
            "python": args.python,
            "paths": paths,
            "fixtures": args.fixtures,
            "threads": args.threads,
            "profiles_dir": str(args.profiles_dir.resolve()) if args.profiles_dir else ".",
            "lane": args.lane,
            "state": args.state.resolve() if args.state else None,
            "without": tuple(args.without_step),
        }
        runs = plan(STEPS, **options, history=history, save_history=not args.no_history_save)
    except ValueError as refused:
        parser.error(str(refused))
    files = {"OURHIKE_WAREHOUSE": str(paths.warehouse), "OURHIKE_PROCESSED_DIR": str(paths.processed_dir)}
    # TZ=UTC and OURHIKE_BUILT_BY: the module docstring, "THE ROW HISTORY IS RESTORED FIRST AND SAVED LAST".
    env = {**os.environ, **files, "TZ": "UTC", "OURHIKE_BUILT_BY": built_by(os.environ)}
    print("-- build_marts: " + " ".join(f"{name}={value}" for name, value in files.items()), flush=True)
    print(f"-- build_marts: OURHIKE_BUILT_BY={env['OURHIKE_BUILT_BY']}", flush=True)
    if notice:
        print(f"-- build_marts: {notice}", flush=True)
    if args.no_history_save:
        print(
            "::warning title=Row history not saved::--no-history-save: this build restores the row history and saves "
            "nothing back, so a row missing from its inputs is never recorded as removed. A row that changed is dated "
            "by the next build that saves.",
            flush=True,
        )
    if args.dry_run:
        for run in runs:
            print(f"{run.label}: (cd {run.cwd} && {' '.join(run.argv)})")
        return 0

    # COPY creates no directory (phone_file.sql), and the writers write here.
    paths.processed_dir.mkdir(parents=True, exist_ok=True)
    degraded = False
    # What this build held back and still finished, for PARTIAL_EXIT (the module docstring, "ONE SOURCE OR ONE WRITER
    # NEVER STOPS THE REST").
    partial: list[str] = []
    stage_a_rerun = False
    position = 0
    while position < len(runs):
        run = runs[position]
        position += 1
        print(f"-- build_marts {position}/{len(runs)}: {run.label}", flush=True)
        started = time.time()
        completed = subprocess.run(run.argv, cwd=run.cwd, env=env, check=False)
        if completed.returncode != 0 and run.stage in (STAGE_A, WRITERS) and completed.returncode not in PUBLISHABLE_EXITS:
            print(f"-- build_marts: {run.label} failed (exit {completed.returncode}): {' '.join(run.argv)}", flush=True)
            for line in failed_test_rows(paths.warehouse, started):
                print(line, flush=True)
            results, manifest = read_run_results(started), _read_manifest()
            if results is not None and run.stage == STAGE_A and not stage_a_rerun:
                if held := one_sources_failures(results, manifest, notice_readers()):
                    for key, tables in sorted(held.items()):
                        dropped = drop_raw_tables(paths.warehouse, tables)
                        print(
                            f"::error title={key} held for a failed model::a model of {key} alone failed in {run.label}, "
                            f"so its raw tables ({', '.join(dropped) or 'none held'}) are dropped from this build's "
                            "warehouse and int_closures__gate holds it as not in this warehouse: it carries its last good "
                            "rows, every other source still publishes, and the run goes red afterwards.",
                            flush=True,
                        )
                    partial.append(f"{', '.join(sorted(held))} held for a failed model")
                    stage_a_rerun = True
                    position -= 1  # stage A once more, with those tables gone
                    continue
            if results is not None and run.stage == WRITERS:
                writers, others = failed_writers(results, manifest)
                if writers and not others:
                    partial.append(_report_writers(results, manifest, writers, paths.processed_dir, started))
                    continue
            return completed.returncode
        if completed.returncode == 0 and run.argv[1:2] == ("build",) and run.cwd == DBT_DIR:
            results = read_run_results(started)
            if results is not None and (holds := source_holds(results, _read_manifest())):
                for line in failed_test_rows(paths.warehouse, started, statuses=("warn",), only=holds):
                    print(line, flush=True)
                for test in sorted(holds):
                    print(
                        f"::error title=A source held for its rows::{test} warned: int_closures__gate holds the source "
                        "of each row it names, which carries its last good rows while every other source publishes. "
                        "The run goes red afterwards.",
                        flush=True,
                    )
                partial.append(f"{len(holds)} test(s) holding a source")
        if completed.returncode != 0 and run.label == RESTORE_LABEL and args.history_on_failure == "degrade":
            # The module docstring, "--history-on-failure degrade": build and publish with null dates, save nothing.
            print(
                f"::error title=Row history not restored::{run.label} failed (exit {completed.returncode}); this leg "
                "builds and publishes with _first_seen_at and _changed_at null, saves no history, and goes red "
                "afterwards. Fix the store before the next run.",
                flush=True,
            )
            degraded = True
            env["OURHIKE_ROW_HISTORY"] = "off"
            runs = runs[:position] + plan(STEPS, **options, snapshots=False)
            continue
        if completed.returncode != 0:
            print(f"-- build_marts: {run.label} failed (exit {completed.returncode}): {' '.join(run.argv)}", flush=True)
            for line in failed_test_rows(paths.warehouse, started):
                print(line, flush=True)
            # PUBLISHABLE_EXITS mean built-and-publishable to publish-conditions.yml, so a command's own 4 is a 1.
            return 1 if completed.returncode in PUBLISHABLE_EXITS else completed.returncode
        if run.label == SEED:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            if problems := derived_source_problems(manifest, STEPS) + lane_problems(manifest, STEPS, args.lane):
                for problem in problems:
                    print(f"-- build_marts: {problem}", flush=True)
                return 1
    if partial:
        print(f"-- build_marts: built with part of it held back ({'; '.join(partial)})", flush=True)
    if degraded:
        code = DEGRADED_PARTIAL_EXIT if partial else DEGRADED_EXIT
        print(f"-- build_marts: built without the row history; exit {code}", flush=True)
        return code
    if partial:
        print(f"-- build_marts: exit {PARTIAL_EXIT}: publish what was written, then go red", flush=True)
        return PARTIAL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
