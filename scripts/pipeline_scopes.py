#!/usr/bin/env python3
"""Which publishing workflows a set of changed files stales (#1123).

THE FAILURE THIS EXISTS TO CATCH is a pull request changing what a pipeline
produces, merging green, and the published data quietly no longer matching
`main` - because rerunning `publish-vector-data.yml` (or the basemap or DEM
build) was nobody's job at the moment the session that knew about it ended.
The suites already have this answer: scripts/test.sh reads each suite's scope
out of its own workflow YAML. The publishes had nothing equivalent, and their
scope is harder to eyeball - export_spurs.py imports from export_poi.py, so a
change to the latter stales a workflow that never names it.

HOW A SCOPE IS DERIVED, never hand-kept (the same one-home argument as
scripts/suite_scopes.py - a hand copy is exactly the half that goes stale):

1. A workflow is a *publishing path* iff one of its steps' `run:` scripts
   invokes `publish.py` with a Python interpreter, or dispatches a workflow
   that does (below). Nine files on 2026-10-08: publish-weather.yml was the
   sixth (2026-09-25), refresh-reference.yml the seventh, and since the
   maintainer's choice B split the monthly lane (2026-10-08) it publishes
   through build-reference.yml, the eighth; check-conditions.yml, decision
   110's hourly checks, the ninth, which `publish.py --sidecar` makes one
   and publish-conditions.yml dispatches after each build, so a change to
   what the checks run stales both and the bake's schedule reruns both. The
   next joins this report by existing rather than by being remembered.
   Only the invocation counts, not a mention (#1552): matching the file's
   whole text counted `nynjtc-archive-recovery.yml` and
   `propose-atc-updates.yml`, whose comments explain why they do NOT publish,
   and handed out dispatch advice for inputs neither workflow has.
   test_pipeline_scopes.py pins the roster exactly, so the next
   misclassification fails a test instead of reaching a PR body.
2. Its direct scope is every `<name>.py` its text mentions that exists under
   pipeline/ - the same deliberately loose filename-mention rule as
   .github/tests/test_exporters_are_published.py, and the same trade: a
   refactor of *how* a step invokes a script cannot break the derivation,
   at the price of a filename that appears only in a comment counting.
3. Plus the transitive import closure over pipeline/'s top-level modules and
   pipeline/lib/'s submodules alike, because the mention rule alone misses
   real edges - measured 2026-08-27: the closure adds export_elevation.py to
   build-basemap's scope, extract_package.py to build-dem's, and
   build_water_distance.py to publish-vector-data's, every one a module a
   workflow runs code from without ever naming it. lib/ joined the closure
   under #1624, replacing a blanket SHARED_ROOTS entry that had every path
   go STALE on any lib/ change, including a change no publishing path's own
   import graph could reach - measured 2026-09-23: two DEM builds ran 26
   minutes on a change to pipeline/lib/work_projects.py, a module neither
   build imports.
4. Plus the workflow file itself, and the SHARED_ROOTS below that feed every
   exporter at once regardless of what imports what.

AN EXTRACT PATH FEEDS A PUBLISH WITHOUT BEING ONE. A workflow that runs
`python -m extract._run` and no publish.py lands raw tables a publishing
path reads later: extract-notices.yml, decision 61's notices legs, whose
served copy publish-conditions.yml's hourly dbt path reads. Its scope is the
extract package's own modules (pipeline/extract/_*.py) and their import
closure, the club files of the types on the hourly lane (extract/_contract.py's
CADENCE_BY_TYPE, read out of that file), the extract's pins and dlt's
committed config. It is reported beside the publishing paths and claims
nothing for the `unclaimed` line, which is about publishing paths.

A PUBLISHING PATH THAT RUNS THE MONTHLY LANE CLAIMS THE MONTHLY EXTRACT.
refresh-reference.yml runs `python -m extract._run --lane monthly` and
publishes what dbt builds from it, so its scope adds the extract package's
modules and their import closure and every club or _shared/ file of a type
the hourly lane does not carry (monthly_extract_scope()): a change to
`_shared/osm/geofabrik.py` (#1652) stales the path that lands it. The hourly
types' files are still unclaimed by publishing paths, since
publish-conditions.yml's legs read them and are not modelled here yet
(pipeline/ELT.md, "scripts/pipelines.sh must learn the new layout").

A WORKFLOW THAT DISPATCHES A PUBLISHING PATH IS ONE TOO. Since the
maintainer's choice B (2026-10-08) refresh-reference.yml extracts and pins,
and its dispatch job starts build-reference.yml, which publishes, with
`gh workflow run build-reference.yml`. So a run script's `gh workflow run
<file>` (dispatched()) makes its workflow a publishing path when <file> is
one, and its scope is its own plus the dispatched workflow's, because a run
of it reruns that one. The dispatched workflow's scope stays its own: a
dispatch of build-reference.yml rebuilds from a pin that exists, so it
carries no change to the extract or to the fetchers the pin ran. Its rerun
note names the scheduled workflow that dispatches it and the inputs a sooner
dispatch needs, read from its workflow_dispatch block, never a
`data_environment` it does not have: advice for inputs a workflow lacks is
what #1552 - A comment naming publish.py makes a workflow count as a
publishing path - found being handed out.

THE CONSERVATIVE DIRECTION IS "STALE". A false STALE costs somebody a
minute deciding not to dispatch; a false fresh is the #1123 failure - a
bucket that disagrees with `main` and nothing saying so. But unlike
.github/actions/changed-paths, an *unanswerable* case here does not resolve
to "rerun everything": a dispatch is not a minute of CI, it is a production
approval and hours of fetching, so the honest output for a file this scope
model cannot place is the `unclaimed` line saying exactly that. An honest
unknown outranks a confident answer (CLAUDE.md); this script's job is the
known half, and saying where the known half ends.

    pipeline_scopes.py             every publishing path and its derived scope
    pipeline_scopes.py --changed   read changed paths from stdin, one per
                                   line, and print the verdict

scripts/pipelines.sh is the driver that feeds it the branch's diff. Exit is
0 when the question was answered (STALE is an answer, not an error) and 2
when a workflow could not be read - callers must treat that as "answer by
hand", never as "nothing is stale".
"""

