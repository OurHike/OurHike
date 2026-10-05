"""The 35-day alarm and the weekly planner's give-way count a monthly run on main that refreshed UA, green or not.

check-upstream-freshness.yml rings #478 when refresh-reference.yml has not
refreshed UA for 35 days, and build-data-release.yml's give-way stops planning
once the monthly lane has run. Both asked the API for `status=success` runs.
Under decision 49 a monthly run that leaves one layer out still loads the rest
and refreshes UA, and its last job ("Fail the run if a layer was refused on
its own") then fails the run on purpose. Monthly runs 16 (37210020925) and 17
(37232256991) both concluded `failure` that way, so neither check counted
either of them, and neither had a branch filter, so a pull request branch's
green dispatch did count (WF3 of the PR #1805 review).

What counts now is the run's own proof that UA serves what it built: its job
"Confirm UA serves what the build wrote" concluded `success`, on a run of
`main`. These tests run each workflow's own script against a stand-in for the
GitHub API on loopback, so they hold the behaviour, not the wording.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
REPOSITORY = "OurHike/OurHike"
MONTHLY = "refresh-reference.yml"
CONFIRM = "Confirm UA serves what the build wrote"
REFUSED = "Fail the run if a layer was refused on its own"
NOW = datetime.now(timezone.utc)


def _stamp(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(run_id: int, days_ago: float, conclusion: str, confirm: str | None, branch: str = "main") -> dict:
    jobs = [{"name": "Extract the monthly resources into the raw store", "status": "completed", "conclusion": "success"}]
    if confirm is not None:
        jobs.append({"name": CONFIRM, "status": "completed", "conclusion": confirm})
    if conclusion == "failure" and confirm == "success":
        jobs.append({"name": REFUSED, "status": "completed", "conclusion": "failure"})
    return {
        "id": run_id,
        "head_branch": branch,
        "status": "completed",
        "conclusion": conclusion,
        "run_started_at": _stamp(days_ago),
        "html_url": f"https://github.com/{REPOSITORY}/actions/runs/{run_id}",
        "jobs": jobs,
    }


class _Api(BaseHTTPRequestHandler):
    """The three GitHub endpoints the two scripts read, filtered the way GitHub filters them."""

    def log_message(self, *args):  # noqa: D102 - quiet
        pass

    def _json(self, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802 - http.server's name
        url = urlparse(self.path)
        query = {key: values[-1] for key, values in parse_qs(url.query).items()}
        runs = self.server.runs
        base = f"/repos/{REPOSITORY}/actions"
        if url.path == f"{base}/workflows/{MONTHLY}":
            return self._json({"name": "Refresh reference data", "created_at": _stamp(60)})
        if url.path == f"{base}/workflows/{MONTHLY}/runs":
            status = query.get("status")
            if status == "completed":
                runs = [run for run in runs if run["status"] == "completed"]
            elif status:
                runs = [run for run in runs if run["conclusion"] == status]
            if "branch" in query:
                runs = [run for run in runs if run["head_branch"] == query["branch"]]
            size, page = int(query.get("per_page", 30)), int(query.get("page", 1))
            listed = [{**run, "jobs_url": f"http://{self.headers['Host']}{base}/runs/{run['id']}/jobs"} for run in runs]
            shown = [{key: value for key, value in run.items() if key != "jobs"} for run in listed]
            return self._json({"total_count": len(runs), "workflow_runs": shown[(page - 1) * size : page * size]})
        for run in runs:
            if url.path == f"{base}/runs/{run['id']}/jobs":
                return self._json({"total_count": len(run["jobs"]), "jobs": run["jobs"]})
        self.send_error(404)


@pytest.fixture
def api():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Api)
    server.runs = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _script(workflow: str, job: str, step_id: str) -> str:
    steps = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))["jobs"][job]["steps"]
    (step,) = [step for step in steps if step.get("id") == step_id]
    lines = step["run"].splitlines()
    start = next(index for index, line in enumerate(lines) if line.rstrip().endswith("<<'PY'"))
    end = next(index for index, line in enumerate(lines) if index > start and line.strip() == "PY")
    return "\n".join(lines[start + 1 : end])


def _execute(api, tmp_path: Path, workflow: str, job: str, step_id: str, **env: str) -> dict[str, str]:
    output, summary = tmp_path / "output", tmp_path / "summary"
    output.touch()
    summary.touch()
    host, port = api.server_address
    completed = subprocess.run(
        [sys.executable, "-c", _script(workflow, job, step_id)],
        cwd=tmp_path,
        env={
            **os.environ,
            "GH_TOKEN": "a-token-the-stand-in-ignores",
            "REPOSITORY": REPOSITORY,
            "API_URL": f"http://{host}:{port}",
            "GITHUB_OUTPUT": str(output),
            "GITHUB_STEP_SUMMARY": str(summary),
            # The sandbox routes outbound requests through a proxy; the stand-in is on loopback.
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
            **env,
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return dict(line.split("=", 1) for line in output.read_text().splitlines() if "=" in line)


def _alarm(api, tmp_path: Path) -> tuple[dict[str, str], dict]:
    outputs = _execute(
        api, tmp_path, "check-upstream-freshness.yml", "check", "monthly", MONTHLY_WORKFLOW=MONTHLY, MAX_AGE_DAYS="35"
    )
    return outputs, json.loads((tmp_path / "monthly_refresh.json").read_text())


def _plans(api, tmp_path: Path) -> bool:
    outputs = _execute(api, tmp_path, "build-data-release.yml", "give-way", "decide", EVENT="schedule")
    return outputs["plan"] == "true"


def test_a_monthly_run_failed_only_by_a_refused_layer_still_counts_as_refreshing_ua(api, tmp_path):
    """Run 17's shape: the confirm job passed, then the refused-layer job failed the run, five days ago."""
    api.runs = [_run(17, 5, "failure", confirm="success")]

    outputs, answer = _alarm(api, tmp_path)
    assert (outputs["state"], outputs["alarm"]) == ("ok", "false"), answer
    assert answer["since"] == api.runs[0]["run_started_at"] and answer["last_refresh"] == api.runs[0]["html_url"]
    assert not _plans(api, tmp_path), "the monthly lane has refreshed UA, so the weekly planner gives way"


