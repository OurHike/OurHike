"""Tests for the public status page (#467, #431's item 3).

`site/status/index.html` answers "is it me or us?" by checking the data bucket
**from the visitor's own browser**. That is not a stylistic choice: the page is
served from the same origin as the app, so a fetch from it crosses the exact
CORS boundary the app's fetches cross - the boundary that took the map down for
eight days in #427 while every server-side check stayed green, because none of
them was a browser.

The page therefore must not carry a bucket URL of its own. It ships a
placeholder, and `pages.yml` substitutes the same `DATA_BASE_URL` the app is
built with, so the two can never disagree. These tests are what hold that
arrangement together - the substitution is a shell step nothing else exercises,
and a page that silently kept its placeholder would report itself unconfigured
forever while looking deployed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_PAGE = REPO_ROOT / "site" / "status" / "index.html"
PAGES_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pages.yml"

PLACEHOLDER = "__DATA_BASE_URL__"


@pytest.fixture(scope="module")
def page_source() -> str:
    return STATUS_PAGE.read_text()


@pytest.fixture(scope="module")
def assemble_step() -> str:
    """The `Assemble the site` step's script, which does the substitution."""
    workflow = yaml.safe_load(PAGES_WORKFLOW.read_text())
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == "Assemble the site":
                return step["run"]
    raise AssertionError("pages.yml has no 'Assemble the site' step")


def test_the_page_exists_where_pages_yml_will_find_it():
    """`cp -r site/. _site/` puts this at `/OurHike/status/`. The path is the
    URL, so moving the file moves the address people were given."""
    assert STATUS_PAGE.is_file()


def test_the_page_carries_a_placeholder_rather_than_a_bucket_url(page_source):
    assert PLACEHOLDER in page_source


def test_the_page_hardcodes_no_bucket_url(page_source):
    """The drift #457 was about, in its cheapest possible form. A URL committed
    here would be a second home for a value the app already has, and the copy
    that goes stale is always the one nobody builds against."""
    for smell in ("r2.dev", "r2.cloudflarestorage.com", "https://pub-"):
        assert smell not in page_source, f"{smell} is hardcoded in the status page"


def test_pages_yml_substitutes_the_placeholder(assemble_step):
    assert PLACEHOLDER in assemble_step
    assert "_site/status/index.html" in assemble_step


def test_the_substitution_reads_the_url_from_the_environment(assemble_step):
    """Data, never code. The URL reaches python through `os.environ` rather
    than being interpolated into the source it runs."""
    assert 'os.environ["DATA_URL"]' in assemble_step
    assert "DATA_URL" in assemble_step


def test_the_substitution_does_not_use_sed(assemble_step):
    """A URL contains `/`, so a sed delimiter collision produces a mangled page
    rather than a failure - the worst shape a bug can take on a page whose
    entire job is to be trustworthy.

    Comment lines are stripped before asserting, because the step explains this
    reasoning in a comment that names `sed` - matching prose rather than
    commands would make the comment unwritable.
    """
    commands = "\n".join(line for line in assemble_step.splitlines() if not line.strip().startswith("#"))

    assert "sed" not in commands


def test_the_substitution_actually_works(tmp_path, assemble_step):
    """The step is a shell fragment nothing else runs. Executing the real
    command against a real copy is the only thing that would catch a quoting
    mistake before a deploy does."""
    site = tmp_path / "_site" / "status"
    site.mkdir(parents=True)
    (site / "index.html").write_text(STATUS_PAGE.read_text())

    command = next(line.strip() for line in assemble_step.splitlines() if line.strip().startswith("python3 -c"))
    subprocess.run(
        command,
        shell=True,
        cwd=tmp_path,
        check=True,
        env={**os.environ, "DATA_URL": "https://data.example.org"},
    )

    written = (site / "index.html").read_text()
    assert PLACEHOLDER not in written
    assert "https://data.example.org" in written


def test_an_unsubstituted_page_reports_itself_unconfigured(page_source):
    """The failure mode that would otherwise be invisible: a deploy where
    DATA_BASE_URL was unset leaves the placeholder in place. The page has to
    notice that about itself, because "not configured" and "the map is down"
    are different sentences and only one of them is about an outage."""
    assert "startsWith('__')" in page_source
    assert "not configured" in page_source


def test_the_page_states_the_two_things_it_cannot_tell_you(page_source):
    """#431 asked for both limits in the page's own copy rather than implied:
    it shares an origin with what it reports on, and a hiker with no signal
    cannot read it. A status page that overstates its coverage is worse than
    none."""
    assert "same place as the app" in page_source
    assert "without one" in page_source


def test_the_page_needs_no_build_step(page_source):
    """`site/` is copied verbatim; nothing compiles it. An import or a bare
    module script would ship as a 404 rather than as a page."""
    assert "import " not in page_source.split("<script>")[-1]
    assert 'type="module"' not in page_source
