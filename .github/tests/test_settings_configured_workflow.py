"""settings-configured.yml reads each setting by name and never `toJSON(secrets)`.

THE BUG THIS EXISTS FOR. The weekly check that notices a revoked R2 token
before a publish fails on it had never once run. Every run of the file since
the #679 split - the four Monday fires from 2026-08-24 to 2026-09-14 and a
manual dispatch on `main` on 2026-09-17 (run 35225565659) - concluded
`action_required` within a second of being created, with zero jobs. GitHub
refuses to run a workflow that resolves the whole context with
`toJSON(secrets)`, and this was the one file here that did; every other
workflow reads secrets one name at a time and runs. BRANCHING.md had
recorded the same signature on pull requests and read it as a gate on
editing a secrets-reading workflow; the dispatch on `main` is what showed
the gate belongs to the expression.

So the step now names every setting `.github/expected-settings.yml`
declares, and this file holds the two lists to each other: a setting added
to the manifest and not to the workflow is a red test rather than a check
that quietly stopped covering it. The reduction to names is run here with
fake values, because "never a value" is the security argument of the whole
workflow and a docstring is not where that should be held.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

GITHUB_DIR = Path(__file__).resolve().parents[1]
WORKFLOW = GITHUB_DIR / "workflows" / "settings-configured.yml"
MANIFEST = GITHUB_DIR / "expected-settings.yml"

SECRET_PREFIX = "OURHIKE_SECRET__"
VARIABLE_PREFIX = "OURHIKE_VARIABLE__"


def _names_step() -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps") or []:
            if step.get("id") == "names":
                return step
    raise LookupError(f"{WORKFLOW.name} has no step with id 'names'")


def _expected_env() -> dict[str, str]:
    """One entry per declared setting, on the tab(s) the manifest declares.
    A github-provided setting is minted per run and is nobody's to configure."""
    settings = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["settings"]
    env: dict[str, str] = {}
    for name, spec in settings.items():
        if spec["where"] == "secret":
            env[f"{SECRET_PREFIX}{name}"] = f"${{{{ secrets.{name} }}}}"
        elif spec["where"] == "variable":
            env[f"{VARIABLE_PREFIX}{name}"] = f"${{{{ vars.{name} }}}}"
            if spec.get("also-accepted-as-secret"):
                env[f"{SECRET_PREFIX}{name}"] = f"${{{{ secrets.{name} }}}}"
    return env


def _strings(node):
    """Every string anywhere in the parsed workflow - parsed rather than the
    raw text, because the file's own comments name the expression it must
    not use, for the reader who wonders why the list is spelled out."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(key)
            yield from _strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)


def test_the_workflow_never_resolves_a_whole_context():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for expression in ("toJSON(secrets)", "toJSON(vars)"):
        used = [text for text in _strings(workflow) if expression in text]
        assert used == [], f"{WORKFLOW.name} uses {expression}, which GitHub answers with action_required and zero jobs: {used}"


def test_the_step_names_every_declared_setting_and_nothing_else():
    assert _names_step()["env"] == _expected_env()


def test_the_manifest_has_settings_on_both_tabs():
    """The list above is only a check while the manifest declares both kinds."""
    env = _expected_env()
    assert any(key.startswith(SECRET_PREFIX) for key in env)
    assert any(key.startswith(VARIABLE_PREFIX) for key in env)


def test_the_reduction_emits_names_only_and_drops_empty_values(tmp_path):
    """The step's own script, run with fake values: the output carries the
    names whose values were non-empty, and never a value."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "python").symlink_to(sys.executable)
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")

    completed = subprocess.run(
        ["bash", "-e", "-c", _names_step()["run"]],
        env={
            "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
            "GITHUB_OUTPUT": str(output),
            f"{SECRET_PREFIX}R2_BUCKET": "hunter2-bucket",
            f"{SECRET_PREFIX}R2_ENDPOINT_URL": "",
            f"{VARIABLE_PREFIX}DATA_BASE_URL": "https://data.example.org",
            f"{VARIABLE_PREFIX}API_BASE_URL": "",
        },
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    written = output.read_text(encoding="utf-8")
    assert written == 'secrets=["R2_BUCKET"]\nvariables=["DATA_BASE_URL"]\n'
    assert "hunter2" not in written and "example.org" not in written
