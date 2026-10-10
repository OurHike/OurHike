"""A deploy refuses when DATA_RELEASE and channels.json's entry for its data environment name two releases.

Decision 145 (pipeline/ELT.md), by poll on 2026-10-09: "Add the guard". A
phone reads the compiled DATA_RELEASE on its first launch and the release
channels.json names from the launch after it reads that file, so a build whose
two values disagree changes release under a new install (overnight offline
review 1, finding 7). `.github/scripts/check_pin_matches_channels.py` is the
guard; pages.yml and ua.yml run it before they deploy.

The script runs here the way a workflow runs it, against small copies of the
two files, so what it decides is checked and not only its text. The workflow
half holds where it runs and which base it reads the environment from.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import check_pin_matches_channels as check
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SCRIPT = REPO_ROOT / ".github" / "scripts" / "check_pin_matches_channels.py"
STEP = "Confirm DATA_RELEASE and channels.json name the same release"
COMMAND = "python3 .github/scripts/check_pin_matches_channels.py"
#: Each deploy, and the step in it that ships the build.
DEPLOYS = [("pages.yml", "Publish to GitHub Pages"), ("ua.yml", "Publish UA")]
#: The base each environment's build is given: production is the bucket root, UA its prefix.
BASES = {"production": "https://data.example.org", "ua": "https://data.example.org/environments/ua"}
PINNED = "2026-10-03-2"
OTHER = "2026-09-24-2"
CLIENT = f"// a comment line\nexport const DATA_RELEASE = '{PINNED}'\n\nexport const DATA_SCHEMA_VERSION = 'v1'\n"


def _other(environment: str) -> str:
    return "ua" if environment == "production" else "production"


def _run(
    tmp_path: Path, channels: dict | str | None, *, environment: str = "production", client: str = CLIENT, base: str | None = None
) -> subprocess.CompletedProcess[str]:
    """The script on a dataRelease.ts holding `client` and a channels.json holding `channels` (None: no file)."""
    client_path = tmp_path / "dataRelease.ts"
    client_path.write_text(client, encoding="utf-8")
    channels_path = tmp_path / "channels.json"
    if channels is not None:
        channels_path.write_text(channels if isinstance(channels, str) else json.dumps(channels), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--client", str(client_path), "--channels", str(channels_path)],
        env={**os.environ, "DATA_URL": BASES[environment] if base is None else base},
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------- the check


@pytest.mark.parametrize("environment", ["production", "ua"])
def test_a_pair_naming_one_release_passes_and_prints_both_values_and_where_each_came_from(tmp_path: Path, environment: str):
    done = _run(tmp_path, {environment: {"v1": PINNED}, _other(environment): {"v1": OTHER}}, environment=environment)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "::error::" not in done.stdout
    assert f"Data environment: {environment}," in done.stdout
    assert f"DATA_RELEASE, what a phone reads on its first launch: {PINNED} ({tmp_path / 'dataRelease.ts'}:2)." in done.stdout
    assert f"channels.json's {environment} v1 entry, what it follows once it has read the pointer: {PINNED}" in done.stdout
    assert f"They agree: a phone of this build reads {PINNED}" in done.stdout


@pytest.mark.parametrize("environment", ["production", "ua"])
def test_a_pair_naming_two_releases_is_refused_with_both_values_and_the_fix(tmp_path: Path, environment: str):
    """The other environment's entry agrees, so this also holds that the entry read is this build's own."""
    done = _run(tmp_path, {environment: {"v1": OTHER}, _other(environment): {"v1": PINNED}}, environment=environment)

    assert done.returncode == 1
    (error,) = [line for line in done.stdout.splitlines() if line.startswith("::error::")]
    assert f"DATA_RELEASE is {PINNED} and channels.json's {environment} v1 entry is {OTHER}" in error
    assert f"reads {PINNED} on its first launch and switches to {OTHER}" in error
    assert "Move both to one release" in error and "in one commit" in error and "RELEASING.md §10" in error


@pytest.mark.parametrize(
    "channels",
    [{"ua": {"v1": PINNED}}, {"production": {"v2": PINNED}}, {"production": None}, []],
    ids=["no entry for the environment", "no entry for the schema version", "a null environment", "not an object"],
)
def test_a_missing_entry_is_refused(tmp_path: Path, channels):
    done = _run(tmp_path, channels)

    assert done.returncode == 1
    assert "::error::" in done.stdout
    assert "names no v1 release for production" in done.stdout


def test_a_missing_channels_json_is_refused(tmp_path: Path):
    done = _run(tmp_path, None)

    assert done.returncode == 1
    assert "channels.json does not exist" in done.stdout


def test_a_channels_json_that_is_not_json_is_refused(tmp_path: Path):
    done = _run(tmp_path, '{"production": {"v1": ')

    assert done.returncode == 1
    assert "is not JSON" in done.stdout


@pytest.mark.parametrize("entry", ["../../latest", 20261003, "2026-10-03-2\n::warning::injected"])
def test_an_entry_that_is_not_a_release_id_is_refused_without_repeating_it(tmp_path: Path, entry):
    """A phone ignores such an entry (lib/dataChannel.ts's entryIn), and the message is a workflow command."""
    done = _run(tmp_path, {"production": {"v1": entry}})

    assert done.returncode == 1
    assert "entry is not a release id" in done.stdout
    assert "latest" not in done.stdout and "20261003" not in done.stdout and "injected" not in done.stdout


@pytest.mark.parametrize(
    "client",
    [
        "export const DATA_RELEASE = SOMETHING\nexport const DATA_SCHEMA_VERSION = 'v1'\n",
        "export const DATA_RELEASE = 'latest'\nexport const DATA_SCHEMA_VERSION = 'v1'\n",
        f"export const DATA_RELEASE = '{PINNED}'\n",
        "",
    ],
    ids=["DATA_RELEASE not a string", "DATA_RELEASE not a release id", "no DATA_SCHEMA_VERSION", "neither"],
)
def test_a_client_whose_constants_cannot_be_read_is_refused(tmp_path: Path, client: str):
    """Restructured, and the check must move with it rather than pass by reading nothing."""
    done = _run(tmp_path, {"production": {"v1": PINNED}}, client=client)

    assert done.returncode == 1
    assert "It has been restructured" in done.stdout


def test_a_build_with_no_data_source_skips_the_check(tmp_path: Path):
    """No base, no pointer: lib/dataChannel.ts's readDataChannel answers `unconfigured`."""
    done = _run(tmp_path, {"production": {"v1": OTHER}}, base="")

    assert done.returncode == 0, done.stdout + done.stderr
    assert "No data source configured - skipping the check." in done.stdout


@pytest.mark.parametrize(
    ("base", "environment"),
    # client/src/lib/dataRelease.pointer.test.ts's table for environmentOf, case for case.
    [
        ("https://data.ourhike.org", "production"),
        ("https://data.ourhike.org/", "production"),
        ("https://data.ourhike.org/environments/ua", "ua"),
        ("https://data.ourhike.org/environments/ua/", "ua"),
        ("https://data.ourhike.org/environments/dev", "dev"),
        ("http://localhost:8080", "production"),
    ],
)
def test_the_environment_is_read_off_the_base_as_the_client_reads_it(base: str, environment: str):
    assert check.environment_of(base) == environment


# ---------------------------------------------------------------- the committed files


def _sed(workflow: str, step: str, variable: str) -> str:
    """What `variable=$(sed ...)` in `step`'s script reads out of client/src/lib/dataRelease.ts."""
    parsed = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
    run = next(s for job in parsed["jobs"].values() for s in job["steps"] if s.get("name") == step)["run"]
    (line,) = [line.strip() for line in run.splitlines() if line.strip().startswith(f"{variable}=$(sed")]
    done = subprocess.run(
        ["bash", "-c", f'{line}\nprintf %s "${variable}"'], cwd=REPO_ROOT / "client", capture_output=True, text=True, check=True
    )
    assert done.stdout, f"{workflow}'s sed read no {variable}"
    return done.stdout


@pytest.mark.parametrize("workflow", ["pages.yml", "ua.yml"])
def test_the_check_reads_the_release_and_schema_version_the_other_two_checks_read(workflow: str):
    release, schema, _ = check.pinned(check.DATA_RELEASE_FILE.read_text(encoding="utf-8"), "dataRelease.ts")
    assert release == _sed(workflow, "Confirm the pinned data release exists", "release")
    assert schema == _sed(workflow, "Confirm channels.json's release exists", "schema")


@pytest.mark.parametrize("environment", ["production", "ua"])
def test_the_check_can_read_the_committed_entry_for_each_environment_a_workflow_deploys(environment: str):
    """The shape of the committed files, not whether they agree: that is the deploy's question to ask."""
    _, schema, _ = check.pinned(check.DATA_RELEASE_FILE.read_text(encoding="utf-8"), "dataRelease.ts")
    entry = check.channel_entry(check.CHANNELS_FILE.read_text(encoding="utf-8"), environment, schema, "channels.json")
    assert check.RELEASE_ID.fullmatch(entry)


# ---------------------------------------------------------------- where it runs


def _job_steps(workflow: str, deploy: str) -> list[dict]:
    """The steps of the job in `workflow` that holds the step named `deploy`."""
    parsed = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
    return next(job["steps"] for job in parsed["jobs"].values() if any(s.get("name") == deploy for s in job.get("steps", [])))


def _index(steps: list[dict], name: str) -> int:
    return next(i for i, step in enumerate(steps) if step.get("name") == name)


@pytest.mark.parametrize(("workflow", "deploy"), DEPLOYS)
def test_the_deploy_runs_the_check_before_it_ships_the_build(workflow: str, deploy: str):
    steps = _job_steps(workflow, deploy)
    assert steps[_index(steps, STEP)]["run"].strip() == COMMAND
    assert _index(steps, STEP) < _index(steps, deploy), f"{workflow} deploys before it compares DATA_RELEASE and channels.json"


@pytest.mark.parametrize(("workflow", "deploy"), DEPLOYS)
def test_the_check_follows_the_check_that_holds_the_uploaded_copy_to_the_committed_one(workflow: str, deploy: str):
    """The script's docstring leans on that step: the two together reach the copy a phone reads."""
    steps = _job_steps(workflow, deploy)
    assert _index(steps, "Confirm channels.json's release exists") < _index(steps, STEP)


@pytest.mark.parametrize(("workflow", "deploy"), DEPLOYS)
def test_the_check_reads_the_environment_off_the_base_the_app_is_built_with(workflow: str, deploy: str):
    """So a UA_DATA_BASE_URL override pointing at production's root checks production's entry, as its phones read."""
    steps = _job_steps(workflow, deploy)
    built = steps[_index(steps, "Build the app")]["env"]["VITE_DATA_BASE_URL"]
    assert steps[_index(steps, STEP)]["env"]["DATA_URL"] == built


def test_ua_checks_whenever_it_deploys():
    steps = _job_steps("ua.yml", "Publish UA")
    assert steps[_index(steps, STEP)].get("if") == steps[_index(steps, "Publish UA")].get("if")


def test_production_checks_a_draft_as_well_as_a_tag():
    """No `if:`: a draft_only dispatch is where a disagreeing pair costs nothing to find (RELEASING.md §10)."""
    steps = _job_steps("pages.yml", "Publish to GitHub Pages")
    assert "if" not in steps[_index(steps, STEP)]
