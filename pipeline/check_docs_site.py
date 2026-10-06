"""Check the dbt docs site before ourhike.org/data/ serves it (pipeline/ELT.md decision 10).

    python check_docs_site.py <site dir> [--project dbt] [--served]

The page is public, counts only and no maps, so it must hold no coordinates
(ELT.md, "Docs and charts at https://ourhike.org/data/"). dbt 2.0.6 writes it
as `index.html`, an `assets/` folder and the Parquet files the page reads with
DuckDB-WASM. Each caller runs this on the directory it produced:
pipeline-tests.yml's `dbt` job and scripts/test.sh on the fixture build's
docs, so a pull request fails before a tag does, and pages.yml's and
pr-preview.yml's assembly steps on `_site/data/`, the bytes that ship.

FAILS (exit 1) on any of:

1. A MISSING PART: `index.html`, a file under `assets/`, or a Parquet file.
   Nothing else would show it on a preview, where `_site/404.html` answers a
   missing docs file with the app shell.
2. A `--vars` OVERRIDE. `dbt_rt.invocations` publishes each invocation's
   `vars_override`. Nothing here passes one; this makes "never pass a secret
   through --vars" a check rather than a habit.
3. TELEMETRY NOT OFF. `index.html` carries the build's settings as
   `window.__DBT_DOCS__ = {...}`, which on 2026-10-03 read
   `"telemetry":{"enabled":false,...}` under the opt-out every build here sets
   (DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false). What the page does in a
   visitor's browser with it on is unmeasured, so anything else, or settings
   that cannot be read, fails.
4. COORDINATE-SHAPED TEXT in any text file or Parquet cell (cast to text),
   by the four SHAPES: WKT with a number (POINT, LINESTRING, POLYGON, their
   MULTI forms, with or without Z/M); a GeoJSON `coordinates` array; a lat,
   lon, lng, latitude or longitude key holding a decimal; and a bare pair of
   decimals of four or more places, each within +-180.

TWO EXEMPTIONS, on provenance: the unit tests' `given` and `expect` cells in
`dbt.unit_tests`, and a singular test's `raw_code` and `compiled_code` in
`dbt.data_tests` when the test is a hand-written file under `tests/singular/`
(added 2026-10-05 for decision 77's
`assert_a_notice_area_covers_every_vertex_of_its_source`, whose made-up shapes
are WKT; the same rule as the unit tests below, and the same open question
for the maintainer). Measured 2026-10-03 on dbt 2.0.6, with the docs built
against an empty warehouse: 159 of the 244 unit tests carry coordinate-shaped
text there (hand-written rows such as
`LINESTRING (-74.12345678901 41.00000049999, ...)`), and all 8,209 numbers of
three or more decimal places in those cells appear in the test's own YAML. So
such a cell passes when every such number in it is in the test's
`original_file_path` under --project (the committed YAML); anything else
fails. Three decimal places is about 110 m of latitude, and a number with
fewer is not traced: that threshold is `@unvalidated`, and what would settle
it is the coarsest precision at which a published point still gives a
sensitive site away, which nobody has measured. Whether decision 10 allows
these rows on the page at all is the maintainer's call; `dbt docs generate
--exclude resource_type:unit_test` does not remove them (measured the same
day: the page still held all 244).

WITH --served, for the copy pages.yml and pr-preview.yml are about to publish
at /data/, one more:

5. CODE FROM ANOTHER ORIGIN (pipeline/ELT.md decision 93, SEC-1 of PR #1805's
   second review). The page runs on the app's own origin, where a signed-in
   hiker's session is kept, so every script, worker and WASM file it loads
   must be a file of this site. Fails:
   - a DuckDB-WASM base (`duckdb_cdn_base` in the page's settings) that is not
     a path under /data/, as dbt 2.0.6's default, jsDelivr, is not; or one
     whose module, `<base>/+esm` read the way a static host reads it (the
     query ignored), is not in the site;
   - a `<script src>`, `<link rel="modulepreload">` or
     `<link rel="preload" as="script|worker">` in an HTML file whose URL has
     a scheme or a `//` host;
   - an absolute URL, written out whole in a JS or HTML file, to a `.js`,
     `.mjs` or `.wasm` file or a `/+esm` module. A link to a page is not
     code, and passes. A URL the code puts together at run time is not seen:
     @duckdb/duckdb-wasm's own getJsDelivrBundles() builds jsDelivr's from
     parts, and the page never calls it (measured 2026-10-06 in Chromium: no
     request left the local server). That run, not this scan, is the
     evidence that the page loads nothing from another origin.
   The fixture build's docs (pipeline-tests.yml, scripts/test.sh) are never
   served, keep dbt's default base, and are checked without it.

A failure names the file, column, row and shape and never prints the matched
text, so a coordinate is not republished in a public CI log.

Exit 0 with a one-line summary otherwise; 2 when the site directory does not
exist.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import duckdb

# The four shapes, by the name a failure reports. Case-insensitive, and
# tolerant of the quotes and backslashes a JSON string inside a Parquet cell
# carries (`\"coordinates\":[[-73.99,...`).
SHAPES: dict[str, re.Pattern[str]] = {
    "WKT": re.compile(r"\b(?:MULTI)?(?:POINT|LINESTRING|POLYGON)\s*(?:ZM|Z|M)?\s*\(\s*\(*\s*[-+]?\d", re.IGNORECASE),
    "GeoJSON coordinates": re.compile(r"""\bcoordinates[\\"']*\s*:\s*\[\s*[\[\d+-]""", re.IGNORECASE),
    "lat/lon value": re.compile(r"""\b(?:lat|lon|lng|latitude|longitude)[\\"']*\s*[:=]\s*[-+]?\d{1,3}\.\d""", re.IGNORECASE),
    "decimal pair": re.compile(r"(?<![\d.])([-+]?\d{1,3}\.\d{4,})[\s,]+([-+]?\d{1,3}\.\d{4,})(?![\d.])"),
}
# The build's settings dbt writes into index.html, one line of JSON.
BUILD_SETTINGS = re.compile(r"window\.__DBT_DOCS__\s*=\s*(\{.*?\});\s*</script>", re.DOTALL)
# A number precise enough to name a place: three decimal places or more.
PRECISE_NUMBER = re.compile(r"[-+]?\d+\.\d{3,}")
# The tables, and the cells in them, that may carry coordinates on provenance:
# a unit test's rows, and a hand-written singular test's own SQL.
UNIT_TESTS = "dbt.unit_tests.parquet"
UNIT_TEST_ROWS = ("given", "expect")
DATA_TESTS = "dbt.data_tests.parquet"
SINGULAR_TEST_CODE = ("raw_code", "compiled_code")
SINGULAR_TESTS_DIR = "tests/singular/"
# --served (check 5). Where pages.yml and pr-preview.yml copy the site, which
# the page's root-relative paths are written against, and where dbt 2.0.6's
# page is when it resolves a relative base: its import() is in assets/.
SERVED_AT = "/data/"
PAGE_SCRIPT = "https://site.invalid/data/assets/index.js"
# A URL with a scheme or a `//` host, rather than a path on this site.
ANOTHER_ORIGIN = re.compile(r"^\s*(?:[A-Za-z][A-Za-z0-9+.-]*:|[/\\]{2})")
# An absolute URL to a script, worker or WASM file, or a jsDelivr-style
# `/+esm` module, written out whole in a JS or HTML file.
CODE_URL = re.compile(
    r"""(?:\bhttps?:)?//([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?::\d+)?)/[^\s"'`<>()\\]*?(?:\.m?js|\.wasm|/\+esm)(?=["'`?#\s)]|$)"""
)
CODE_FILES = (".js", ".mjs", ".html")


