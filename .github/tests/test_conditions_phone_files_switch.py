"""publish-conditions.yml's cutover switch has one home, and today's bake is what the schedule runs.

`PHONE_FILES` chooses which pipeline writes a run's phone files: `exporters`,
today's Python bake, or `dbt`, pipeline/ELT.md's hourly lane (dlt into the raw
store, then the closures and warnings marts and their pub_ writers). A
dispatch picks with `phone_files`; the schedule takes the workflow-level
default. The cutover after the merge is ELT.md's open question 4, which only
the maintainer answers, so the default stays `exporters`, and changing it is
one line. These tests hold that shape: the switch is read in one place, every
step that belongs to one path says so in its `if:`, and publish.py is told the
same value the steps branched on.
"""

from __future__ import annotations

import re

import yaml

from test_conditions_production_leg_needs_main import WORKFLOW, _evaluate, _expression

PATHS = ("exporters", "dbt")


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps() -> list[dict]:
    return _workflow()["jobs"]["publish"]["steps"]


def _phone_files(event: str, phone_files: str | None) -> str:
    inputs = {} if phone_files is None else {"phone_files": phone_files}
    return _evaluate(_expression(_workflow()["env"]["PHONE_FILES"]), {"github": {"event_name": event}, "inputs": inputs})


def test_the_schedule_runs_todays_bake_and_a_dispatch_chooses_either():
    """The schedule carries no inputs, so it takes the default, which is today's bake until the maintainer answers
    ELT.md's open question 4. A dispatch gets the path it names."""
    assert _phone_files("schedule", None) == "exporters"
    assert _phone_files("workflow_dispatch", "dbt") == "dbt"
    assert _phone_files("workflow_dispatch", "exporters") == "exporters"
    choice = _workflow()[True]["workflow_dispatch"]["inputs"]["phone_files"]
    assert choice["type"] == "choice" and set(choice["options"]) == set(PATHS) and choice["default"] == "exporters"


def test_the_cutover_is_one_line_the_default_in_phone_files():
    """`inputs.phone_files` is read once, in the workflow-level PHONE_FILES, so the schedule's path is that one
    expression's fallback and nothing else names it."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert len(re.findall(r"inputs\.phone_files", text)) == 1
    assert re.search(r"^  PHONE_FILES: \$\{\{ inputs\.phone_files \|\| '(exporters|dbt)' \}\}$", text, re.M)


def test_publish_py_is_told_the_path_the_steps_branched_on():
    publish = next(step for step in _steps() if "publish.py" in str(step.get("run", "")))
    assert publish["env"]["OURHIKE_PHONE_FILES"] == "${{ env.PHONE_FILES }}"
    assert "if" not in publish, "both paths publish, through the same step"


def test_every_step_of_one_path_names_its_path_by_the_switch():
    """A step that reads the raw store or runs dlt or dbt is the dbt path's, and one that runs today's ATC or
    NYNJTC fetchers is the exporters' (the dbt path reads both through the extract); each says so in its `if:`."""
    dbt_markers = ("extract._run", "build_marts.py", "R2_RAW_", "requirements-dbt.txt", "dbt-v2-runtime")
    exporters_only = ("fetch_atc_updates.py", "export_atc_updates.py", "fetch_nynjtc_alerts.py", "export_nynjtc_alerts.py")
    unmarked = []
    for step in _steps():
        text = yaml.safe_dump(step)
        condition = str(step.get("if", ""))
        if any(marker in text for marker in dbt_markers) and "env.PHONE_FILES == 'dbt'" not in condition:
            unmarked.append(f"{step.get('name') or step.get('uses')}: a dbt-path step without env.PHONE_FILES == 'dbt'")
        if any(marker in text for marker in exporters_only) and "env.PHONE_FILES == 'exporters'" not in condition:
            unmarked.append(f"{step.get('name') or step.get('uses')}: an exporters-path step without its condition")
    assert unmarked == []
