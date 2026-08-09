"""The workflow's scope list, against what this suite actually reads.

TESTING.md's "Redundancy" section states the rule: **a suite's scope list
includes every file its tests read.** #317 is what happens without it - the
client suite read `pipeline/reference/gain_vectors.json` and `site/index.html`
while scoped to `client/` alone, so a pull request editing the shared
elevation-gain vectors ran only the Python half of a two-language drift guard,
and the hole closed after the merge rather than before it.

This suite has the same exposure in the other direction. Two contract tests
read client modules - `test_preferences_contract.py` compares the two halves
of `UserPreferences`, `test_client_report_contract.py` the report vocabulary
and the photo cap - and the drift they exist to catch arrives in a pull
request that touches only the client, which is exactly the run a `backend/`-
only scope would skip.

WHY THE SCOPE LIST NAMES FILES RATHER THAN `client/src/lib/`

Because the broad prefix is a tax on the commonest pull request in this
repository, and an unusually heavy one here: `client/src/lib/` is touched by
most client work, and this job stands up a Postgres service container and a
pgbouncer before it runs a test. Paying that on every client change, to catch
drift in four modules edited a few times a year, is the kind of cost that gets
a rule quietly relaxed later.

The trade is that a narrow list is only correct while it is complete, and
"remember to add the file to the workflow too" is not a mechanism. This is the
mechanism. It reads the workflow back and compares it against the paths the
contract tests declare, so a client file added to either without a matching
scope entry fails here rather than silently ceasing to be checked in CI.

WHY IT IMPORTS THE OTHER TEST MODULES

The alternative is a list of client paths written here, which would be a
second copy of the thing the scope list is already a copy of - three places to
keep in step instead of two. Importing means the declaration lives with the
code that reads the files, and this module only asks whether CI agrees with
it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from tests.test_client_report_contract import CLIENT_FILES_READ
from tests.test_preferences_contract import CLIENT_MODEL

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "backend-tests.yml"
ACTION = ".github/actions/changed-paths"

# Every client file this suite reads, from the modules that read them.
# `CLIENT_MODEL` is `userPreferences.ts`, which both contract tests happen to
# read - the set is what matters, not the count.
CLIENT_FILES = {*CLIENT_FILES_READ, CLIENT_MODEL}


def scope_prefixes() -> list[str]:
    """The `paths:` input handed to the changed-paths action.

    Parsed out of the YAML rather than grepped for `paths:`, because the word
    appears twice in that file - once in the comment explaining why the
    trigger deliberately has no `paths:` filter, which is the opposite
    decision and would be a confusing thing to match by accident.
    """
    assert WORKFLOW.exists(), (
        f"{WORKFLOW} is missing, so this test cannot check anything. It fails "
        "rather than skips: a guard that quietly stops looking is worse than "
        "no guard, because the suite still reports green."
    )

    workflow = yaml.safe_load(WORKFLOW.read_text())
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if ACTION in str(step.get("uses", "")):
                return str(step["with"]["paths"]).split()

    raise AssertionError(
        f"No step in {WORKFLOW.name} uses {ACTION}. If the scoping moved, fix "
        "this test rather than deleting it - it is what keeps the narrow path "
        "list honest."
    )


def test_every_client_file_this_suite_reads_is_in_the_scope_list():
    """The rule, applied to this suite.

    A file read by a contract test and absent from the scope list is worse
    than an untested contract: the test exists, passes locally, passes on
    `main` after the merge, and never runs on the pull request that broke it.
    """
    prefixes = scope_prefixes()
    missing = []

    for path in sorted(CLIENT_FILES):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if not any(relative.startswith(prefix) for prefix in prefixes):
            missing.append(relative)

    assert not missing, (
        f"This suite's contract tests read client files that {WORKFLOW.name} "
        "does not list, so a pull request changing only those would skip the "
        "suite and the drift guard with it:\n"
        + "\n".join(f"  - {path}" for path in missing)
        + f"\n\nThe list today is: {' '.join(prefixes)}"
    )


def test_the_suite_still_scopes_itself_and_its_own_gate():
    """The three entries that are not about the client.

    `backend/` is the suite; the workflow and the action are on the list so a
    change to the gate still proves the suite it gates. Losing any of them
    while narrowing the client entries would be an easy edit to make and a
    hard one to notice.
    """
    prefixes = set(scope_prefixes())

    assert "backend/" in prefixes
    assert ".github/workflows/backend-tests.yml" in prefixes
    assert f"{ACTION}/" in prefixes


def test_this_is_actually_reading_a_scope_list():
    """Guards the guard: a parse that returned nothing would pass everything
    above by finding no files to be missing."""
    prefixes = scope_prefixes()

    assert len(prefixes) >= 5
    assert len(CLIENT_FILES) >= 4