def coordinate_shapes(text: str) -> list[str]:
    """The names of the shapes found in `text`, each once."""
    found = []
    for name, pattern in SHAPES.items():
        for match in pattern.finditer(text):
            if name == "decimal pair" and not all(abs(float(value)) <= 180 for value in match.groups()):
                continue
            found.append(name)
            break
    return found


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    traced: int = 0
    traced_tests: set[str] = field(default_factory=set)


def _check_parts(site: Path, report: Report) -> None:
    index = site / "index.html"
    if not index.is_file() or index.stat().st_size == 0:
        report.failures.append(f"no {index}")
    else:
        _check_telemetry(index, report)
    assets = site / "assets"
    if not assets.is_dir() or not any(path.is_file() for path in assets.rglob("*")):
        report.failures.append(f"no file under {assets}")
    if not any(site.rglob("*.parquet")):
        report.failures.append(f"no Parquet file under {site}")


def _build_settings(index: Path) -> dict | None:
    """window.__DBT_DOCS__ from index.html, or None when it cannot be read."""
    match = BUILD_SETTINGS.search(index.read_text(encoding="utf-8", errors="replace"))
    try:
        settings = json.loads(match.group(1)) if match else None
    except json.JSONDecodeError:
        settings = None
    return settings if isinstance(settings, dict) else None


