"""build_marts: the dbt build in the order the Python steps need, from the seeds to the phone files.

    python build_marts.py --fixtures [--dbt dbt] [--python <interpreter>]
        [--warehouse data/warehouse.duckdb] [--processed-dir data/processed/dbt]
        [--raw-dir data/raw] [--threads N] [--dry-run]
    python build_marts.py --lane monthly ...                 # refresh-reference.yml
    python build_marts.py --lane hourly [--state <dir>] ...  # the hourly conditions lane

The one home of the build order (pipeline/ELT.md, "Python steps, outside dbt"
and "Running it"). CI's dbt job and scripts/test.sh call it with --fixtures.

WHY MORE THAN ONE `dbt build`. A rule that has to stay Python runs as a step
between dbt invocations: it reads a named intermediate and writes
`derived.<table>`, which dbt reads back as a source (models/staging/derived/).
A single `dbt build` cannot do that: it reaches the first stg_derived__ model
before any step has written its table, and fails. So:

1. `dbt seed`;
2. stage A, everything that is not downstream of a `derived` source - the
   steps' inputs among it - except the evaluator package, which CI runs on its
   own at severity error, and the pub_ writers;
3. for each entry of STEPS, in order: the step, then
   `dbt build -s source:derived.<its table>+`, which is what that table
   unblocks. Anything also downstream of a later step's table waits for that
   step, so each invocation excludes the later tables' descendants;
4. the pub_ writers, `dbt build -s path:models/publish`, LAST: `dbt build`
   tests each model after building it, so a writer built beside its parents
   would write its file before a failing test upstream stopped it
   (pipeline/ELT.md, "Publish (reverse ETL)").

Contracts are enforced by the models' own config in every invocation;
nothing here turns them off. `dbt deps` is not here: CI and scripts/test.sh
run it before `dbt parse` and `dbt lint`, which need the packages first, and
a sandbox whose proxy cannot fetch them skips it (scripts/test.sh
--no-dbt-deps).

A LANE BUILDS ONLY ITS OWN NODES (--lane; pipeline/ELT.md, "Every node
carries its cadence": "each node is built only by the lane equal to its
effective cadence"). A node's effective cadence is the fastest `meta.cadence`
among the sources it reads, and dbt's own graph selection gives it:
`config.meta.cadence:hourly+` is every node an hourly source reaches.
- `monthly` (refresh-reference.yml) is the build above with every node an
  hourly or daily source reaches excluded from each invocation, the writers'
  included. Its warehouse holds only the monthly lane's raw tables, so those
  nodes would fail on a missing source rather than build, and a monthly
  build that did build them would store month-old closures (ELT.md's probe,
  measured on dbt-oss 2.0.5). A source with no `meta.cadence` is built here:
  excluding is what the lane does, so an untagged source lands where today's
  build puts it rather than nowhere.
- `hourly` is the seeds, then every node an hourly or daily source reaches,
  then those nodes' writers, and no Python step: a step's table is the
  monthly lane's. Whatever an hourly node reads from the monthly lane comes
  from the warehouse it builds into (the restored monthly one) or, with
  --state, through `--defer --state`.
- Both refuse, after `dbt seed` writes the manifest, a STEPS entry that reads
  a node an hourly or daily source reaches: the monthly lane would leave that
  input unbuilt, and the hourly lane would rebuild it under a step that only
  runs monthly. What a step reads is its `step_<name>` exposure's
  `depends_on` (models/intermediate/*/_*__intermediate.yml).
With no --lane, every node builds, as CI's fixture build needs: the fixture
warehouse holds both lanes' tables.

dbt's `selectors.yml` (ELT.md's shape) is not the home: each invocation here
already carries its own `-s`/`--exclude`, and dbt documents `--selector` as
not combinable with either, so a selector file would need one selector per
invocation per lane. A lane is one more `--exclude` on each invocation
instead, and LANE_EXCLUDES is the one home. That 2.0.6 keeps dbt's rule is
@unvalidated: the one probe (2026-10-02) named an undefined selector beside
`--exclude`, and dbt crashed rather than answering.

A NEW STEP IS ONE ENTRY IN STEPS, plus its script: its name, the derived
table it writes, its command, and the arguments --fixtures adds to point it
at the fixture inputs make_dbt_fixtures.py wrote. The command's `{warehouse}`
and `{raw_dir}` are filled in from the arguments here. Nothing in CI or
scripts/test.sh changes for one.

THE DERIVED SOURCES AND STEPS AGREE, or nothing past the seeds runs. A
`derived` table no step writes would leave everything downstream of it
unbuilt without one failing node, so after `dbt seed` this reads the
manifest it wrote (target/manifest.json) and refuses either mismatch.

WHICH PROGRAM RUNS WHAT. --dbt is the dbt executable (default `dbt`, from
PATH); --python is the interpreter the steps run on (default this one).
They differ in CI, where dbt is in the job's own requirements-dbt.txt venv
and the steps need requirements.txt's rasterio, in $RUNNER_TEMP/pipeline.
This file imports nothing beyond the standard library, so it runs on either.

WHERE THE FILES ARE. dbt's profile reads the warehouse from OURHIKE_WAREHOUSE
and dbt_project.yml's processed_dir from OURHIKE_PROCESSED_DIR. This passes
both to every dbt command, as absolute paths, so dbt and the steps always
read one warehouse: --warehouse and --processed-dir set them, else those
variables as the caller set them, else the profile's own defaults.
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


#: The Python steps, in the order they run (pipeline/ELT.md, "Python steps,
#: outside dbt", has the four planned and why each stays Python).
STEPS: list[Step] = [
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
    lane: str | None = None,
    state: Path | None = None,
) -> list[Run]:
    """Every command of the build, in order, for these steps, in `lane` (None: every node)."""
    if lane not in (None, *LANES):
        raise ValueError(f"no lane {lane!r}; lanes are {', '.join(LANES)}")
    if state is not None and lane != HOURLY:
        raise ValueError("--state is the hourly lane's: only it defers to another build's nodes")
    common = ("--profiles-dir", ".", *(("--threads", str(threads)) if threads else ()))
    runs = [Run(SEED, (dbt, "seed", *common), DBT_DIR)]
    if lane == HOURLY:
        defer = ("--defer", "--state", str(state)) if state is not None else ()
        hourly = ("-s", *LANE_EXCLUDES, "--exclude", "package:dbt_project_evaluator", "path:models/publish")
        runs.append(
            Run(
                "the hourly lane: every node an hourly or daily source reaches", (dbt, "build", *common, *hourly, *defer), DBT_DIR
            )
        )
        writers = tuple(f"path:models/publish,{selector}" for selector in LANE_EXCLUDES)
        runs.append(Run("the hourly lane's pub_ writers", (dbt, "build", *common, "-s", *writers, *defer), DBT_DIR))
        return runs
    lane_exclude = LANE_EXCLUDES if lane == MONTHLY else ()
    fields = {"warehouse": str(paths.warehouse), "raw_dir": str(paths.raw_dir)}
    stage_a_exclude = ["package:dbt_project_evaluator", "path:models/publish"]
    if steps:
        stage_a_exclude.append(f"source:{DERIVED_SOURCE}+")
    stage_a_exclude += lane_exclude
    runs.append(
        Run("stage A: everything no Python step reads back", (dbt, "build", *common, "--exclude", *stage_a_exclude), DBT_DIR)
    )
    for position, step in enumerate(steps):
        arguments = step.command + (step.fixture_args if fixtures else ())
        runs.append(Run(step.name, (python, *(argument.format(**fields) for argument in arguments)), PIPELINE_DIR))
        later = [f"source:{DERIVED_SOURCE}.{after.table}+" for after in steps[position + 1 :]]
        runs.append(
            Run(
                f"what {DERIVED_SOURCE}.{step.table} unblocks",
                (
                    dbt,
                    "build",
                    *common,
                    "-s",
                    f"source:{DERIVED_SOURCE}.{step.table}+",
                    "--exclude",
                    "path:models/publish",
                    *later,
                    *lane_exclude,
                ),
                DBT_DIR,
            )
        )
    writers = ("-s", "path:models/publish", *(("--exclude", *lane_exclude) if lane_exclude else ()))
    runs.append(Run("the pub_ writers", (dbt, "build", *common, *writers), DBT_DIR))
    return runs


def _cadence(source: dict) -> str | None:
    return ((source.get("config") or {}).get("meta") or {}).get("cadence") or (source.get("meta") or {}).get("cadence")


def faster_nodes(manifest: dict) -> set[str]:
    """Every node a faster-than-monthly source reaches, followed down the manifest's child_map as dbt's `+` follows it."""
    queue = [uid for uid, source in (manifest.get("sources") or {}).items() if _cadence(source) in FASTER_THAN_MONTHLY]
    children = manifest.get("child_map") or {}
    reached: set[str] = set()
    while queue:
        node = queue.pop()
        if node in reached:
            continue
        reached.add(node)
        queue.extend(children.get(node) or [])
    return reached


def lane_problems(manifest: dict, steps: list[Step], lane: str | None) -> list[str]:
    """What stops a lane's build: a step with no exposure naming its inputs, or a step reading a faster-than-monthly node."""
    if lane is None:
        return []
    exposures = {exposure.get("name"): exposure for exposure in (manifest.get("exposures") or {}).values()}
    reached = faster_nodes(manifest)
    problems = []
    for step in steps:
        exposure = exposures.get(step.name)
        if exposure is None:
            problems.append(
                f"{step.name} has no exposure named {step.name} listing what it reads, so the {lane} lane cannot "
                "check that it builds the step's inputs"
            )
            continue
        for node in (exposure.get("depends_on") or {}).get("nodes") or []:
            if node in reached:
                problems.append(
                    f"{step.name} reads {node}, which an hourly or daily source reaches: the monthly lane does not "
                    "build it, and the hourly lane runs no step, so the step's answer would go stale under it"
                )
    return problems


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
    parser.add_argument("--lane", choices=LANES, help="build only that lane's nodes (default: every node, as CI's fixtures need)")
    parser.add_argument("--state", type=Path, help="the hourly lane only: defer to the build whose target/ this is")
    parser.add_argument("--dry-run", action="store_true", help="print the commands and run none")
    args = parser.parse_args(argv)

    paths = Paths(
        warehouse=_resolved(args.warehouse, "OURHIKE_WAREHOUSE", PIPELINE_DIR / "data" / "warehouse.duckdb"),
        processed_dir=_resolved(args.processed_dir, "OURHIKE_PROCESSED_DIR", PIPELINE_DIR / "data" / "processed" / "dbt"),
        raw_dir=args.raw_dir.resolve(),
    )
    if args.state is not None and args.lane != HOURLY:
        parser.error("--state is the hourly lane's: only it defers to another build's nodes")
    runs = plan(
        STEPS,
        dbt=args.dbt,
        python=args.python,
        paths=paths,
        fixtures=args.fixtures,
        threads=args.threads,
        lane=args.lane,
        state=args.state.resolve() if args.state else None,
    )
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
