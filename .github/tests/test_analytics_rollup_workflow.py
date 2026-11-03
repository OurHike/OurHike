"""Tests for the nightly usage rollup and its checks (`analytics-rollup.yml`, #1902).

Two properties, each of which would fail quietly:

**A failed rollup still reaches the checks and the issue.** The rollup is the
job that deletes usage rows at six months, and `POST /usage-events` stops
collecting once it has not run for `analytics_rollup_stale_days`. A step's
`if:` without `always()` is skipped as soon as an earlier step fails, so the
night the rollup broke was the one night nothing said so.

**A failed archive neither stops the rollup nor goes unrecorded** (#1923).
The archive runs first, so the rollup counts rows held after the move, and a
step after a failed one is skipped unless its `if:` says otherwise - so the
night the archive broke would also be the night the six-month deletion did
not run. Each job archives into its own environment's bucket with its own
token, and only the archive step holds them: the archive's role can read
`sealed`, which neither the rollup's nor the checks' can.

**A check that starts failing on an open issue is announced.** Updating an
issue body notifies nobody (tracking-issue.js), so without `announce` a
second fault joining an open episode would wait for somebody to reread the
issue. Driven under `node` with the real script, as
test_pending_approvals_workflow.py drives its own.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "analytics-rollup.yml"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _step(job: dict, name_starts: str) -> dict:
    return next(step for step in job["steps"] if step.get("name", "").startswith(name_starts))


@pytest.mark.parametrize("job_id", ["ua", "production"])
def test_the_checks_run_after_a_failed_rollup_and_are_told_it_failed(workflow, job_id):
    job = workflow["jobs"][job_id]
    rollup = _step(job, "Roll up")
    checks = _step(job, "Check ")

    assert rollup.get("id") == "rollup"
    assert checks["if"].replace(" ", "").startswith("always()&&steps.can.outputs.go=='true'")
    assert checks["env"]["ROLLUP_OUTCOME"] == "${{ steps.rollup.outcome }}"
    assert '--rollup-outcome "$ROLLUP_OUTCOME"' in checks["run"]


@pytest.mark.parametrize("job_id", ["ua", "production"])
def test_the_archive_runs_before_the_rollup_and_a_failed_one_does_not_skip_it(workflow, job_id):
    job = workflow["jobs"][job_id]
    names = [step.get("name", "") for step in job["steps"]]
    archive = _step(job, "Archive ")
    rollup = _step(job, "Roll up")

    assert archive.get("id") == "archive"
    assert names.index(archive["name"]) < names.index(rollup["name"])
    condition = rollup["if"].replace(" ", "")
    assert "!cancelled()" in condition, "without it, the night the archive fails the rollup is skipped too"
    assert "steps.install.outcome=='success'" in condition, "a failed install must still stop the rollup"


@pytest.mark.parametrize("job_id", ["ua", "production"])
def test_the_checks_are_told_whether_the_archive_failed(workflow, job_id):
    checks = _step(workflow["jobs"][job_id], "Check ")

    assert checks["env"]["ARCHIVE_OUTCOME"] == "${{ steps.archive.outcome }}"
    assert '--archive-outcome "$ARCHIVE_OUTCOME"' in checks["run"]


@pytest.mark.parametrize(
    ("job_id", "prefix", "bucket"),
    [("ua", "UA_", "ourhike-usage-ua"), ("production", "PRODUCTION_", "ourhike-usage-production")],
)
def test_each_job_archives_into_its_own_bucket_with_its_own_credentials(workflow, job_id, prefix, bucket):
    """The #1923 poll's third answer: one bucket and one token per environment."""
    env = _step(workflow["jobs"][job_id], "Archive ")["env"]

    assert env["USAGE_ARCHIVE_R2_BUCKET"] == bucket
    assert env["DATABASE_URL"] == f"${{{{ secrets.{prefix}ANALYTICS_ARCHIVE_DATABASE_URL }}}}"
    for half in ("ACCESS_KEY_ID", "SECRET_ACCESS_KEY"):
        assert env[f"USAGE_ARCHIVE_R2_{half}"] == f"${{{{ secrets.{prefix}USAGE_ARCHIVE_R2_{half} }}}}"


