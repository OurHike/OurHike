#!/usr/bin/env python3
"""Each test suite's changed-paths scope, read from its own workflow YAML.

One home for the reading (#660): scripts/test.sh and scripts/threads.sh both
need these lists, and the hand-kept copy threads.sh carried instead had
drifted - site/, pipeline/reference/, .github/ISSUE_TEMPLATE/ and the named
cross-suite contract files were invisible to it, so the ledger reported
`none (docs only)` for changes CI runs a full client suite on. Parsed out of
the YAML rather than grepped for, for the reason backend/tests/
test_ci_scope.py gives about the same parse: the word `paths` appears in
those files inside a comment explaining the OPPOSITE decision.

    suite_scopes.py            every suite, one per line: "<suite> <paths...>"
    suite_scopes.py client     one suite's paths, space-separated

The settings suite is deliberately absent: it runs on every pull request
unfiltered (TESTING.md, "Repository settings"), so it has no scope list to
read and both callers select it whenever anything changed at all.

Exit is non-zero when a workflow cannot be read - the callers treat that as
"run the suite" (scripts/test.sh) or "say the scope is unreadable"
(scripts/threads.sh), never as "the suite is unreachable".
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

#: Each suite is one CI job: its workflow file and its job id. The job is
#: named rather than taken as "the first job with a scope", because one
#: workflow can carry two suites - pipeline-tests.yml runs the pytest job and
#: the dbt job, each with its own changed-paths list, and the first-job rule
#: could only ever read the pytest one. That is how a dbt-only change used to
#: reach scripts/test.sh as "the pipeline suite" and run no dbt at all
#: (#1793 - Rebuild the data platform as dlt → dbt: seven contracted marts,
#: a monthly refresh, published docs, and lighter phone downloads).
WORKFLOWS = {
    "client": (".github/workflows/client-tests.yml", "test"),
    "pipeline": (".github/workflows/pipeline-tests.yml", "pytest"),
    "dbt": (".github/workflows/pipeline-tests.yml", "dbt"),
    "backend": (".github/workflows/backend-tests.yml", "pytest-postgres"),
}


def scope_for(workflow_path: Path, job_id: str) -> str:
    workflow = yaml.safe_load(workflow_path.read_text())
    job = workflow["jobs"].get(job_id)
    if job is None:
        # A renamed job is an unreadable scope, which both callers already
        # treat as "run it" or "say so" - never as "unreachable".
        raise LookupError(f"{workflow_path} has no job {job_id!r}")
    for step in job.get("steps", []):
        if ".github/actions/changed-paths" in str(step.get("uses", "")):
            return " ".join(str(step["with"]["paths"]).split())
    raise LookupError(f"{workflow_path}'s {job_id!r} job has no changed-paths step")


def main(argv: list[str]) -> int:
    wanted = argv[1:] or sorted(WORKFLOWS)
    for suite in wanted:
        if suite not in WORKFLOWS:
            print(f"unknown suite {suite!r} - one of {sorted(WORKFLOWS)}", file=sys.stderr)
            return 2
        workflow, job_id = WORKFLOWS[suite]
        scope = scope_for(ROOT / workflow, job_id)
        prefix = "" if len(wanted) == 1 else f"{suite} "
        print(f"{prefix}{scope}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
