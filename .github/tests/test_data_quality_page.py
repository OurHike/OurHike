"""/data/quality/, the data-quality page (pipeline/ELT.md decision 102, step 4), as both site builds deploy it.

The page ships two placeholders and reads its two files in the visitor's
browser, so it is right only if the deploy points it at the data the app in
the same deploy reads. `.github/scripts/configure_quality_page.py` makes that
substitution in pages.yml's "Assemble the site" and pr-preview.yml's "Assemble
the preview", and it lands under /data/, the dbt docs' path, so the same two
steps must keep the docs and the page from replacing each other. These tests
hold both halves, and run the shell fragment and the script rather than only
reading them: nothing else exercises either before a deploy does.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import configure_quality_page as configure
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
PAGE = REPO_ROOT / "site" / "src" / "pages" / "data" / "quality" / "index.astro"
SCRIPT = REPO_ROOT / ".github" / "scripts" / "configure_quality_page.py"
DATA_RELEASE_FILE = REPO_ROOT / "client" / "src" / "lib" / "dataRelease.ts"
PAGE_SOURCES = [
    PAGE,
    REPO_ROOT / "site" / "src" / "lib" / "dataQuality.mjs",
    REPO_ROOT / "site" / "src" / "lib" / "dataQualityHtml.mjs",
    REPO_ROOT / "site" / "src" / "scripts" / "dataQuality.js",
]
COMMAND = "python .github/scripts/configure_quality_page.py _site/data/quality/index.html"
SITE_BUILDS = [("pages.yml", "Assemble the site"), ("pr-preview.yml", "Assemble the preview")]
DOCS_COPY = 'cp -r "$DOCS_DIR"/. _site/data/'


def _steps(workflow: str) -> list[dict]:
    parsed = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
    return [step for job in parsed["jobs"].values() for step in job.get("steps", [])]


def _step(workflow: str, name: str) -> dict:
    return next(step for step in _steps(workflow) if step.get("name") == name)


def _commands(run: str) -> list[str]:
    return [line.strip() for line in run.splitlines() if line.strip() and not line.strip().startswith("#")]


def _minimal_page() -> str:
    return '<main id="data-quality" data-base="__DATA_BASE_URL__" data-release="__DATA_RELEASE__"></main>'


# ---------------------------------------------------------------- the page


def test_the_page_carries_each_placeholder_once_on_the_element_its_script_reads():
    """As data attributes, because Astro may move the script into /_astro/, where the substitution would not reach.

    Counted in the template, after the frontmatter: the frontmatter's comment
    names both placeholders, and Astro drops it from the page it builds.
    """
    template = PAGE.read_text(encoding="utf-8").split("---", 2)[2]
    assert 'data-base="__DATA_BASE_URL__"' in template
    assert 'data-release="__DATA_RELEASE__"' in template
    assert template.count(configure.BASE_PLACEHOLDER) == 1
    assert template.count(configure.RELEASE_PLACEHOLDER) == 1


@pytest.mark.parametrize("path", PAGE_SOURCES, ids=lambda path: path.name)
def test_the_page_hardcodes_no_bucket_url(path: Path):
    """The drift #457 was about: a second home for a value the app already has."""
    source = path.read_text(encoding="utf-8")
    for smell in ("r2.dev", "r2.cloudflarestorage.com", "https://pub-", "data.ourhike.org"):
        assert smell not in source, f"{smell} is hardcoded in {path.relative_to(REPO_ROOT)}"


# ---------------------------------------------------------------- both workflows


@pytest.mark.parametrize(("workflow", "assemble"), SITE_BUILDS)
def test_both_site_builds_point_the_page_at_the_data_their_app_reads(workflow: str, assemble: str):
    step = _step(workflow, assemble)
    assert COMMAND in _commands(step["run"])
    app = _step(workflow, "Build the app")["env"]["VITE_DATA_BASE_URL"]
    assert step["env"]["DATA_URL"] == app, f"{workflow} points /data/quality/ at another base than its app reads"


