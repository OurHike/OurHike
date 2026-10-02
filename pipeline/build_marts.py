"""build_marts: the dbt build in the order the Python steps need, from the seeds to the phone files.

    python build_marts.py --fixtures [--dbt dbt] [--python <interpreter>]
        [--warehouse data/warehouse.duckdb] [--processed-dir data/processed/dbt]
        [--raw-dir data/raw] [--threads N] [--dry-run]

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


def plan(steps: list[Step], *, dbt: str, python: str, paths: Paths, fixtures: bool, threads: int | None = None) -> list[Run]:
    """Every command of the build, in order, for these steps."""
    common = ("--profiles-dir", ".", *(("--threads", str(threads)) if threads else ()))
    fields = {"warehouse": str(paths.warehouse), "raw_dir": str(paths.raw_dir)}
    runs = [Run(SEED, (dbt, "seed", *common), DBT_DIR)]
    stage_a_exclude = ["package:dbt_project_evaluator", "path:models/publish"]
    if steps:
        stage_a_exclude.append(f"source:{DERIVED_SOURCE}+")
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
                ),
                DBT_DIR,
            )
        )
    runs.append(Run("the pub_ writers", (dbt, "build", *common, "-s", "path:models/publish"), DBT_DIR))
    return runs


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
    parser.add_argument("--dry-run", action="store_true", help="print the commands and run none")
    args = parser.parse_args(argv)

    paths = Paths(
        warehouse=_resolved(args.warehouse, "OURHIKE_WAREHOUSE", PIPELINE_DIR / "data" / "warehouse.duckdb"),
        processed_dir=_resolved(args.processed_dir, "OURHIKE_PROCESSED_DIR", PIPELINE_DIR / "data" / "processed" / "dbt"),
        raw_dir=args.raw_dir.resolve(),
    )
    runs = plan(STEPS, dbt=args.dbt, python=args.python, paths=paths, fixtures=args.fixtures, threads=args.threads)
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
            if problems := derived_source_problems(manifest, STEPS):
                for problem in problems:
                    print(f"-- build_marts: {problem}", flush=True)
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
