"""`.github/scripts/docs_host.py`: the data docs on docs.ourhike.org (pipeline/ELT.md decision 144).

Two promises are held here, and the rest serves them. ourhike.org never sends
a visitor to a host with nothing on it: `live` says the docs host serves the
docs only when its front page is ours, and never raises. And a docs deploy
that cannot finish says plainly what is missing: `target` names the project
or the token, `confirm` names the domain. The network is a stand-in function
throughout; whether the real host answers is what the deploy's own last step
asks.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import docs_host
import pytest

ORIGIN = "https://docs.ourhike.org"
BUILD = "5c0782771234567890abcdef1234567890abcdef"
OTHER = "e49ca6011234567890abcdef1234567890abcdef"


def _files(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


# The shape pages.yml's "Assemble the site" leaves in `_site`: the site, its
# assets, and data/ holding dbt's page (relative links only, as dbt 2.0.6
# writes it) beside the quality page, whose site links Base.astro writes in
# full and whose tabs and assets are root-relative.
QUALITY = (
    '<link rel="stylesheet" href="/_astro/site.css"><link rel="icon" href="/favicon.svg">'
    '<link rel="preload" href="/fonts/bitter-latin.woff2" as="font">'
    '<a href="https://ourhike.org/about/">About</a><a href="/data/">How the data is built</a>'
    '<a href="/data/quality/">Data quality</a><a href="#main">Skip</a><script src="/_astro/quality.js"></script>'
)
SITE = {
    "index.html": "<p>home</p>",
    "about/index.html": "<p>about</p>",
    "favicon.svg": "<svg/>",
    "fonts/bitter-latin.woff2": "font",
    "_astro/site.css": "body{font-family:x;src:url(/fonts/bitter-latin.woff2)}",
    "_astro/quality.js": "start()",
    "data/index.html": '<script type="module" src="./assets/index.js"></script>',
    "data/assets/index.js": "docs()",
    "data/info_schema/v1/dbt.models.parquet": "parquet",
    "data/duckdb/duckdb.js": "duckdb()",
    "data/quality/index.html": QUALITY,
}


def _site(tmp_path: Path, **changes: str | None) -> Path:
    files = {**SITE, **changes}
    return _files(tmp_path / "_site", {path: text for path, text in files.items() if text is not None})


# ---------------------------------------------------------------- the pages


@pytest.mark.parametrize(
    ("relative", "url"),
    [
        ("index.html", f"{ORIGIN}/data/"),
        ("quality/index.html", f"{ORIGIN}/data/quality/"),
        ("notes.html", f"{ORIGIN}/data/notes.html"),
        ("a b/index.html", f"{ORIGIN}/data/a%20b/"),
    ],
)
def test_a_file_under_data_is_served_at_the_same_path_on_the_docs_host(relative: str, url: str):
    assert docs_host.docs_url(f"{ORIGIN}/", PurePosixPath(relative)) == url


def test_a_page_left_at_an_old_address_sends_a_visitor_on_three_ways():
    """The script carries the fragment, which is where dbt's docs keep a deep link (/data/#/...);
    the refresh is for a browser running no script; the link for one following neither."""
    page = docs_host.redirect_page(f"{ORIGIN}/data/quality/")
    assert f'<script>location.replace("{ORIGIN}/data/quality/" + location.search + location.hash)</script>' in page
    assert f'<meta http-equiv="refresh" content="0; url={ORIGIN}/data/quality/">' in page
    assert f'<a href="{ORIGIN}/data/quality/">docs.ourhike.org/data/quality/</a>' in page
    assert f'<link rel="canonical" href="{ORIGIN}/data/quality/">' in page
    assert page.index("<script>") < page.index('http-equiv="refresh"')
    assert "have moved to docs.ourhike.org" in page


def test_a_target_cannot_close_the_script_that_carries_it():
    """The paths come from file names in dbt's output, so they are escaped as if anybody could write one."""
    page = docs_host.redirect_page(f"{ORIGIN}/data/</script><script>alert(1)</script>/")
    script = page.split("<script>", 1)[1].split("</script>", 1)[0]
    assert script == (
        f'location.replace("{ORIGIN}/data/\\u003c/script>\\u003cscript>alert(1)\\u003c/script>/"'
        " + location.search + location.hash)"
    )
    assert "&lt;/script&gt;&lt;script&gt;alert(1)" in page.split("<body>", 1)[1]


