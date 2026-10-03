"""Check the dbt docs site before ourhike.org/data/ serves it (pipeline/ELT.md decision 10).

    python check_docs_site.py <site dir> [--project dbt]

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

ONE EXEMPTION, on provenance: the unit tests' `given` and `expect` cells in
`dbt.unit_tests`. Measured 2026-10-03 on dbt 2.0.6, with the docs built
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
from pathlib import Path

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
# The table, and the cells in it, that may carry coordinates on provenance.
UNIT_TESTS = "dbt.unit_tests.parquet"
UNIT_TEST_ROWS = ("given", "expect")


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


def _check_telemetry(index: Path, report: Report) -> None:
    match = BUILD_SETTINGS.search(index.read_text(encoding="utf-8", errors="replace"))
    try:
        settings = json.loads(match.group(1)) if match else None
    except json.JSONDecodeError:
        settings = None
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
    for row in rows:
        row_id = row[0]
        for column, value in zip(columns, row):
            if value is None:
                continue
            shapes = coordinate_shapes(value)
            if not shapes:
                continue
            if unit_tests and column in UNIT_TEST_ROWS and "original_file_path" in columns:
                declared_in = row[columns.index("original_file_path")]
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


def check(site: Path, project: Path) -> Report:
    report = Report()
    _check_parts(site, report)
    cache: dict[str, set[str] | None] = {}
    for path in sorted(site.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".parquet":
            _check_parquet(path, site, project, report, cache)
            continue
        shapes = coordinate_shapes(path.read_text(encoding="utf-8", errors="replace"))
        if shapes:
            report.failures.append(f"{path.relative_to(site)} holds {', '.join(shapes)}")
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
    args = parser.parse_args(argv)
    if not args.site.is_dir():
        print(f"{args.site} does not exist.", file=sys.stderr)
        return 2
    report = check(args.site, args.project)
    for line in report.failures:
        print(f"FAIL {line}")
    files = [path for path in args.site.rglob("*") if path.is_file()]
    print(
        f"{args.site}: {len(files)} files, {sum(path.stat().st_size for path in files):,} bytes, "
        f"{sum(1 for path in files if path.suffix == '.parquet')} Parquet; "
        f"{report.traced:,} precise numbers in the coordinate-shaped rows of {len(report.traced_tests)} unit tests, "
        "each in the test's own YAML; "
        f"{len(report.failures)} failure(s)."
    )
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
