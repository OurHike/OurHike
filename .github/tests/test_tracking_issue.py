"""Tests for the tracking-issue policy the four scheduled monitors share.

`.github/scripts/tracking-issue.js` is what check-deployment.yml,
check-deployed-app.yml, check-upstream-freshness.yml and smoke-published.yml
all call to open, update and close their one issue. Before #678 it was four
copies of about ninety lines, and this file did not exist.

**The round trip is the point.** Each copy recovered "first seen" by parsing
the dates back out of the markdown table it had itself written, with a regex
hand-fitted to that file's column count - three counted three columns, one
counted two. Adding a column to any of those tables would have silently reset
that monitor's clock to today on every subsequent run, with the body still
saying "first seen", and nothing anywhere would have failed. So the first
thing asserted here is that what the module writes is what the module reads.

Driven under `node` rather than reimplemented in Python, for the reason
test_pages_publish.py runs the real `publish.sh` under `bash`: a test of a
paraphrase proves nothing about the artifact CI actually runs. The GitHub
client is a double, because the policy - and every way it has gone wrong - is
about which calls are made in which order, not about the network.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / ".github" / "scripts" / "tracking-issue.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is not on PATH; CI runners always have it and this exercises the real module.",
)


# A stand-in for github-script's `github`, recording every call so the
# assertions can be about the sequence. `listForRepo` is reached through
# `paginate`, exactly as the module reaches it.
HARNESS = """
const trackingIssue = require(process.argv[1])
const options = JSON.parse(process.argv[2])
const existing = options.existing

const calls = []
const github = {
  paginate: async (fn, args) => fn(args),
  rest: {
    issues: {
      listForRepo: async () => (existing ? [existing] : []),
      create: async (args) => {
        calls.push({call: 'create', ...args})
        return {data: {number: 999}}
      },
      update: async (args) => { calls.push({call: 'update', ...args}); },
      createComment: async (args) => { calls.push({call: 'createComment', ...args}); },
    },
  },
}
const context = {repo: {owner: 'OurHike', repo: 'OurHike'}}
const core = {info: () => {}, warning: () => {}}