import ast
import functools
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
PIPELINE = ROOT / "pipeline"

#: Changes that stale every publishing path at once, because every exporter
#: reads them and nothing here has an import to chase: the source registry,
#: the reviewed reference joins (data, not code - no import graph reaches
#: them), the dbt layer, and the pins the runners install. pipeline/lib/
#: used to live here too; #1624 moved it to the import closure instead,
#: because unlike these, lib/'s submodules are code with real edges the
#: closure can (and, before #1624, should have) followed.
#: Directional bias argued in the module docstring - when in doubt a path
#: belongs here, because the false-fresh is the expensive mistake.
SHARED_ROOTS = (
    "pipeline/sources.json",
    "pipeline/reference/",
    "pipeline/dbt/",
    "pipeline/requirements.txt",
    "pipeline/requirements.in",
    "pipeline/requirements-dbt.txt",
    "pipeline/requirements-dbt.in",
)

#: Changed files that are never evidence of a stale publish, whatever scope
#: they land in: tests assert behaviour rather than produce artifacts, and
#: prose produces nothing.
NEVER_STALE_RE = re.compile(r"^pipeline/tests/|\.md$")

#: `python publish.py`, `python3 pipeline/publish.py`, `python -m publish`.
#: Searched only in `run:` scripts with their comment lines dropped - see
#: run_scripts() - because an echo or a comment can name the publisher too.
INVOKES_PUBLISH_RE = re.compile(r"(?<![\w.])python3?\s+(?:(?:[\w./-]*/)?publish\.py\b|-m\s+publish\b)")
#: `python -m extract._run`, from any interpreter path: the workflows run the
#: extract's own venv, `"$RUNNER_TEMP/extract/bin/python" -m extract._run`.
INVOKES_EXTRACT_RE = re.compile(r"python3?\"?\s+-m\s+extract\._run\b")
#: The same, running the whole monthly lane: refresh-reference.yml's extract step. Matched per command, its
#: backslash continuations joined (runs_whole_monthly_lane()), so a run that names `--only` tables, such as
#: publish-conditions.yml's read of the registry alone, is not taken for the lane.
INVOKES_MONTHLY_EXTRACT_RE = re.compile(r"python3?\"?\s+-m\s+extract\._run\b[^\n]*--lane\s+monthly\b")
#: `gh workflow run <file>.yml`: another workflow dispatched by file name, as refresh-reference.yml's dispatch job
#: starts build-reference.yml.
DISPATCHES_RE = re.compile(r"(?<![\w.-])gh\s+workflow\s+run\s+[\"']?([\w.-]+\.ya?ml)\b")
#: A _shared/ extract file's type, as it declares it.
SHARED_TYPE_RE = re.compile(r'^TYPE = "([a-z_]+)"', re.M)
#: An extract path's scope beyond its modules' import closure (see extract_scope_for()).
EXTRACT_ROOTS = (
    "pipeline/requirements-extract.txt",
    "pipeline/requirements-extract.in",
    "pipeline/.dlt/",
)
SCRIPT_MENTION_RE = re.compile(r"(?<![\w.])([A-Za-z0-9_]+\.py)\b")
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_]+)", re.M)

