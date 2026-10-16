"""The data docs on a host of their own, docs.ourhike.org.

    python3 .github/scripts/docs_host.py live <origin>
    python3 .github/scripts/docs_host.py bundle <site dir> <out dir> --build <sha>
    python3 .github/scripts/docs_host.py redirects <docs host's data dir> <out dir> <origin>
    python3 .github/scripts/docs_host.py check <docs host dir>
    python3 .github/scripts/docs_host.py target
    python3 .github/scripts/docs_host.py confirm <origin> --build <sha> --domain <status> [--site-sends <origin>]

WHY. The dbt docs and the data-quality page used to be served at
ourhike.org/data/, the same origin as the app at /app/, where a signed-in
hiker's session is kept in browser storage, so any script on /data/ (dbt's
own page, DuckDB-WASM) could read it. Decision 144's first half hash-pinned
what those scripts are built from; this is the second half, which the
maintainer chose by poll on 2026-10-10: the docs move to docs.ourhike.org,
a Cloudflare Pages project named `ourhike-docs` (pages.yml's env names both).

THE DOCS HOST SERVES THE BUNDLE UNDER /data/, byte for byte the `_site/data/`
pages.yml assembles, configures and checks for ourhike.org. Not at its root,
because the bundle names its own paths from the root: DuckDB-WASM's base is
`/data/duckdb/duckdb.js?` (.github/actions/dbt-docs-site/build.sh), the one
decision 93's browser run measured, and the data pages' tabs are `/data/` and
`/data/quality/`. Served under /data/, one bundle is right on the docs host,
on every preview and on ourhike.org; served at the root it would need a
second build and a second browser run. Beside data/, `bundle` adds what the
quality page asks for outside /data/ (the site's `_astro/`, `fonts/` and
`favicon.svg`), a front page that sends a visitor on to /data/ and names the
commit it was built from, and a 404.html, which stops Pages answering a
missing file with the front page (it does that for a project with no
404.html, which it takes for a single-page app).

WHEN ourhike.org/data/ BECOMES PAGES THAT SEND A VISITOR ON. pages.yml's
build job runs `live` before it builds the site, and only when docs.ourhike.org
already answers with a front page of ours does it build the site's links to
point there and replace `_site/data/` with `redirects`' pages. Otherwise
ourhike.org keeps serving the docs itself, as it did before, so no page ever
sends a visitor to a host with nothing on it. The question is asked of the
host and not of this run's upload because the upload (the `docs-host` job)
runs after the build job, so that a tag the release gates refuse deploys
nothing anywhere, and the build job is the one that publishes ourhike.org. The
cost is one deploy: the run that first fills docs.ourhike.org still serves
the docs at ourhike.org/data/, and the next deploy of a tag (a re-dispatch
is enough) is the one that sends visitors on. Once moved, a tag whose upload
fails keeps sending visitors to the previous tag's docs rather than putting
dbt's page back on the app's origin.

`target` and `confirm` are the `docs-host` job's: they find the Cloudflare
project and its domain before the upload and wait for docs.ourhike.org to
serve the upload after it, and each says plainly what is missing when one of
them is. Neither prints a token, and neither prints what a host answered
beyond its status and the commit on its front page.
"""

from __future__ import annotations

import argparse
import html
import http.client
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

