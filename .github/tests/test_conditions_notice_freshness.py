"""publish-conditions.yml's dbt path measures the notice sources' freshness after it has published, and only that is red.

Decision 100 (the maintainer's poll of 2026-10-07, on round-2 finding ARC-5:
"Red after 24h. But this should be Red in the data source freshness feature
of dbt. Not blocking a datasource pipeline"): a notice source that has gone 24
hours without being read or confirmed unchanged turns red in dbt's source
freshness, and the check never holds back a publish. So the step runs
`dbt source freshness` after "Publish to R2" and after the build, which saves
the row history, and after every other red step, so none of theirs is lost to
its failure; and its exit is dbt's. The step's script runs here under bash,
with a stand-in for dbt that writes down what it was asked and answers with
a chosen exit and a sources.json.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish-conditions.yml"
STEP = "Check the notice sources' freshness, red after 24 hours unread (dbt path)"


def _steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["publish"]["steps"]


def _step() -> dict:
    (step,) = [step for step in _steps() if step.get("name") == STEP]
    return step


def _run(tmp_path: Path, read: str, status: int, results: list[dict]) -> tuple[subprocess.CompletedProcess, str]:
    """The step's script, from a copy of pipeline/dbt's place, with dbt standing in. Returns it and dbt's arguments."""
    dbt = tmp_path / "dbt" / "bin" / "dbt"
    dbt.parent.mkdir(parents=True)
    record = tmp_path / "dbt.args"
    sources = json.dumps({"results": results})
    dbt.write_text(
        f'#!/bin/bash\necho "$@" > "{record}"\nmkdir -p target\ncat > target/sources.json <<\'JSON\'\n{sources}\nJSON\nexit {status}\n'
    )
    dbt.chmod(dbt.stat().st_mode | stat.S_IXUSR)
    workdir = tmp_path / "pipeline" / "dbt"
    workdir.mkdir(parents=True)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "NOTICES_READ": read,
    }
    finished = subprocess.run(["bash", "-e", "-c", _step()["run"]], cwd=workdir, env=env, capture_output=True, text=True)
    return finished, record.read_text() if record.exists() else ""


def _result(table: str, status: str, hours: float) -> dict:
    return {"unique_id": f"source.ourhike.{table}", "status": status, "max_loaded_at_time_ago_in_s": hours * 3600}


def test_the_freshness_step_runs_after_the_publish_and_after_every_other_red_step():
    """After "Publish to R2" so it can never hold one back; after the red steps, because a failed step skips every
    later one whose `if:` does not say otherwise, and theirs say nothing."""
    names = [step.get("name") or step.get("uses") for step in _steps()]
    here = names.index(STEP)
    assert names.index("Publish to R2") < here
    assert names.index("Build the closures and warnings marts and their writers (dbt path)") < here, "history saved"
    reds = [index for index, name in enumerate(names) if str(name).startswith("Fail the run if")]
    assert reds and max(reds) < here, "a red step after this one would be skipped whenever this one is red"


def test_the_freshness_step_runs_whatever_turned_the_run_red_before_it_but_only_after_a_build():
    condition = str(_step()["if"])
    assert "!cancelled()" in condition, "an earlier red step must not hide which sources have gone unread"
    assert "env.PHONE_FILES == 'dbt'" in condition and "steps.build.outcome == 'success'" in condition
    assert "secrets." not in json.dumps(_step()), "it reads the warehouse alone"
    assert _step()["working-directory"] == "pipeline/dbt"
    assert _step()["env"]["NOTICES_READ"] == "${{ steps.notices.outputs.read }}"


@pytest.mark.parametrize(("read", "notices"), [("latest", True), ("older", True), ("none", False), ("unread", False)])
def test_the_notices_jobs_sources_are_measured_only_when_the_build_read_a_notices_copy(tmp_path, read, notices):
    """Their run log rows reach the warehouse only with a served copy (extract/_warehouse.py's add_served()), and
    without one every notices source would read as never read, a red that decision 96's 8 hours and the `unread`
    step already own. The conditions job's own sources are measured every run."""
    finished, argv = _run(tmp_path, read, 0, [])
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert argv.startswith("source freshness --profiles-dir .")
    assert "tag:conditions_job" in argv
    assert ("tag:notices_job" in argv) == notices
    assert ("::notice title=" in finished.stdout) == (not notices)


def test_a_source_past_24_hours_unread_turns_the_step_red_and_the_summary_names_it(tmp_path):
    results = [
        _result("amc.raw_amc__amc_net_closures_notices", "error", 30),
        _result("blm.raw_blm__blm_press_utah", "warn", 13),
        _result("nws.raw_nws__alerts", "pass", 1),
        {"unique_id": "source.ourhike.oprhp.raw_nysparks__oprhp_trail_closures", "status": "runtime error"},
    ]
    finished, _argv = _run(tmp_path, "latest", 1, results)
    assert finished.returncode == 1
    summary = (tmp_path / "summary").read_text()
    assert "4 sources measured: 2 red, 1 warned." in summary, "a source dbt could not measure is red too"
    assert "amc.raw_amc__amc_net_closures_notices`: error, last read or confirmed unchanged 30.0 h ago" in summary
    assert "oprhp.raw_nysparks__oprhp_trail_closures`: runtime error, not measured" in summary
    assert "blm.raw_blm__blm_press_utah" in summary and "nws.raw_nws__alerts" not in summary
    assert "::error title=" in finished.stdout


def test_a_warning_alone_leaves_the_step_green(tmp_path):
    finished, _argv = _run(tmp_path, "latest", 0, [_result("blm.raw_blm__blm_press_utah", "warn", 13)])
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "::error title=" not in finished.stdout