#: `from lib.x import y` or `import lib.x` - the submodule is the part after
#: the dot, which IMPORT_RE can't see: it stops at "lib" itself.
LIB_SUBMODULE_RE = re.compile(r"^\s*(?:from\s+lib\.([A-Za-z0-9_]+)\s+import|import\s+lib\.([A-Za-z0-9_]+))", re.M)
#: `from lib import x, y as z` - one or more submodules named on one line.
LIB_PACKAGE_IMPORT_RE = re.compile(r"^\s*from\s+lib\s+import\s+([^#\n]+)", re.M)


def lib_imports(text: str) -> set[str]:
    """Every pipeline/lib/ submodule this file's own text imports directly -
    the edges IMPORT_RE can't see because `lib` is a package, not a module.
    `lib/__init__.py` is empty, so a name after `from lib import` always
    names a submodule, never something re-exported from the package itself."""
    names = {a or b for a, b in LIB_SUBMODULE_RE.findall(text)}
    for line in LIB_PACKAGE_IMPORT_RE.findall(text):
        for part in line.split(","):
            token = part.strip().split()
            if token:
                names.add(token[0])
    return {f"lib/{name}.py" for name in names}


@functools.lru_cache(maxsize=None)
def _parse(text: str) -> dict:
    """A workflow file's YAML, parsed once per distinct text. The dispatch rule reads every workflow's run scripts for
    every publishing path's note, and parsing each time took one `--changed` verdict from 4.1 s to 12.5 s; kept, it
    took 1.3 to 1.6 s against 2.1 to 2.5 s for the script before the rule (measured back to back, 2026-10-08, in a
    web sandbox). Keyed on the text, not the path, so a file rewritten in place is parsed again. Never mutated."""
    return yaml.safe_load(text) or {}


