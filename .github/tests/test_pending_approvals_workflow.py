"""Tests for the monitor that notices a run waiting on the production gate.

`check-pending-approvals.yml` exists because the platform's own notice does not
arrive (#701). Measured before it was built, run #21 of Publish vector data
waited 8h52m unnoticed. The Actions notification setting is not the cause and
not the fix - that channel fires when a run you triggered has *completed*, so
it cannot carry a pending approval at any setting; the approval notice is a
separate email to the environment's required reviewers, routed through account
settings no checkout can read. Which is the case for reporting into the
repository instead.

What is asserted here is the handful of properties that would let it go quiet
again without failing anything:

**It must not be able to approve.** `deployments: write` is what approving a
pending deployment needs. Its absence is the difference between "approves
nothing, ever" being a property of the token and being a sentence in a comment.

**It must stay scoped to `waiting`.** That status is the environment gate.
`action_required` is the unrelated fork-and-secrets approval BRANCHING.md
documents, and folding the two together would make the environment column
meaningless for half the rows.

**Its cadence must stay useful and off the hour.** Thirty minutes is the
worst-case silence the issue argued for; the hour marks are where GitHub queues
everyone's cron behind everyone else's.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "check-pending-approvals.yml"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def source():
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _crons(workflow):
    # `on` parses as the boolean True under YAML 1.1, which is why this is not
    # simply workflow["on"] - the same footgun test_supabase_keepalive_workflow
    # documents.
    triggers = workflow.get("on", workflow.get(True))
    return [entry["cron"] for entry in triggers["schedule"]]


# --- What it is allowed to do ---------------------------------------------


def test_it_cannot_approve_the_thing_it_watches(workflow):
    """A monitor that could approve a production deployment would be a way
    around RELEASING.md §12 rather than a notice about it."""
    permissions = workflow["permissions"]
    assert "deployments" not in permissions, (
        "Approving a pending deployment needs `deployments: write`. A monitor that holds it is one "
        "compromised action away from shipping to hikers without anybody deciding to."
    )
    assert permissions["actions"] == "read"
    assert permissions["issues"] == "write"


def test_it_holds_no_credentials(source):
    """Its whole input is this repository's own run list. Nothing here should
    ever need R2, Supabase or Cloudflare."""
    reads = set(re.findall(r"\bsecrets\.([A-Za-z_][A-Za-z0-9_]*)", source))
    assert not reads - {"GITHUB_TOKEN"}, f"This monitor grew a credential it has no use for: {sorted(reads - {'GITHUB_TOKEN'})}"


# --- What it looks at ------------------------------------------------------


def test_it_asks_for_waiting_runs_specifically(source):
    assert "status: 'waiting'" in source, (
        "Dropping the filter would make this list every run in the repository, and the issue would stop "
        "being about approvals at all."
    )


def test_action_required_is_not_quietly_folded_in(workflow, source):
    """The two gates have different audiences and different remedies. If a
    later change does want both, it needs a column saying which - so this
    failing is a prompt to design that, not to delete the assertion."""
    script = yaml.dump(workflow)
    assert "action_required" not in script, (
        "`action_required` is the fork-and-secrets approval, not the environment gate. Mixing them makes "
        "the `environment` column meaningless for half the rows."
    )


def test_a_run_that_vanishes_mid_check_does_not_cost_the_alert(source):
    """A waiting run can be approved, cancelled or expire between the listing
    and the per-run call. Losing the whole notice to a 404 on one of four is
    the failure mode worth a try/catch."""
    assert "catch (error)" in source and "core.warning" in source, (
        "The per-run pending-deployments read lost its tolerance, so one vanished run now takes the "
        "notice for every other run with it."
    )


# --- When it looks --------------------------------------------------------


def test_it_checks_at_least_every_thirty_minutes(workflow):
    """The cadence is the worst-case silence, and #701 measured what that is
    worth: 8h52m of not knowing, against a 30-day expiry at the far end."""
    minutes = []
    for cron in _crons(workflow):
        field = cron.split()[0]
        assert field != "*", "every minute is not a cadence, it is a rate limit incident"
        minutes.extend(int(part) for part in field.split(","))

    minutes.sort()
    assert minutes, "the schedule vanished, and with it the whole point of the monitor"

    # Wrap around the hour so the gap from the last fire to the first of the
    # next hour is measured too - `5,10 * * * *` is twice an hour and a
    # 55-minute silence, which the naive difference would miss.
    gaps = [b - a for a, b in zip(minutes, minutes[1:])] + [60 - minutes[-1] + minutes[0]]
    assert max(gaps) <= 30, (
        f"The longest silence is {max(gaps)} minutes. The half-hour is what makes this better than "
        f"noticing at the next daily monitor."
    )


def test_it_stays_off_the_hour(workflow):
    """Every cron in this directory records the same reason: GitHub queues
    everything submitted at :00 behind everyone else's."""
    for cron in _crons(workflow):
        for part in cron.split()[0].split(","):
            assert int(part) % 30 != 0, (
                f"`{cron}` fires on an hour or half-hour mark, where GitHub's scheduler is most contended "
                f"and a cheap job waits behind everyone else's."
            )