def test_a_run_whose_confirm_job_failed_does_not_count_and_the_last_one_that_passed_dates_the_refresh(api, tmp_path):
    """A build that failed, or a publish cancelled in publish-data (#1513 - A queued publish is silently cancelled
    when another one joins publish-data, and it looks like a green build), refreshed nothing."""
    api.runs = [
        _run(19, 2, "failure", confirm="failure"),
        _run(18, 4, "failure", confirm=None),
        _run(16, 40, "success", confirm="success"),
    ]

    outputs, answer = _alarm(api, tmp_path)
    assert outputs["state"] == "overdue" and answer["since"] == api.runs[2]["run_started_at"], answer


def test_a_pull_request_branchs_green_dispatch_is_not_the_monthly_lane_refreshing_ua(api, tmp_path):
    api.runs = [_run(30, 2, "success", confirm="success", branch="claude/some-branch")]

    outputs, answer = _alarm(api, tmp_path)
    assert outputs["state"] == "overdue" and answer["last_refresh"] is None, answer
    assert _plans(api, tmp_path), "nothing on main has refreshed UA, so the weekly planner keeps planning"


def test_a_green_run_on_main_counts_as_before(api, tmp_path):
    api.runs = [_run(20, 3, "success", confirm="success")]

    outputs, _answer = _alarm(api, tmp_path)
    assert outputs["state"] == "ok"
    assert not _plans(api, tmp_path)


def test_a_dispatch_always_plans_whatever_the_monthly_lane_did(api, tmp_path):
    api.runs = [_run(20, 3, "success", confirm="success")]

    outputs = _execute(api, tmp_path, "build-data-release.yml", "give-way", "decide", EVENT="workflow_dispatch")
    assert outputs["plan"] == "true"