def run_scripts(workflow: Path) -> str:
    """Every step's `run:` script in the workflow, shell comment lines
    removed. What the runner would actually execute, give or take an echo."""
    parsed = _parse(workflow.read_text())
    lines = []
    for job in (parsed.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            script = step.get("run") if isinstance(step, dict) else None
            if isinstance(script, str):
                lines += [line for line in script.splitlines() if not line.lstrip().startswith("#")]
    return "\n".join(lines)


def _triggers(workflow: Path) -> dict:
    """The workflow's `on:` block. YAML 1.1 reads a bare `on:` key as boolean True."""
    parsed = _parse(workflow.read_text())
    return parsed.get("on", parsed.get(True)) or {}


def dispatched(workflow: Path) -> list[Path]:
    """The workflows in this directory that this one's run scripts dispatch by file name (`gh workflow run`)."""
    names = set(DISPATCHES_RE.findall(run_scripts(workflow)))
    return [WORKFLOWS / name for name in sorted(names) if (WORKFLOWS / name).is_file() and name != workflow.name]


def publishing_workflows() -> list[Path]:
    """Every workflow that runs publish.py, and every one that dispatches such a workflow (the module docstring)."""
    workflows = sorted(WORKFLOWS.glob("*.yml"))
    direct = {path for path in workflows if INVOKES_PUBLISH_RE.search(run_scripts(path))}
    return [path for path in workflows if path in direct or direct.intersection(dispatched(path))]


def extract_paths() -> list[Path]:
    """Workflows that run the extract and publish nothing, themselves or through a dispatch: a publishing path reads
    what they land."""
    publishing = set(publishing_workflows())
    return [
        workflow
        for workflow in sorted(WORKFLOWS.glob("*.yml"))
        if INVOKES_EXTRACT_RE.search(run_scripts(workflow)) and workflow not in publishing
    ]


def hourly_types() -> set[str]:
    """The types whose club files ride the hourly lane, read from extract/_contract.py's CADENCE_BY_TYPE literal."""
    tree = ast.parse((PIPELINE / "extract" / "_contract.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == "CADENCE_BY_TYPE" for target in node.targets):
            return {kind for kind, cadence in ast.literal_eval(node.value).items() if cadence in ("hourly", "daily")}
    raise ValueError("extract/_contract.py has no CADENCE_BY_TYPE literal to read the hourly types from")


def _lane_extract_files(hourly: bool) -> set[str]:
    """The extract package's own modules and their import closure, and every club folder's or _shared/ file whose type
    rides the hourly lane (`hourly`) or does not (the monthly lane's). A file that declares no type (a _shared/
    notes.py, not_clubs.py) is neither lane's."""
    modules = {str(path.relative_to(PIPELINE)) for path in (PIPELINE / "extract").glob("_*.py")}
    files = {f"pipeline/{name}" for name in import_closure(modules)}
    kinds = hourly_types()
    for path in (PIPELINE / "extract").rglob("*.py"):
        if path.parent.parent.name == "_shared":
            # A _shared/ file is named freely and says its type in `TYPE = "<type>"` (extract/_contract.py).
            declared = SHARED_TYPE_RE.search(path.read_text())
            kind = declared.group(1) if declared is not None else None
        else:
            kind = path.stem if path.parent.parent.name == "extract" and not path.parent.name.startswith("_") else None
        if kind is not None and (kind in kinds) == hourly:
            files.add(f"pipeline/{path.relative_to(PIPELINE)}")
    return files


def extract_scope_for(workflow: Path) -> set[str]:
    """Repo-relative paths whose change stales what an extract path lands: the workflow, the extract package's own
    modules and their import closure, and every club folder's file of an hourly type. EXTRACT_ROOTS and SHARED_ROOTS
    are prefixes, matched in print_verdict()."""
    return _lane_extract_files(hourly=True) | {f".github/workflows/{workflow.name}"}


def monthly_extract_scope() -> set[str]:
    """What a publishing path that runs the monthly lane lands through the extract: the package and every file of a
    monthly type (the module docstring, "A PUBLISHING PATH THAT RUNS THE MONTHLY LANE")."""
    return _lane_extract_files(hourly=False)


def import_closure(scripts: set[str]) -> set[str]:
    """The scripts plus every pipeline/ module they import, transitively -
    top-level modules and pipeline/lib/ submodules alike, so a lib/ module
    only reachable from one publishing path's own import graph stales only
    that path (#1624), rather than all of them via SHARED_ROOTS."""
    seen = set(scripts)
    queue = list(scripts)
    while queue:
        text = (PIPELINE / queue.pop()).read_text()
        found = {f"{module}.py" for module in IMPORT_RE.findall(text)} | lib_imports(text)
        for name in found:
            if name not in seen and (PIPELINE / name).is_file():
                seen.add(name)
                queue.append(name)
    return seen


def scope_for(workflow: Path, _seen: frozenset[Path] = frozenset()) -> set[str]:
    """Repo-relative paths whose change stales this workflow's output, the scopes of the workflows it dispatches
    included, since a run of it reruns them. SHARED_ROOTS is global and deliberately not repeated per scope."""
    direct = {n for n in SCRIPT_MENTION_RE.findall(workflow.read_text()) if (PIPELINE / n).is_file()}
    if BUILD_MARTS in direct:
        direct |= build_marts_steps()
    files = {f"pipeline/{name}" for name in import_closure(direct)}
    files.add(f".github/workflows/{workflow.name}")
    if runs_whole_monthly_lane(workflow):
        files |= monthly_extract_scope()
    for callee in dispatched(workflow):
        if callee not in _seen:
            files |= scope_for(callee, _seen | {workflow})
    return files


#: build_marts.py runs each Python step as a subprocess, by the script name in its STEPS entry's `command`, so no
#: import reaches a step and the mention rule sees only the steps a workflow's comments happen to name.
BUILD_MARTS = "build_marts.py"
STEP_COMMAND_RE = re.compile(r'command=\(\s*"([A-Za-z0-9_]+\.py)"')


def build_marts_steps() -> set[str]:
    """The step scripts build_marts.py's STEPS run, read from its source: every lane's, so the answer errs to STALE."""
    return {name for name in STEP_COMMAND_RE.findall((PIPELINE / BUILD_MARTS).read_text()) if (PIPELINE / name).is_file()}


def runs_whole_monthly_lane(workflow: Path) -> bool:
    """Whether a run script extracts the whole monthly lane: `-m extract._run --lane monthly` with no `--only`."""
    commands = re.sub(r"\\\n\s*", " ", run_scripts(workflow)).splitlines()
    return any(INVOKES_MONTHLY_EXTRACT_RE.search(command) and "--only" not in command for command in commands)


def rerun_note(workflow: Path) -> str:
    """How a stale answer gets acted on, read from the workflow itself: a
    schedule means it reruns from main on its own; a run_despite_withdrawal
    input is build-raster's #855 switch-off; everything else is a dispatch.

    A `variant` input makes that dispatch ONE PER VARIANT (#1147), and saying
    so is the whole of that issue: since #1088 `build-dem.yml` builds
    `dem.pmtiles` or `dem_light.pmtiles` depending on the input, so one run
    refreshes one artifact and the other quietly ages. Nothing said so - not
    this note, not the release train - and nothing would have caught it
    either, because until #1144 verify_release did not check the hiking
    sheet's artifacts at all. Read from the workflow rather than keyed on
    build-dem's name, for the reason everything else here is: a second
    variant-taking workflow gets the right answer without editing this file.

    A workflow with no schedule that a scheduled one dispatches (choice B's
    build-reference.yml, which refresh-reference.yml starts after each pin)
    is rerun by that schedule, and can be dispatched sooner with its own
    required inputs, which the note names from its workflow_dispatch block
    rather than assuming publish and data_environment.
    """
    triggers = _triggers(workflow)
    if "schedule" in triggers:
        return "nothing to dispatch: its own schedule reruns it from main after the merge"
    inputs = (triggers.get("workflow_dispatch") or {}).get("inputs") or {}
    if "run_despite_withdrawal" in inputs:
        return "withdrawn (#855) - a rerun is a deliberate revival, not a routine dispatch"
    callers = [path for path in sorted(WORKFLOWS.glob("*.yml")) if workflow in dispatched(path) and "schedule" in _triggers(path)]
    if callers:
        required = " ".join(f"-f {name}=<{name}>" for name, spec in inputs.items() if (spec or {}).get("required"))
        return (
            f"{callers[0].name}'s schedule dispatches it from main after the merge; to rerun it sooner on its own: "
            f"gh workflow run {workflow.name} --ref main {required}".rstrip()
        )
    note = "after the merge: dispatch it with publish=true, data_environment=ua - production is the release train's promotion"
    variants = (inputs.get("variant") or {}).get("options") or []
    if len(variants) > 1:
        note += f" - ONCE PER VARIANT ({', '.join(variants)}), because one run builds one artifact"
    return note


def print_scopes() -> None:
    for workflow in publishing_workflows():
        print(f"{workflow.name} {' '.join(sorted(scope_for(workflow)))}")
    for workflow in extract_paths():
        print(f"extract-path {workflow.name} {' '.join(sorted(extract_scope_for(workflow) | set(EXTRACT_ROOTS)))}")
    print(f"every-path {' '.join(SHARED_ROOTS)}")


def print_verdict(changed: list[str]) -> None:
    relevant = [f for f in changed if not NEVER_STALE_RE.search(f)]
    shared_hits = sorted(f for f in relevant if any(f == root.rstrip("/") or f.startswith(root) for root in SHARED_ROOTS))
    claimed: set[str] = set(shared_hits)

    for workflow in publishing_workflows():
        scope = scope_for(workflow)
        hits = sorted(set(f for f in relevant if f in scope) | set(shared_hits))
        claimed.update(hits)
        if hits:
            print(f"STALE  {workflow.name}  <- {', '.join(hits)}")
            print(f"       {rerun_note(workflow)}")
        else:
            print(f"fresh  {workflow.name}")

    for workflow in extract_paths():
        scope = extract_scope_for(workflow)
        hits = sorted(
            set(f for f in relevant if f in scope or any(f.startswith(root) for root in EXTRACT_ROOTS)) | set(shared_hits)
        )
        if hits:
            print(f"STALE  {workflow.name}  <- {', '.join(hits)}  (an extract path: a publish reads what it lands)")
            print(f"       {rerun_note(workflow)}")
        else:
            print(f"fresh  {workflow.name}")

    for f in relevant:
        if f.startswith("pipeline/") and f.endswith(".py") and f not in claimed:
            print(
                f"unclaimed  {f} - no publishing path names or imports it. Usually a spike or a "
                "standing check; if it feeds a publish, treat that path as stale and say so in the PR."
            )

    migrations = [f for f in changed if f.startswith("backend/alembic/versions/")]
    if migrations:
        print(
            f"migrations  {', '.join(sorted(migrations))} - UA applies on the merge "
            "(migrate.yml); production is a release-train dispatch."
        )


def main(argv: list[str]) -> int:
    if argv[1:] == ["--changed"]:
        print_verdict([line.strip() for line in sys.stdin if line.strip()])
    elif not argv[1:]:
        print_scopes()
    else:
        print(f"usage: {Path(argv[0]).name} [--changed]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
