"""publish-conditions.yml's dlt extract runs with its own leg's conditions database URL and no other, anywhere it can read.

The extract step's env hands each leg its own database's URL as
CONDITIONS_DATABASE_URL, the one name dlt and the rest of
requirements-extract.txt read. Both secrets are named literally ("Is there a
database to read" says why), each behind its own leg's test, so an unset
secret is an empty string rather than the other leg's.

PICKING IT IN THE SCRIPT AND UNSETTING THE REST WAS NOT ENOUGH (review finding
SEC-7 of PR #1805 — dlt → dbt re-platform as one go/no-go change). The step
used to name both URLs in its env and `unset` them before the extract, which
keeps a variable from the shell's later children, not from the shell's own
/proc/<pid>/environ, which a child running as the same user reads: the step's
bash held production's URL there on every UA run, and the extract's python is
that bash's child. So the step's env, evaluated here for each leg by
test_conditions_production_leg_needs_main.py's evaluator of GitHub's
expression language, must not carry the other leg's URL, and the stand-in for
the extract's python reads its own environment and every ancestor's up to
this test's process.

WHAT THIS DOES NOT COVER. GitHub sends the runner every secret the job
references, production's on the UA leg included, and the runner's worker
process holds them in its memory (not its environment); a dependency that can
read another process's memory is past what a step's env can keep from it. A
GitHub environment per leg, holding only that leg's URL, is the repository
setting that would close it (SEC-7's full fix, the maintainer's).
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

from test_conditions_production_leg_needs_main import _evaluate, _expression

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish-conditions.yml"
STEP = "Extract this leg's closures and warnings into the raw store (dbt path)"
SECRETS = {
    "PRODUCTION_CONDITIONS_DATABASE_URL": "postgresql://production.invalid/conditions",
    "UA_CONDITIONS_DATABASE_URL": "postgresql://ua.invalid/conditions",
    "R2_RAW_BUCKET": "raw-bucket",
}
HOSTS = {"production": "production.invalid", "ua": "ua.invalid"}


def _step() -> dict:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["publish"]["steps"]
    return next(step for step in steps if step.get("name") == STEP)


def _step_env(environment: str, secrets: dict[str, str] | None = None) -> dict[str, str]:
    """The step's `env:` as GitHub hands it to one leg's shell: each `${{ }}` evaluated, a null as an empty string."""
    context = {"matrix": {"data_environment": environment}, "secrets": SECRETS if secrets is None else secrets}

    def evaluated(match: re.Match) -> str:
        found = _evaluate(_expression(match.group(0)), context)
        return "" if found is None or found is False else str(found)

    return {name: re.sub(r"\$\{\{.*?\}\}", evaluated, str(value)) for name, value in _step()["env"].items()}


def _run_extract(tmp_path: Path, environment: str) -> tuple[dict[str, str], list[str]]:
    """The step's script under bash, with the leg's evaluated env: the environment the extract's stand-in started
    with, and every line of each ancestor's /proc/<pid>/environ, from its parent up to this test's process."""
    python = tmp_path / "extract" / "bin" / "python"
    python.parent.mkdir(parents=True)
    seen, ancestors = tmp_path / "env.txt", tmp_path / "ancestors.txt"
    python.write_text(
        "#!/bin/bash\n"
        f'env > "{seen}"\n'
        "pid=$PPID\n"
        f'while [ -n "$pid" ] && [ "$pid" -gt 1 ] && [ "$pid" != "{os.getpid()}" ]; do\n'
        f'  tr "\\0" "\\n" < "/proc/$pid/environ" >> "{ancestors}"\n'
        "  pid=$(awk '/^PPid:/ {print $2}' \"/proc/$pid/status\")\n"
        "done\n"
    )
    python.chmod(python.stat().st_mode | stat.S_IXUSR)
    env = {
        **_step_env(environment),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(tmp_path / "output"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
    }
    subprocess.run(["bash", "-e", "-c", _step()["run"]], env=env, check=True, capture_output=True, text=True)
    own = dict(line.split("=", 1) for line in seen.read_text().splitlines() if "=" in line)
    return own, ancestors.read_text().splitlines()


def test_the_step_names_both_legs_secrets_literally_in_its_one_url():
    """The case this file guards exists: both secrets are in the step's env, each by its own name, and no other name
    in the step carries a database URL."""
    env = _step()["env"]
    assert "secrets.PRODUCTION_CONDITIONS_DATABASE_URL" in env["CONDITIONS_DATABASE_URL"]
    assert "secrets.UA_CONDITIONS_DATABASE_URL" in env["CONDITIONS_DATABASE_URL"]
    assert [name for name, value in env.items() if "CONDITIONS_DATABASE_URL" in str(value)] == ["CONDITIONS_DATABASE_URL"]


@pytest.mark.parametrize("environment", sorted(HOSTS))
def test_each_leg_is_handed_its_own_url_and_never_the_others_even_when_its_own_secret_is_unset(environment):
    other = next(leg for leg in HOSTS if leg != environment)
    assert HOSTS[environment] in _step_env(environment)["CONDITIONS_DATABASE_URL"]
    unset = {name: value for name, value in SECRETS.items() if not name.startswith(environment.upper())}
    assert _step_env(environment, unset)["CONDITIONS_DATABASE_URL"] == ""
    for secrets in (SECRETS, unset):
        env = _step_env(environment, secrets)
        assert [name for name, value in env.items() if HOSTS[other] in value] == [], f"{other}'s URL reaches {environment}"


@pytest.mark.parametrize("environment", sorted(HOSTS))
def test_the_extract_runs_with_its_own_legs_url_alone(tmp_path, environment):
    own, _ = _run_extract(tmp_path, environment)

    assert HOSTS[environment] in own["CONDITIONS_DATABASE_URL"]
    assert "PRODUCTION_URL" not in own
    assert "UA_URL" not in own
    other = next(leg for leg in HOSTS if leg != environment)
    assert [name for name, value in own.items() if HOSTS[other] in value] == []


@pytest.mark.parametrize("environment", sorted(HOSTS))
def test_no_process_above_the_extract_holds_the_other_legs_url_in_its_environment(tmp_path, environment):
    """SEC-7's probe (`/proc/<parent>/environ` read by the extract's own process), over the whole chain of shells."""
    _, ancestors = _run_extract(tmp_path, environment)

    assert ancestors, "the stand-in read no ancestor's environment, so this test would pass on anything"
    other = next(leg for leg in HOSTS if leg != environment)
    assert [line.split("=", 1)[0] for line in ancestors if HOSTS[other] in line] == []
