"""The preview comment carries pictures of the build, and nothing is committed.

WHY THIS IS A TEST AND NOT A CONVENTION. #984 put a screenshot in every pull
request by committing the PNG and linking into the commit, which worked and
cost 79,290 measured bytes of permanent, unretractable image per pull request
in a public tree. #988 replaced that: `pr-preview.yml` photographs the build it
is about to upload, writes the images INTO that upload, and puts them in the
sticky comment it already posts. Nothing reaches a commit. #998 then pointed
the camera: the workflow hands the pull request's file list to
`client/scripts/photograph-preview.mjs`, which photographs the standing two
shots plus every shot recipe (`client/preview-shots/`) the pull request adds
or changes, and writes the comment's whole image block next to the PNGs.

The failure this guards against is silent in both directions. Drop the
screenshot steps and every pull request keeps its preview and quietly stops
showing anything - a missing image in a comment is not a red check. Point the
capture at a tracked directory instead of the deployed one and the bytes come
back, one pull request at a time, with nothing to notice until the repository
is measurably bigger.

Deliberately assertions about the WIRING rather than about the picture. What
the runner decides - which paths count as recipes, what a deleted one means,
when to nudge - is held by client/src/test/photographPreview.test.ts, beside
the code that decides it. What a suite over the WORKFLOW can hold is that the
workflow still runs the runner against the deployed build, still hands it the
file list, still ships the output inside the deployment, and still refers to
it from the comment - including the one seam neither side can check alone:
the placeholder the runner writes is the placeholder the workflow replaces.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-preview.yml"
RUNNER = REPO_ROOT / "client" / "scripts" / "photograph-preview.mjs"
RECIPES = REPO_ROOT / "client" / "preview-shots"

#: Where the captures are written, and the reason the path is asserted rather
#: than merely used: it has to be inside the directory wrangler uploads
#: (`client/dist`), or the images 404 from URLs the comment already printed.
SCREENSHOT_DIR = "__screenshot"

#: What the runner writes where the preview's URL belongs, because the shots
#: are taken before the deploy that mints it. Asserted on BOTH sides below.
PLACEHOLDER = "__PREVIEW_BASE__"


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


def test_the_build_is_photographed_by_the_runner(steps: list[dict]):
    run = _step(steps, "Photograph the build")["run"]
    assert "scripts/photograph-preview.mjs" in run
    # --dist, or the pictures are of the dev server rather than of the
    # artifact being deployed, and can differ from it in exactly the ways a
    # reviewer would be the first to discover.
    assert "--dist" in run


def test_the_camera_is_handed_the_pull_requests_files(steps: list[dict]):
    """The half of #998 that lives in the workflow: the runner can only lead
    with the pull request's own shots if something tells it what the pull
    request touched."""
    listing = _step(steps, "List what this pull request touches")
    photograph = _step(steps, "Photograph the build")
    # Same file on both ends, or the runner reads a list nobody wrote.
    assert listing["env"]["LIST"] == photograph["env"]["LIST"]
    assert '--changed="$LIST"' in photograph["run"]
    # The list step may fail without costing the preview or the standing
    # shots - the runner treats an unreadable list as an empty one.
    assert listing["continue-on-error"] is True
    assert _index(steps, "List what this pull request touches") < _index(steps, "Photograph the build")


def test_the_standing_shots_are_recipes_that_exist(steps: list[dict]):
    """First run covers everybody's first launch; the trail screen covers the
    app past it. They used to be spelled in this workflow's run line; now they
    are recipes the runner names (STANDING), so what this suite can hold is
    that the files exist and still disagree about first run - if both skipped
    it, or both kept it, one of the two states would be unphotographed."""
    first_run = (RECIPES / "first-run.mjs").read_text()
    trail_screen = (RECIPES / "trail-screen.mjs").read_text()
    assert "export const entry = true" in first_run
    assert "entry = true" not in trail_screen


def test_the_photograph_happens_before_the_upload(steps: list[dict]):
    """The images travel inside the deployment. Taken after the upload they
    would need a second one, and the comment would link at a 404 until then."""
    assert _index(steps, "Photograph the build") < _index(steps, "Publish the preview")


def test_a_browser_is_installed_before_it_is_used(steps: list[dict]):
    assert _index(steps, "Install a browser to photograph it with") < _index(steps, "Photograph the build")


def test_a_failed_screenshot_does_not_cost_the_preview(steps: list[dict]):
    """A testable build is worth more than a picture of one. If the browser
    will not start, the deploy and the link still happen."""
    assert _step(steps, "Photograph the build")["continue-on-error"] is True


def test_the_comment_shows_the_runners_block(steps: list[dict]):
    message = _step(steps, "Say where the preview is")["with"]["message"]
    assert "steps.images.outputs.block" in message

    # The workflow's job is to read the block the runner wrote - from inside
    # the uploaded directory - and fill in the preview URL where the runner
    # left the placeholder. Both sides of that seam, or a rename in one file
    # quietly blanks every comment.
    block = _step(steps, "Name the images")["run"]
    assert f"client/dist/{SCREENSHOT_DIR}/comment.md" in block
    assert f"s|{PLACEHOLDER}|$BASE|g" in block
    assert PLACEHOLDER in RUNNER.read_text()


def test_the_images_are_sized_for_a_comment():
    """<img>, not ![](), because markdown image syntax carries no width and a
    2x capture is 780 px wide - twice the size of the phone it is of. The
    markup moved from the workflow into the runner with #998; the requirement
    did not."""
    runner = RUNNER.read_text()
    assert "<img src=" in runner
    assert 'width="' in runner


def test_the_comment_says_so_when_there_is_no_image(steps: list[dict]):
    """Rather than rendering a broken one. A pull request from a fork gets no
    secrets, so it gets no preview and no screenshot, and that is expected.
    The same line covers a photograph step that died before writing the
    block, which is why the run checks for the file and not just the flag."""
    block = _step(steps, "Name the images")["run"]
    assert "No screenshot this run" in block
    assert '[ ! -f "$BLOCK" ]' in block


def test_the_image_url_cannot_pick_up_a_double_slash(steps: list[dict]):
    """The two candidate bases disagree about a trailing slash - a wrangler
    alias URL may carry one, the worked-out URL does not - and
    `https://host//__screenshot/x.png` is a 404 on Pages."""
    assert 'BASE="${BASE%/}"' in _step(steps, "Name the images")["run"]


def test_no_screenshot_is_tracked_anywhere(steps: list[dict]):
    """The whole point of #988. `client/dist` is gitignored, so a capture
    written there cannot be committed even by `git add -A` - and the recipe
    directory, which IS tracked, holds drives and captions, never pixels."""
    assert not (REPO_ROOT / ".github" / "pr-screenshots").exists()
    assert not list(RECIPES.glob("*.png"))

    run = _step(steps, "Photograph the build")["run"]
    # No --out: the runner's own default is client/dist/__screenshot, which is
    # inside the gitignored build directory AND inside what wrangler uploads.
    # A --out here would be someone moving it back out of both at once.
    assert "--out" not in run
