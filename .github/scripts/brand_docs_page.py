"""Put OurHike's name on the dbt docs page that /data/ serves (review of PR #1805, thread 4279330823).

    python .github/scripts/brand_docs_page.py <docs dir>/index.html

`dbt docs generate` (dbt 2.0.6) writes the page as its own app titled "dbt docs v2", dark unless a
visitor picks light, with dbt's "Upgrade" cards in its left rail and no way back to the site.
.github/actions/dbt-docs-site/build.sh runs this right after dbt has written the page, before it adds
DuckDB-WASM beside it, and this rewrites that one file:

- THE TITLE: "How the data is built — OurHike", the name site/src/components/DataNav.astro gives
  the page, in the site's "<page> — OurHike" shape.
- A BAR ACROSS THE TOP, the site's two data tabs as DataNav.astro draws them on /data/quality/,
  after the site's name: OurHike, to the site's front page by its full address (site/CNAME, the
  one copy of the hostname), because docs.ourhike.org has none of the site's pages (pipeline/ELT.md
  decision 144); "How the data is built", this page; "Data quality", /data/quality/, root-relative
  as DataNav's tabs are, since every host serving the docs serves both at /data/. Its colours are
  read from client/src/design-system/tokens/colors.css, light and dark, never copied here. The app
  sizes itself to the window (`.app` at 100vh, its `.shell` at 100vh less its 64 px header, in dbt
  2.0.6's stylesheet), which would push its own bottom, the theme switch, under the window's edge
  by the bar's height; so the page becomes a column, the bar and then the app's root, and the two
  rules are restated to fill the root instead.
- DBT'S UPGRADE CARDS HIDDEN. The app draws them in its left rail inside a box classed
  `locate-pane__connect-hook` (read 2026-10-15 from the page's own code in dbt 2.0.6), with an
  "Upgrade" button to getdbt.com's contact page; a stylesheet rule hides that box.
- LIGHT UNLESS THE VISITOR CHOSE OTHERWISE. The app keeps the visitor's choice in localStorage
  under `dbt-docs-v2:theme` ("light", "dark" or "system") and is dark when the key is unset (read
  the same day). A line of script before the app starts sets the key to "light" only when it is
  unset, so the app's own switch still works and is remembered.

Exit 1 when the page is not shaped as dbt 2.0.6 writes it (its title, `</head>` and `<body>` each
exactly once), already carries the bar, or links an app that no longer holds what this relies on:
the Upgrade box's class and the theme key in its script, and the two 100vh rules in its stylesheet
(app_problems()). A dbt that writes another page must be looked at, not branded blind.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CNAME = REPO_ROOT / "site" / "CNAME"
COLORS = REPO_ROOT / "client" / "src" / "design-system" / "tokens" / "colors.css"

#: The title dbt 2.0.6 gives the page.
DBT_TITLE = "<title>dbt docs v2</title>"
TITLE = "How the data is built — OurHike"
#: The bar's element; its class is how a branded page is recognised.
BAR_CLASS = "ourhike-bar"
#: The box the app draws dbt's Upgrade cards in (the docstring).
UPGRADE_BOX = ".locate-pane__connect-hook"
#: The app's theme key and the value it starts at here (the docstring).
THEME_KEY = "dbt-docs-v2:theme"
THEME = "light"
#: The site's tokens the bar is drawn in, by what each colours.
TOKENS = {
    "bg": "--bg-surface",
    "border": "--border-1",
    "fg": "--fg-1",
    "muted": "--fg-2",
    "current-bg": "--bg-sunken",
    "current-fg": "--brand-primary-hover",
}
#: The tabs, as site/src/components/DataNav.astro names them.
TABS = (("/data/", "How the data is built"), ("/data/quality/", "Data quality"))
#: What this relies on in dbt 2.0.6's own app (the docstring), by the file that holds it.
APP_SCRIPT_HOLDS = ("locate-pane__connect-hook", f'"{THEME_KEY}"')
APP_STYLESHEET_HOLDS = (
    re.compile(r"\.app\{[^}]*height:100vh"),
    re.compile(r"\.shell\{[^}]*height:calc\(100vh - 64px\)"),
)
APP_SCRIPT = re.compile(r'<script type="module" crossorigin src="\./(assets/index-[\w-]+\.js)"></script>')
APP_STYLESHEET = re.compile(r'<link rel="stylesheet" crossorigin href="\./(assets/index-[\w-]+\.css)">')
BLOCK = re.compile(r"(:root(?:\[data-theme='dark'\])?)\s*\{(.*?)\}", re.DOTALL)
DECLARATION = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
VAR = re.compile(r"var\((--[\w-]+)\)")


class Refused(Exception):
    """The page, or a file this reads, is not shaped the way this step expects."""


def site_origin(cname: str) -> str:
    """https://<the hostname site/CNAME holds>, or Refused."""
    host = cname.strip()
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host):
        raise Refused(f"site/CNAME does not hold one hostname: {host!r}")
    return f"https://{host}"