def test_it_can_be_run_by_hand(workflow):
    triggers = workflow.get("on", workflow.get(True))
    assert "workflow_dispatch" in triggers, (
        "The first thing anybody does with a monitor that seems quiet is run it, and the second is edit it."
    )


# --- How it reports -------------------------------------------------------


def test_it_shares_the_deployment_health_label_without_sharing_an_issue(source):
    """check-deployment.yml and smoke-published.yml already share this label.
    The module matches on label *and* title, so a third sharer is fine and a
    duplicated title is not."""
    assert "ISSUE_LABEL: deployment-health" in source

    titles = set()
    for path in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
        found = re.search(r'^\s*ISSUE_TITLE:\s*"?([^"\n]+)"?\s*$', path.read_text(encoding="utf-8"), re.M)
        if found:
            titles.add((found.group(1).strip(), path.name))

    by_title = {}
    for title, name in titles:
        by_title.setdefault(title, []).append(name)
    clashes = {title: names for title, names in by_title.items() if len(names) > 1}
    assert not clashes, f"Two monitors would fight over one issue, each overwriting the other's findings: {clashes}"


# --- What it actually writes ----------------------------------------------
#
# The half above reads the YAML; this half runs the JavaScript inside it. The
# distinction earns its keep - the script is a block string as far as YAML is
# concerned, so a bug in it parses, lints and reaches the cron unchallenged,
# and the cron is the only thing that ever runs it. The first draft shipped a
# table whose rows carried one more cell than the header, which every
# string-matching assertion above was happy with.
#
# Driven under `node` against a stubbed Octokit, for the reason
# test_tracking_issue.py gives for doing the same: a test of a paraphrase
# proves nothing about the artifact CI runs.

HARNESS = """
const fs = require('fs')
const body = fs.readFileSync(process.argv[1], 'utf8')
const fixture = JSON.parse(process.argv[2])

const calls = []
const github = {
  paginate: async (fn, args) => fn(args),
  rest: {
    issues: {
      listForRepo: async () => (fixture.existing ? [fixture.existing] : []),
      create: async (a) => { calls.push({call: 'create', ...a}); return {data: {number: 702}} },
      update: async (a) => { calls.push({call: 'update', ...a}) },
      createComment: async (a) => { calls.push({call: 'createComment', ...a}) },
    },
    actions: {
      listWorkflowRunsForRepo: async () => fixture.runs,
      getPendingDeploymentsForRun: async ({run_id}) => {
        if (fixture.unreadable) throw new Error('Not Found')
        return {data: [{environment: {name: 'production'}}]}
      },
    },
  },
}
const context = {repo: {owner: 'OurHike', repo: 'OurHike'}}
const core = {info: () => {}, warning: () => {}}

process.env.ISSUE_TITLE = 'Runs waiting for approval'
process.env.ISSUE_LABEL = 'deployment-health'
process.env.RUN_URL = 'https://example.invalid/run'

const script = new Function('github', 'context', 'core', 'require', `return (async () => {${body}})()`)
script(github, context, core, require)
  .then(() => console.log(JSON.stringify(calls)))
  .catch((error) => { console.error(error.stack); process.exit(1) })
"""


@pytest.fixture(scope="module")
def script_body(workflow, tmp_path_factory):
    """The inline `script:` lifted out of the github-script step."""
    step = next(s for s in workflow["jobs"]["check"]["steps"] if "github-script" in str(s.get("uses", "")))
    path = tmp_path_factory.mktemp("script") / "body.js"
    path.write_text(step["with"]["script"], encoding="utf-8")
    return path


