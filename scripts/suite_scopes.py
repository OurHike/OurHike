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

WORKFLOWS = {
    "client": ".github/workflows/client-tests.yml",
    "pipeline": ".github/workflows/pipeline-tests.yml",
    "backend": ".github/workflows/backend-tests.yml",
}


def scope_for(workflow_path: Path) -> str:
    workflow = yaml.safe_load(workflow_path.read_text())
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if ".github/actions/changed-paths" in str(step.get("uses", "")):
                return " ".join(str(step["with"]["paths"]).split())
    raise LookupError(f"{workflow_path} has no changed-paths step")


def main(argv: list[str]) -> int:
    wanted = argv[1:] or sorted(WORKFLOWS)
    for suite in wanted:
        if suite not in WORKFLOWS:
            print(f"unknown suite {suite!r} - one of {sorted(WORKFLOWS)}", file=sys.stderr)
            return 2
        scope = scope_for(ROOT / WORKFLOWS[suite])
        prefix = "" if len(wanted) == 1 else f"{suite} "
        print(f"{prefix}{scope}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
