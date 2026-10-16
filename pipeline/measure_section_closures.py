"""Count what the section-closure rule (lib/section_closures.py, decision 212) would close, before it ships.

Reads a conditions/notices.json and a nearby_trails.geojson (UA's, or any release's) and prints how many notices
from how many organizations the rule places, how many lines and miles it closes, every match, and every near-miss
it refuses, by kind. Writes nothing. The maintainer reads this list before the rule's output reaches a phone.

    python measure_section_closures.py --notices notices.json --lines nearby_trails.geojson
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import duckdb

from lib.section_closures import VERDICTS, evaluate, line_sets
from lib.source_registry import load_registry

ROOT = Path(__file__).parent


def read_lines(path: Path) -> list[tuple]:
    """(id, source, name, length_miles) for every feature, through GDAL: the whole network is 540 MB of JSON."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    return con.execute(f"select id, source, name, length_miles from ST_Read('{path.as_posix()}')").fetchall()


def report(outcomes) -> list[str]:
    out = []
    counts = Counter(o.verdict for o in outcomes)
    closes = [o for o in outcomes if o.verdict == "closes"]
    out.append(
        f"places {len(closes)} notice(s) from {len({o.notice['provider'] for o in closes})} organization(s), closing "
        f"{sum(len(s.line_ids) for o in closes for s in o.candidates)} line(s), "
        f"{sum(s.miles for o in closes for s in o.candidates):.2f} mi"
    )
    for verdict in VERDICTS:
        rows = [o for o in outcomes if o.verdict == verdict]
        out.append(f"\n{verdict}: {counts[verdict]} notice(s) from {len({o.notice['provider'] for o in rows})} org(s)")
        for o in rows:
            sets = "; ".join(f"{s.source_key} {s.name!r}, {len(s.line_ids)} line(s), {s.miles:.2f} mi" for s in o.candidates)
            out.append(f"  {o.notice['notice_id']} | {o.notice.get('title')!r} | {sets or 'section ' + repr(o.section)}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--notices", type=Path, required=True)
    parser.add_argument("--lines", type=Path, required=True)
    args = parser.parse_args(argv)
    providers = {s["key"]: s.get("provider") for s in load_registry(ROOT / "sources.json")["sources"]}
    notices = json.loads(args.notices.read_text(encoding="utf-8"))["notices"]
    closing = [n for n in notices if n.get("obstructs_trail")]
    print(
        f"{len(notices)} notices, {len(closing)} closing from {len({n['provider'] for n in closing})} organizations, "
        f"{sum(1 for n in closing if (n.get('place') or {}).get('kind') != 'geometry')} of them with no geometry of their own"
    )
    print("\n".join(report(evaluate(notices, line_sets(read_lines(args.lines), providers)))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