def theme_colours(css: str) -> dict[str, dict[str, str]]:
    """{"light": {...}, "dark": {...}}: each of TOKENS' values in colors.css's two blocks, var() resolved."""
    blocks = {selector: dict(DECLARATION.findall(body)) for selector, body in BLOCK.findall(css)}
    light = blocks.get(":root")
    dark = blocks.get(":root[data-theme='dark']")
    if light is None or dark is None:
        raise Refused("colors.css no longer holds a :root block and a :root[data-theme='dark'] block")

    def resolve(name: str, scope: dict[str, str]) -> str:
        value = scope.get(name, light.get(name))
        for _ in range(8):
            if value is None:
                break
            match = VAR.fullmatch(value.strip())
            if match is None:
                return value.strip()
            value = scope.get(match.group(1), light.get(match.group(1)))
        raise Refused(f"colors.css gives {name} no value this step can read")

    return {
        theme: {role: resolve(token, scope) for role, token in TOKENS.items()}
        for theme, scope in (("light", light), ("dark", {**light, **dark}))
    }


def _custom_properties(colours: dict[str, str]) -> str:
    return "".join(f"--{BAR_CLASS}-{role}:{value};" for role, value in colours.items())


def style(colours: dict[str, dict[str, str]]) -> str:
    """The bar's rules, the app laid out under it, and the Upgrade box hidden."""
    bar = f".{BAR_CLASS}"
    return (
        "<style>"
        "html,body{height:100%}"
        "body{margin:0;display:flex;flex-direction:column}"
        "#root{flex:1 1 0;min-height:0;position:relative}"
        "#root>.app{height:100%}"
        "#root .shell{height:auto}"
        f"{bar}{{{_custom_properties(colours['light'])}flex:none;display:flex;flex-wrap:wrap;align-items:center;"
        f"gap:4px 16px;padding:6px 16px;background:var(--{BAR_CLASS}-bg);"
        f"border-bottom:1px solid var(--{BAR_CLASS}-border);"
        'font:600 14px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif}'
        f"html.dark {bar}{{{_custom_properties(colours['dark'])}}}"
        f"{bar}__home{{color:var(--{BAR_CLASS}-fg);font-size:15px;font-weight:700;text-decoration:none}}"
        f"{bar}__tabs{{display:flex;flex-wrap:wrap;gap:4px}}"
        f"{bar}__tab{{display:inline-flex;align-items:center;min-height:32px;padding:0 12px;border-radius:999px;"
        f"color:var(--{BAR_CLASS}-muted);text-decoration:none}}"
        f"{bar}__tab:hover{{color:var(--{BAR_CLASS}-fg)}}"
        f"{bar}__tab[aria-current=page]{{background:var(--{BAR_CLASS}-current-bg);"
        f"color:var(--{BAR_CLASS}-current-fg)}}"
        f"{bar} a:focus-visible{{outline:2px solid var(--{BAR_CLASS}-current-fg);outline-offset:2px}}"
        f"@media (max-width:720px){{{bar}__tab{{min-height:44px}}}}"
        f"{UPGRADE_BOX}{{display:none!important}}"
        "</style>"
    )