def test_the_front_page_names_its_commit_and_sends_a_visitor_to_the_docs():
    page = docs_host.front_page(BUILD, quality=True)
    assert f'<meta name="ourhike-docs-build" content="{BUILD}">' in page
    assert '<script>location.replace("/data/" + location.search + location.hash)</script>' in page
    assert '<a href="/data/">How the data is built</a>' in page
    assert '<a href="/data/quality/">Data quality</a>' in page
    assert "Data quality" not in docs_host.front_page(BUILD, quality=False)


def test_the_not_found_page_sends_nobody_anywhere_and_is_not_indexed():
    page = docs_host.not_found_page(quality=True)
    assert "location.replace" not in page and "http-equiv" not in page
    assert '<meta name="robots" content="noindex">' in page
    assert '<a href="/data/">How the data is built</a>' in page


# ---------------------------------------------------------------- the files


def test_the_bundle_is_data_as_assembled_and_what_its_pages_ask_for_beside_it(tmp_path: Path):
    out = tmp_path / "docs-host"
    copied = docs_host.bundle(_site(tmp_path), out, BUILD)

    assert copied == ["data", "_astro", "fonts", "favicon.svg"]
    assert (out / "data" / "quality" / "index.html").read_text() == QUALITY
    assert (out / "data" / "info_schema" / "v1" / "dbt.models.parquet").is_file()
    assert (out / "_astro" / "site.css").is_file() and (out / "fonts" / "bitter-latin.woff2").is_file()
    assert not (out / "about").exists(), "the site's own pages stay on ourhike.org"
    assert BUILD in (out / "index.html").read_text()
    assert "There is no page at this address" in (out / "404.html").read_text()
    assert docs_host.missing_references(out) == []


@pytest.mark.parametrize(
    ("build", "make_out", "drop", "message"),
    [
        ("main", False, None, "is not a commit"),
        (BUILD, True, None, "already exists"),
        (BUILD, False, "data/index.html", "holds no index.html"),
    ],
    ids=["not a commit", "out exists", "no docs"],
)
def test_the_bundle_refuses_what_it_cannot_build_from(tmp_path: Path, build: str, make_out: bool, drop: str | None, message: str):
    site = _site(tmp_path, **({drop: None} if drop else {}))
    out = tmp_path / "docs-host"
    if make_out:
        out.mkdir()
    with pytest.raises(docs_host.Refused, match=message):
        docs_host.bundle(site, out, build)


def test_ourhike_org_gets_a_page_at_every_old_html_address_and_nothing_else(tmp_path: Path):
    out = tmp_path / "docs-host"
    docs_host.bundle(_site(tmp_path), out, BUILD)
    old = tmp_path / "old-data"

    written = docs_host.write_redirects(out / "data", old, ORIGIN)

    assert written == [f"index.html -> {ORIGIN}/data/", f"quality/index.html -> {ORIGIN}/data/quality/"]
    assert sorted(path.relative_to(old).as_posix() for path in old.rglob("*") if path.is_file()) == [
        "index.html",
        "quality/index.html",
    ]
    assert f'url={ORIGIN}/data/quality/"' in (old / "quality" / "index.html").read_text()


