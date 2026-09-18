"""publish-vector-data.yml's archive-photograph carry fails when the run listing fails.

THE BUG THIS EXISTS FOR. The step lists nynjtc-archive-recovery.yml's recent
runs with `gh api` and walks them for the largest unexpired artifact. It did
so as `for run in $(gh api ...)`, and `set -e` does not see a failure inside
a `for` word list: a rate-limited or unreachable API produced an empty list,
the step printed "No unexpired nynjtc-archive-recovery artifact in the last
20 runs" and exited 0, and the publish went on without the photographs it
was told to carry. publish.py's promise check catches the ones no earlier
publish uploaded, but as a failed publish half an hour later with a message
about photographs rather than about the API.

Tested by running the step's own script with a stub `gh` and `python` on
PATH, from an empty working directory, so the only thing under test is what
the shell does with a listing that fails.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish-vector-data.yml"
STEP_NAME = "Carry the confirmed archive photographs to the publisher"


def _step() -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps") or []:
            if step.get("name") == STEP_NAME:
                return step
    raise LookupError(f"{WORKFLOW.name} has no step named {STEP_NAME!r}")


def _executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run(tmp_path: Path, *, listing: str) -> subprocess.CompletedProcess:
    """`listing` is what the stub `gh` does with the runs request: "fails"
    exits 1 with an error, anything else is printed as the id list."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    # The step asks python how many archive photographs the reviewed file
    # confirms; three is enough to make it look for the artifact.
    _executable(stubs / "python", "#!/usr/bin/env bash\necho 3\n")
    gh = [
        "#!/usr/bin/env bash",
        'case "$*" in',
        "  *runs?per_page*)",
        '    if [ "$STUB_LISTING" = "fails" ]; then echo "gh: HTTP 403: API rate limit exceeded" >&2; exit 1; fi',
        "    printf '%s' \"$STUB_LISTING\"",
        "    ;;",
        '  *) echo "unexpected gh call: $*" >&2; exit 1;;',
        "esac",
    ]
    _executable(stubs / "gh", "\n".join(gh) + "\n")
    workdir = tmp_path / "pipeline"
    workdir.mkdir()
    return subprocess.run(
        ["bash", "-e", "-c", _step()["run"]],
        cwd=workdir,
        env={
            **os.environ,
            "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
            "GH_TOKEN": "not-a-token",
            "GITHUB_REPOSITORY": "OurHike/OurHike",
            "STUB_LISTING": listing,
        },
        capture_output=True,
        text=True,
    )


def test_a_failed_run_listing_fails_the_step_rather_than_reading_as_no_artifact(tmp_path):
    completed = _run(tmp_path, listing="fails")

    assert completed.returncode != 0
    assert "No unexpired" not in completed.stdout
    assert "rate limit" in completed.stderr


def test_a_listing_with_no_runs_still_says_so_and_carries_nothing(tmp_path):
    """The honest empty case is unchanged: no runs is no artifact, exit 0,
    and publish.py's promise check is what decides whether that matters."""
    completed = _run(tmp_path, listing="")

    assert completed.returncode == 0, completed.stderr
    assert "No unexpired nynjtc-archive-recovery artifact" in completed.stdout