def _check_telemetry(index: Path, report: Report) -> None:
    settings = _build_settings(index)
    if not isinstance(settings, dict):
        report.failures.append(f"{index.name}: no readable window.__DBT_DOCS__ settings, so telemetry cannot be seen to be off")
    elif (settings.get("telemetry") or {}).get("enabled") is not False:
        report.failures.append(f"{index.name}: the page's settings do not say telemetry is off")


def _project_numbers(project: Path, relative: str, cache: dict[str, set[str] | None]) -> set[str] | None:
    """The precise numbers in a file of the project, or None when the project holds no such file.

    A path that climbs out of the project (`../`) is None too: the exemption is
    for the repository's own YAML, and a file elsewhere on the machine is not it.
    """
    if relative not in cache:
        path = (project / relative).resolve()
        inside = path.is_relative_to(project.resolve()) and path.is_file()
        cache[relative] = set(PRECISE_NUMBER.findall(path.read_text(encoding="utf-8"))) if inside else None
    return cache[relative]


def _check_parquet(path: Path, site: Path, project: Path, report: Report, cache: dict[str, set[str] | None]) -> None:
    connection = duckdb.connect()
    # Every column as text, in DuckDB's own rendering, so a struct or a list
    # is searched as the page would show it rather than skipped.
    cursor = connection.execute("SELECT COLUMNS(*)::VARCHAR FROM read_parquet(?)", [str(path)])
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    relative = path.relative_to(site)
    if path.name == "dbt_rt.invocations.parquet" and "vars_override" in columns:
        at = columns.index("vars_override")
        for row in rows:
            if row[at] not in (None, "", "{}", "null"):
                report.failures.append(f"{relative}: invocation {row[0]} records a --vars override, which the page publishes")
    unit_tests = path.name == UNIT_TESTS
    data_tests = path.name == DATA_TESTS
    for row in rows:
        row_id = row[0]
        declared_in = row[columns.index("original_file_path")] if "original_file_path" in columns else None
        for column, value in zip(columns, row):
            if value is None:
                continue
            shapes = coordinate_shapes(value)
            if not shapes:
                continue
            traceable = (unit_tests and column in UNIT_TEST_ROWS) or (
                data_tests and column in SINGULAR_TEST_CODE and (declared_in or "").startswith(SINGULAR_TESTS_DIR)
            )
            if traceable and "original_file_path" in columns:
                numbers = _project_numbers(project, declared_in, cache) if declared_in else None
                if numbers is None:
                    report.failures.append(
                        f"{relative}: {column} of {row_id} holds {', '.join(shapes)}, and the file declaring it "
                        f"({declared_in}) is not under {project}"
                    )
                    continue
                untraced = [number for number in PRECISE_NUMBER.findall(value) if number not in numbers]
                if untraced:
                    report.failures.append(
                        f"{relative}: {column} of {row_id} holds {', '.join(shapes)} with {len(untraced)} number(s) "
                        f"not in {declared_in}"
                    )
                    continue
                report.traced += len(PRECISE_NUMBER.findall(value))
                report.traced_tests.add(row_id)
                continue
            report.failures.append(f"{relative}: {column} of {row_id} holds {', '.join(shapes)}")


def _origin(url: str) -> str:
    """Where `url` points, for a failure: its scheme and host where it has a host, else the URL."""
    parts = urlsplit(url.strip())
    if parts.netloc:
        return f"{parts.scheme + ':' if parts.scheme else ''}//{parts.netloc}"
    return url


