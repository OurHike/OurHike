#!/usr/bin/env python3
"""The parity families pipeline-tests.yml's dbt job runs, read from its own "Parity with today's exporters" step.

scripts/test.sh's dbt suite runs some of them and names the rest it leaves
out (WF8 of the PR #1805 review), so the list it compares with is CI's own,
read at run time rather than copied, as scripts/suite_scopes.py reads the
suites' scopes. One family per line, in the step's order, each once.

    dbt_ci_parity.py      every family CI's dbt job compares

Exit is non-zero when the step cannot be read; test.sh then says it could
not tell what it leaves out, never that it leaves out nothing.
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "pipeline-tests.yml"
STEP = "Parity with today's exporters"
#: A parity line: `parity.py [--json-dir DIR] FAMILY --new ...`, the family maybe quoted, maybe the POI loop's.
LINE = re.compile(r'parity\.py (?:--json-dir \S+ )?"?([a-z0-9_$]+)"? --new')
POI_LOOP = re.compile(r"for poi_type in ([a-z ]+); do")


def families() -> list[str]:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["dbt"]["steps"]
    (script,) = [step["run"] for step in steps if step.get("name") == STEP]
    loop = POI_LOOP.search(script)
    kinds = loop.group(1).split() if loop else []
    found: list[str] = []
    for family in LINE.findall(script):
        for name in [family.replace("$poi_type", kind) for kind in kinds] if "$poi_type" in family else [family]:
            if name not in found:
                found.append(name)
    return found


def main() -> int:
    try:
        names = families()
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as error:
        print(f"could not read the step {STEP!r} of {WORKFLOW}'s dbt job: {error!r}", file=sys.stderr)
        return 1
    if not names:
        print(f"the step {STEP!r} of {WORKFLOW}'s dbt job names no parity family", file=sys.stderr)
        return 1
    print("\n".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
