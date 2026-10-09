"""publish-conditions.yml's cutover switch is one line per data environment, and the schedule runs each leg on its own.

`PHONE_FILES` chooses which pipeline writes a leg's phone files: `exporters`,
today's Python bake, or `dbt`, pipeline/ELT.md's hourly lane (dlt into the raw
store, then the closures and warnings marts and their pub_ writers). Decision
92 (the maintainer's poll, 2026-10-06, answering ELT.md's open question 4:
"UA on dbt, prod on exporters") made it one setting per environment, at the
top of the workflow: `UA_PHONE_FILES: dbt`, so UA's scheduled leg keeps the
dbt path the soak ran, and `PRODUCTION_PHONE_FILES: exporters` until the
cutover, which is changing that one line. A dispatch's `phone_files` wins for
that run; its default, `scheduled`, takes each leg's own line. The job's
"Choose which pipeline writes this leg's phone files" step turns the leg's
line into PHONE_FILES, so these tests run that step's script under bash for
each leg, rather than read its text. They also hold that every step that
belongs to one path says so in its `if:`, and that publish.py is told the
same value the steps branched on.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from test_conditions_production_leg_needs_main import MAIN, WORKFLOW, _evaluate, _expression
from test_notices_job import ADD_STEP, BUILD_STEP, _base_env, _outputs, _run, _stand_in

PATHS = ("exporters", "dbt")
#: The dispatch's `phone_files` choice that leaves each leg on its own line, as the schedule does.
SCHEDULED = "scheduled"
CHOOSE_STEP = "Choose which pipeline writes this leg's phone files"
#: Each environment's line, as decision 92 set them on 2026-10-06.
SETTINGS = {"production": ("PRODUCTION_PHONE_FILES", "exporters"), "ua": ("UA_PHONE_FILES", "dbt")}


def _workflow(path: Path = WORKFLOW) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps() -> list[dict]:
    return _workflow()["jobs"]["publish"]["steps"]


def _phone_files(
    tmp_path: Path, leg: str, event: str = "schedule", phone_files: str | None = None, workflow: Path = WORKFLOW
) -> str | None:
    """The PHONE_FILES a leg's steps branch on, for one run of `event` from main with `phone_files` as the dispatch's
    input (None on a schedule, which carries none).

    However the workflow chooses it: the workflow's and the job's `env`, each `${{ }}` evaluated, and then every step
    before the first `if:` that reads env.PHONE_FILES which writes PHONE_FILES to $GITHUB_ENV, its script run under
    bash with the env the step gives it. A step whose script fails is a run that stops there, so the answer is None.
    """
    document = _workflow(workflow)
    job = document["jobs"]["publish"]
    inputs = {} if phone_files is None else {"phone_files": phone_files}
    context = {"github": {"event_name": event, "ref": MAIN}, "inputs": inputs, "matrix": {"data_environment": leg}}

    def value(text) -> str:
        text = str(text)
        if "${{" not in text:
            return text
        found = _evaluate(_expression(text), context)
        return "" if found is None else str(found)

    env = {name: value(text) for name, text in {**(document.get("env") or {}), **(job.get("env") or {})}.items()}
    for number, step in enumerate(job["steps"]):
        if "env.PHONE_FILES" in str(step.get("if", "")):
            break
        script = str(step.get("run", ""))
        if "GITHUB_ENV" not in script or "PHONE_FILES" not in script:
            continue
        github_env = tmp_path / f"github_env_{leg}_{number}"
        step_env = {name: value(text) for name, text in (step.get("env") or {}).items()}
        finished = subprocess.run(
            ["bash", "-e", "-c", script],
            env={**env, **step_env, "GITHUB_ENV": str(github_env), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
        )
        if finished.returncode != 0:
            return None
        for line in github_env.read_text().splitlines() if github_env.exists() else []:
            name, _, written = line.partition("=")
            env[name] = written
    return env.get("PHONE_FILES")


def test_the_schedule_runs_uas_leg_on_the_dbt_path_and_productions_on_the_exporters(tmp_path):
    """Decision 92: UA's scheduled leg keeps the soak's dbt path on main's code, and production's keeps today's bake
    until the cutover. Before it, one workflow-wide `inputs.phone_files || 'exporters'` put both scheduled legs on
    the exporters, so after the merge no schedule ran the dbt path and UA's conditions/notices.json and
    hazard_areas.json, which only dbt writes, froze (review finding ARC-2 of PR #1805 — dlt → dbt re-platform as one
    go/no-go change)."""
    assert _phone_files(tmp_path, "ua") == "dbt", "UA's scheduled leg runs today's bake, so nothing rewrites its dbt files"
    assert _phone_files(tmp_path, "production") == "exporters", "production's scheduled leg left the exporters"


def test_a_dispatch_left_at_scheduled_runs_each_leg_on_its_own_line(tmp_path):
    """A dispatch from the Actions tab that picks nothing runs what the schedule runs."""
    choice = _workflow()[True]["workflow_dispatch"]["inputs"]["phone_files"]
    assert choice["type"] == "choice" and set(choice["options"]) == {SCHEDULED, *PATHS}
    assert choice["default"] == SCHEDULED, "a dispatch that picks nothing would run another path than the schedule"
    assert _phone_files(tmp_path, "ua", "workflow_dispatch", SCHEDULED) == "dbt"
    assert _phone_files(tmp_path, "production", "workflow_dispatch", SCHEDULED) == "exporters"


@pytest.mark.parametrize("leg", ["production", "ua"])
@pytest.mark.parametrize("asked", PATHS)
def test_a_dispatchs_phone_files_wins_for_that_run(tmp_path, leg, asked):
    """Whatever the leg's line says. A production leg asked for `dbt` never gets this far: the matrix leaves it out and
    the bash lock refuses it (test_conditions_production_leg_needs_main.py)."""
    assert _phone_files(tmp_path, leg, "workflow_dispatch", asked) == asked


def test_each_environment_has_one_line_and_the_cutover_is_productions():
    """One `KEY: value` line each at the top of the workflow, where its header points, and no other default anywhere:
    the cutover is changing PRODUCTION_PHONE_FILES to `dbt`, and extract-notices.yml reads that same line
    (test_notices_job.py). `inputs.phone_files` has four readers: the matrix and the bash lock, which keep a
    dispatched dbt path off the production leg, the step that chooses, and the `checks` job, which starts
    check-conditions.yml on the legs the matrix ran (decision 110) by the matrix's own rule."""
    text = WORKFLOW.read_text(encoding="utf-8")
    for name, value in SETTINGS.values():
        assert re.findall(rf"^  {name}: (\S+)$", text, re.M) == [value], name
        assert _workflow()["env"][name] == value
    assert "PHONE_FILES" not in _workflow()["env"], "a workflow-wide PHONE_FILES would be the one value for both legs"
    readers = [line.strip() for line in text.splitlines() if "inputs.phone_files" in line]
    assert len(readers) == 4, readers
    assert readers[0].startswith("data_environment: ${{ fromJSON(") and "inputs.phone_files != 'dbt'" in readers[0]
    assert readers[1] == readers[2] == "ASKED_PHONE_FILES: ${{ inputs.phone_files }}"
    matrix_rule = readers[0][readers[0].index("((") + 1 : readers[0].index(") &&") + 1]
    assert readers[3].startswith("LEGS: ${{ ") and matrix_rule in readers[3], (matrix_rule, readers[3])
    names = [step.get("name") for step in _steps()]
    (first,) = [number for number, step in enumerate(_steps()) if "env.PHONE_FILES" in str(step.get("if", ""))][:1]
    assert names.index(CHOOSE_STEP) < first, "every step that branches on PHONE_FILES comes after the choice"
    assert "if" not in _steps()[names.index(CHOOSE_STEP)], "every leg chooses"