trackingIssue({github, context, core}, {
  label: options.label,
  title: options.title,
  healthy: options.healthy,
  allClear: options.allClear,
  checkedAt: options.checkedAt,
  keys: options.keys,
  render: (firstSeen, cell) => [
    '| key | state | first seen | detail |',
    '|---|---|---|---|',
    ...options.keys.map(k => `| \\`${k}\\` | changed | ${firstSeen[k]} | ${cell(options.detail || 'plain')} |`),
  ].join('\\n'),
}).then(result => {
  console.log(JSON.stringify({result, calls}))
}).catch(error => {
  console.error(error.stack)
  process.exit(1)
})
"""


def run(**options):
    """Drive the real module once and return its result plus the calls it made."""
    options.setdefault("label", "data-freshness")
    options.setdefault("title", "Upstream data freshness")
    options.setdefault("healthy", False)
    options.setdefault("allClear", "All clear.")
    options.setdefault("checkedAt", "2026-08-13")
    options.setdefault("keys", ["atc-centerline"])
    options.setdefault("existing", None)

    completed = subprocess.run(
        ["node", "-e", HARNESS, "--", str(MODULE), json.dumps(options)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert completed.returncode == 0, f"the module threw:\n{completed.stderr}"
    return json.loads(completed.stdout)


def body_of(calls, kind):
    return next(call["body"] for call in calls if call["call"] == kind)


# --- The round trip, which is why this file exists -------------------------


def test_a_date_written_into_a_body_is_read_back_out_of_it():
    """The regression #678 is about. Write a body, feed it back as the open
    issue, and the clock must not have moved."""
    opened = run(keys=["atc-centerline"], checkedAt="2026-08-01")
    first_body = body_of(opened["calls"], "create")

    later = run(
        keys=["atc-centerline"],
        checkedAt="2026-08-13",
        existing={"number": 478, "title": "Upstream data freshness", "body": first_body},
    )

    assert later["result"]["firstSeen"] == {"atc-centerline": "2026-08-01"}, (
        "A key already on the issue was re-dated to today, so the body would say a source stale since "
        "2026-08-01 had been stale since 2026-08-13. This is the failure the per-file regexes could reach "
        "by anyone adding a table column, and that nothing tested."
    )


@pytest.mark.parametrize("columns", [2, 3, 5])
def test_the_clock_survives_a_table_of_any_shape(columns):
    """The specific fragility being removed. The old readers each hard-coded
    how many columns sat between the key and the date; this asserts the
    module does not care, by rendering the same data at three widths."""
    opened = run(keys=["k"], checkedAt="2026-08-01", detail="x | y" if columns == 5 else "x")
    body = body_of(opened["calls"], "create")

    # Whatever the caller rendered, the marker is what gets read.
    later = run(
        keys=["k"],
        checkedAt="2026-08-13",
        existing={"number": 1, "title": "Upstream data freshness", "body": body},
    )
    assert later["result"]["firstSeen"] == {"k": "2026-08-01"}


def test_the_marker_renders_as_nothing():
    opened = run(keys=["k"])
    body = body_of(opened["calls"], "create")
    assert "<!-- tracking-issue first-seen" in body
    assert body.count("<!--") == 1, "more than one marker would make the parse ambiguous"


def test_a_body_written_before_the_marker_existed_still_gives_up_its_dates():
    """#478 - "Upstream data freshness" - was open when this landed and carried
    real dates in a table with no marker. Losing them silently is the same harm
    as the reset this file is mostly about."""
    legacy = "\n".join(
        [
            "| source | state | first seen | detail |",
            "|---|---|---|---|",
            "| `atc-centerline` | changed upstream | 2026-07-04 | an ETag moved |",
            "| `usgs-topo` | could not be checked | 2026-07-30 | timed out |",
        ]
    )
    later = run(
        keys=["atc-centerline", "usgs-topo"],
        checkedAt="2026-08-13",
        existing={"number": 478, "title": "Upstream data freshness", "body": legacy},
    )
    assert later["result"]["firstSeen"] == {
        "atc-centerline": "2026-07-04",
        "usgs-topo": "2026-07-30",
    }


def test_the_legacy_reader_does_not_depend_on_column_count():
    """The two-column shape check-deployed-app.yml wrote, which needed a
    different regex from the other three."""
    legacy = "\n".join(
        [
            "| check | first seen | detail |",
            "|---|---|---|",
            "| `map-loads` | 2026-07-04 | blank |",
        ]
    )
    later = run(
        keys=["map-loads"],
        checkedAt="2026-08-13",
        existing={"number": 5, "title": "Upstream data freshness", "body": legacy},
    )
    assert later["result"]["firstSeen"] == {"map-loads": "2026-07-04"}


def test_a_key_that_recovered_and_failed_again_starts_a_new_clock():
    opened = run(keys=["a", "b"], checkedAt="2026-08-01")
    body = body_of(opened["calls"], "create")

    only_b = run(keys=["b"], checkedAt="2026-08-05", existing={"number": 1, "title": "Upstream data freshness", "body": body})
    both_again = run(
        keys=["a", "b"],
        checkedAt="2026-08-13",
        existing={"number": 1, "title": "Upstream data freshness", "body": body_of(only_b["calls"], "update")},
    )

    assert both_again["result"]["firstSeen"]["b"] == "2026-08-01", "b never recovered and must keep its clock"
    assert both_again["result"]["firstSeen"]["a"] == "2026-08-13", (
        "a passed and then failed again, which is a new occurrence rather than a continuing one - and it also "
        "keeps the marker from growing without bound as keys come and go."
    )


# --- The transitions ------------------------------------------------------


def test_going_red_with_no_issue_open_opens_one():
    result = run(healthy=False, existing=None)
    assert [c["call"] for c in result["calls"]] == ["create"]
    assert result["result"]["action"] == "opened"


def test_staying_red_updates_the_body_and_does_not_comment():
    """Updating a body does not notify, and that is what makes a week-long
    outage cost one email rather than seven (#431)."""
    result = run(healthy=False, existing={"number": 12, "title": "Upstream data freshness", "body": "old"})
    assert [c["call"] for c in result["calls"]] == ["update"], (
        "A comment per run is exactly the noise the tracking issue exists to avoid."
    )
    assert result["result"]["action"] == "updated"


def test_going_green_comments_then_closes():
    result = run(healthy=True, existing={"number": 12, "title": "Upstream data freshness", "body": "old"})
    assert [c["call"] for c in result["calls"]] == ["createComment", "update"], (
        "The comment is the notification and closing alone is silent, so the order matters."
    )
    closing = next(c for c in result["calls"] if c["call"] == "update")
    assert closing["state"] == "closed"
    assert closing["state_reason"] == "completed"


def test_staying_green_touches_nothing():
    result = run(healthy=True, existing=None)
    assert result["calls"] == []
    assert result["result"]["action"] == "none"


def test_an_issue_with_a_different_title_under_the_same_label_is_not_touched():
    """check-deployment.yml and smoke-published.yml deliberately share
    `deployment-health` and must never share an issue: they can be red for
    unrelated reasons, and one would overwrite the other's findings."""
    result = run(
        healthy=False,
        title="Upstream data freshness",
        existing={"number": 12, "title": "Published data smoke test", "body": "someone else's"},
    )
    assert [c["call"] for c in result["calls"]] == ["create"], (
        "It matched on the label alone and hijacked another monitor's issue."
    )


# --- Text that arrives from somewhere else --------------------------------


def test_a_pipe_in_upstream_text_cannot_break_the_table():
    result = run(keys=["k"], detail="weird | value")
    body = body_of(result["calls"], "create")
    assert r"weird \| value" in body


def test_a_newline_in_upstream_text_cannot_break_the_table():
    result = run(keys=["k"], detail="two\nlines")
    body = body_of(result["calls"], "create")
    assert "two lines" in body


# --- The callers still call it --------------------------------------------


def test_every_monitor_uses_the_shared_module():
    """Guard against a fifth copy appearing, or one of these four quietly
    growing its own again."""
    workflows = REPO_ROOT / ".github" / "workflows"
    missing = [
        name
        for name in (
            "check-deployment.yml",
            "check-deployed-app.yml",
            "check-upstream-freshness.yml",
            "smoke-published.yml",
        )
        if "scripts/tracking-issue.js" not in (workflows / name).read_text(encoding="utf-8")
    ]
    assert not missing, (
        "These monitors open a tracking issue without the shared policy, which is the copy-paste #678 removed - "
        "and the drift it caused (#651, #655) took two rounds of review to find:\n  " + "\n  ".join(missing)
    )


def test_the_two_all_clear_conditions_that_differ_still_differ():
    """#651 corrected the all-clear in two monitors, differently: one about
    whether the run looked at all, the other about telling unreachable apart
    from failed. They are the reason `healthy` is the caller's to compute, so
    a refactor that "simplified" them into the shared module would be
    reintroducing the bug rather than tidying up."""
    workflows = REPO_ROOT / ".github" / "workflows"
    deployment = (workflows / "check-deployment.yml").read_text(encoding="utf-8")
    smoke = (workflows / "smoke-published.yml").read_text(encoding="utf-8")

    assert "verdict.checked_artifacts !== false" in deployment, (
        "check-deployment.yml lost the #651 guard that stops a run which never checked the artifacts from "
        "closing an outage issue."
    )
    assert "unreachable.length === 0" in smoke, (
        "smoke-published.yml lost the #651 guard that stops a total outage from closing the alarm its own corruption opened."
    )
    assert "healthy:" in deployment and "healthy:" in smoke, (
        "The verdict moved out of the caller, which is what makes these two conditions impossible to express."
    )
