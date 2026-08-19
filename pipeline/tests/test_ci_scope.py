"""The workflow's scope list, against what this suite actually reads.

TESTING.md's "Redundancy" section states the rule: **a suite's scope list
includes every file its tests read.** #317 is what happens without it - the
client suite read `pipeline/reference/gain_vectors.json` and `site/index.html`
while scoped to `client/` alone, so a pull request editing the shared
elevation-gain vectors ran only the Python half of a two-language drift guard,
and the hole closed after the merge rather than before it.

This suite now has the same exposure in the other direction:
`test_published_key_contract.py` reads four client modules, and the drift it
exists to catch arrives in a pull request that touches only those - which is
exactly the run a `pipeline/`-only scope would skip.

`test_export_spurs.py` reads `features/SPUR_TRAILS.md` for the same kind of
reason (#501): the doc and `export_spurs.py` have to agree about which POI
types are destinations, and the edit that breaks that agreement is a
docs-only pull request - the exact shape a `pipeline/` scope skips.

WHY THE SCOPE LIST NAMES FILES RATHER THAN `client/src/lib/`

Because the broad prefix is a tax on the commonest pull request in this
repository. `client/src/lib/` is touched by most client work, and the pipeline
suite is a thousand tests and a DuckDB spatial extension; spending that on
every client change, to catch drift in four modules that are edited a few
times a year, is the kind of cost that gets a rule quietly relaxed later.

The trade is that a narrow list is only correct while it is complete, and
"remember to add the file to the workflow too" is not a mechanism. This is the
mechanism. It reads the workflow back and compares it against the paths the
contract test declares, so a client file added there without a matching scope
entry fails here rather than silently ceasing to be checked in CI.

WHAT IT DOES NOT CHECK

Whether the scope list has entries nothing reads. An over-broad list runs a
suite that had nothing to do, which costs a minute; an under-broad one skips a
suite that did, which costs a merge. Only the second is a failure, and the
action itself already takes that side of the trade for every case it is
unsure about.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from test_export_spurs import SPUR_TRAILS_DOC
from test_published_key_contract import CLIENT_FILES_READ

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pipeline-tests.yml"
ACTION = ".github/actions/changed-paths"


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

    for path in CLIENT_FILES_READ:
        relative = path.relative_to(REPO_ROOT).as_posix()
        if not any(relative.startswith(prefix) for prefix in prefixes):
            missing.append(relative)

    assert not missing, (
        "test_published_key_contract.py reads client files that "
        f"{WORKFLOW.name} does not list, so a pull request changing only "
        "those would skip this suite and the drift guard with it:\n"
        + "\n".join(f"  - {path}" for path in missing)
        + f"\n\nThe list today is: {' '.join(prefixes)}"
    )


def test_the_design_doc_this_suite_reads_is_in_the_scope_list():
    """The same rule for the one non-client file the suite reads.

    A docs-only pull request is the commonest way `features/SPUR_TRAILS.md`
    changes, and it is the only kind of change the drift guard in
    test_export_spurs.py exists to catch. Off the scope list, that guard runs
    on every pull request except the ones that matter.
    """
    prefixes = scope_prefixes()
    relative = SPUR_TRAILS_DOC.relative_to(REPO_ROOT).as_posix()

    assert any(relative.startswith(prefix) for prefix in prefixes), (
        f"test_export_spurs.py reads {relative}, which {WORKFLOW.name} does "
        "not list, so a pull request changing only that doc would skip this "
        "suite and the destination-partition guard with it.\n\n"
        f"The list today is: {' '.join(prefixes)}"
    )


def test_the_suite_still_scopes_itself_and_its_own_gate():
    """The three entries that are not about the client.

    `pipeline/` is the suite; the workflow and the action are on the list so a
    change to the gate still proves the suite it gates. Losing any of them
    while narrowing the client entries would be an easy edit to make and a
    hard one to notice.
    """
    prefixes = set(scope_prefixes())

    assert "pipeline/" in prefixes
    assert ".github/workflows/pipeline-tests.yml" in prefixes
    assert f"{ACTION}/" in prefixes


def test_this_is_actually_reading_a_scope_list():
    """Guards the guard: a parse that returned nothing would pass everything
    above by finding no files to be missing."""
    prefixes = scope_prefixes()

    assert len(prefixes) >= 5
    assert len(CLIENT_FILES_READ) >= 4
    assert SPUR_TRAILS_DOC.name in {Path(prefix).name for prefix in prefixes}