#: The path every host serves the docs bundle under.
DATA = "data"
#: What the quality page asks for outside /data/, from the assembled site.
ASSET_DIRS = ("_astro", "fonts")
ASSET_FILES = ("favicon.svg",)
#: The meta tag on the docs host's front page naming the commit it was built from.
BUILD_META = "ourhike-docs-build"
BUILD_MARKER = re.compile(r'<meta name="ourhike-docs-build" content="([0-9a-f]{7,40})">')
COMMIT = re.compile(r"[0-9a-f]{7,40}")
#: A Pages production branch as it may reach wrangler's command line.
BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}")
#: Cloudflare's error code for a Pages project that does not exist, as remembered
#: from wrangler's own check for it and not read here; a 404 counts too, so the
#: plain message does not rest on the code alone.
PROJECT_NOT_FOUND = 8000007
API_BASE = "https://api.cloudflare.com/client/v4"
USER_AGENT = "OurHike deploy check (+https://github.com/OurHike/OurHike)"
TIMEOUT_SECONDS = 30
MAX_BODY_BYTES = 1_000_000
#: `live`: five tries 5 s apart. @unvalidated: how often a request from a
#: runner to docs.ourhike.org goes unanswered is unmeasured. The two mistakes
#: cost different amounts, which is what set the budget: a miss costs that
#: release the move (ourhike.org serves the docs itself again, on the app's
#: origin, until the next deploy, and the build job's warning says so), while
#: waiting costs about 20 s a deploy, and only while the host is not there.
#: Counting misses across deploys would settle whether five is enough.
LIVE_ATTEMPTS = 5
LIVE_INTERVAL_SECONDS = 5
#: `confirm`: the budget ua.yml gives a fresh alias, 30 tries 5 s apart.
#: @unvalidated for this case: how long a custom domain takes to serve a new
#: production deployment is unmeasured here; the first runs' logs would settle
#: it, and a run that outwaits it fails saying what the host last answered.
CONFIRM_ATTEMPTS = 30
CONFIRM_INTERVAL_SECONDS = 5

STYLE = "body{font:1rem/1.5 system-ui,sans-serif;margin:2rem auto;max-width:36rem;padding:0 1rem}"

Getter = Callable[..., "tuple[int | None, str]"]


class Refused(Exception):
    """Something is not shaped the way this step expects, said in a sentence."""


# ------------------------------------------------------------ the pages


def _js_string(value: str) -> str:
    """`value` as a JavaScript string literal that cannot close the script holding it."""
    return json.dumps(value).replace("<", "\\u003c")


def _page(*, title: str, body: str, to: str | None = None, build: str | None = None) -> str:
    """A small page of ours: `body` under `title`, sending a visitor to `to` when there is one.

    The script comes first and wins, because it carries the query and the
    fragment, and the fragment is where dbt's docs keep which page a link
    was to: dbt 2.0.6's docs app routes with react-router's HashRouter
    (`createHashHistory({window, v5Compat: true})` in its assets/react-*.js,
    read 2026-10-10 from a 2.0.6 build), so every deep link is /data/#/...
    The refresh is for a browser running no script, and the link for one
    following neither; a refresh waits for the page to load, so it never
    races the script.
    """
    head = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="color-scheme" content="light dark">',
        f"<title>{html.escape(title)}</title>",
    ]
    if build:
        head.append(f'<meta name="{BUILD_META}" content="{build}">')
    if to:
        attribute = html.escape(to, quote=True)
        head += [
            f'<link rel="canonical" href="{attribute}">',
            f"<script>location.replace({_js_string(to)} + location.search + location.hash)</script>",
            f'<meta http-equiv="refresh" content="0; url={attribute}">',
        ]
    else:
        head.append('<meta name="robots" content="noindex">')
    head.append(f"<style>{STYLE}</style>")
    return '<!doctype html>\n<html lang="en">\n<head>\n' + "\n".join(head) + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n"


def _link(href: str, text: str) -> str:
    return f'<a href="{html.escape(href, quote=True)}">{html.escape(text)}</a>'


def docs_url(origin: str, relative: PurePosixPath) -> str:
    """Where `origin` serves the bundle's file at `relative`, a path under data/: a directory's index.html as the directory."""
    parts = list(relative.parts)
    index = parts[-1] == "index.html"
    if index:
        parts = parts[:-1]
    path = "/".join(quote(part) for part in parts)
    if index and parts:
        path += "/"
    return f"{origin.rstrip('/')}/{DATA}/{path}"


def redirect_page(to: str) -> str:
    """The page left at an old ourhike.org/data/ address."""
    host = urlsplit(to).hostname or to
    shown = to.split("://", 1)[-1]
    return _page(
        title=f"Moved to {host} — OurHike",
        body=f"<p>OurHike's data docs have moved to {html.escape(host)}.</p>\n<p>{_link(to, shown)}</p>",
        to=to,
    )


