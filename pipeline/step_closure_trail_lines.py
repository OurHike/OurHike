"""step_closure_trail_lines: the nearby trail lines that may run inside an area closure, into derived.closure_trail_lines.

    python step_closure_trail_lines.py [--warehouse data/warehouse.duckdb] [--lines data/raw/closure_trail_lines/lines.parquet]
    python step_closure_trail_lines.py --warehouse W --geojson <nearby_trails.geojson> --release fixture   # fixtures

Decision 187 (S6, the maintainer's poll of 2026-10-11) crosses out an area
closure's trails where they run inside it, and int_closures__area_trail_cuts
cuts them, in SQL. This hands that model its lines: the release's nearby
trail lines, which prepare_closure_trail_lines.py read once per release and
publish-conditions.yml restores from the cache before the hourly build.

WHY A STEP AND NOT A SOURCE OF THE EXTRACT: the lines are this project's own
published file, not anybody's upstream, as the weather squares are
(step_weather_squares.py), and they change with a release, not with the hour.

WHY THIS LANDS SOME LINES AND NOT ALL. A line can only run inside an area
whose bounding box its own bounding box meets, so the step lands every line
whose box meets the box of a row of int_closures__trail_closure_areas, and no
other: a filter that can keep more lines than the cut needs, never fewer
(Reasoned: a box holds every point of its geometry). The cut itself, which
lines run inside which area and where, is the SQL's. Landing every line
instead would add the whole layer to every hourly warehouse, which
publish-conditions.yml then hands to its checks within a minute: measured
2026-10-11 on UA's release 2026-10-10-2, its 364,668 lines took a DuckDB file
of 417,607,680 bytes, 143,762,233 gzipped at the hand-off's level 1, where
soak run 624's whole warehouse went up as 960,100,794 in 38.21 s of that
step's 60. Against the 193 area closures of UA's conditions/notices.json of
2026-10-11 16:23 UTC, whose outlines are grown 100 m and so hold the source
areas this lands lines for, land() kept 1,332 of the release's 364,167 lines
in 3.67 s and grew the warehouse by 20,185,088 bytes (Measured the same day in
a 4-core sandbox other builds shared, at a load average of 25 to 41).

NO LINES IS AN ANSWER, NEVER A FAILURE. Before the weather job has prepared
any release's lines (a first run, or an environment with no release, as
production had on 2026-10-11), this lands an empty table, so no area row
reaches conditions/trail_closures.json that run, and says so in a warning on
the run's summary; line and point closures, which need no lines, still
publish. It never stops the build for it.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import duckdb

import prepare_closure_trail_lines

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
LINES_PATH = prepare_closure_trail_lines.OUT_DIR / prepare_closure_trail_lines.LINES_FILE
SCHEMA = "derived"
TABLE = "closure_trail_lines"
#: The areas this step lands lines near, each with its bounding box (models/intermediate/closures/).
AREAS = "intermediate.int_closures__trail_closure_areas"
NO_LINES_TITLE = "No trail lines to cut area closures against"


def create_empty(con: duckdb.DuckDBPyConnection) -> None:
    """derived.closure_trail_lines with no row: the table of an hour that has no lines to cut against."""
    con.execute(f"create schema if not exists {SCHEMA}")
    con.execute(
        f"""
        create or replace table {SCHEMA}.{TABLE} (
            release varchar, line_id varchar, geometry varchar, _loaded_at timestamptz
        )
        """
    )


def land(con: duckdb.DuckDBPyConnection, lines: Path | None, loaded_at: datetime) -> dict:
    """Replace derived.closure_trail_lines with the lines of `lines` whose bounding box meets an area's, or with no row
    when `lines` is None. Returns the counts: `landed`, `held` (the file's), `areas`, and the file's `release`."""
    con.execute(f"create schema if not exists {SCHEMA}")
    (areas,) = con.execute(f"select count(*) from {AREAS}").fetchone()
    if lines is None:
        create_empty(con)
        return {"landed": 0, "held": 0, "areas": areas, "release": None}
    con.execute(
        f"""
        create or replace table {SCHEMA}.{TABLE} as
        select
            lines.release,
            lines.line_id,
            lines.geometry,
            cast(? as timestamptz) as _loaded_at
        from read_parquet(?) as lines
        where exists (
            select 1
            from {AREAS} as areas
            where
                lines.xmin <= areas.xmax
                and lines.xmax >= areas.xmin
                and lines.ymin <= areas.ymax
                and lines.ymax >= areas.ymin
        )
        order by lines.line_id
        """,
        [loaded_at.isoformat(), str(lines)],
    )
    (landed,) = con.execute(f"select count(*) from {SCHEMA}.{TABLE}").fetchone()
    held, release = con.execute("select count(*), any_value(release) from read_parquet(?)", [str(lines)]).fetchone()
    return {"landed": landed, "held": held, "areas": areas, "release": release}


def _summary(line: str) -> None:
    """One line of the run's step summary, when the build runs inside a workflow."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as summary:
            summary.write(f"- {line}\n\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--lines", type=Path, default=LINES_PATH, help="prepare_closure_trail_lines.py's lines file")
    parser.add_argument("--geojson", type=Path, help="prepare this nearby_trails.geojson first, in place of --lines")
    parser.add_argument("--release", default="local", help="with --geojson: the release the file stands for")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="closure-trail-lines-") as scratch:
        lines: Path | None = args.lines
        if args.geojson is not None:
            out_dir = Path(scratch)
            prepare_closure_trail_lines.prepare(args.geojson, out_dir, release=args.release, environment=None, source_sha256=None)
            lines = out_dir / prepare_closure_trail_lines.LINES_FILE
        why = f"{args.lines} is not there"
        if lines is not None and not lines.exists():
            lines = None
        with duckdb.connect(str(args.warehouse)) as con:
            try:
                counts = land(con, lines, datetime.now(UTC))
                if lines is not None and counts["release"] is None:
                    why = f"{lines} holds no line"
            except duckdb.Error as error:
                if lines is None:
                    raise  # no file was read, so the warehouse itself is wrong: the areas' table is missing
                # A file that will not read is no lines at all, never a reason to stop every conditions file.
                why = f"{lines} could not be read ({type(error).__name__}: {error})"
                counts = land(con, None, datetime.now(UTC))

    if counts["release"] is None:
        message = (
            f"{why}, so no area closure was cut this run: none of the {counts['areas']} reaches "
            "conditions/trail_closures.json, and every line and point closure still does. publish-weather.yml "
            "prepares a release's nearby trail lines and publish-conditions.yml restores them before the build."
        )
        print(f"::warning title={NO_LINES_TITLE}::{message}")
        _summary(f"**{NO_LINES_TITLE}.** {message}")
        return 0
    line = (
        f"{SCHEMA}.{TABLE}: {counts['landed']:,} of release {counts['release']}'s {counts['held']:,} nearby trail lines, "
        f"those whose box meets one of {counts['areas']:,} area closures"
    )
    print(line)
    _summary(f"area closures cut against {line.split(': ', 1)[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
