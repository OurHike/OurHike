"""Tests for the duplicate-issue warning in `pr-issue-link.yml`.

The warning itself is a judgement a reader makes: two pull requests closing
one issue is usually two people doing the same work and is occasionally
deliberate. What is NOT a judgement, and what these tests are about, is that
finding it out can never make things worse.

That matters more here than the feature does, because this is the check most
likely to be the first one required on `main` (the workflow's own header says
so). A required check has exactly one job, and a secondary lookup that turns it
red for a reason unrelated to its rule would be a gate rejecting good work.
Three properties keep that from happening, and each is one deleted line away
from being false with nothing else to notice:

  - the GraphQL lookup is wrapped, so a failed query reports "could not be
    determined" instead of throwing out of the step;
  - both comment steps carry `continue-on-error`, so a comment that cannot be
    posted is a lost warning rather than a blocked pull request;
  - both are skipped on forks, whose tokens are read-only whatever the
    workflow's `permissions:` block asks for - so attempting it there would
    fail on somebody else's contribution every time.

The comment is also asserted to be removable. A "duplicate!" comment left at
the top of a thread after the collision was settled is the noise that gets a
useful check muted.

Read as YAML rather than by grepping the file: an `if:` that has drifted onto
a different step, or a `continue-on-error` under the wrong key, is exactly the
mistake a text search cannot see and a parse can.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-issue-link.yml"

# The one sticky-comment identity. Both the post and the delete must name it,
# or the delete tidies away nothing and the warning becomes permanent.
STICKY_HEADER = "pr-issue-link-duplicate"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


@pytest.fixture(scope="module")
def steps(workflow: dict) -> list[dict]:
    return workflow["jobs"]["linked"]["steps"]


@pytest.fixture(scope="module")
def script(steps: list[dict]) -> str:
    """The inline github-script body - the step that decides the conclusion."""
    return steps[0]["with"]["script"]


@pytest.fixture(scope="module")
def comment_steps(steps: list[dict]) -> list[dict]:
    """Every step that touches the sticky comment, posting or deleting."""
    return [step for step in steps if "sticky-pull-request-comment" in str(step.get("uses", ""))]


def test_the_duplicate_lookup_is_wrapped_rather_than_left_to_throw(script: str):
    """A pull request that correctly closes an issue must not fail this check
    because a secondary query broke. The lookup returns null - "could not be
    determined" - and the summary says so."""
    assert "try {" in script
    assert "catch (error)" in script
    assert "could not be determined" in script


def test_the_check_still_fails_a_pull_request_that_closes_no_issue(script: str):
    """The rule this workflow exists for, unchanged. Everything above is a
    warning; this is the only `setFailed` and it must stay."""
    assert script.count("core.setFailed") == 1
    assert "No linked issue" in script


def test_a_collision_warns_and_never_fails(script: str):
    """Two pull requests closing one issue is sometimes the point - a change
    split for review, or a replacement opened while the original stays up. A
    red check would block that case to catch the common one."""
    assert "core.warning" in script
    # The warning text and the failure text must not be the same call site.
    warning_index = script.index("core.warning")
    failure_index = script.index("core.setFailed")
    assert warning_index < failure_index


def test_the_collision_lookup_ignores_this_pull_request(script: str):
    """Every pull request closes its own issue. Without this it would report
    itself as its own duplicate, on every run, forever."""
    assert "other.number !== pr.number" in script


def test_only_open_pull_requests_count_as_a_collision(script: str):
    """A merged or closed pull request closing the same issue is the normal
    history of an issue, not a collision. Filtered on the answer rather than by
    a query argument, so it holds however the field defaults."""
    assert "other.state === 'OPEN'" in script


def test_both_comment_steps_cannot_fail_the_check(comment_steps: list[dict]):
    """The property that keeps a courtesy from becoming a gate."""
    assert len(comment_steps) == 2
    for step in comment_steps:
        assert step.get("continue-on-error") is True, step.get("name")


def test_both_comment_steps_are_skipped_on_a_fork(comment_steps: list[dict]):
    """A fork's token is read-only regardless of the `permissions:` block, so
    attempting a comment there fails every time - on a contribution from
    somebody who did nothing wrong."""
    for step in comment_steps:
        assert "github.event.pull_request.head.repo.full_name == github.repository" in step["if"]


def test_the_warning_is_removed_once_it_stops_being_true(comment_steps: list[dict]):
    """Otherwise a settled collision leaves a permanent accusation at the top
    of the thread, which is how a useful check gets muted."""
    deleting = [step for step in comment_steps if step["with"].get("delete") is True]

    assert len(deleting) == 1
    assert deleting[0]["with"]["header"] == STICKY_HEADER


def test_the_post_and_the_delete_name_the_same_comment(comment_steps: list[dict]):
    """A header typo would leave the delete tidying away a comment that does
    not exist while the real one stays."""
    assert {step["with"]["header"] for step in comment_steps} == {STICKY_HEADER}


def test_the_two_comment_steps_are_mutually_exclusive(comment_steps: list[dict]):
    """One posts when there are collisions and the other deletes when there are
    none. Both firing would post and immediately remove the warning, which
    looks exactly like the feature not working."""
    conditions = [step["if"] for step in comment_steps]
    posting = next(c for c in conditions if "!= '[]'" in c)
    deleting = next(c for c in conditions if "== '[]'" in c)

    assert "collisions != ''" in posting
    assert "collisions == ''" in deleting


def test_the_comment_reads_the_output_the_script_actually_sets(steps: list[dict], script: str):
    """The step id and the output name are a pair spelled in two languages,
    and a mismatch renders an empty comment rather than erroring."""
    assert steps[0]["id"] == "check"
    for output in ("collisions", "collisions_markdown"):
        # Whitespace-tolerant: prettier-style wrapping moves the argument onto
        # its own line, and a test that pins the indentation fails on a reformat
        # rather than on a mistake.
        assert re.search(rf"core\.setOutput\(\s*'{output}'", script), output

    posting = next(step for step in steps if step.get("name") == "Say so on the pull request")
    assert "steps.check.outputs.collisions_markdown" in posting["with"]["message"]


def test_writing_is_scoped_to_pull_requests_and_nothing_else(workflow: dict):
    """`pull-requests: write` is here for the comment and for nothing else.
    The check's power to gate a merge comes from being in the required list on
    `main`, which no workflow can grant itself - contents stays read."""
    assert workflow["permissions"]["pull-requests"] == "write"
    assert workflow["permissions"]["contents"] == "read"
    assert workflow["permissions"]["issues"] == "read"


def test_a_merge_queue_entry_still_reports_green_without_asking_anything(script: str):
    """Unchanged and load-bearing: a required check that reports nothing hangs
    a queue entry rather than failing it. The duplicate lookup must not have
    introduced a path that runs before this early return."""
    assert "if (!pr) {" in script
    # Against the first real query rather than the first mention of a field
    # name - the header comment names `closingIssuesReferences` in prose long
    # before any code runs, and matching that would assert nothing.
    assert script.index("if (!pr) {") < script.index("await github.graphql(")
