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
selector beside `--exclude`, and dbt crashed rather than answering.

A NEW STEP IS ONE STEPS ENTRY plus its script; nothing in CI or
scripts/test.sh changes. After `dbt seed`, derived_source_problems() refuses
a `derived` table no step writes, which would leave everything downstream of
it unbuilt without one failing node, and a step writing a table no source
declares.

--dbt and --python differ in CI, where dbt is in the job's
requirements-dbt.txt venv and the steps need requirements.txt's rasterio
($RUNNER_TEMP/pipeline); this file imports only the standard library, so it
runs on either. Every dbt command gets OURHIKE_WAREHOUSE and
OURHIKE_PROCESSED_DIR as absolute paths, so dbt and the steps read one
warehouse.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
DBT_DIR = PIPELINE_DIR / "dbt"
DERIVED_SOURCE = "derived"
# The first run, after which the manifest it wrote is checked against STEPS.
SEED = "dbt seed"
MANIFEST_PATH = DBT_DIR / "target" / "manifest.json"

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
    pipeline/; `fixture_args` are added under --fixtures. Both may hold
    `{warehouse}` and `{raw_dir}`."""

    name: str
    table: str
    command: tuple[str, ...]
    fixture_args: tuple[str, ...] = ()
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
    # answers make_dbt_fixtures.py wrote, never the network.
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
    ),
    # PO03: OSM's water points, a stand-in for the extract that waits on
    # #1652. Under --fixtures it lands make_dbt_fixtures.py's points; otherwise
    # it lands none (step_osm_water.py's docstring says why).
    Step(
        name="step_osm_water",
        table="osm_water",
        command=("step_osm_water.py", "--warehouse", "{warehouse}"),
        fixture_args=("--points", "{raw_dir}/osm_water/points.geojson"),
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


@dataclass(frozen=True)
class Run:
    """One command of the build: what the log calls it, its argv, and the directory it runs in."""

    label: str
    argv: tuple[str, ...]
    cwd: Path


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
) -> list[Run]:
    """Every command of the build, in order, for these steps, in `lane` (None: every node), less the steps `without` names."""
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
    stage_a_exclude += [*held, *lane_exclude]
    label = "stage A: everything no Python step reads back"
    if lane == HOURLY:
        label = "stage A of the hourly lane: every node an hourly or daily source reaches, no step reads back"
    runs.append(Run(label, (dbt, "build", *common, *selection, "--exclude", *stage_a_exclude, *after), DBT_DIR))
    for position, step in enumerate(running):
        arguments = step.command + (step.fixture_args if fixtures else ())
        runs.append(Run(step.name, (python, *(argument.format(**fields) for argument in arguments)), PIPELINE_DIR))
        later = [f"source:{DERIVED_SOURCE}.{following.table}+" for following in running[position + 1 :]]
        unblocks = ("-s", f"source:{DERIVED_SOURCE}.{step.table}+", "--exclude", "path:models/publish", *later, *held)
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
    runs.append(Run(label, (dbt, "build", *common, *writers, *after), DBT_DIR))
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
    parser.add_argument("--dry-run", action="store_true", help="print the commands and run none")
    args = parser.parse_args(argv)

    paths = Paths(
        warehouse=_resolved(args.warehouse, "OURHIKE_WAREHOUSE", PIPELINE_DIR / "data" / "warehouse.duckdb"),
        processed_dir=_resolved(args.processed_dir, "OURHIKE_PROCESSED_DIR", PIPELINE_DIR / "data" / "processed" / "dbt"),
        raw_dir=args.raw_dir.resolve(),
    )
    if args.state is not None and args.lane != HOURLY:
        parser.error("--state is the hourly lane's: only it defers to another build's nodes")
    try:
        runs = plan(
            STEPS,
            dbt=args.dbt,
            python=args.python,
            paths=paths,
            fixtures=args.fixtures,
            threads=args.threads,
            profiles_dir=str(args.profiles_dir.resolve()) if args.profiles_dir else ".",
            lane=args.lane,
            state=args.state.resolve() if args.state else None,
            without=tuple(args.without_step),
        )
    except ValueError as refused:
        parser.error(str(refused))
    files = {"OURHIKE_WAREHOUSE": str(paths.warehouse), "OURHIKE_PROCESSED_DIR": str(paths.processed_dir)}
    env = {**os.environ, **files}
    print("-- build_marts: " + " ".join(f"{name}={value}" for name, value in files.items()), flush=True)
    if args.dry_run:
        for run in runs:
            print(f"{run.label}: (cd {run.cwd} && {' '.join(run.argv)})")
        return 0

    # COPY creates no directory (phone_file.sql), and the writers write here.
    paths.processed_dir.mkdir(parents=True, exist_ok=True)
    for position, run in enumerate(runs, start=1):
        print(f"-- build_marts {position}/{len(runs)}: {run.label}", flush=True)
        completed = subprocess.run(run.argv, cwd=run.cwd, env=env, check=False)
        if completed.returncode != 0:
            print(f"-- build_marts: {run.label} failed (exit {completed.returncode}): {' '.join(run.argv)}", flush=True)
            return completed.returncode
        if run.label == SEED:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            if problems := derived_source_problems(manifest, STEPS) + lane_problems(manifest, STEPS, args.lane):
                for problem in problems:
                    print(f"-- build_marts: {problem}", flush=True)
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