def front_page(build: str, *, quality: bool) -> str:
    """docs.ourhike.org/ itself: the commit it was built from, and on to /data/."""
    links = [f"<li>{_link('/data/', 'How the data is built')}</li>"]
    if quality:
        links.append(f"<li>{_link('/data/quality/', 'Data quality')}</li>")
    return _page(
        title="OurHike data docs",
        body="<p>OurHike's data docs:</p>\n<ul>\n" + "\n".join(links) + "\n</ul>",
        to="/data/",
        build=build,
    )


def not_found_page(*, quality: bool) -> str:
    """The docs host's 404.html, which also stops Pages answering a missing file with the front page."""
    links = _link("/data/", "How the data is built")
    if quality:
        links += " &middot; " + _link("/data/quality/", "Data quality")
    return _page(
        title="Not found — OurHike data docs",
        body=f"<p>There is no page at this address.</p>\n<p>OurHike's data docs: {links}</p>",
    )


# ------------------------------------------------------------ the files


def bundle(site: Path, out: Path, build: str) -> list[str]:
    """The docs host's files, from a site assembled for ourhike.org: its data/, and what data/ asks for beside it.

    Copies only, plus two pages of ours, so that it cannot fail the build
    job on the docs' account: whether every page finds what it asks for is
    `check`'s question, asked in the job that uploads them.
    """
    if not COMMIT.fullmatch(build):
        raise Refused(f"{build!r} is not a commit, and the docs host's front page names the commit it was built from.")
    if out.exists():
        raise Refused(f"{out} already exists. Give the docs host a directory that is not there yet.")
    data = site / DATA
    if not (data / "index.html").is_file():
        raise Refused(f"{data} holds no index.html, so there are no docs to serve.")
    shutil.copytree(data, out / DATA)
    copied = [DATA]
    for name in ASSET_DIRS:
        if (site / name).is_dir():
            shutil.copytree(site / name, out / name)
            copied.append(name)
    for name in ASSET_FILES:
        if (site / name).is_file():
            shutil.copy2(site / name, out / name)
            copied.append(name)
    quality = (out / DATA / "quality" / "index.html").is_file()
    (out / "index.html").write_text(front_page(build, quality=quality), encoding="utf-8")
    (out / "404.html").write_text(not_found_page(quality=quality), encoding="utf-8")
    return copied


def write_redirects(docs: Path, out: Path, origin: str) -> list[str]:
    """A page at the path of every HTML file under `docs`, inside `out`, sending a visitor to that file's page on `origin`.

    HTML only. The other files are what the pages load, not what anybody
    opens, and GitHub Pages types a file by its extension, so a redirect page
    could not stand at their paths anyway.
    """
    if out.exists() and any(out.iterdir()):
        raise Refused(f"{out} is not empty. The pages that send visitors on replace the docs there; remove them first.")
    pages = sorted(path for path in docs.rglob("*.html") if path.is_file())
    if docs / "index.html" not in pages:
        raise Refused(f"{docs} holds no index.html, so there is no front page to send ourhike.org/{DATA}/ to.")
    written = []
    for page in pages:
        relative = page.relative_to(docs)
        to = docs_url(origin, PurePosixPath(*relative.parts))
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(redirect_page(to), encoding="utf-8")
        written.append(f"{relative.as_posix()} -> {to}")
    return written


