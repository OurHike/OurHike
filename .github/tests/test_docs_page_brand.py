"""The dbt docs page /data/ serves, with OurHike's name on it (review of PR #1805, thread 4279330823).

`.github/scripts/brand_docs_page.py` rewrites the `index.html` that `dbt docs generate` writes:
the title, a bar back to the site and to /data/quality/, light by default, dbt's Upgrade cards
hidden. `.github/actions/dbt-docs-site/build.sh` runs it on every docs build pages.yml and
pr-preview.yml ship. These tests hold the script to dbt 2.0.6's page and build.sh to running it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import brand_docs_page as brand
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "brand_docs_page.py"
BUILD_SH = REPO_ROOT / ".github" / "actions" / "dbt-docs-site" / "build.sh"
#: The page dbt 2.0.6 writes, as its binary holds it (read 2026-10-15), with the bootstrap comment
#: replaced by the settings script `dbt docs generate` writes there.
DBT_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>dbt docs v2</title>
    <script>window.__DBT_DOCS__ = {"telemetry":{"enabled":false}};</script>
  <script type="module" crossorigin src="./assets/index-_HuaFKD4.js"></script>
  <link rel="modulepreload" crossorigin href="./assets/react-DrLDXEZi.js">
  <link rel="stylesheet" crossorigin href="./assets/index-VfmGkBLZ.css">
</head>
  <body>
    <div id="root"></div>
  </body>
</html>
"""
#: The app's two files as far as the script relies on them (brand_docs_page.py's app_problems()), cut from
#: dbt 2.0.6's own (read 2026-10-15).
APP_SCRIPT = 'const N9="dbt-docs-v2:theme";className:"locate-pane__connect-hook"'
APP_STYLESHEET = (
    ".app{display:grid;grid-template-rows:64px 1fr;height:100vh}.shell{display:grid;height:calc(100vh - 64px);min-height:0}"
)
COLOURS = {
    "light": dict.fromkeys(brand.TOKENS, "#ffffff"),
    "dark": dict.fromkeys(brand.TOKENS, "#000000"),
}


def _branded() -> str:
    return brand.brand(DBT_PAGE, origin="https://ourhike.org", colours=COLOURS)