def drive(script_body, runs, existing=None, unreadable=False):
    """Run the real script once and return the API calls it made."""
    fixture = {"runs": runs, "existing": existing, "unreadable": unreadable}
    completed = subprocess.run(
        ["node", "-e", HARNESS, "--", str(script_body), json.dumps(fixture)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, "GITHUB_WORKSPACE": str(REPO_ROOT)},
    )
    assert completed.returncode == 0, f"the script threw:\n{completed.stderr}"
    return json.loads(completed.stdout)


def a_run(number=21, waited_hours=9, name="Publish vector data", run_id=None):
    started = datetime.now(timezone.utc) - timedelta(hours=waited_hours)
    return {
        "id": run_id if run_id is not None else 31712795726 + number,
        "run_number": number,
        "name": name,
        "html_url": f"https://github.com/OurHike/OurHike/actions/runs/{31712795726 + number}",
        "run_started_at": started.isoformat().replace("+00:00", "Z"),
        "created_at": started.isoformat().replace("+00:00", "Z"),
        "triggering_actor": {"login": "jaimito-asuntos-gringuenos"},
    }


def body_of(calls, kind):
    return next(call["body"] for call in calls if call["call"] == kind)


def table_rows(body):
    lines = [line for line in body.splitlines() if line.startswith("|")]
    return [line for line in lines if not set(line) <= set("|- ")]


needs_node = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is not on PATH; CI runners always have it and this exercises the real script.",
)


@needs_node
def test_it_opens_an_issue_naming_the_waiting_run(script_body):
    calls = drive(script_body, [a_run(number=21, waited_hours=9)])
    assert [c["call"] for c in calls] == ["create"]

    body = body_of(calls, "create")
    assert "#21" in body
    assert "Publish vector data" in body
    assert "`production`" in body, "The environment is the fact that decides whether to go and look."
    assert "9h" in body, "The age is the number that makes this actionable rather than merely true."


@needs_node
def test_every_row_carries_exactly_as_many_cells_as_the_header(script_body):
    """The bug the string-matching half could not see: a row with a trailing
    empty cell renders as a ragged table, and the column it appears to add is
    the one a reader would take for the expiry."""
    body = body_of(drive(script_body, [a_run(), a_run(number=22, waited_hours=1)]), "create")
    rows = table_rows(body)
    assert len(rows) == 3, "one header plus two runs"

    widths = {row.count(" | ") for row in rows}
    assert len(widths) == 1, "The rows and the header disagree about how many columns this table has:\n  " + "\n  ".join(rows)


@needs_node
def test_an_empty_queue_closes_the_issue(script_body):
    calls = drive(script_body, [], existing={"number": 702, "title": "Runs waiting for approval", "body": "old"})
    assert [c["call"] for c in calls] == ["createComment", "update"]
    assert next(c for c in calls if c["call"] == "update")["state"] == "closed"


@needs_node
def test_nothing_waiting_and_nothing_open_stays_quiet(script_body):
    assert drive(script_body, []) == []


@needs_node
def test_a_run_joining_an_open_episode_is_announced_and_the_first_is_not(script_body):
    """`concurrency: publish-data` queues dispatches behind one another, so
    this is the ordinary case rather than the rare one. Silence here would
    announce the first run of an episode and nothing after it."""
    first = a_run(number=21, waited_hours=9)
    opened = drive(script_body, [first])

    second = a_run(number=22, waited_hours=1)
    calls = drive(
        script_body,
        [first, second],
        existing={
            "number": 702,
            "title": "Runs waiting for approval",
            "body": body_of(opened, "create"),
        },
    )

    assert [c["call"] for c in calls] == ["update", "createComment"]
    comment = body_of(calls, "createComment")
    assert "#22" in comment
    assert "#21" not in comment, (
        "The run that was already on the issue got re-announced, which is the comment-per-run noise the "
        "tracking issue exists to avoid."
    )


@needs_node
def test_a_run_whose_environment_cannot_be_read_still_reaches_the_table(script_body):
    """A waiting run can be approved, cancelled or expire between the listing
    and the per-run call. Losing the notice for the other three to a 404 on
    one is the failure worth tolerating."""
    body = body_of(drive(script_body, [a_run()], unreadable=True), "create")
    assert "#21" in body, "One unreadable environment took the whole alert with it."


@needs_node
def test_a_run_near_the_30_day_expiry_is_marked(script_body):
    """GitHub fails an unapproved deployment at 30 days, which turns "this is
    waiting" into "this is about to be lost"."""
    body = body_of(drive(script_body, [a_run(waited_hours=28 * 24)]), "create")
    assert "⚠️" in body, "A run three days from expiring reads the same as one dispatched this morning."
