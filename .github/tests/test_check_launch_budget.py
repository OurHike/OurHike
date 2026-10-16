"""A deploy refuses a pinned release carrying a file a phone fetches whole over the launch budget.

Review 5528343443 on PR #1805 (2026-10-15): UA's release 2026-10-03-2 listed
a 41,216,145-byte network_overview.geojson against the client's
33,554,432-byte LAUNCH_ARTIFACT_BUDGET_BYTES, ua.yml deployed builds pinned to
it, and every UA phone declined the sketch at the manifest and drew an opening
map with the A.T. alone. Check 22 (pipeline/lib/client_contract.py) would have
said so, and ran only in verify-release.yml, a dispatch-only promotion gate.

`.github/scripts/check_launch_budget.py` runs check 22 on the pinned manifest a
guard step has just fetched. The first half here runs the script as a step
runs it, under `python -S`, so it also proves the script needs nothing outside
the standard library, as a runner's bare python3 has. The second half runs the
steps themselves, the shell and all, against a stub `curl` serving a fake
bucket: ua.yml's and pages.yml's refuse, and pr-preview.yml's warns and leads
the preview comment with it.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import check_launch_budget as guard
import pytest
import yaml

import test_pages_publish as pages_publish

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SCRIPT = REPO_ROOT / ".github" / "scripts" / "check_launch_budget.py"
BUDGET = guard.client_contract.launch_artifact_budget()
#: A key the client at this commit fetches whole, so check 22 weighs it.
WHOLE = "network_overview.geojson"
RELEASE = "2026-10-10-2"
BASE = "https://data.example.org"


def _manifest(**sizes: int | None) -> dict:
    """A release manifest listing each key at its decoded size (None: no `size_bytes`)."""
    return {
        "artifacts": {
            key.replace("__", "."): {"sha256": "0" * 64, **({} if size is None else {"size_bytes": size})}
            for key, size in sizes.items()
        }
    }


def _run(tmp_path: Path, manifest: dict | str, *arguments: str, release: str = RELEASE) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "manifest.json"
    path.write_text(manifest if isinstance(manifest, str) else json.dumps(manifest), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-S", str(SCRIPT), str(path), "--release", release, *arguments],
        capture_output=True,
        text=True,
    )


def _commands(done: subprocess.CompletedProcess[str], level: str) -> list[str]:
    return [line for line in done.stdout.splitlines() if line.startswith(f"::{level}::")]


# ---------------------------------------------------------------- the check


def test_the_file_these_tests_weigh_is_one_the_client_fetches_whole():
    assert WHOLE in guard.client_contract.expected_client_keys()


def test_a_release_whose_files_fit_passes_and_says_what_it_weighed(tmp_path: Path):
    done = _run(tmp_path, _manifest(network_overview__geojson=BUDGET))

    assert done.returncode == 0, done.stdout + done.stderr
    assert not _commands(done, "error") and not _commands(done, "warning")
    assert f"1 within the {BUDGET:,}-byte launch budget; largest {BUDGET:,} bytes ({WHOLE})" in done.stdout
    assert f"No file release {RELEASE} lists that a phone fetches whole is over the launch budget." in done.stdout


def test_a_file_over_the_budget_is_refused_with_its_size_the_budget_and_the_fix(tmp_path: Path):
    done = _run(tmp_path, _manifest(network_overview__geojson=41_216_145))

    assert done.returncode == guard.OVER
    (error,) = _commands(done, "error")
    assert f"Release {RELEASE}'s {WHOLE} is 41,216,145 bytes decoded, over the {BUDGET:,}-byte launch budget" in error
    assert "declines it at the manifest and draws without it" in error
    assert "Pin a release whose files fit" in error


def test_warn_annotates_a_warning_and_writes_one_line_for_the_preview_comment(tmp_path: Path):
    banner = tmp_path / "banner.md"

    done = _run(tmp_path, _manifest(network_overview__geojson=BUDGET + 1), "--warn", "--banner", str(banner))

    assert done.returncode == guard.OVER
    assert not _commands(done, "error")
    assert len(_commands(done, "warning")) == 1
    text = banner.read_text(encoding="utf-8")
    assert "\n" not in text, "a step output is one line"
    assert text.startswith(f"**This build's pinned release (`{RELEASE}`) carries 1 file(s) over the launch budget**")
    assert f"{WHOLE} is {BUDGET + 1:,} bytes decoded" in text


def test_no_banner_is_written_for_a_release_that_fits(tmp_path: Path):
    banner = tmp_path / "banner.md"

    done = _run(tmp_path, _manifest(network_overview__geojson=1), "--warn", "--banner", str(banner))

    assert done.returncode == 0
    assert not banner.exists()


def test_a_file_with_no_size_is_counted_and_left_to_the_phone(tmp_path: Path):
    """UA's 2026-10-10-2 lists 201 hike details with no size_bytes; a phone weighs each once it arrives."""
    done = _run(tmp_path, _manifest(network_overview__geojson=1, suggested_hikes_detail_7__json=None))

    assert done.returncode == 0, done.stdout
    assert "1 file(s) a phone fetches whole publish no size_bytes, so they were not weighed here" in done.stdout