def _check_duckdb_base(site: Path, report: Report) -> None:
    """Check 5's first part: the page's DuckDB-WASM base is a path under /data/, and its module is in the site."""
    index = site / "index.html"
    settings = _build_settings(index) if index.is_file() else None
    base = (settings or {}).get("duckdb_cdn_base")
    if not isinstance(base, str) or not base.strip():
        report.failures.append(
            f"{index.name}: no DuckDB-WASM base in the page's settings, so where it loads code from cannot be seen"
        )
        return
    if ANOTHER_ORIGIN.match(base):
        report.failures.append(f"{index.name}: the page loads DuckDB-WASM from {_origin(base)}, another origin")
        return
    # dbt 2.0.6's page imports `${base}/+esm`; a static host ignores the query.
    module = unquote(urlsplit(urljoin(PAGE_SCRIPT, base + "/+esm")).path)
    if not module.startswith(SERVED_AT) or ".." in module.split("/"):
        report.failures.append(f"{index.name}: the page loads DuckDB-WASM from {module}, which is not under {SERVED_AT}")
    elif not (site / module.removeprefix(SERVED_AT)).is_file():
        report.failures.append(f"{index.name}: the page loads DuckDB-WASM from {module}, which is not in the site")


class _ScriptTags(HTMLParser):
    """The URL of every `<script src>`, `<link rel=modulepreload>` and `<link rel=preload as=script|worker>`."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        named = {name: value or "" for name, value in attrs}
        rel = named.get("rel", "").lower().split()
        if tag == "script" and named.get("src"):
            self.urls.append(named["src"])
        elif tag == "link" and named.get("href"):
            if "modulepreload" in rel or ("preload" in rel and named.get("as", "").lower() in ("script", "worker")):
                self.urls.append(named["href"])


def _check_code(path: Path, text: str, site: Path, report: Report) -> None:
    """Check 5's second and third parts, for one JS or HTML file of the site."""
    relative = path.relative_to(site)
    if path.suffix == ".html":
        tags = _ScriptTags()
        tags.feed(text)
        for origin in sorted({_origin(url) for url in tags.urls if ANOTHER_ORIGIN.match(url)}):
            report.failures.append(f"{relative} loads a script from {origin}, another origin")
    hosts = sorted({match.group(1) for match in CODE_URL.finditer(text)})
    if hosts:
        report.failures.append(f"{relative} names a script, worker or WASM file on {', '.join(hosts)}, another origin")


def check(site: Path, project: Path, *, served: bool = False) -> Report:
    report = Report()
    _check_parts(site, report)
    if served:
        _check_duckdb_base(site, report)
    cache: dict[str, set[str] | None] = {}
    for path in sorted(site.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".parquet":
            _check_parquet(path, site, project, report, cache)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        shapes = coordinate_shapes(text)
        if shapes:
            report.failures.append(f"{path.relative_to(site)} holds {', '.join(shapes)}")
        if served and path.suffix in CODE_FILES:
            _check_code(path, text, site, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("site", type=Path, help="the docs site directory dbt docs generate wrote")
    parser.add_argument(
        "--project",
        type=Path,
        default=Path(__file__).resolve().parent / "dbt",
        help="the dbt project the unit tests' original_file_path is relative to (default: pipeline/dbt)",
    )
    parser.add_argument(
        "--served",
        action="store_true",
        help="the copy a workflow is about to publish at /data/: also refuse code from another origin (check 5)",
    )
    args = parser.parse_args(argv)
    if not args.site.is_dir():
        print(f"{args.site} does not exist.", file=sys.stderr)
        return 2
    report = check(args.site, args.project, served=args.served)
    for line in report.failures:
        print(f"FAIL {line}")
    files = [path for path in args.site.rglob("*") if path.is_file()]
    print(
        f"{args.site}: {len(files)} files, {sum(path.stat().st_size for path in files):,} bytes, "
        f"{sum(1 for path in files if path.suffix == '.parquet')} Parquet; "
        f"{report.traced:,} precise numbers in the coordinate-shaped cells of {len(report.traced_tests)} tests, "
        "each in the test's own file; "
        f"{len(report.failures)} failure(s)."
    )
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
