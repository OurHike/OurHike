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

1. A workflow is a *publishing path* iff its text invokes `publish.py`. Today
   that is five files, and a sixth joins this report by existing rather than
   by being remembered.
2. Its direct scope is every `<name>.py` its text mentions that exists under
   pipeline/ - the same deliberately loose filename-mention rule as
   .github/tests/test_exporters_are_published.py, and the same trade: a
   refactor of *how* a step invokes a script cannot break the derivation,
   at the price of a filename that appears only in a comment counting.
3. Plus the transitive import closure over pipeline/'s top-level modules,
   because the mention rule alone misses real edges - measured 2026-08-27:
   the closure adds export_elevation.py to build-basemap's scope,
   extract_package.py to build-dem's, and build_water_distance.py to
   publish-vector-data's, every one a module a workflow runs code from
   without ever naming it.
4. Plus the workflow file itself, and the SHARED_ROOTS below that feed every
   exporter at once.

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

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
PIPELINE = ROOT / "pipeline"

#: Changes that stale every publishing path at once, because every exporter
#: reads them: the shared library, the source registry, the reviewed
#: reference joins, the dbt layer, and the pins the runners install.
#: Directional bias argued in the module docstring - when in doubt a path
#: belongs here, because the false-fresh is the expensive mistake.
SHARED_ROOTS = (
    "pipeline/lib/",
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

INVOKES_PUBLISH_RE = re.compile(r"(?<![\w.])publish\.py\b")
SCRIPT_MENTION_RE = re.compile(r"(?<![\w.])([A-Za-z0-9_]+\.py)\b")
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_]+)", re.M)


def publishing_workflows() -> list[Path]:
    return [p for p in sorted(WORKFLOWS.glob("*.yml")) if INVOKES_PUBLISH_RE.search(p.read_text())]


def import_closure(scripts: set[str]) -> set[str]:
    """The scripts plus every pipeline/ top-level module they import,
    transitively. `from lib.x import y` resolves to no top-level module and
    is deliberately not chased - SHARED_ROOTS already carries all of lib/."""
    seen = set(scripts)
    queue = list(scripts)
    while queue:
        text = (PIPELINE / queue.pop()).read_text()
        for module in IMPORT_RE.findall(text):
            name = f"{module}.py"
            if name not in seen and (PIPELINE / name).is_file():
                seen.add(name)
                queue.append(name)
    return seen


def scope_for(workflow: Path) -> set[str]:
    """Repo-relative paths whose change stales this workflow's output.
    SHARED_ROOTS is global and deliberately not repeated per scope."""
    direct = {n for n in SCRIPT_MENTION_RE.findall(workflow.read_text()) if (PIPELINE / n).is_file()}
    files = {f"pipeline/{name}" for name in import_closure(direct)}
    files.add(f".github/workflows/{workflow.name}")
    return files


def rerun_note(workflow: Path) -> str:
    """How a stale answer gets acted on, read from the workflow itself: a
    schedule means it reruns from main on its own; a run_despite_withdrawal
    input is build-raster's #855 switch-off; everything else is a dispatch."""
    parsed = yaml.safe_load(workflow.read_text())
    # YAML 1.1 reads a bare `on:` key as boolean True.
    triggers = parsed.get("on", parsed.get(True, {}))
    if "schedule" in triggers:
        return "nothing to dispatch: its own schedule reruns it from main after the merge"
    inputs = (triggers.get("workflow_dispatch") or {}).get("inputs", {})
    if "run_despite_withdrawal" in inputs:
        return "withdrawn (#855) - a rerun is a deliberate revival, not a routine dispatch"
    return "after the merge: dispatch it with publish=true, data_environment=ua - production is the release train's promotion"


def print_scopes() -> None:
    for workflow in publishing_workflows():
        print(f"{workflow.name} {' '.join(sorted(scope_for(workflow)))}")
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
