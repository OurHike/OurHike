"""A repository this project does not use cannot fail a job here.

`apt-get update` refreshes EVERY configured repository and exits non-zero if
any one of them fails. The GitHub runner image ships several vendor
repositories - Google's Chrome, Microsoft's - that OurHike neither installs
from nor references, so their availability is not something this project
controls and must not be something a job depends on.

WHAT GETTING IT WRONG COST (#1361, measured 2026-09-09). Google's Chrome
repository published a `Release` file at 17:16:59 UTC whose package index the
CDN still served from 09:41:12, so every `apt-get update` on every runner
failed:

    E: Failed to fetch .../chrome-stable/deb/.../Packages.gz  Hash Sum mismatch
    E: Some index files failed to download. They have been ignored, or old
       ones used instead.

Two shapes of job died on that, on four pull requests at once, none of which
had touched the code involved:

  - `sudo apt-get update -qq && sudo apt-get install -y -qq <pkg>`, where the
    `&&` meant the install never ran. `pytest-postgres` reported "pgbouncer is
    not installed" and went red HAVING RUN NO TESTS - and it is one of the six
    required checks in expected-protections.yml, so a third party's CDN could
    block a merge.
  - `npx playwright install --with-deps chromium`, where the flag has
    Playwright shell out to its own apt and propagate apt's exit 100.

Re-running reproduced it with byte-identical hashes: this is not a flake a
retry clears, it lasts as long as the upstream mirror is inconsistent.

THE RULE, in both directions:

  - Never chain the install behind `update` with `&&`. Run
    `apt-get update -qq || true` and then install as its own command. apt says
    it ignores the bad index and uses what it has, so the install still
    succeeds; and a genuinely broken update surfaces as an install failure,
    which names the package rather than the repository.
  - Never pass `--with-deps` to `playwright install`. Downloading a browser
    needs no apt at all.

This lives here rather than in any workflow because it is a property of all of
them, and because the next workflow to install a package is the one that will
otherwise reintroduce it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"


def _workflows():
    return sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml"))


def _run_lines(path: Path):
    """Every `run:` line in the workflow, as (step name, line).

    Comments are dropped: this file's own explanations quote both forbidden
    forms, and a check that cannot tell a warning from an instance would fail
    on the fix as readily as on the defect.
    """
    doc = yaml.safe_load(path.read_text()) or {}
    for job in (doc.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if not isinstance(run, str):
                continue
            name = step.get("name") or step.get("uses") or "<unnamed step>"
            for line in run.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    yield name, stripped


@pytest.mark.parametrize("workflow", _workflows(), ids=lambda p: p.name)
def test_an_install_is_never_chained_behind_apt_get_update(workflow):
    """`update && install` makes an unrelated repository's outage fatal."""
    offenders = [(name, line) for name, line in _run_lines(workflow) if "apt-get update" in line and "&&" in line]

    assert not offenders, (
        f"{workflow.name} chains an install behind `apt-get update &&`, so any "
        f"vendor repository preinstalled on the runner can stop it running "
        f"(#1361):\n" + "\n".join(f"  {name}: {line}" for name, line in offenders) + "\n\nSplit it:\n"
        "  sudo apt-get update -qq || true\n"
        "  sudo apt-get install -y -qq <package>"
    )


@pytest.mark.parametrize("workflow", _workflows(), ids=lambda p: p.name)
def test_playwright_installs_a_browser_without_installing_system_packages(workflow):
    """`--with-deps` hands the job's fate to apt, for a download that needs none."""
    offenders = [(name, line) for name, line in _run_lines(workflow) if "playwright install" in line and "--with-deps" in line]

    assert not offenders, (
        f"{workflow.name} passes `--with-deps` to `playwright install`, which "
        f"makes Playwright run apt and fail with it (#1361):\n"
        + "\n".join(f"  {name}: {line}" for name, line in offenders)
        + "\n\nDrop the flag - the browser download needs no apt. If a shared "
        "library really is missing on the runner image, chromium fails to "
        "launch and pr-preview.yml's comment says what to do."
    )


def test_the_check_can_see_both_forms_it_forbids():
    """The guard reads `run:` blocks, so prove it on the two lines it exists for.

    Without this, a refactor that stopped reading multi-line `run:` scripts -
    which is where five of the six offenders lived - would leave both tests
    above passing vacuously against every workflow in the tree.
    """
    fixture = yaml.safe_load(
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        "      - name: Install dependencies\n"
        "        run: |\n"
        "          pip install -r requirements.txt\n"
        "          sudo apt-get update -qq && sudo apt-get install -y -qq osmium-tool\n"
        "      - name: Install Chromium\n"
        "        run: npx playwright install --with-deps chromium\n"
    )

    lines = [line for job in fixture["jobs"].values() for step in job["steps"] for line in step["run"].splitlines()]

    assert any("apt-get update" in line and "&&" in line for line in lines)
    assert any("playwright install" in line and "--with-deps" in line for line in lines)
