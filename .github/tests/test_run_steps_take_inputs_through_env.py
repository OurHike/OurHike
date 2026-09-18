"""A `run:` script never has dispatcher- or event-controlled text pasted into it.

`${{ ... }}` is substituted into the script BEFORE bash parses it, so a
free-text `workflow_dispatch` input, a branch name, or a step output that
carries one is not an argument to the script - it is the script. GitHub's
own hardening guide says so; #660 made it this repository's rule ("Through
env, never interpolated") and migrate.yml's UA gate followed it, while its
production gate, three lines under a comment restating the rule, compared
`"${{ github.ref }}"` in shell - the step that decides whether a production
migration proceeds, and git allows quotes and semicolons in a branch name.

Measured 2026-09-17: 16 steps across 7 workflows pasted a free-text input,
`github.ref`, or a step or needs output into their script. All 16 take it
through `env:` now, and this file is what keeps the count at zero.

WHAT IS AND IS NOT FLAGGED. An input typed `boolean`, `choice` or `number`
can only take values the workflow file itself lists or GitHub validates, and
`matrix.*` values are literals in the file too: neither is somebody else's
text, and both stay allowed. Every `type: string` input (and an untyped one,
which GitHub reads as a string), `github.ref`, `head_ref`, `base_ref` and
`ref_name`, anything under `github.event`, and every `steps.*.outputs.*` or
`needs.*.outputs.*` is flagged - the outputs because a step output is
whatever an earlier step echoed, and verify-release.yml's
`steps.can.outputs.base` is `inputs.base` one hop later.

Held alongside, for every `run:` script and not only the rewritten ones:
each parses under `bash -n` once its expressions are replaced by a
placeholder, so a rewrite from an interpolation to `${VAR:+...}` that drops
a quote fails this suite rather than the next dispatch.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"

EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.S)
FLAGGED = re.compile(
    r"\b(inputs\.[A-Za-z0-9_]+"
    r"|github\.(?:ref|ref_name|head_ref|base_ref|event\.[A-Za-z0-9_.]+)"
    r"|steps\.[A-Za-z0-9_-]+\.outputs\.[A-Za-z0-9_-]+"
    r"|needs\.[A-Za-z0-9_-]+\.outputs\.[A-Za-z0-9_-]+)\b"
)
CONSTRAINED_INPUT_TYPES = {"boolean", "choice", "number"}


def _input_types(workflow: dict) -> dict[str, str]:
    # YAML 1.1 reads a bare `on:` key as the boolean True.
    triggers = workflow.get("on", workflow.get(True, {})) or {}
    inputs = ((triggers.get("workflow_dispatch") or {}).get("inputs") or {}) if isinstance(triggers, dict) else {}
    return {name: (spec or {}).get("type", "string") for name, spec in inputs.items()}


def _run_steps():
    """(workflow, job id, step label, shell, script, input types) for every step with a `run:`."""
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        input_types = _input_types(workflow)
        for job_id, job in (workflow.get("jobs") or {}).items():
            for index, step in enumerate(job.get("steps") or []):
                script = step.get("run")
                if script is None:
                    continue
                label = step.get("name") or step.get("id") or f"step {index}"
                yield path.name, job_id, label, step.get("shell"), str(script), input_types


def _pasted_text(script: str, input_types: dict[str, str]) -> list[str]:
    found = []
    for expression in EXPRESSION.finditer(script):
        for match in FLAGGED.finditer(expression.group(1)):
            reference = match.group(1)
            if reference.startswith("inputs.") and input_types.get(reference[len("inputs.") :]) in CONSTRAINED_INPUT_TYPES:
                continue
            found.append(reference)
    return found


def test_there_are_run_scripts_to_check():
    """Hundreds on the day this was written; a parse that found none would
    pass the two tests below over nothing."""
    assert sum(1 for _ in _run_steps()) >= 150


def test_no_run_script_carries_dispatcher_or_event_text():
    offenders = [
        f"{workflow} :: {job_id} :: {label}: {sorted(set(pasted))}"
        for workflow, job_id, label, _shell, script, input_types in _run_steps()
        if (pasted := _pasted_text(script, input_types))
    ]
    assert offenders == [], (
        "These steps paste text the dispatcher or an earlier step controls straight into a shell script. "
        'Hand it over through `env:` and read `"$NAME"` instead (#660):\n  ' + "\n  ".join(offenders)
    )


def test_every_run_script_parses_as_bash():
    """`bash -n` over the script with every `${{ }}` replaced by a placeholder.
    Steps that name a shell other than bash are left to that shell."""
    failures = []
    for workflow, job_id, label, shell, script, _input_types in _run_steps():
        if shell is not None and "bash" not in shell:
            continue
        placeholder_script = EXPRESSION.sub("EXPR", script)
        completed = subprocess.run(["bash", "-n"], input=placeholder_script, capture_output=True, text=True)
        if completed.returncode != 0:
            failures.append(f"{workflow} :: {job_id} :: {label}: {completed.stderr.strip()}")
    assert failures == [], "These run: scripts do not parse:\n  " + "\n  ".join(failures)
