"""The preview comment carries a picture of the build, and nothing is committed.

WHY THIS IS A TEST AND NOT A CONVENTION. #984 put a screenshot in every pull
request by committing the PNG and linking into the commit, which worked and
cost 79,290 measured bytes of permanent, unretractable image per pull request
in a public tree. #988 replaced that: `pr-preview.yml` photographs the build it
is about to upload, writes the image INTO that upload, and puts it in the
sticky comment it already posts. Nothing reaches a commit.

The failure this guards against is silent in both directions. Drop the
screenshot steps and every pull request keeps its preview and quietly stops
showing anything - a missing image in a comment is not a red check. Point the
capture at a tracked directory instead of the deployed one and the bytes come
back, one pull request at a time, with nothing to notice until the repository
is measurably bigger.

Deliberately assertions about the WIRING rather than about the picture. Whether
the screenshot looks right is a question for the person reading the comment;
whether the workflow still takes one, still ships it inside the deployment, and
still refers to it from the comment is a question a suite can hold.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-preview.yml"

#: Where the capture is written, and the reason the path is asserted rather
#: than merely used: it has to be inside the directory wrangler uploads
#: (`client/dist`), or the image 404s from a URL the comment already printed.
SCREENSHOT_DIR = "__screenshot"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


@pytest.fixture(scope="module")
def steps(workflow: dict) -> list[dict]:
    return workflow["jobs"]["preview"]["steps"]


def _step(steps: list[dict], name: str) -> dict:
    for step in steps:
        if step.get("name") == name:
            return step
    raise AssertionError(f"pr-preview.yml has no step named {name!r}")


def _index(steps: list[dict], name: str) -> int:
    return next(i for i, step in enumerate(steps) if step.get("name") == name)


def test_the_build_is_photographed(steps: list[dict]):
    run = _step(steps, "Photograph the build")["run"]
    assert "scripts/screenshot.mjs" in run
    # --dist, or the picture is of the dev server rather than of the artifact
    # being deployed, and can differ from it in exactly the ways a reviewer
    # would be the first to discover.
    assert "--dist" in run


def test_it_photographs_both_states_a_reviewer_wants(steps: list[dict]):
    """First run covers everybody's first launch; the trail screen covers the
    app past it. Either alone answers half of "does this branch come up"."""
    run = _step(steps, "Photograph the build")["run"]
    assert "first-run" in run
    assert "--entry" in run
    assert "trail-screen" in run


def test_the_photograph_happens_before_the_upload(steps: list[dict]):
    """The image travels inside the deployment. Taken after the upload it
    would need a second one, and the comment would link at a 404 until then."""
    assert _index(steps, "Photograph the build") < _index(steps, "Publish the preview")


def test_a_browser_is_installed_before_it_is_used(steps: list[dict]):
    assert _index(steps, "Install a browser to photograph it with") < _index(steps, "Photograph the build")


def test_a_failed_screenshot_does_not_cost_the_preview(steps: list[dict]):
    """A testable build is worth more than a picture of one. If the browser
    will not start, the deploy and the link still happen."""
    assert _step(steps, "Photograph the build")["continue-on-error"] is True


def test_the_comment_shows_the_images(steps: list[dict]):
    message = _step(steps, "Say where the preview is")["with"]["message"]
    assert "steps.images.outputs.block" in message

    block = _step(steps, "Name the images")["run"]
    assert f"/{SCREENSHOT_DIR}/first-run.png" in block
    assert f"/{SCREENSHOT_DIR}/trail-screen.png" in block
    # <img>, not ![](), because markdown image syntax carries no width and a
    # 2x capture is 780 px wide - twice the size of the phone it is of.
    assert "<img src=" in block
    assert 'width="' in block


def test_the_comment_says_so_when_there_is_no_image(steps: list[dict]):
    """Rather than rendering a broken one. A pull request from a fork gets no
    secrets, so it gets no preview and no screenshot, and that is expected."""
    block = _step(steps, "Name the images")["run"]
    assert "No screenshot this run" in block


def test_the_image_url_cannot_pick_up_a_double_slash(steps: list[dict]):
    """The two candidate bases disagree about a trailing slash - a wrangler
    alias URL may carry one, the worked-out URL does not - and
    `https://host//__screenshot/x.png` is a 404 on Pages."""
    assert 'BASE="${BASE%/}"' in _step(steps, "Name the images")["run"]


def test_no_screenshot_is_tracked_anywhere(steps: list[dict]):
    """The whole point of #988. `client/dist` is gitignored, so a capture
    written there cannot be committed even by `git add -A`."""
    assert not (REPO_ROOT / ".github" / "pr-screenshots").exists()

    run = _step(steps, "Photograph the build")["run"]
    # No --out: the script's own default is client/dist/__screenshot, which is
    # inside the gitignored build directory AND inside what wrangler uploads.
    # A --out here would be someone moving it back out of both at once.
    assert "--out" not in run