def test_the_redirects_refuse_to_write_over_docs_that_are_still_there(tmp_path: Path):
    site = _site(tmp_path)
    with pytest.raises(docs_host.Refused, match="not empty"):
        docs_host.write_redirects(site / "data", site / "data", ORIGIN)
    with pytest.raises(docs_host.Refused, match="no index.html"):
        docs_host.write_redirects(site / "_astro", tmp_path / "out", ORIGIN)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"data/quality/index.html": QUALITY.replace("https://ourhike.org/about/", "/about/")}, "asks for /about/"),
        ({"_astro/site.css": None}, "asks for /_astro/site.css"),
        ({"fonts/bitter-latin.woff2": None}, "_astro/site.css asks for /fonts/bitter-latin.woff2"),
        ({"data/quality/index.html": QUALITY + '<a href="/data/../../etc/passwd">x</a>'}, "asks for /data/../../etc/passwd"),
    ],
    ids=["a site link left bare", "a missing stylesheet", "a font a stylesheet names", "a path out of the bundle"],
)
def test_the_check_names_what_a_page_asks_for_and_the_docs_host_lacks(tmp_path: Path, change: dict, expected: str):
    out = tmp_path / "docs-host"
    docs_host.bundle(_site(tmp_path, **change), out, BUILD)
    missing = docs_host.missing_references(out)
    assert any(expected in line for line in missing), missing
    assert docs_host.main(["check", str(out)]) == 1


def test_the_check_skips_the_paths_the_zone_answers_itself(tmp_path: Path):
    """/cdn-cgi/ is Cloudflare's on every host it fronts (docs_host.EDGE_PATHS), never a file of the bundle."""
    page = QUALITY + '<a href="/cdn-cgi/content?id=abc" aria-hidden="true"></a><script src="/cdn-cgi/x.js"></script>'
    out = tmp_path / "docs-host"
    docs_host.bundle(_site(tmp_path, **{"data/quality/index.html": page}), out, BUILD)
    assert docs_host.missing_references(out) == []


def test_the_check_reports_a_missing_file_once_per_page(tmp_path: Path):
    page = QUALITY.replace("https://ourhike.org/about/", "/about/") + '<a href="/about/">About again</a>'
    out = tmp_path / "docs-host"
    docs_host.bundle(_site(tmp_path, **{"data/quality/index.html": page}), out, BUILD)
    assert docs_host.missing_references(out) == ["data/quality/index.html asks for /about/"]


# ---------------------------------------------------------------- the network


class Host:
    """A stand-in for `_get`: answers each URL from a table, and counts what it was asked."""

    def __init__(self, answers: dict[str, tuple[int | None, str]] | None = None, *, default=(None, "no such host")):
        self.answers = answers or {}
        self.default = default
        self.asked: list[tuple[str, dict]] = []

    def __call__(self, url: str, *, headers: dict | None = None, timeout: float = 30):
        self.asked.append((url, headers or {}))
        answer = self.answers.get(url, self.default)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _front(build: str = BUILD) -> tuple[int, str]:
    return 200, docs_host.front_page(build, quality=True)


# What the zone in front of docs.ourhike.org adds right after <body> when a
# non-browser agent asks (docs_host.EDGE_PATHS; measured by the lead against
# the maintainer's placeholder, 2026-10-10 21:07 UTC).
INJECTED = (
    '<a href="https://docs.ourhike.org/cdn-cgi/content?id=abc" aria-hidden="true" rel="nofollow noopener"'
    ' style="display: none !important; visibility: hidden !important"></a>'
)


def _as_served(page: str) -> str:
    return page.replace("<body>\n", "<body>\n" + INJECTED, 1)


@pytest.mark.parametrize(
    ("answer", "served", "said"),
    [
        (_front(), BUILD, "the docs built from 5c0782771234"),
        ((200, _as_served(_front()[1])), BUILD, "the docs built from 5c0782771234"),
        ((200, "<p>a placeholder somebody uploaded</p>"), None, "HTTP 200, with a page that is not the data docs' front page"),
        (
            (200, _as_served("<html><head></head><body>\n<p>the maintainer's placeholder</p></body></html>")),
            None,
            "HTTP 200, with a page that is not the data docs' front page",
        ),
        ((404, "Not found"), None, "HTTP 404"),
        ((None, "Name or service not known"), None, "no answer (Name or service not known)"),
    ],
    ids=[
        "ours",
        "ours, with the zone's link",
        "somebody else's page",
        "a placeholder, with the zone's link",
        "nothing there",
        "no such host",
    ],
)
def test_the_front_page_is_what_says_the_docs_host_serves_the_docs(answer, served, said):
    assert docs_host.served_build(ORIGIN, Host({f"{ORIGIN}/": answer})) == (served, said)