@pytest.mark.parametrize("job_id", ["ua", "production"])
def test_only_the_archive_steps_hold_the_archive_credentials(workflow, job_id):
    for step in workflow["jobs"][job_id]["steps"]:
        if step.get("id") in ("archive", "archive_can"):
            continue
        text = json.dumps(step)
        assert "ARCHIVE_DATABASE_URL" not in text, f"{step.get('name')} holds the URL of a role that reads `sealed`"
        assert "USAGE_ARCHIVE_R2" not in text, f"{step.get('name')} holds the usage bucket's token"


def test_the_issue_step_runs_after_a_failed_rollup_but_only_when_the_checks_ran(workflow):
    issue = _step(workflow["jobs"]["production"], "Open, update, or close")
    condition = issue["if"].replace(" ", "")

    assert condition.startswith("always()&&")
    assert "steps.quality.outcome=='success'" in condition, "a run that could not look must not close the issue (#651)"


# A stand-in for github-script's `github`: records every call. Same shape as
# test_pending_approvals_workflow.py's.
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
      create: async (a) => { calls.push({call: 'create', ...a}); return {data: {number: 1903}} },
      update: async (a) => { calls.push({call: 'update', ...a}) },
      createComment: async (a) => { calls.push({call: 'createComment', ...a}) },
    },
  },
}
const context = {repo: {owner: 'OurHike', repo: 'OurHike'}}
const core = {info: () => {}, warning: () => {}}

process.env.ISSUE_TITLE = 'Usage numbers look wrong'
process.env.ISSUE_LABEL = 'usage-data-health'
process.env.RUN_URL = 'https://example.invalid/run'

const script = new Function('github', 'context', 'core', 'require', `return (async () => {${body}})()`)
script(github, context, core, require)
  .then(() => console.log(JSON.stringify(calls)))
  .catch((error) => { console.error(error.stack); process.exit(1) })
"""

needs_node = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is not on PATH; CI runners always have it and this exercises the real script.",
)


@pytest.fixture(scope="module")
def script_body(workflow, tmp_path_factory):
    step = _step(workflow["jobs"]["production"], "Open, update, or close")
    path = tmp_path_factory.mktemp("script") / "body.js"
    path.write_text(step["with"]["script"], encoding="utf-8")
    return path


def _finding(check: str, scope: str, status: str = "low", day: str = "2026-11-19") -> dict:
    return {"key": f"{check}|{scope}", "check": check, "scope": scope, "status": status, "day": day}


def drive(script_body, tmp_path, open_findings, existing=None):
    """Run the real script against a verdict file, and return the API calls it made."""
    (tmp_path / "backend").mkdir(exist_ok=True)
    verdict = {"checked_at": "2026-11-20T10:30:00Z", "open": open_findings}
    (tmp_path / "backend" / "quality-verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    completed = subprocess.run(
        ["node", "-e", HARNESS, "--", str(script_body), json.dumps({"existing": existing})],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "GITHUB_WORKSPACE": str(REPO_ROOT)},
    )
    assert completed.returncode == 0, f"the script threw:\n{completed.stderr}"
    return json.loads(completed.stdout)


@needs_node
def test_the_slice_is_written_as_code_like_the_check(script_body, tmp_path):
    calls = drive(script_body, tmp_path, [_finding("sessions", "platform:android", "zero")])

    body = next(call["body"] for call in calls if call["call"] == "create")
    assert "| `sessions` | `platform:android` | zero |" in body


@needs_node
def test_a_new_check_on_an_open_issue_is_announced_and_an_old_one_is_not(script_body, tmp_path):
    marker = '<!-- tracking-issue first-seen {"rows_refused|*":"2026-11-18"} -->'
    existing = {"number": 1903, "title": "Usage numbers look wrong", "body": f"earlier\n\n{marker}"}
    open_findings = [_finding("rows_refused", "*", "warn"), _finding("rollup_failed", "*", "warn", day="2026-11-20")]

    calls = drive(script_body, tmp_path, open_findings, existing=existing)

    assert [call["call"] for call in calls] == ["update", "createComment"]
    comment = calls[1]["body"]
    assert "`rollup_failed`" in comment
    assert "rows_refused" not in comment, "a key already on the issue stays silent"


@needs_node
def test_an_open_issue_with_nothing_new_is_updated_silently(script_body, tmp_path):
    marker = '<!-- tracking-issue first-seen {"rows_refused|*":"2026-11-18"} -->'
    existing = {"number": 1903, "title": "Usage numbers look wrong", "body": f"earlier\n\n{marker}"}

    calls = drive(script_body, tmp_path, [_finding("rows_refused", "*", "warn")], existing=existing)

    assert [call["call"] for call in calls] == ["update"]