@pytest.mark.parametrize("key", ["trail_graph.json", "nearby_trails.pmtiles", "v2/network_overview.geojson"])
def test_a_file_no_phone_of_this_build_fetches_whole_is_not_weighed(tmp_path: Path, key: str):
    """The whole graph and the whole network stay in the bucket for older clients; a range-read archive is
    never fetched whole; a v2 file is for a build that reads v2."""
    done = _run(tmp_path, {"artifacts": {key: {"sha256": "0" * 64, "size_bytes": 646_883_515}}})

    assert done.returncode == 0, done.stdout


def test_a_name_with_a_line_break_is_weighed_but_never_repeated(tmp_path: Path):
    """The manifest is text the check did not write, and its lines are workflow commands."""
    done = _run(tmp_path, {"artifacts": {"suggested_hikes_detail_7.json\n": {"sha256": "0", "size_bytes": BUDGET + 1}}})

    assert done.returncode == guard.OVER
    (error,) = _commands(done, "error")
    assert "a file whose name this check does not repeat" in error
    assert all(line.startswith(("::error::", "Release ", "No file ")) for line in done.stdout.splitlines()), done.stdout


@pytest.mark.parametrize(
    "manifest",
    ['{"artifacts": ', "[]", '{"artifacts": []}', '{"artifacts": {"trails.geojson": 7}}', '{"release": "x"}'],
    ids=["not JSON", "not an object", "artifacts not a mapping", "an entry not an object", "no artifacts"],
)
def test_a_manifest_that_cannot_be_read_is_refused_rather_than_passed(tmp_path: Path, manifest: str):
    done = _run(tmp_path, manifest)

    assert done.returncode == guard.UNREADABLE
    assert len(_commands(done, "error")) == 1
    assert "nothing was weighed" in done.stdout


def test_a_release_that_is_not_an_id_is_refused_without_being_repeated(tmp_path: Path):
    done = _run(tmp_path, _manifest(network_overview__geojson=1), release="latest\n::warning::injected")

    assert done.returncode == guard.UNREADABLE
    assert "injected" not in done.stdout


# ---------------------------------------------------------------- the steps


def _step(workflow: str, name: str) -> dict:
    parsed = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
    return next(step for job in parsed["jobs"].values() for step in job.get("steps", []) if step.get("name") == name)


def _pin() -> str:
    """DATA_RELEASE, read as the deploy steps read it, with sed's pattern."""
    source = (REPO_ROOT / "client" / "src" / "lib" / "dataRelease.ts").read_text(encoding="utf-8")
    match = re.search(r"^export const DATA_RELEASE = '(.*)'$", source, re.MULTILINE)
    assert match, "could not read DATA_RELEASE out of client/src/lib/dataRelease.ts"
    return match.group(1)


def _publish(bucket: Path, prefix: str, size: int) -> None:
    """The pinned release's manifest in one environment's tree, with the sketch at `size` bytes."""
    path = bucket / prefix / "releases" / _pin() / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_manifest(network_overview__geojson=size)), encoding="utf-8")


def _run_step(tmp_path: Path, workflow: str, name: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """`name`'s script as Actions runs it under bash, with a stub `curl` answering from tmp_path/bucket."""
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    pages_publish.TestTheUploadedPointer._stub_curl(stubs)
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir(exist_ok=True)
    step = _step(workflow, name)
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]],
        cwd=REPO_ROOT / step.get("working-directory", "."),
        env={
            **os.environ,
            "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
            "RUNNER_TEMP": str(runner_temp),
            "STUB_BUCKET": str(tmp_path / "bucket"),
            "STUB_BASE": BASE,
            **env,
        },
        capture_output=True,
        text=True,
    )