@pytest.mark.parametrize(("workflow", "assemble"), SITE_BUILDS)
def test_the_page_is_pointed_after_it_is_copied_in(workflow: str, assemble: str):
    commands = _commands(_step(workflow, assemble)["run"])
    assert commands.index("cp -r site/dist/. _site/") < commands.index(DOCS_COPY) < commands.index(COMMAND)


def _guard(workflow: str, assemble: str) -> str:
    """The lines of the step from its data/ guard to the docs copy, exactly as written."""
    lines = _step(workflow, assemble)["run"].splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "if [ -e _site/data ]; then")
    end = next(i for i, line in enumerate(lines) if line.strip() == DOCS_COPY)
    return "\n".join(lines[start : end + 1])


def _assemble(tmp_path: Path, workflow: str, assemble: str, *, site: dict[str, str], docs: dict[str, str]):
    for root, files in (("_site", site), ("docs", docs)):
        (tmp_path / root).mkdir(exist_ok=True)
        for relative, text in files.items():
            path = tmp_path / root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    # GitHub runs a `run:` script with `bash --noprofile --norc -eo pipefail`.
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", _guard(workflow, assemble)],
        cwd=tmp_path,
        env={**os.environ, "DOCS_DIR": str(tmp_path / "docs")},
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(("workflow", "assemble"), SITE_BUILDS)
def test_the_docs_land_beside_the_page_and_leave_it_alone(tmp_path: Path, workflow: str, assemble: str):
    done = _assemble(
        tmp_path,
        workflow,
        assemble,
        site={"index.html": "home", "data/quality/index.html": "the page"},
        docs={"index.html": "the docs", "assets/index.js": "js"},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert (tmp_path / "_site" / "data" / "quality" / "index.html").read_text() == "the page"
    assert (tmp_path / "_site" / "data" / "index.html").read_text() == "the docs"


@pytest.mark.parametrize(("workflow", "assemble"), SITE_BUILDS)
def test_a_site_that_puts_anything_else_under_data_is_refused(tmp_path: Path, workflow: str, assemble: str):
    done = _assemble(
        tmp_path,
        workflow,
        assemble,
        site={"data/quality/index.html": "the page", "data/index.html": "a stray"},
        docs={"index.html": "the docs"},
    )
    assert done.returncode != 0
    assert "::error::site/dist holds data/index.html beside data/quality/" in done.stdout
    assert (tmp_path / "_site" / "data" / "index.html").read_text() == "a stray", "refused before the docs were copied"


@pytest.mark.parametrize(("workflow", "assemble"), SITE_BUILDS)
def test_docs_that_bring_a_quality_folder_are_refused(tmp_path: Path, workflow: str, assemble: str):
    done = _assemble(
        tmp_path,
        workflow,
        assemble,
        site={"data/quality/index.html": "the page"},
        docs={"index.html": "the docs", "quality/index.html": "the docs' own"},
    )
    assert done.returncode != 0
    assert "::error::The dbt docs hold a quality/ of their own" in done.stdout
    assert (tmp_path / "_site" / "data" / "quality" / "index.html").read_text() == "the page"


@pytest.mark.parametrize(("workflow", "assemble"), SITE_BUILDS)
def test_a_site_with_no_data_folder_still_gets_the_docs(tmp_path: Path, workflow: str, assemble: str):
    done = _assemble(tmp_path, workflow, assemble, site={"index.html": "home"}, docs={"index.html": "the docs"})
    assert done.returncode == 0, done.stdout + done.stderr
    assert (tmp_path / "_site" / "data" / "index.html").read_text() == "the docs"


# ---------------------------------------------------------------- the script


def test_the_script_substitutes_both_placeholders_and_escapes_them():
    page = configure.configure(_minimal_page(), data_url='https://data.example.org/env/ua/?a=1&b="2"', release="2026-10-03-2")
    assert configure.BASE_PLACEHOLDER not in page
    assert configure.RELEASE_PLACEHOLDER not in page
    assert 'data-base="https://data.example.org/env/ua/?a=1&amp;b=&quot;2&quot;"' in page
    assert 'data-release="2026-10-03-2"' in page
    assert 'data-base="https://data.example.org"' in configure.configure(
        _minimal_page(), data_url="https://data.example.org/", release="2026-10-03-2"
    ), "a trailing slash is dropped, as the page drops it"


def test_no_data_url_leaves_the_page_saying_it_is_not_configured():
    page = configure.configure(_minimal_page(), data_url="", release="2026-10-03-2")
    assert 'data-base="__DATA_BASE_URL__"' in page
    assert 'data-release="2026-10-03-2"' in page


@pytest.mark.parametrize(
    "page",
    [
        '<main data-base="__DATA_BASE_URL__"></main>',
        '<main data-base="__DATA_BASE_URL__" data-release="__DATA_RELEASE__">__DATA_BASE_URL__</main>',
        "<main></main>",
    ],
    ids=["no release placeholder", "a placeholder twice", "neither"],
)
def test_the_script_refuses_a_page_whose_placeholders_moved(page: str):
    with pytest.raises(configure.Refused):
        configure.configure(page, data_url="https://data.example.org", release="2026-10-03-2")


def test_the_script_reads_the_release_pages_yml_checks():
    """The same line, read the same way: pages.yml's pin check runs sed over it, and this runs that sed command."""
    run = _step("pages.yml", "Confirm the pinned data release exists")["run"]
    (line,) = [line.strip() for line in run.splitlines() if line.strip().startswith("release=$(sed")]
    sed = subprocess.run(
        ["bash", "-c", f'{line}\nprintf %s "$release"'],
        cwd=REPO_ROOT / "client",
        capture_output=True,
        text=True,
        check=True,
    )
    assert sed.stdout
    assert configure.pinned_release(DATA_RELEASE_FILE.read_text(encoding="utf-8")) == sed.stdout


@pytest.mark.parametrize(
    "source",
    ["export const DATA_RELEASE = SOMETHING", "export const DATA_RELEASE = 'latest'", ""],
    ids=["not a string", "not a release id", "absent"],
)
def test_the_script_refuses_a_client_whose_release_it_cannot_read(source: str):
    with pytest.raises(configure.Refused):
        configure.pinned_release(source)


def _run_script(tmp_path: Path, page: str, data_url: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    target = tmp_path / "index.html"
    target.write_text(page, encoding="utf-8")
    done = subprocess.run(
        ["python3", str(SCRIPT), str(target)],
        env={**os.environ, "DATA_URL": data_url},
        capture_output=True,
        text=True,
    )
    return done, target


def test_the_script_rewrites_the_page_it_is_given(tmp_path: Path):
    done, target = _run_script(tmp_path, _minimal_page(), "https://data.example.org")
    assert done.returncode == 0, done.stderr
    release = configure.pinned_release(DATA_RELEASE_FILE.read_text(encoding="utf-8"))
    assert target.read_text() == (
        f'<main id="data-quality" data-base="https://data.example.org" data-release="{release}"></main>'
    )
    assert f"reads https://data.example.org, release {release}" in done.stdout


def test_the_script_warns_rather_than_fails_without_a_data_url(tmp_path: Path):
    done, target = _run_script(tmp_path, _minimal_page(), "")
    assert done.returncode == 0, done.stderr
    assert "::warning::No DATA_URL" in done.stdout
    assert configure.BASE_PLACEHOLDER in target.read_text()


def test_the_script_fails_on_a_page_it_cannot_configure(tmp_path: Path):
    done, target = _run_script(tmp_path, "<main></main>", "https://data.example.org")
    assert done.returncode == 1
    assert "::error::" in done.stderr
    assert target.read_text() == "<main></main>", "nothing is written when the page is refused"
    missing = subprocess.run(["python3", str(SCRIPT), str(tmp_path / "absent.html")], capture_output=True, text=True)
    assert missing.returncode == 1
    assert "did not reach the site" in missing.stderr