def _docs(tmp_path: Path, *, script: str = APP_SCRIPT, stylesheet: str = APP_STYLESHEET) -> Path:
    """A docs directory holding DBT_PAGE and its two app files; the page's path."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-_HuaFKD4.js").write_text(script, encoding="utf-8")
    (tmp_path / "assets" / "index-VfmGkBLZ.css").write_text(stylesheet, encoding="utf-8")
    page = tmp_path / "index.html"
    page.write_text(DBT_PAGE, encoding="utf-8")
    return page


def test_build_sh_brands_the_page_dbt_wrote_before_adding_duckdb_beside_it():
    lines = [line.strip() for line in BUILD_SH.read_text(encoding="utf-8").splitlines()]
    generate = next(i for i, line in enumerate(lines) if line.startswith("dbt docs generate"))
    (branded,) = [i for i, line in enumerate(lines) if "brand_docs_page.py" in line and not line.startswith("#")]
    copy = next(i for i, line in enumerate(lines) if line.startswith('cp -r "$duckdb_dir" "$out/duckdb"'))
    assert generate < branded < copy
    assert '"$out/index.html"' in lines[branded]


def test_the_page_is_titled_as_the_site_names_it():
    page = _branded()
    assert "<title>How the data is built — OurHike</title>" in page
    assert "dbt docs v2" not in page


def test_the_bar_leads_the_body_and_names_the_site_and_both_data_pages():
    page = _branded()
    body = page.split("<body>", 1)[1]
    assert body.lstrip().startswith('<nav class="ourhike-bar" aria-label="OurHike">')
    assert '<a class="ourhike-bar__home" href="https://ourhike.org/">OurHike</a>' in body
    assert '<a class="ourhike-bar__tab" href="/data/how/" aria-current="page">How the data is built</a>' in body
    assert '<a class="ourhike-bar__tab" href="/data/quality/">Data quality</a>' in body


def test_the_tabs_are_the_ones_data_nav_draws_on_data_quality():
    """site/src/components/DataNav.astro names the two data pages; the bar names them the same way."""
    nav = (REPO_ROOT / "site" / "src" / "components" / "DataNav.astro").read_text(encoding="utf-8")
    for href, label in brand.TABS:
        assert f"{{ href: '{href}', label: '{label}' }}" in nav


def test_the_site_is_named_by_site_cname():
    """The one copy of the hostname (#733), never retyped."""
    origin = brand.site_origin((REPO_ROOT / "site" / "CNAME").read_text(encoding="utf-8"))
    assert origin == f"https://{(REPO_ROOT / 'site' / 'CNAME').read_text(encoding='utf-8').strip()}"
    with pytest.raises(brand.Refused):
        brand.site_origin("ourhike.org\nexample.com")


def test_dbt_upgrade_cards_are_hidden_and_the_page_starts_light():
    page = _branded()
    assert ".locate-pane__connect-hook{display:none!important}" in page
    assert "#root>.app{height:100%}" in page, "the app fills what the bar leaves, not the whole window"
    head = page.split("</head>", 1)[0]
    script = brand.theme_script()
    assert script in head
    assert head.index(script) < head.index('<script type="module"'), "set before the app reads it"
    assert 'if(!localStorage.getItem("dbt-docs-v2:theme"))' in script, "a visitor's own choice is kept"


def test_the_bar_takes_the_site_tokens_in_both_themes():
    css = """:root{--white:#ffffff;--ink:#111111;--bg-surface:var(--white);--border-1:#e4ddca;--fg-1:var(--ink);
    --fg-2:#5a5346;--bg-sunken:#e3ecda;--brand-primary-hover:#284029;}
    :root[data-theme='dark']{--bg-surface:var(--ink);--fg-1:var(--white);}"""
    colours = brand.theme_colours(css)
    assert colours["light"]["bg"] == "#ffffff"
    assert colours["light"]["fg"] == "#111111"
    assert colours["dark"]["bg"] == "#111111"
    assert colours["dark"]["fg"] == "#ffffff"
    assert colours["dark"]["border"] == "#e4ddca", "a token the dark block leaves alone keeps its light value"
    real = brand.theme_colours(brand.COLORS.read_text(encoding="utf-8"))
    assert set(real) == {"light", "dark"}
    assert all(value.startswith("#") for theme in real.values() for value in theme.values())
    assert real["light"]["bg"] != real["dark"]["bg"]


@pytest.mark.parametrize(
    "page",
    [
        DBT_PAGE.replace("<title>dbt docs v2</title>", "<title>dbt docs v3</title>"),
        DBT_PAGE.replace("<body>", "<body><body>"),
        DBT_PAGE.replace("</head>", ""),
    ],
    ids=["another title", "two bodies", "no head end"],
)
def test_a_page_dbt_writes_differently_is_refused(page: str):
    with pytest.raises(brand.Refused):
        brand.brand(page, origin="https://ourhike.org", colours=COLOURS)


def test_a_page_is_branded_once():
    with pytest.raises(brand.Refused, match="already carries"):
        brand.brand(_branded(), origin="https://ourhike.org", colours=COLOURS)


@pytest.mark.parametrize(
    ("script", "stylesheet", "missing"),
    [
        (APP_SCRIPT.replace("locate-pane__connect-hook", "rail"), APP_STYLESHEET, "locate-pane__connect-hook"),
        (APP_SCRIPT.replace("dbt-docs-v2:theme", "theme"), APP_STYLESHEET, "dbt-docs-v2:theme"),
        (APP_SCRIPT, APP_STYLESHEET.replace("height:100vh}", "height:100dvh}"), "app"),
        (APP_SCRIPT, APP_STYLESHEET.replace("calc(100vh - 64px)", "calc(100vh - 56px)"), "shell"),
    ],
    ids=["no Upgrade box", "another theme key", "the app sized another way", "another header height"],
)
def test_an_app_that_no_longer_holds_what_the_brand_relies_on_is_refused(
    tmp_path: Path, script: str, stylesheet: str, missing: str
):
    page = _docs(tmp_path, script=script, stylesheet=stylesheet)
    problems = brand.app_problems(DBT_PAGE, tmp_path)
    assert len(problems) == 1 and missing in problems[0]
    done = subprocess.run(["python3", str(SCRIPT), str(page)], capture_output=True, text=True)
    assert done.returncode == 1
    assert page.read_text(encoding="utf-8") == DBT_PAGE, "nothing is written when the app is refused"


def test_the_app_files_this_relies_on_are_found_beside_the_page(tmp_path: Path):
    _docs(tmp_path)
    assert brand.app_problems(DBT_PAGE, tmp_path) == []
    assert brand.app_problems(DBT_PAGE, tmp_path / "elsewhere") == [
        "the page's app script, assets/index-_HuaFKD4.js, is not beside it",
        "the page's app stylesheet, assets/index-VfmGkBLZ.css, is not beside it",
    ]
    assert brand.app_problems(DBT_PAGE.replace("index-_HuaFKD4.js", "main.js"), tmp_path) == [
        "the page links 0 app scripts, not one"
    ]


def test_the_script_rewrites_the_page_and_refuses_what_it_cannot(tmp_path: Path):
    page = _docs(tmp_path)
    done = subprocess.run(["python3", str(SCRIPT), str(page)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert 'class="ourhike-bar"' in page.read_text(encoding="utf-8")
    again = subprocess.run(["python3", str(SCRIPT), str(page)], capture_output=True, text=True)
    assert again.returncode == 1
    assert "::error::" in again.stderr
    missing = subprocess.run(["python3", str(SCRIPT), str(tmp_path / "absent.html")], capture_output=True, text=True)
    assert missing.returncode == 1