@pytest.mark.parametrize("typo", ["dbtt", "Exporters", ""])
def test_a_line_that_names_neither_path_stops_its_leg_before_either_path_runs(tmp_path, typo):
    """A typo in a leg's line would otherwise leave PHONE_FILES naming neither path, so that every step of both paths
    skipped and publish.py refused at the end. The choice stops the leg first, and says which line."""
    broken = tmp_path / "publish-conditions.yml"
    text = WORKFLOW.read_text(encoding="utf-8")
    broken.write_text(
        re.sub(r"^  PRODUCTION_PHONE_FILES: \S+$", f'  PRODUCTION_PHONE_FILES: "{typo}"', text, count=1, flags=re.M)
    )
    assert _phone_files(tmp_path, "production", workflow=broken) is None
    assert _phone_files(tmp_path, "ua", workflow=broken) == "dbt", "one leg's typo is its own"


def test_a_scheduled_production_leg_on_the_exporters_never_reads_a_notices_copy_so_no_notices_step_turns_it_red(tmp_path):
    """extract-notices.yml skips its production leg while production is on the exporters (decision 92), so production's
    notices store has no copy, which decision 96 counts as overdue. The production leg must not go red for a copy it
    never reads: on the exporters path the notices read is skipped, a skipped step has no outputs, and every step that
    reads them, the red ones among them, evaluates false."""
    from test_conditions_production_leg_needs_main import _evaluate

    phone_files = _phone_files(tmp_path, "production")
    assert phone_files == "exporters"
    context = {"env": {"PHONE_FILES": phone_files}, "matrix": {"data_environment": "production"}, "steps": {}}
    (add,) = [step for step in _steps() if step.get("name") == ADD_STEP]
    assert not _evaluate(str(add["if"]), context), "the production leg reads the notices copy on the exporters path"
    readers = [step for step in _steps() if "steps.notices.outputs" in str(step.get("if", ""))]
    assert len(readers) >= 3, [step["name"] for step in readers]
    assert [step["name"] for step in readers if _evaluate(str(step["if"]), context)] == []
    (overdue,) = [step for step in readers if "overdue" in step["if"]]
    fired = {**context, "steps": {"notices": {"outputs": {"read": "none", "overdue": "true"}}}}
    assert _evaluate(str(overdue["if"]), fired), "the red step would fire, had the notices read run"


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
