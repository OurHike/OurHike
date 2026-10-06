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

import pytest
import yaml

from test_conditions_production_leg_needs_main import WORKFLOW, _evaluate, _expression
from test_notices_job import BUILD_STEP, _base_env, _outputs, _run, _stand_in

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
    """`inputs.phone_files` picks the path only in the workflow-level PHONE_FILES, so the schedule's path is that
    one expression's fallback. Its two other readers keep a dispatched dbt path off the production leg (the matrix,
    which cannot read `env`, and its bash lock; test_conditions_production_leg_needs_main.py), and a schedule passes
    no input."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"^  PHONE_FILES: \$\{\{ inputs\.phone_files \|\| '(exporters|dbt)' \}\}$", text, re.M)
    readers = [line.strip() for line in text.splitlines() if "inputs.phone_files" in line]
    assert len(readers) == 3, readers
    assert readers[1].startswith("data_environment: ${{ fromJSON(") and "inputs.phone_files != 'dbt'" in readers[1]
    assert readers[2] == "ASKED_PHONE_FILES: ${{ inputs.phone_files }}"


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


def test_the_dbt_path_keeps_each_legs_row_history_under_a_prefix_of_its_own():
    """pipeline/row_history.py: each conditions leg is its own pipeline, so its snapshots are restored from and
    saved to history/conditions_<leg>/, never one prefix for both, and never with a cold start forced."""
    (build,) = [step for step in _steps() if "build_marts.py" in str(step.get("run", ""))]

    assert '--history-url "s3://$R2_RAW_BUCKET/history/conditions_$ENVIRONMENT"' in build["run"]
    assert build["env"]["ENVIRONMENT"] == "${{ matrix.data_environment }}"
    assert '--history-python "$RUNNER_TEMP/extract/bin/python"' in build["run"]
    assert "--history-cold-start" not in build["run"]


def test_a_failed_history_restore_still_publishes_and_then_turns_the_run_red():
    """The maintainer, by poll, 2026-10-03: closures and warnings publish without their history, with both row
    dates null, and the run goes red afterwards. build_marts.py --history-on-failure degrade exits 4 for exactly
    that (DEGRADED_EXIT, which no other failure returns); the build step records it and carries on, and the last
    step fails the run on it, after the publish."""
    steps = _steps()
    names = [step.get("name") or step.get("uses") for step in steps]
    (build,) = [step for step in steps if "build_marts.py" in str(step.get("run", ""))]
    (red,) = [step for step in steps if "steps.build.outputs.history_lost" in str(step.get("if", ""))]
    (publish,) = [step for step in steps if step.get("name") == "Publish to R2"]

    assert build["id"] == "build" and "--history-on-failure degrade" in build["run"]
    assert 'if [ "$status" -eq 4 ]; then\n  echo "history_lost=true" >> "$GITHUB_OUTPUT"' in build["run"]
    assert 'elif [ "$status" -ne 0 ]; then\n  exit "$status"' in build["run"], "any other failure still stops the leg"
    assert red["if"] == "steps.build.outputs.history_lost == 'true'" and red["run"].rstrip().endswith("exit 1")
    assert names.index(publish["name"]) < names.index(red["name"]), "the files publish before the run goes red"
    assert "if" not in publish, "the publish runs on a degraded build, whose step succeeded"


@pytest.mark.parametrize(
    ("status", "outcome", "outputs"),
    [
        (0, 0, {}),
        (4, 0, {"history_lost": "true"}),
        (5, 0, {"partial": "true"}),
        (6, 0, {"history_lost": "true", "partial": "true"}),
        (1, 1, {}),
        (3, 3, {}),
    ],
)
def test_a_build_that_held_a_source_or_a_writer_back_still_publishes_and_then_turns_the_run_red(
    tmp_path, status, outcome, outputs
):
    """Decision 81 (the maintainer's poll, 2026-10-05: "Hold that source and publish the rest"): build_marts.py exits
    PARTIAL_EXIT, 5, when the gate held a source for its rows, a per-source model's failure held its source, or some
    writers failed while the rest wrote; 6 is that and a degraded build together. The build step records `partial`
    and carries on, "Publish to R2" tells publish.py so (OURHIKE_BUILD_PARTIAL, which keeps a failed writer's key at the
    bucket's last copy), and the last step turns the run red, after the publish, as the extract's exit 3 does. Every
    other failure still stops the leg. The step's own script runs here under bash, with build_marts.py's python a
    stand-in that answers `status`."""
    _stand_in(tmp_path / "bin" / "python", status)
    (build,) = [step for step in _steps() if step.get("name") == BUILD_STEP]
    finished = _run(build["run"], {**_base_env(tmp_path), "ENVIRONMENT": "ua", "NOTICES_READ": "latest"})

    assert finished.returncode == outcome, finished.stdout + finished.stderr
    assert _outputs(tmp_path) == outputs

    steps = _steps()
    names = [step.get("name") or step.get("uses") for step in steps]
    (publish,) = [step for step in steps if step.get("name") == "Publish to R2"]
    (red,) = [step for step in steps if step.get("if") == "steps.build.outputs.partial == 'true'"]
    assert publish["env"]["OURHIKE_BUILD_PARTIAL"] == "${{ steps.build.outputs.partial }}"
    assert "if" not in publish, "the publish runs on a partial build, whose step succeeded"
    assert names.index(publish["name"]) < names.index(red["name"]) and red["run"].rstrip().endswith("exit 1")


def test_build_marts_exit_codes_the_workflow_reads_are_the_ones_it_defines():
    """The step's 4, 5 and 6 are build_marts.py's DEGRADED_EXIT, PARTIAL_EXIT and DEGRADED_PARTIAL_EXIT, read from its
    source: this suite installs no DuckDB."""
    import ast

    tree = ast.parse((WORKFLOW.parents[2] / "pipeline" / "build_marts.py").read_text(encoding="utf-8"))
    values = {
        target.id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert (values["DEGRADED_EXIT"], values["PARTIAL_EXIT"], values["DEGRADED_PARTIAL_EXIT"]) == (4, 5, 6)
    (build,) = [step for step in _steps() if step.get("name") == BUILD_STEP]
    for code in (4, 5, 6):
        assert f'"$status" -eq {code} ]' in build["run"]


#: Today's exporters whose every file a dbt writer writes on the dbt path. There, publish.py's with_dbt_phone_files()
#: drops each exporter entry whose key a writer owns, so running them asked NWS a second time for its whole active
#: list, or rebuilt a reviewed file, for an entry thrown away (review finding ARC-10 of PR #1805 — dlt → dbt
#: re-platform as one go/no-go change).
DBT_OWNED_EXPORTERS = ("export_weather_alerts.py", "export_work_projects.py")
#: export_conditions.py's four files (the `written` list in its main()).
CONDITIONS_EXPORTS = ("closures", "reports", "notes", "disputes")


def _conditions_keys_with_a_writer() -> dict[str, bool]:
    """Each key a conditions exposure names, and whether a pub_ writer writes it (an exposure with none documents a
    file Python still writes, as publish.py's collect_dbt_phone_files() reads it)."""
    path = WORKFLOW.parents[2] / "pipeline" / "dbt" / "models" / "publish" / "_publish__conditions.yml"
    keys = {}
    for exposure in yaml.safe_load(path.read_text(encoding="utf-8"))["exposures"]:
        written = any(str(parent).replace('"', "'").startswith("ref('pub_") for parent in exposure.get("depends_on") or [])
        for key in exposure["config"]["meta"]["r2_keys"]:
            keys[key] = written
    return keys


def _payload(script: str) -> str:
    """A conditions exporter's PAYLOAD, the name of its file under conditions/, read from its source."""
    import ast

    tree = ast.parse((WORKFLOW.parents[2] / "pipeline" / script).read_text(encoding="utf-8"))
    (value,) = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PAYLOAD" for t in node.targets)
    ]
    return value


def _step_running(script: str) -> dict:
    (step,) = [step for step in _steps() if f"python {script}" in str(step.get("run", ""))]
    return step


@pytest.mark.parametrize("script", DBT_OWNED_EXPORTERS)
def test_an_exporter_whose_every_file_a_dbt_writer_writes_runs_on_the_exporters_path_alone(script):
    key = f"conditions/{_payload(script)}.json"
    assert _conditions_keys_with_a_writer().get(key), f"{key} has no dbt writer, so the dbt path still publishes {script}'s"

    step = _step_running(script)
    assert "env.PHONE_FILES == 'exporters'" in str(step.get("if", "")), f"{step['name']} runs on the dbt path for nothing"


def test_export_conditions_runs_on_both_paths_because_no_dbt_writer_writes_its_notes_or_disputes():
    """Its closures and reports are thrown away on the dbt path, as ARC-10 says, and its notes and disputes are not:
    the dbt path publishes those two from it (no mart owns field notes, WN11), so the step runs on both paths."""
    writers = _conditions_keys_with_a_writer()
    assert [kind for kind in CONDITIONS_EXPORTS if not writers.get(f"conditions/{kind}.json")] == ["notes", "disputes"]
    assert "PHONE_FILES" not in str(_step_running("export_conditions.py").get("if", ""))