class _References(HTMLParser):
    """Every `href` and `src` in a page."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.urls += [value.strip() for name, value in attrs if name in ("href", "src") and value]


CSS_URL = re.compile(r"""url\(\s*['"]?(/[^'")\s]*)""")

#: Paths the zone in front of docs.ourhike.org answers itself, never the
#: bundle. Cloudflare serves /cdn-cgi/ on every host it fronts, and this zone
#: adds a hidden `<a href="https://docs.ourhike.org/cdn-cgi/content?id=…"
#: aria-hidden="true" rel="nofollow noopener" style="display: none !important">`
#: right after `<body>` of a page it serves to a non-browser agent: a bot
#: setting on the zone, AI Labyrinth by its look (measured by the lead against
#: the maintainer's placeholder, 2026-10-10 21:07 UTC; ourhike-docs.pages.dev
#: does not add it). `check` reads the bundle, where no such link can be, so
#: this only matters to a copy saved from the served site; it is skipped there
#: rather than reported as a file the bundle lacks.
EDGE_PATHS = ("/cdn-cgi/",)


def _resolves(root: Path, url: str) -> bool:
    """Whether a host serving `root` answers the root-relative `url` with a file: `/x/` as x/index.html, `/x` as x or x/index.html."""
    path = unquote(urlsplit(url).path)
    relative = path.lstrip("/")
    candidates = [root / relative / "index.html"] if path.endswith("/") else [root / relative, root / relative / "index.html"]
    inside = root.resolve()
    return any(candidate.resolve().is_relative_to(inside) and candidate.is_file() for candidate in candidates)


def missing_references(root: Path) -> list[str]:
    """Every root-relative link, script, stylesheet or font that a page or stylesheet under `root` asks for and `root` lacks.

    Root-relative only (`/about/`, not `about/` or `https://...`): a relative
    one moves with its page, and these are the ones a move to another host
    can break. A site link left bare on a /data/ page is one, and on the docs
    host it would send a visitor to a page that host does not have. The
    zone's own paths (EDGE_PATHS) are skipped.
    """
    asked: dict[str, list[str]] = {}
    for page in sorted(root.rglob("*.html")):
        parser = _References()
        parser.feed(page.read_text(encoding="utf-8", errors="replace"))
        asked[page.relative_to(root).as_posix()] = [url for url in parser.urls if url.startswith("/")]
    for sheet in sorted(root.rglob("*.css")):
        asked[sheet.relative_to(root).as_posix()] = CSS_URL.findall(sheet.read_text(encoding="utf-8", errors="replace"))
    missing = []
    for where, urls in asked.items():
        for url in dict.fromkeys(urls):
            if url.startswith("//") or url.startswith(EDGE_PATHS):
                continue
            if not _resolves(root, url):
                missing.append(f"{where} asks for {url}")
    return missing


# ------------------------------------------------------------ the network


def _get(url: str, *, headers: dict[str, str] | None = None, timeout: float = TIMEOUT_SECONDS) -> tuple[int | None, str]:
    """(status, body) for a GET of `url`, or (None, why) when nothing answered."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(MAX_BODY_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read(MAX_BODY_BYTES).decode("utf-8", "replace") if error.fp else ""
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as error:
        return None, str(getattr(error, "reason", error)) or error.__class__.__name__


def served_build(origin: str, get: Getter | None = None) -> tuple[str | None, str]:
    """The commit `origin`'s front page names, or None; and what it answered, in words fit for a log.

    The marker is searched for in what the host answers, never compared
    byte for byte with the front page the bundle holds: this request comes
    from a non-browser agent, so the zone in front of docs.ourhike.org adds
    its hidden /cdn-cgi/ link after `<body>` (EDGE_PATHS says what and since
    when), and the marker sits in `<head>`, before it.
    """
    status, body = (get or _get)(f"{origin.rstrip('/')}/")
    if status is None:
        return None, f"no answer ({body})"
    if status != 200:
        return None, f"HTTP {status}"
    marker = BUILD_MARKER.search(body)
    if marker is None:
        return None, "HTTP 200, with a page that is not the data docs' front page"
    return marker.group(1), f"the docs built from {marker.group(1)[:12]}"


def _api(path: str, token: str, get: Getter) -> tuple[int | None, dict]:
    status, body = get(f"{os.environ.get('API_BASE', API_BASE)}{path}", headers={"Authorization": f"Bearer {token}"})
    if status is None:
        raise Refused(f"Could not reach the Cloudflare API ({body}).")
    try:
        payload = json.loads(body)
    except ValueError:
        payload = {}
    return status, payload if isinstance(payload, dict) else {}


def _reasons(payload: dict) -> str:
    return (
        "; ".join(str(error.get("message")) for error in payload.get("errors") or [] if isinstance(error, dict))
        or "no reason given"
    )


# ------------------------------------------------------------ the commands


def _escape(message: str) -> str:
    """A workflow command's message, which must be one line."""
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _say(kind: str, message: str) -> None:
    print(f"::{kind}::{_escape(message)}")


def _output(**values: str) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    for line in lines:
        print(line)
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


def _summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _fail(message: str) -> int:
    _say("error", message)
    _summary(f"### The data docs were not deployed\n\n{message}")
    return 1


def _host(origin: str) -> str:
    return urlsplit(origin).hostname or origin


def live(origin: str, *, get: Getter | None = None, sleep: Callable[[float], None] | None = None) -> str:
    """`origin` when it already serves a front page of ours, else empty. Never raises: not knowing is the old layout."""
    host = _host(origin)
    said = "nothing was asked"
    sleep = sleep or time.sleep
    try:
        for attempt in range(LIVE_ATTEMPTS):
            served, said = served_build(origin, get)
            if served:
                _say(
                    "notice",
                    f"{host} serves the data docs ({said}), so ourhike.org/{DATA}/ becomes pages that send visitors "
                    "there, and the site's data links point there.",
                )
                return origin
            if attempt + 1 < LIVE_ATTEMPTS:
                sleep(LIVE_INTERVAL_SECONDS)
    except Exception as error:  # noqa: BLE001 - any failure here means "not known to be there"
        said = f"the question failed: {error.__class__.__name__}"
    _say(
        "warning",
        f"{host} does not serve the data docs ({said}), so ourhike.org/{DATA}/ keeps serving them itself and the site's "
        "data links stay there. LAUNCH_CHECKLIST.md 3c is what moves them.",
    )
    return ""


def target(environ: dict[str, str], *, get: Getter | None = None) -> int:
    """Find the docs project's production branch and its custom domain's status, or say plainly which is missing."""
    get = get or _get
    token = environ.get("API_TOKEN", "").strip()
    account = environ.get("ACCOUNT_ID", "").strip()
    project = environ.get("DOCS_PAGES_PROJECT", "").strip()
    host = _host(environ.get("DOCS_ORIGIN", "").strip())
    if not project or not host:
        return _fail("DOCS_PAGES_PROJECT and DOCS_ORIGIN must both be set; pages.yml's env holds them.")
    if not token or not account:
        return _fail(
            "CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID are not both set (LAUNCH_CHECKLIST.md 3a), so the data docs "
            f"cannot be uploaded to {project}. ourhike.org/{DATA}/ keeps serving them itself."
        )
    base = f"/accounts/{quote(account, safe='')}/pages/projects/{quote(project, safe='')}"
    try:
        status, payload = _api(base, token, get)
        if not payload.get("success"):
            codes = {error.get("code") for error in payload.get("errors") or [] if isinstance(error, dict)}
            if status == 404 or PROJECT_NOT_FOUND in codes:
                return _fail(
                    f"Cloudflare Pages has no project named {project} in this account, so the data docs cannot be "
                    f"deployed. Create it (LAUNCH_CHECKLIST.md 3c): Workers & Pages, Create, Pages, Upload assets, "
                    f"named {project}; then attach {host} under its Custom domains. Until then ourhike.org/{DATA}/ "
                    "keeps serving the docs itself."
                )
            return _fail(
                f"Cloudflare declined to describe {project}: {_reasons(payload)}. If that is a permissions problem, "
                'the token needs "Cloudflare Pages: Edit" on this account (LAUNCH_CHECKLIST.md 3a).'
            )
        result = payload.get("result") or {}
        branch = result.get("production_branch") if isinstance(result, dict) else None
        if not isinstance(branch, str) or not BRANCH.fullmatch(branch):
            return _fail(
                f"Cloudflare names no usable production branch for {project} ({branch!r}), so an upload would not go live."
            )
        status, payload = _api(f"{base}/domains", token, get)
    except Refused as refused:
        return _fail(str(refused))
    if payload.get("success"):
        entries = [entry for entry in payload.get("result") or [] if isinstance(entry, dict) and entry.get("name") == host]
        domain = str(entries[0].get("status") or "unknown") if entries else "missing"
        if not re.fullmatch(r"[a-z_]{1,32}", domain):
            domain = "unknown"
    else:
        domain = "unknown"
        _say(
            "warning",
            f"Cloudflare would not list {project}'s custom domains ({_reasons(payload)}), so whether {host} is attached is not known here.",
        )
    _say("notice", f"Uploading to {project}'s production branch, {branch}. {host} on it: {domain}.")
    _output(branch=branch, domain=domain)
    return 0


def confirm(
    origin: str,
    build: str,
    domain: str,
    *,
    project: str,
    site_sends: str = "",
    get: Getter | None = None,
    sleep: Callable[[float], None] | None = None,
    attempts: int = CONFIRM_ATTEMPTS,
) -> int:
    """Wait for `origin` to serve the docs built from `build`, or say plainly why it does not."""
    host = _host(origin)
    sleep = sleep or time.sleep
    if domain == "missing":
        return _fail(
            f"{host} is not a custom domain of {project}, so this build is on {project}.pages.dev and on no address a "
            f"visitor is sent to. Attach it (LAUNCH_CHECKLIST.md 3c): {project}, Custom domains, Set up a custom domain, "
            f"{host}."
        )
    said = "nothing was asked"
    for attempt in range(attempts):
        served, said = served_build(origin, get)
        if served == build:
            where = (
                f"ourhike.org/{DATA}/ sends visitors here."
                if site_sends
                else f"ourhike.org/{DATA}/ still serves the docs itself, because this run's build job asked {host} "
                "before this upload. Dispatch Deploy Pages against this tag again to send it here (LAUNCH_CHECKLIST.md 3c)."
            )
            _say("notice", f"{host} serves the data docs built from {build[:12]}. {where}")
            _summary(f"### The data docs\n\n{origin}/{DATA}/ serves the docs built from `{build[:12]}`. {where}")
            return 0
        if attempt + 1 < attempts:
            sleep(CONFIRM_INTERVAL_SECONDS)
    if domain == "unknown":
        why = "Cloudflare's list of the project's domains could not be read, so whether it is attached is not known here."
    elif domain != "active":
        why = (
            f"Cloudflare lists it on {project} as {domain}, and it serves nothing until that is active, which needs its "
            "DNS record and its certificate (LAUNCH_CHECKLIST.md 3c)."
        )
    else:
        why = f"Cloudflare lists it on {project} as active, so the upload has not reached it yet or went somewhere else."
    return _fail(f"{host} did not serve the docs built from {build[:12]} in {attempts} tries; it last answered {said}. {why}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("live", help="write origin= (the docs host, or empty) to $GITHUB_OUTPUT; never fails")
    command.add_argument("origin")
    command = commands.add_parser("bundle", help="the docs host's files, from an assembled site")
    command.add_argument("site", type=Path)
    command.add_argument("out", type=Path)
    command.add_argument("--build", required=True)
    command = commands.add_parser("redirects", help="pages at the docs' old paths that send a visitor to the docs host")
    command.add_argument("docs", type=Path)
    command.add_argument("out", type=Path)
    command.add_argument("origin")
    command = commands.add_parser("check", help="fail when a page or stylesheet asks for a file the docs host lacks")
    command.add_argument("root", type=Path)
    commands.add_parser("target", help="the project's production branch and the domain's status, to $GITHUB_OUTPUT")
    command = commands.add_parser("confirm", help="wait for the docs host to serve this build")
    command.add_argument("origin")
    command.add_argument("--build", required=True)
    command.add_argument("--domain", required=True)
    command.add_argument("--site-sends", default="")
    args = parser.parse_args(argv)

    if args.command == "live":
        _output(origin=live(args.origin))
        return 0
    try:
        if args.command == "bundle":
            copied = bundle(args.site, args.out, args.build)
            print(
                f"The docs host's files: {', '.join(copied)}, a front page naming {args.build[:12]}, and a 404 page, in {args.out}."
            )
            return 0
        if args.command == "redirects":
            for line in write_redirects(args.docs, args.out, args.origin):
                print(line)
            return 0
    except Refused as refused:
        _say("error", str(refused))
        return 1
    if args.command == "check":
        missing = missing_references(args.root)
        if missing:
            return _fail(f"{len(missing)} thing(s) a docs page asks for are not on the docs host: {'; '.join(missing)}.")
        print(f"Every page and stylesheet under {args.root} finds what it asks for.")
        return 0
    if args.command == "target":
        return target(dict(os.environ))
    return confirm(
        args.origin,
        args.build,
        args.domain,
        project=os.environ.get("DOCS_PAGES_PROJECT", "the docs project"),
        site_sends=args.site_sends,
    )


if __name__ == "__main__":
    sys.exit(main())
