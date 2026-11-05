"""The single-page apps' fallback on production GitHub Pages (#2014).

`.github/scripts/spa_fallback.py` writes `_site/404.html` in pages.yml's
"Assemble the site". Without it every deep link into the app answered GitHub
Pages' own 404 in production (measured 2026-09-17; features/ORG_ONBOARDING.md's
Known gaps) while the Cloudflare previews and UA resolved the same addresses.
These tests pin the step in the assembly and the page it writes; whether a
browser boots the shell from that page is measured, not asserted here, because
this suite runs no browser - the pull request for #2014 records the run.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import spa_fallback
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pages.yml"
SCRIPT = REPO_ROOT / ".github" / "scripts" / "spa_fallback.py"
COMMAND = "python .github/scripts/spa_fallback.py _site"
SHELL = '<!doctype html><html><head><script type="module" src="/app/assets/index-abc.js"></script></head></html>'


def _assemble() -> str:
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    steps = [step for job in jobs.values() for step in job["steps"]]
    return next(step for step in steps if step.get("name") == "Assemble the site")["run"]


def _site(tmp_path: Path, *shells: str) -> Path:
    site = tmp_path / "_site"
    (site).mkdir()
    (site / "index.html").write_text("<p>the landing page</p>", encoding="utf-8")
    for base in shells:
        (site / base).mkdir(parents=True)
        (site / base / "index.html").write_text(SHELL.replace("/app/", f"/{base}/"), encoding="utf-8")
    return site


def _bases(page: str) -> list[str]:
    (bases,) = re.findall(r"var bases = (\[.*?\]);", page)
    return json.loads(bases)


class TestTheProductionAssembly:
    def test_the_site_is_given_the_fallback(self):
        """Run on the assembled `_site`, once, and only after the app shell is in it."""
        lines = [line.strip() for line in _assemble().splitlines()]
        assert lines.count(COMMAND) == 1
        assert lines.index("cp -r site/dist/. _site/") < lines.index(COMMAND)
        assert lines.index("cp -r client/dist/. _site/app/") < lines.index(COMMAND)

    def test_production_is_not_given_the_app_shell_as_its_404(self):
        """The previews' one-line copy would boot the map for a mistyped site address, and never the survey."""
        run = _assemble()
        assert "_site/404.html" not in run
        assert "_redirects" not in run


class TestThePage:
    def test_it_falls_back_to_the_app_and_nothing_the_deploy_does_not_hold(self, tmp_path):
        site = _site(tmp_path, "app")
        assert spa_fallback.write(site) == ["/app/"]
        assert _bases((site / "404.html").read_text(encoding="utf-8")) == ["/app/"]

    def test_the_survey_door_opens_in_the_deploy_that_holds_its_shell(self, tmp_path):
        """features/STRUCTURE_INVENTORY.md conflict 6: the survey is a second shell at `/survey/`."""
        site = _site(tmp_path, "app", "survey")
        assert spa_fallback.write(site) == ["/app/", "/survey/"]
        assert _bases((site / "404.html").read_text(encoding="utf-8")) == ["/app/", "/survey/"]

    def test_it_boots_the_shell_at_the_address_it_was_asked_for(self, tmp_path):
        """The shell replaces the page in place, so `location` is still the deep link the app reads."""
        site = _site(tmp_path, "app")
        spa_fallback.write(site)
        page = (site / "404.html").read_text(encoding="utf-8")
        assert "fetch(base," in page
        assert "document.write(shell)" in page
        assert "location.replace" not in page and "location.href =" not in page

    def test_everything_else_is_a_not_found_page(self, tmp_path):
        """Shown when no shell's base matches or the shell cannot be fetched, and without script at all."""
        site = _site(tmp_path, "app")
        spa_fallback.write(site)
        page = (site / "404.html").read_text(encoding="utf-8")
        assert '<main id="not-found" hidden>' in page
        assert ".catch(notFound)" in page
        noscript = re.search(r"<noscript>(.*?)</noscript>", page, re.S)
        assert noscript and "There is no page at this address" in noscript.group(1)
        assert '<meta name="robots" content="noindex" />' in page

    def test_the_shells_it_names_are_its_own_list(self):
        assert spa_fallback.SHELLS == ("/app/", "/survey/")
        assert all(base.startswith("/") and base.endswith("/") for base in spa_fallback.SHELLS)


class TestRefusals:
    def test_no_app_shell_is_a_broken_assembly(self, tmp_path):
        site = _site(tmp_path, "survey")
        with pytest.raises(spa_fallback.Refused, match="app/index.html is missing"):
            spa_fallback.write(site)
        assert not (site / "404.html").exists()

    def test_a_404_html_the_site_brought_is_not_silently_replaced(self, tmp_path):
        site = _site(tmp_path, "app")
        (site / "404.html").write_text("the site's own", encoding="utf-8")
        with pytest.raises(spa_fallback.Refused, match="already exists"):
            spa_fallback.write(site)
        assert (site / "404.html").read_text(encoding="utf-8") == "the site's own"

    @pytest.mark.parametrize(("shells", "code"), [(("app",), 0), ((), 1)])
    def test_the_command_pages_yml_runs(self, tmp_path, shells, code):
        site = _site(tmp_path, *shells)
        done = subprocess.run([sys.executable, str(SCRIPT), str(site)], capture_output=True, text=True)
        assert done.returncode == code, done.stdout + done.stderr
        assert (site / "404.html").exists() == (code == 0)
        if code:
            assert done.stdout.startswith("::error::")