def test_live_is_the_docs_host_when_it_serves_any_build_of_ours(capsys):
    assert docs_host.live(ORIGIN, get=Host({f"{ORIGIN}/": _front(OTHER)}), sleep=lambda _: None) == ORIGIN
    assert "::notice::docs.ourhike.org serves the data docs" in capsys.readouterr().out


def test_live_is_empty_and_says_so_when_the_host_does_not_serve_them(capsys):
    host = Host({f"{ORIGIN}/": (404, "")})
    assert docs_host.live(ORIGIN, get=host, sleep=lambda _: None) == ""
    assert len(host.asked) == docs_host.LIVE_ATTEMPTS
    out = capsys.readouterr().out
    assert "::warning::docs.ourhike.org does not serve the data docs (HTTP 404)" in out
    assert "keeps serving them itself" in out


def test_live_never_raises_because_not_knowing_is_the_old_layout(capsys):
    assert docs_host.live(ORIGIN, get=Host({f"{ORIGIN}/": RuntimeError("boom")}), sleep=lambda _: None) == ""
    assert "the question failed: RuntimeError" in capsys.readouterr().out


def test_the_live_command_writes_its_answer_for_the_next_steps(tmp_path: Path, monkeypatch):
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(docs_host, "_get", Host({f"{ORIGIN}/": (None, "no such host")}))
    monkeypatch.setattr(docs_host.time, "sleep", lambda _: None)
    assert docs_host.main(["live", ORIGIN]) == 0
    assert output.read_text() == "origin=\n"


# ---------------------------------------------------------------- target

API = "https://api.example.invalid/client/v4"
ACCOUNT = "acct-1234"
PROJECT_URL = f"{API}/accounts/{ACCOUNT}/pages/projects/ourhike-docs"
ENV = {
    "API_TOKEN": "cf-token-value",
    "ACCOUNT_ID": ACCOUNT,
    "DOCS_PAGES_PROJECT": "ourhike-docs",
    "DOCS_ORIGIN": ORIGIN,
}


def _json(payload: dict, status: int = 200) -> tuple[int, str]:
    return status, json.dumps(payload)


def _project(branch: object = "main") -> tuple[int, str]:
    return _json({"success": True, "errors": [], "result": {"name": "ourhike-docs", "production_branch": branch}})


def _domains(*entries: dict) -> tuple[int, str]:
    return _json({"success": True, "errors": [], "result": list(entries)})


