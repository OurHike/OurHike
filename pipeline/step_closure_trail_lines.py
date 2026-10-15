"""step_closure_trail_lines: the trail lines that may run inside an area closure, into derived.closure_trail_lines.

    python step_closure_trail_lines.py [--warehouse data/warehouse.duckdb] [--lines data/raw/closure_trail_lines/lines.parquet]
    python step_closure_trail_lines.py --warehouse W --geojson <nearby_trails.geojson> \\
        [--at-geojson <trails.geojson>] --release fixture   # fixtures

Decision 187 (S6, the maintainer's poll of 2026-10-11) crosses out an area
closure's trails where they run inside it, and int_closures__area_trail_cuts
cuts them, in SQL. This hands that model its lines: the release's trail
lines, its nearby trail lines and, since decision 192, the A.T.'s own, which
prepare_closure_trail_lines.py read once per release and
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

THE TABLE IS EMPTY EXACTLY WHEN NO LINES WERE READ. Decision 191 (the
maintainer's poll of 2026-10-14, "Shade them, no edge") shades an area no
mapped trail runs inside, so the cut has to tell "no line runs inside this
area" from "this hour had no lines to look with", and this table is all it
sees. So when a lines file is read and no line's box meets an area's, the
step lands the file's first line by id anyway, one line no area needs, and
the table holds a row whenever lines were read. Without it, a release whose
lines came near no area at all would read as an hour with no lines, and
every area would be left out rather than shaded. On UA that has not
happened: 1,332 lines landed for 193 areas (Measured 2026-10-11, above).

NO LINES IS AN ANSWER, NEVER A FAILURE. Before the weather job has prepared
any release's lines (a first run, or an environment with no release, as
production had on 2026-10-11), this lands an empty table, so no area row
reaches conditions/trail_closures.json that run, neither crossed out nor
shaded, since nothing then says which areas have a trail inside; it says so
in a warning on the run's summary. Line and point closures, which need no
lines, still publish. It never stops the build for it.

ANOTHER RELEASE'S LINES ARE SAID, NEVER REFUSED. publish-conditions.yml
restores the newest prepared entry its branch can see, which is the leg's
current release only once publish-weather.yml has prepared that release and
nothing older of the branch's own is newer (that workflow's restore step says
why; review finding S2-4 of PR #1805 — dlt → dbt re-platform as one go/no-go
change). Given the leg (--leg, or CLOSURE_LINES_LEG, which the workflow sets)
and DATA_BASE_URL, this asks the leg's latest.json which release is current,
once and never again that run (LATEST_SECONDS), and when the lines landed are
another release's it says so in a warning and on the run's summary, naming
both: a trail the current release added or moved inside an area is then not
crossed out, and a stretch it removed can still be. The cut still runs on the
lines it has (Reasoned: they differ from the current release's only where a
release moved a trail, while refusing them would land none, and no area
closure at all would reach conditions/trail_closures.json that hour), and
every closure still publishes. A latest.json that cannot be read is said on
the summary as not checked. Under --geojson nothing is asked.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import duckdb

import prepare_closure_trail_lines
from lib import data_env
from lib.http_retry import request_with_retry
from lib.user_agent import USER_AGENT

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
LINES_PATH = prepare_closure_trail_lines.OUT_DIR / prepare_closure_trail_lines.LINES_FILE
SCHEMA = "derived"
TABLE = "closure_trail_lines"
#: The areas this step lands lines near, each with its bounding box (models/intermediate/closures/).
AREAS = "intermediate.int_closures__trail_closure_areas"
NO_LINES_TITLE = "No trail lines to cut area closures against"
OTHER_RELEASE_TITLE = "Area closures cut against another release's trail lines"
#: The leg whose latest.json names the release the lines should be: publish-conditions.yml's build step sets it.
LEG_VARIABLE = "CLOSURE_LINES_LEG"
#: One read of latest.json, never retried, its connect and each of its reads given this long (requests' timeout, which
#: bounds a stalled server, not a slow whole body): an answer the build can do without (the docstring's "ANOTHER
#: RELEASE'S LINES ARE SAID"). @unvalidated, picked: UA's latest.json is 1,004,519 bytes and came back whole in 1.26
#: to 2.29 s through a sandbox's proxy (Measured 2026-10-15, three reads); a runner's figure is this step's own.
LATEST_SECONDS = 10


def leg_release(base: str, leg: str) -> tuple[str | None, str]:
    """The release `leg`'s latest.json names, with the URL it was read from; or None, with why it is not known."""
    try:
        url = f"{data_env.resolve_base(base, leg)}/latest.json"
    except data_env.UnknownEnvironment as unknown:
        return None, str(unknown)
    try:
        response = request_with_retry(
            url, timeout=LATEST_SECONDS, backoff=(), label="latest.json", headers={"User-Agent": USER_AGENT}
        )
        release = prepare_closure_trail_lines.current_release(response.json())
    except (Exception, SystemExit) as failed:  # noqa: BLE001 - any failure is "not checked", said, never the build's
        return None, f"{url} could not be read ({type(failed).__name__})"
    if release is None:
        return None, f"{url} names no release carrying {' and '.join(prepare_closure_trail_lines.SOURCE_KEYS)}"
    return release, url


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
    when `lines` is None. When the file holds a line and none meets an area, its first line by `line_id` lands alone,
    so the table is empty exactly when no line was read (the docstring's "THE TABLE IS EMPTY EXACTLY WHEN NO LINES
    WERE READ"). Returns the counts: `landed` (the lines near an area), `held` (the file's), `areas`, and the file's
    `release`."""
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
    if landed == 0 and held > 0:
        con.execute(
            f"""
            insert into {SCHEMA}.{TABLE}
            select release, line_id, geometry, cast(? as timestamptz)
            from read_parquet(?)
            order by line_id
            limit 1
            """,
            [loaded_at.isoformat(), str(lines)],
        )
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
    parser.add_argument("--at-geojson", type=Path, help="with --geojson: the A.T.'s trails.geojson to prepare beside it")
    parser.add_argument("--release", default="local", help="with --geojson: the release the files stand for")
    parser.add_argument(
        "--leg",
        default=os.environ.get(LEG_VARIABLE) or None,
        help=f"the leg whose latest.json names its current release (default ${LEG_VARIABLE}); unset, nothing is asked",
    )
    parser.add_argument("--base", help="data base URL for --leg's latest.json; defaults to $DATA_BASE_URL")
    args = parser.parse_args(argv)
    if args.at_geojson is not None and args.geojson is None:
        parser.error("--at-geojson needs --geojson")

    with tempfile.TemporaryDirectory(prefix="closure-trail-lines-") as scratch:
        lines: Path | None = args.lines
        if args.geojson is not None:
            out_dir = Path(scratch)
            sources = {prepare_closure_trail_lines.NEARBY_KEY: args.geojson}
            if args.at_geojson is not None:
                sources[prepare_closure_trail_lines.AT_KEY] = args.at_geojson
            prepare_closure_trail_lines.prepare(sources, out_dir, release=args.release, environment=None, source_sha256s=None)
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
            f"{why}, so no area closure was cut or shaded this run: none of the {counts['areas']} reaches "
            "conditions/trail_closures.json, and every line and point closure still does. publish-weather.yml "
            "prepares a release's trail lines and publish-conditions.yml restores them before the build."
        )
        print(f"::warning title={NO_LINES_TITLE}::{message}")
        _summary(f"**{NO_LINES_TITLE}.** {message}")
        return 0
    line = (
        f"{SCHEMA}.{TABLE}: {counts['landed']:,} of release {counts['release']}'s {counts['held']:,} trail lines, "
        f"those whose box meets one of {counts['areas']:,} area closures"
    )
    if counts["landed"] == 0:
        line += ", and its first line besides, to say the lines were read"
    if args.geojson is None and args.leg:
        line += _against_the_legs_release(str(counts["release"]), args.leg, data_env.resolve_base(args.base))
    print(line)
    _summary(f"area closures cut against {line.split(': ', 1)[1]}")
    return 0


def _against_the_legs_release(lines_release: str, leg: str, base: str) -> str:
    """What the summary line adds about `lines_release` against `leg`'s current release, after warning when they
    differ (the docstring's "ANOTHER RELEASE'S LINES ARE SAID, NEVER REFUSED")."""
    if not base:
        return f"; whether it is the {leg} leg's current release was not checked, as no DATA_BASE_URL was given"
    current, said = leg_release(base, leg)
    if current is None:
        return f"; whether it is the {leg} leg's current release was not checked: {said}"
    if current == lines_release:
        return f", the {leg} leg's current release"
    message = (
        f"{SCHEMA}.{TABLE} holds release {lines_release}'s trail lines, and {said} names release {current}, so this "
        f"hour's area closures were crossed out and shaded against {lines_release}'s trails: a trail {current} added "
        f"or moved inside an area is not crossed out, and a stretch it removed can still be. Every closure still "
        "publishes. The lines are the newest entry this branch's cache can see (publish-conditions.yml's step 2c), "
        "and publish-weather.yml prepares a release's lines on a run that finds no entry of that release's."
    )
    print(f"::warning title={OTHER_RELEASE_TITLE}::{message}")
    _summary(f"**{OTHER_RELEASE_TITLE}.** {message}")
    return f", not the {leg} leg's current release, {current}"


if __name__ == "__main__":
    raise SystemExit(main())