def bar(origin: str) -> str:
    """The bar's markup: the site's name, then the two data tabs, this page's marked current."""
    current = ' aria-current="page"'
    tabs = "".join(
        f'<a class="{BAR_CLASS}__tab" href="{href}"{current if href == TABS[0][0] else ""}>{html.escape(label)}</a>'
        for href, label in TABS
    )
    return (
        f'<nav class="{BAR_CLASS}" aria-label="OurHike">'
        f'<a class="{BAR_CLASS}__home" href="{html.escape(origin, quote=True)}/">OurHike</a>'
        f'<span class="{BAR_CLASS}__tabs">{tabs}</span>'
        "</nav>"
    )


def theme_script() -> str:
    """Light until the visitor picks otherwise in the app's own switch (the docstring)."""
    return (
        f'<script>try{{if(!localStorage.getItem("{THEME_KEY}"))'
        f'localStorage.setItem("{THEME_KEY}","{THEME}")}}catch(e){{}}</script>'
    )


def brand(page: str, *, origin: str, colours: dict[str, dict[str, str]]) -> str:
    """The page with its title, the bar, the stylesheet and the theme line, or Refused."""
    if f'class="{BAR_CLASS}"' in page:
        raise Refused("the docs page already carries OurHike's bar: brand it once, from dbt's own output")
    for part in (DBT_TITLE, "</head>", "<body>"):
        if page.count(part) != 1:
            raise Refused(
                f"the docs page holds {part} {page.count(part)} times, not once: dbt writes it differently now, "
                "and .github/scripts/brand_docs_page.py must be updated with it"
            )
    page = page.replace(DBT_TITLE, f"<title>{html.escape(TITLE)}</title>\n    {theme_script()}")
    page = page.replace("</head>", f"{style(colours)}\n</head>")
    return page.replace("<body>", f"<body>\n    {bar(origin)}")


def app_problems(page: str, directory: Path) -> list[str]:
    """What the page's app no longer holds of APP_SCRIPT_HOLDS and APP_STYLESHEET_HOLDS, read from its own files."""
    problems = []
    for pattern, kind in ((APP_SCRIPT, "script"), (APP_STYLESHEET, "stylesheet")):
        found = pattern.findall(page)
        if len(found) != 1:
            problems.append(f"the page links {len(found)} app {kind}s, not one")
            continue
        if not (directory / found[0]).is_file():
            problems.append(f"the page's app {kind}, {found[0]}, is not beside it")
            continue
        text = (directory / found[0]).read_text(encoding="utf-8")
        if kind == "script":
            problems += [f"{found[0]} no longer holds {needle}" for needle in APP_SCRIPT_HOLDS if needle not in text]
        else:
            problems += [f"{found[0]} no longer holds {rule.pattern}" for rule in APP_STYLESHEET_HOLDS if not rule.search(text)]
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        if not path.is_file():
            raise Refused(f"{path} does not exist, so dbt wrote no docs page there")
        page = path.read_text(encoding="utf-8")
        branded = brand(
            page,
            origin=site_origin(CNAME.read_text(encoding="utf-8")),
            colours=theme_colours(COLORS.read_text(encoding="utf-8")),
        )
        problems = app_problems(page, path.parent)
        if problems:
            raise Refused(
                "dbt's app is not the one .github/scripts/brand_docs_page.py was written against: " + "; ".join(problems)
            )
    except Refused as refused:
        print(f"::error::{refused}", file=sys.stderr)
        return 1
    path.write_text(branded, encoding="utf-8")
    print(f"branded {path}: titled {TITLE!r}, with the site's bar, light by default, dbt's Upgrade cards hidden")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