@pytest.fixture
def api(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("API_BASE", API)
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    return output


@pytest.mark.parametrize("status", ["active", "pending"])
def test_target_reads_the_production_branch_and_the_domains_status(api: Path, capsys, status: str):
    host = Host(
        {
            PROJECT_URL: _project("main"),
            f"{PROJECT_URL}/domains": _domains(
                {"name": "elsewhere.example", "status": "active"}, {"name": "docs.ourhike.org", "status": status}
            ),
        }
    )
    assert docs_host.target(ENV, get=host) == 0
    assert api.read_text() == f"branch=main\ndomain={status}\n"
    assert all(headers["Authorization"] == "Bearer cf-token-value" for _, headers in host.asked)
    assert "cf-token-value" not in capsys.readouterr().out


def test_target_says_the_domain_is_missing_rather_than_failing_before_the_upload(api: Path):
    host = Host({PROJECT_URL: _project(), f"{PROJECT_URL}/domains": _domains()})
    assert docs_host.target(ENV, get=host) == 0
    assert api.read_text().endswith("domain=missing\n")


def test_target_carries_on_when_the_domains_cannot_be_listed(api: Path, capsys):
    host = Host(
        {PROJECT_URL: _project(), f"{PROJECT_URL}/domains": _json({"success": False, "errors": [{"message": "nope"}]}, 403)}
    )
    assert docs_host.target(ENV, get=host) == 0
    assert api.read_text().endswith("domain=unknown\n")
    assert "would not list ourhike-docs's custom domains (nope)" in capsys.readouterr().out


@pytest.mark.parametrize(
    "answer",
    [
        _json({"success": False, "errors": [{"code": 8000007, "message": "Project not found."}]}, 404),
        _json({"success": False, "errors": [{"code": 8000007, "message": "Project not found."}]}, 200),
    ],
    ids=["a 404", "a 200 saying not found"],
)
def test_a_missing_project_is_named_with_the_dashboard_step_that_makes_it(api: Path, capsys, answer):
    assert docs_host.target(ENV, get=Host({PROJECT_URL: answer})) == 1
    out = capsys.readouterr().out
    assert "::error::Cloudflare Pages has no project named ourhike-docs in this account" in out
    assert "Upload assets" in out and "LAUNCH_CHECKLIST.md 3c" in out and "docs.ourhike.org" in out
    assert "keeps serving the docs itself" in out
    assert not api.exists(), "nothing for the upload to read"


def test_missing_settings_are_named_and_no_request_is_made(api: Path, capsys):
    host = Host()
    assert docs_host.target({**ENV, "API_TOKEN": ""}, get=host) == 1
    assert host.asked == []
    assert "CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID are not both set (LAUNCH_CHECKLIST.md 3a)" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (_json({"success": False, "errors": [{"code": 10000, "message": "Authentication error"}]}, 403), "Authentication error"),
        ((None, "timed out"), "Could not reach the Cloudflare API (timed out)"),
        (_project("main --project-name=elsewhere"), "no usable production branch"),
        (_project(None), "no usable production branch"),
    ],
    ids=["refused", "no answer", "a branch that is not a name", "no branch"],
)
def test_other_failures_are_red_and_say_what_cloudflare_said(api: Path, capsys, answer, expected: str):
    assert docs_host.target(ENV, get=Host({PROJECT_URL: answer})) == 1
    assert expected in capsys.readouterr().out


# ---------------------------------------------------------------- confirm


def _confirm(answers: dict, domain: str = "active", site_sends: str = ORIGIN, attempts: int = 3):
    host = Host(answers)
    code = docs_host.confirm(
        ORIGIN, BUILD, domain, project="ourhike-docs", site_sends=site_sends, get=host, sleep=lambda _: None, attempts=attempts
    )
    return code, host


def test_confirm_passes_once_the_docs_host_serves_this_build(api: Path, capsys):
    code, _ = _confirm({f"{ORIGIN}/": _front(BUILD)})
    assert code == 0
    assert "ourhike.org/data/ sends visitors here." in capsys.readouterr().out


def test_the_first_fill_says_ourhike_org_still_serves_the_docs_and_what_moves_them(api: Path, capsys):
    code, _ = _confirm({f"{ORIGIN}/": _front(BUILD)}, site_sends="")
    assert code == 0
    out = capsys.readouterr().out
    assert "ourhike.org/data/ still serves the docs itself" in out
    assert "Dispatch Deploy Pages against this tag again" in out


def test_a_domain_that_is_not_attached_is_named_without_waiting(api: Path, capsys):
    code, host = _confirm({}, domain="missing")
    assert code == 1
    assert host.asked == []
    out = capsys.readouterr().out
    assert "docs.ourhike.org is not a custom domain of ourhike-docs" in out
    assert "Custom domains" in out and "LAUNCH_CHECKLIST.md 3c" in out


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("pending", "lists it on ourhike-docs as pending"),
        ("unknown", "could not be read"),
        ("active", "as active, so the upload has not reached it yet"),
    ],
)
def test_a_host_still_serving_another_build_fails_after_waiting_and_says_why(api: Path, capsys, domain: str, expected: str):
    code, host = _confirm({f"{ORIGIN}/": _front(OTHER)}, domain=domain, attempts=3)
    assert code == 1
    assert len(host.asked) == 3
    out = capsys.readouterr().out
    assert "did not serve the docs built from 5c0782771234 in 3 tries" in out
    assert "the docs built from e49ca6011234" in out
    assert expected in out
