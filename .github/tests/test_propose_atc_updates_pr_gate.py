"""propose-atc-updates.yml's open-pull-request lookup fails loudly on an API error.

THE BUG THIS EXISTS FOR. The step asked the API for open pull requests from
the proposal branch and piped the answer to `jq 'length'`. GitHub answers an
error with a JSON OBJECT - `{"message": ..., "documentation_url": ...,
"status": ...}`, three keys on a 404, measured 2026-09-17 - and `curl`
without `-f` exits 0 on it. So a rate-limited or unauthorised hour produced
`count=3`, the next step read that as "a pull request already exists", and
the branch was force-pushed with no pull request ever opened, in a run that
stayed green. That is the #1501 gap arriving one step earlier than the
comment about it.

Tested by running the step's own script with a stub `curl` on PATH, because
the failure is in the shell and the shell is what has to be shown refusing.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "propose-atc-updates.yml"
STEP_NAME = "Check for an existing open pull request"

ERROR_OBJECT = (
    '{"message":"API rate limit exceeded for 1.2.3.4.","documentation_url":"https://docs.github.com/rest","status":"403"}'
)


def _step() -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps") or []:
            if step.get("name") == STEP_NAME:
                return step
    raise LookupError(f"{WORKFLOW.name} has no step named {STEP_NAME!r}")


def _stub_curl(directory: Path, body: str, *, honour_fail_flag: bool) -> None:
    """A `curl` that answers `body` with exit 0 - or, when told to honour
    `-f` and given an error body, exits 22 with nothing on stdout, which is
    what the real curl does to a 4xx under `-f`."""
    script = ["#!/usr/bin/env bash", "fail=false", 'for arg in "$@"; do case "$arg" in -f*|--fail) fail=true;; esac; done']
    if honour_fail_flag:
        script.append(
            'if $fail && [ "$STUB_HTTP_ERROR" = "1" ]; then echo "curl: (22) The requested URL returned error: 403" >&2; exit 22; fi'
        )
    script.append(f"printf '%s' '{body}'")
    path = directory / "curl"
    path.write_text("\n".join(script) + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run(
    tmp_path: Path, body: str, *, honour_fail_flag: bool = False, http_error: bool = False
) -> tuple[subprocess.CompletedProcess, str]:
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    _stub_curl(stubs, body, honour_fail_flag=honour_fail_flag)
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    completed = subprocess.run(
        ["bash", "-e", "-c", _step()["run"]],
        env={
            **os.environ,
            "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
            "GH_TOKEN": "not-a-token",
            "REPO": "OurHike/OurHike",
            "GITHUB_OUTPUT": str(output),
            "STUB_HTTP_ERROR": "1" if http_error else "0",
        },
        capture_output=True,
        text=True,
    )
    return completed, output.read_text(encoding="utf-8")


def test_an_error_object_is_a_failure_not_a_count_of_its_keys(tmp_path):
    """The regression: without the type check this wrote count=3."""
    completed, written = _run(tmp_path, ERROR_OBJECT)

    assert completed.returncode != 0
    assert "count=" not in written
    assert "expected a list of pull requests" in completed.stderr


def test_an_http_error_under_fail_flag_is_a_failure(tmp_path):
    """`-f` is the first line of defence: the real curl exits 22 on a 4xx."""
    completed, written = _run(tmp_path, ERROR_OBJECT, honour_fail_flag=True, http_error=True)

    assert completed.returncode != 0
    assert "count=" not in written


@pytest.mark.parametrize(("body", "expected"), [("[]", "count=0"), ('[{"number": 7}]', "count=1")])
def test_a_list_is_counted(tmp_path, body, expected):
    completed, written = _run(tmp_path, body)

    assert completed.returncode == 0, completed.stderr
    assert written.strip() == expected


def test_the_step_asks_curl_to_fail_on_an_http_error():
    """Shape, held alongside behaviour: `-f` is what turns a 403 into a
    non-zero exit before jq ever sees the body."""
    assert "curl -fsS" in _step()["run"]
