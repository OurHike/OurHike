"""step_section_closures: the network lines an organization's own notice closes by naming their section, into derived.section_closures.

    python step_section_closures.py --warehouse W --notices <notices.json>      # a file, as the fixture build passes
    OURHIKE_DATA_ENV=ua DATA_BASE_URL=https://data.ourhike.org \\
        python step_section_closures.py --warehouse W --from-bucket            # the environment's published file

lib/section_closures.py's rule, in the monthly lane (the maintainer, 2026-10-15, for #1801 — The junction graph routes hikers onto the Tuscarora's Doll Ridge section, which PATC says is
closed for loss of landowner permission): a notice that closes the trail in its own words, has no geometry of its own
(a notice with its own geometry is never read here), and is the line's steward's
or a club's naming the trail, closes the one line set whose name is the section it names. This lands one row per line
it closes, with the notice's own title as the reason, verbatim, and int_trail_lines__network_section_closures marks
those lines closed, so nearby_trails.geojson carries the closure and int_trail_network__routable refuses them.

WHY A MONTHLY STEP READING THE PUBLISHED FILE. The lines and the graph are built only in the monthly lane, whose
warehouse holds no hourly notice table (build_marts.py, "A LANE BUILDS ONLY ITS OWN NODES"), and the hourly lane
builds no line. The notices the rule reads are the ones the hourly lane already published, gated and dated, in
conditions/notices.json: so the monthly lane reads that file, once, as step_closure_trail_lines has the hourly lane
read the release's lines. It is the file a phone reads, so a line closes only on a notice a hiker can also read.

A CLOSURE IS AS OLD AS THE MONTHLY BUILD. A notice published after the build closes its lines only at the next one,
and a notice withdrawn after it leaves its lines closed until then. Both are said here rather than hidden: the
conditions file a phone reads every hour stays the current word, and this is the line a route is refused on.

NO FILE IS AN ANSWER, NEVER A FAILURE. A bucket that cannot be read, or an environment with no notices file, lands an
empty table, closes nothing, and says so in a warning: the lines ship as their stewards publish them, as before this
step existed. It never stops the build.

Every outcome the rule lists for a person (ambiguous sets, sections no line carries, near-misses that do not close, and
closing notices left to their own geometry) is printed, as measure_section_closures.py prints them.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from lib import data_env
from lib.derived import replace_table
from lib.http_retry import request_with_retry
from lib.section_closures import evaluate, line_sets
from lib.source_registry import load_registry
from lib.user_agent import USER_AGENT

PIPELINE = Path(__file__).parent
SCHEMA = "derived"
TABLE = "section_closures"
#: The network lines as the monthly lane holds them after NYS Parks' area closures split them.
LINES = "intermediate.int_trail_lines__network_area_closures"
NOTICES_KEY = "conditions/notices.json"
COLUMNS = ("trail_segment_key", "notice_id", "closure_source", "closure_reason", "line_set")


def read_notices(path: Path | None, from_bucket: bool) -> tuple[list[dict] | None, str]:
    """The notices and where they came from, or None and why there are none."""
    if path is not None:
        if not path.exists():
            return None, f"{path} does not exist"
        return json.loads(path.read_text(encoding="utf-8"))["notices"], str(path)
    if not from_bucket:
        return None, "neither --notices nor --from-bucket was given"
    try:
        env = data_env.resolve()
        base = data_env.resolve_base(None, env)
    except data_env.UnknownEnvironment as error:
        return None, str(error)
    if not base:
        return None, "DATA_BASE_URL is not set"
    url = f"{base}/{NOTICES_KEY}"
    try:
        document = request_with_retry(url, label=NOTICES_KEY, headers={"User-Agent": USER_AGENT}).json()
    except Exception as error:  # noqa: BLE001 - any failure to read is an empty answer, said, never a stopped build
        return None, f"{url} could not be read: {error}"
    return document["notices"], url


def read_lines(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """(trail_segment_key, source_key, name, miles) for every network line that is not already closed."""
    con.execute("load spatial")
    return con.execute(f"""
        select
            trail_segment_key,
            source_key,
            name,
            st_length(st_transform(st_geomfromtext(geom_wkt), 'EPSG:4326', 'EPSG:5070', always_xy := true))
                / 1609.344 as miles
        from {LINES}
        where coalesce(trail_status, '') != 'closed'
    """).fetchall()


def closures(notices: list[dict], lines: list[tuple], providers: dict[str, str]) -> tuple[list[dict], list]:
    """One row per line a notice closes, and every outcome the rule has something to say about."""
    outcomes = evaluate(notices, line_sets(lines, providers))
    rows = [
        {
            "trail_segment_key": line_id,
            "notice_id": outcome.notice["notice_id"],
            "closure_source": outcome.notice["source_key"],
            "closure_reason": outcome.notice.get("title"),
            "line_set": f"{line_set.source_key} {line_set.name}",
        }
        for outcome in outcomes
        if outcome.verdict == "closes"
        for line_set in outcome.candidates
        for line_id in line_set.line_ids
    ]
    return rows, outcomes


def write(con: duckdb.DuckDBPyConnection, rows: list[dict], loaded_at: datetime) -> None:
    replace_table(
        con,
        TABLE,
        [(name, "varchar") for name in COLUMNS] + [("_loaded_at", "timestamptz")],
        [(*(row[name] for name in COLUMNS), loaded_at) for row in rows],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse", type=Path, default=PIPELINE / "data" / "warehouse.duckdb")
    parser.add_argument("--notices", type=Path, help="a conditions/notices.json on disk")
    parser.add_argument(
        "--from-bucket", action="store_true", help="read $OURHIKE_DATA_ENV's published notices.json from $DATA_BASE_URL"
    )
    args = parser.parse_args(argv)

    notices, where = read_notices(args.notices, args.from_bucket)
    providers = {s["key"]: s.get("provider") for s in load_registry(PIPELINE / "sources.json")["sources"]}
    with duckdb.connect(str(args.warehouse)) as con:
        if notices is None:
            write(con, [], datetime.now(UTC))
            print(f"WARNING: no notices to read ({where}), so no section closes this build.")
            return 0
        rows, outcomes = closures(notices, read_lines(con), providers)
        write(con, rows, datetime.now(UTC))
    closing = [o for o in outcomes if o.verdict == "closes"]
    print(
        f"{len(notices):,} notices from {where}: {len(closing)} close {len(rows)} line(s), "
        f"{sum(s.miles for o in closing for s in o.candidates):.2f} mi"
    )
    for outcome in outcomes:
        sets = "; ".join(f"{s.source_key} {s.name!r}, {len(s.line_ids)} line(s)" for s in outcome.candidates)
        print(f"  {outcome.verdict}: {outcome.notice['notice_id']} | {sets or 'section ' + repr(outcome.section)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