GUARDS = [("ua.yml", "environments/ua", f"{BASE}/environments/ua"), ("pages.yml", "", BASE)]
GUARD_STEP = "Confirm the pinned data release exists"


@pytest.mark.parametrize(("workflow", "prefix", "url"), GUARDS)
def test_a_deploy_refuses_a_pinned_release_over_the_budget(tmp_path: Path, workflow: str, prefix: str, url: str):
    _publish(tmp_path / "bucket", prefix, BUDGET + 1)

    done = _run_step(tmp_path, workflow, GUARD_STEP, {"DATA_URL": url})

    assert done.returncode != 0
    (error,) = _commands(done, "error")
    assert f"Release {_pin()}'s {WHOLE} is {BUDGET + 1:,} bytes decoded" in error


@pytest.mark.parametrize(("workflow", "prefix", "url"), GUARDS)
def test_a_deploy_passes_a_pinned_release_that_fits(tmp_path: Path, workflow: str, prefix: str, url: str):
    _publish(tmp_path / "bucket", prefix, BUDGET)

    done = _run_step(tmp_path, workflow, GUARD_STEP, {"DATA_URL": url})

    assert done.returncode == 0, done.stdout + done.stderr
    assert f"Pinned release {_pin()} resolves at {url}." in done.stdout
    assert not _commands(done, "error")
    assert f"No file release {_pin()} lists that a phone fetches whole is over the launch budget." in done.stdout


@pytest.mark.parametrize(("workflow", "prefix", "url"), GUARDS)
def test_a_deploy_still_refuses_a_pin_that_does_not_resolve(tmp_path: Path, workflow: str, prefix: str, url: str):
    (tmp_path / "bucket").mkdir()

    done = _run_step(tmp_path, workflow, GUARD_STEP, {"DATA_URL": url})

    assert done.returncode != 0
    assert "does not resolve" in done.stdout


PREVIEW_STEP = "Resolve the data source"


def _preview(tmp_path: Path, **env: str) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    output = tmp_path / "github-output"
    output.touch()
    done = _run_step(
        tmp_path,
        "pr-preview.yml",
        PREVIEW_STEP,
        {"FROM_VAR": BASE, "FROM_SECRET": "", "DATA_ENVIRONMENT": "", "GITHUB_OUTPUT": str(output), **env},
    )
    outputs = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if "=" in line)
    return done, outputs


def test_a_preview_of_a_release_over_the_budget_still_deploys_and_leads_its_comment_with_it(tmp_path: Path):
    _publish(tmp_path / "bucket", "", BUDGET + 1)

    done, outputs = _preview(tmp_path)

    assert done.returncode == 0, done.stdout + done.stderr
    assert len(_commands(done, "warning")) == 1
    assert outputs["environment"] == "production"
    assert outputs["banner"].startswith(f"**This build's pinned release (`{_pin()}`) carries 1 file(s) over the launch budget**")


def test_a_preview_weighs_the_release_in_the_environment_it_falls_back_to(tmp_path: Path):
    """Production lacks the pin and UA holds it: the preview reads UA, and says both things."""
    _publish(tmp_path / "bucket", "environments/ua", BUDGET + 1)

    done, outputs = _preview(tmp_path)

    assert done.returncode == 0, done.stdout + done.stderr
    assert outputs["environment"] == "ua"
    assert outputs["banner"].startswith("**Previewing UA data**")
    assert "over the launch budget**" in outputs["banner"]


def test_a_preview_dispatched_against_ua_weighs_uas_release(tmp_path: Path):
    _publish(tmp_path / "bucket", "environments/ua", BUDGET + 1)

    done, outputs = _preview(tmp_path, DATA_ENVIRONMENT="ua")

    assert done.returncode == 0, done.stdout + done.stderr
    assert "over the launch budget**" in outputs["banner"]


def test_a_preview_of_a_release_that_fits_says_nothing_about_the_budget(tmp_path: Path):
    _publish(tmp_path / "bucket", "", BUDGET)

    done, outputs = _preview(tmp_path)

    assert done.returncode == 0, done.stdout + done.stderr
    assert outputs["banner"] == ""
    assert not _commands(done, "warning")
