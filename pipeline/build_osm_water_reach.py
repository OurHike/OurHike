"""Decide which of the corridor's OSM water points a hiker could actually
reach, and write down why for every one of them (#749).

`fetch_osm_water.py` scans fourteen state extracts for OSM's water point
sources. The only geographic filter between that scan and a hiker's screen was
`lib/corridor.py`'s `BUFFER_MILES = 30`, so the gate a water pin had to pass was
*"somewhere within thirty miles of the Appalachian Trail"* - which is most of
the eastern seaboard's tap water. A pin drawn in the water style says *there is
water here* in a voice a hiker reads at dusk with an empty bottle, and a
drinking fountain in a town park eight miles east is a true OSM node and a false
promise on this map.

This is the gate `export_poi.py` reads instead, in `fetch_trail_water.py`'s
shape and on its constants:

  1. **Distance** - within `MATCH_RADIUS_FT` of the nearest of the centerline,
     any side trail, any trail another organization maintains, or any shelter
     or campsite. A union of four, not four rules: a point passes on whichever
     is closest. The maintainer's decision (2026-08-17); the fourth arrived
     with #1016 and did not change the radius, only what the radius is measured
     from.
  2. **Grade** - `MAX_GRADE` rise-over-run from real USGS EPQS elevations at
     both ends, measured to whichever feature the point passed on, so the
     question stays *"can a hiker get from there to the water and back"* - and
     only where the run is at least `MIN_GRADE_RUN_FT`, below which there is no
     walk for a ratio to be about (#815, and see that constant).
  3. **Every rejection keeps its reason and its numbers**, so either gate can be
     re-argued from this file rather than re-run in the dark - the same promise
     `fetch_trail_water.py` makes about its own candidates.

WHY THE UNION IS THREE THINGS AND NOT THE CENTERLINE

`trailPosition.ts` measured it against the live ATC layers (#308): the median
shelter is 197 ft from the centerline and 72% of shelters sit past 90 ft,
because a shelter is at the end of a side trail, which is what side trails are
for. A centerline-only gate would delete OSM water for exactly the reason it
would delete most shelters. **"Any side trail" is ATC's own `side_trails.geojson`
and never OSM's path network**, which would quietly widen this gate back out
toward the thing it exists to close.

AND WHY IT IS FOUR SINCE #1016

The same argument, one trail system over. A hiker standing on a Harriman trail
is standing on ground this app draws, and until #1016 the union held no line
they could be standing on - so an OSM spring fifty feet from them was fetched,
clipped into the corridor, and then refused for being far from the A.T. Four
organizations' trails shipped that way. `nearby_trails.geojson` is the fourth
member, and the same "never OSM's path network" rule governs it: it is the
published artifact of registered stewards' own layers, not a scrape.

WHAT THIS COSTS, MEASURED

`spike_osm_water_gate.py` is the census #749 asked for before any threshold was
written here, and it imports this module's own measurement so the two cannot
disagree. Against the live ATC layers and a 2026-08-18 OSM scan (7,593 nodes
across the fourteen states):

    1,576 OSM water points inside the 30-mile corridor
      146 (9.3%) clear the 100 ft union gate
    1,344 of the 1,430 removed are further than 0.2 mi from anything a hiker
          walks - 1,159 of them further than 5 miles

So the clutter really was the far-away points, which was #749's third open
question and the one it could not assume the answer to.

**THE COST IS THE 86 POINTS BETWEEN 100 FT AND 0.2 MI, AND 55 OF THEM ARE
SPRINGS.** That band is the contested one: a spring 0.2 mi down a blue-blaze is
real, guide-listed water, and this gate deletes it. `spike_guide_water_check.py`
measured (2026-08-14) that springs are the structural gap in our data - a
crossing cannot find one by construction, and OSM's mapped points are the only
reason spring coverage against a commercial guide reaches 37% at all. This gate
takes 176 near-trail springs down to 121.

That is the maintainer's call and a defensible one - a pin nobody can reach is
worse than no pin - but it is a real cost in the direction CLAUDE.md names as
one of the four ways this app can hurt somebody, and it is written here rather
than presented as clean-up. **@unvalidated** - whether those 55 springs are
water a guidebook lists is exactly the check `spike_guide_water_check.py` runs,
and it needs the maintainer's own copy of The A.T. Guide, which no other machine
has. Running it against this file's rejects is what would settle it.

THE GRADE GATE HAD A FLOOR ADDED AFTER THE CENSUS ABOVE WAS TAKEN (#815)

The 61 grade refusals in that run include 12 whose whole walk is under 5 ft -
springs essentially ON the trail, refused because grade is drop over run and
this source's run is often the width of the tread. `MIN_GRADE_RUN_FT` is the
floor that stops it, so the counts above understate what publishes today by up
to those 12. They are left as measured rather than adjusted by arithmetic: the
number in this docstring is a number somebody ran, and re-running
`spike_osm_water_gate.py` is what may replace it.

Output: `data/raw/osm_water_reach.json` - gitignored derived geometry, not a
join somebody reviews row by row, exactly as `fetch_trail_water.py`'s output is
and for the reason `export_poi.py` records beside `TRAIL_WATER_PATH`.

Run:  python build_osm_water_reach.py            # distance pass, then EPQS
      python build_osm_water_reach.py --limit N  # cap the EPQS lookups, resumable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

from export_nearby_trails import SOURCES_PATH, shipped_line_source_keys
from fetch_trail_water import M_PER_FT, MATCH_RADIUS_FT, MAX_GRADE, MIN_GRADE_RUN_FT, elevation_ft, grade_gate
from lib import fetch_receipts
from lib.corridor import GEOGRAPHIC_CRS, PROJECTED_CRS, build_corridor, count_features
from lib.source_registry import load_registry

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = RAW_DIR / "osm_water_reach.json"

# fetch_trail_water.py's radius in metres. Imported rather than restated so a
# re-tune moves this gate and that one together - they are the same judgement
# ("somewhere you walk with a bottle") applied to two sources.
MATCH_RADIUS_M = MATCH_RADIUS_FT * M_PER_FT

# How far out distances are measured before a point is simply "far".
#
# NOT a gate - a reporting ceiling, and the range join's prefilter radius. The
# corridor is 30 miles wide, so a water point can honestly sit 30 miles from the
# trail; past a few miles the exact figure tells a reviewer nothing the verdict
# does not. Five miles keeps every band the gate could plausibly be re-tuned to
# well inside the measured range - the widest bucket the census reports is
# 1-5 mi, and 73.5% of the corridor's points fall past even that.
MEASURE_CEILING_M = 5.0 * 1609.344

# What a hiker could be walking from. Three line layers and two point layers,
# and which one a point passed on is recorded but never changes the gate.
LINE_SOURCES = {"centerline": "centerline.geojson", "side_trail": "side_trails.geojson"}
SITE_SOURCES = {"shelter": "shelters.geojson", "campsite": "campsites.geojson"}

# The third line layer, and the one this file was missing until #1016: every
# other organization's published lines, in one artifact under data/processed/
# rather than one file per key under data/raw/.
#
# ONE ARTIFACT IS WHY THIS NEEDS NO CODE PER ORGANIZATION, which is the half of
# #1016 that matters more than the four sources it fixes today.
# `export_nearby_trails.network_line_sources` puts every registry entry carrying
# `blaze_field` or `blaze_default` into this file, so registering a Catskills or
# NJ layer in sources.json brings its water with it on the next run with nobody
# editing a list here - the shape #1011 gave the DEM index.
#
# Absent is a normal state and means A.T. only, exactly as it did before: a
# publish that skipped the network export, or one whose licence gate held those
# lines back. main() says which happened rather than quietly gating a smaller
# world.
NETWORK_LINES_PATH = ROOT / "data" / "processed" / "nearby_trails.geojson"
NETWORK_LINE_TABLE = "network_trail"

TOO_FAR = "the nearest {feature} is {distance_ft:.0f} ft away, past the {radius:.0f} ft a hiker walks for water"
TOO_STEEP = (
    "the ground drops {drop_ft:.0f} ft over {distance_ft:.0f} ft - a {grade:.0%} grade, which is a scramble rather than a walk"
)
NOTHING_NEAR = "no trail, side trail, network trail, shelter or campsite within {ceiling:.0f} miles"
NO_ELEVATION = "USGS would not give an elevation for one end of the walk, so the ground between is unknown"

# Write guards, in fetch_osm_water.py's shape and for its reason: a well-formed
# but collapsed result must not overwrite a good file. The floor is far under
# the 146 the census measured (2026-08-18) because it is here to catch a run
# that read no trail geometry at all - a corridor clip that silently returned
# nothing would otherwise publish as "no water is reachable", which is both
# false and exactly the direction a water gate must never fail in.
MIN_REACHABLE = 40
MAX_REACHABLE_DROP_RATIO = 0.5


def load_water(con: duckdb.DuckDBPyConnection) -> int:
    """The OSM water points, clipped to the corridor.

    The same `ST_Intersects` clip `export_poi.py`'s `clip_to_corridor` applies,
    so this file's population is exactly the population that would otherwise
    reach the map - the 30-mile corridor is the gate being replaced, and
    measuring inside it is the point.
    """
    water_path = (RAW_DIR / "osm_water.geojson").as_posix()
    con.execute(f"""
        CREATE OR REPLACE TABLE water AS
        SELECT
            w.osm_id,
            w.kind,
            ST_X(w.geom) AS lon,
            ST_Y(w.geom) AS lat,
            ST_Transform(w.geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS g
        FROM ST_Read('{water_path}') w, corridor
        WHERE ST_Intersects(w.geom, corridor.geom)
    """)
    return con.execute("SELECT count(*) FROM water").fetchone()[0]


def load_lines(
    con: duckdb.DuckDBPyConnection,
    table: str,
    path: Path,
    source_field: str | None = None,
    keys: set[str] | None = None,
) -> int:
    """One line layer, projected to metres, with its bounding box as columns.

    The bbox columns are a prefilter and never a distance: a range join on four
    doubles picks the handful of lines worth measuring against each point, and
    `ST_Distance` then runs on the real geometry. Nearest-vertex would be the
    cheap alternative and is wrong at this frame - the gate binds at 30.5 m and
    the centerline carries 690,040 vertices, so a vertex approximation could
    move a point across the gate by a couple of metres.

    `source_field` names a property carrying which organization drew the line,
    for the one layer that mixes several (`nearby_trails.geojson`). It is
    reported and never gated on: a spring is reachable or it is not, and whose
    trail it sits beside has no bearing on whether a hiker can walk to it.

    `keys` restricts which of those organizations count - see
    `shipped_network_keys`, and note that this is not a gate on the water
    either: it decides whose LINES this build is allowed to measure against.
    """
    label = f'"{source_field}"' if source_field else "NULL::VARCHAR"
    where = ""
    if keys is not None:
        # Empty set -> no rows, which is the right answer and not a no-op: it
        # means every organization in the artifact is still review-only.
        quoted = ", ".join("'" + key.replace("'", "''") + "'" for key in sorted(keys)) or "NULL"
        where = f'WHERE "{source_field}" IN ({quoted})'
    con.execute(f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT g, src, ST_XMin(g) AS xmin, ST_XMax(g) AS xmax, ST_YMin(g) AS ymin, ST_YMax(g) AS ymax
        FROM (
            SELECT ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS g,
                   {label} AS src
            FROM ST_Read('{path.as_posix()}')
            {where}
        )
    """)
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def shipped_network_keys() -> set[str]:
    """The organizations whose lines this build may measure against - those
    whose data reaches hikers. See export_nearby_trails.shipped_line_source_keys
    for why the artifact holds more than that."""
    return shipped_line_source_keys(load_registry(SOURCES_PATH))


def load_network_lines(con: duckdb.DuckDBPyConnection, path: Path | None = None) -> int:
    """The published network lines, or 0 when there is no artifact to read.

    Zero is not an error and must not be treated as one - see NETWORK_LINES_PATH
    for the two ordinary ways it happens. What it costs is stated where it can
    be seen: this run then gates exactly the A.T.'s water, and `main` prints
    that it did.
    """
    path = NETWORK_LINES_PATH if path is None else path
    if not count_features(con, path):
        return 0
    return load_lines(con, NETWORK_LINE_TABLE, path, source_field="source", keys=shipped_network_keys())


def load_sites(con: duckdb.DuckDBPyConnection) -> int:
    """Shelters and campsites as one projected point table - the gate's union
    treats them as one class, and which of the two won is reported only."""
    selects = [
        f"""
            SELECT '{label}' AS site_kind,
                   ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS g
            FROM ST_Read('{(RAW_DIR / filename).as_posix()}')
        """
        for label, filename in SITE_SOURCES.items()
    ]
    con.execute(f"CREATE OR REPLACE TABLE sites AS {' UNION ALL '.join(selects)}")
    return con.execute("SELECT count(*) FROM sites").fetchone()[0]


def nearest_line(con: duckdb.DuckDBPyConnection, table: str) -> dict[str, dict]:
    """Each water point's distance to the nearest line in `table`, plus the
    coordinate on that line it is nearest to.

    That coordinate is the OTHER END OF THE WALK and the grade gate needs it:
    the question is about the ground between the water and the trail a hiker
    leaves from, not the ground under some vertex nearby.
    """
    rows = con.execute(f"""
        WITH pairs AS (
            SELECT w.osm_id, ST_Distance(w.g, t.g) AS d, ST_ClosestPoint(t.g, w.g) AS cp, t.src AS src
            FROM water w
            JOIN {table} t
              ON t.xmin <= ST_X(w.g) + {MEASURE_CEILING_M}
             AND t.xmax >= ST_X(w.g) - {MEASURE_CEILING_M}
             AND t.ymin <= ST_Y(w.g) + {MEASURE_CEILING_M}
             AND t.ymax >= ST_Y(w.g) - {MEASURE_CEILING_M}
        )
        SELECT osm_id,
               MIN(d) AS d,
               ST_X(ST_Transform(arg_min(cp, d), '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true)) AS lon,
               ST_Y(ST_Transform(arg_min(cp, d), '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true)) AS lat,
               arg_min(src, d) AS src
        FROM pairs
        WHERE d <= {MEASURE_CEILING_M}
        GROUP BY 1
    """).fetchall()
    return {r[0]: {"dist_m": r[1], "lon": r[2], "lat": r[3], "src": r[4]} for r in rows}


def nearest_site(con: duckdb.DuckDBPyConnection) -> dict[str, dict]:
    """Each water point's distance to the nearest shelter or campsite."""
    rows = con.execute(f"""
        WITH pairs AS (
            SELECT w.osm_id, s.site_kind,
                   ST_Distance(w.g, s.g) AS d,
                   ST_X(ST_Transform(s.g, '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true)) AS lon,
                   ST_Y(ST_Transform(s.g, '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true)) AS lat
            FROM water w
            JOIN sites s
              ON ST_X(s.g) BETWEEN ST_X(w.g) - {MEASURE_CEILING_M} AND ST_X(w.g) + {MEASURE_CEILING_M}
             AND ST_Y(s.g) BETWEEN ST_Y(w.g) - {MEASURE_CEILING_M} AND ST_Y(w.g) + {MEASURE_CEILING_M}
        )
        SELECT osm_id, MIN(d) AS d, arg_min(lon, d) AS lon, arg_min(lat, d) AS lat, arg_min(site_kind, d) AS site_kind
        FROM pairs
        WHERE d <= {MEASURE_CEILING_M}
        GROUP BY 1
    """).fetchall()
    return {r[0]: {"dist_m": r[1], "lon": r[2], "lat": r[3], "site_kind": r[4]} for r in rows}


def measure_distances(con: duckdb.DuckDBPyConnection, quiet: bool = False) -> list[dict]:
    """One record per corridor water point, carrying its distance to each of
    the three, which one it is nearest to, and whether that clears the gate.

    The grade verdict is NOT filled in here - `apply_grade_gate` does that, and
    keeping the passes separate is what lets the slow half resume.
    """

    def say(message: str) -> None:
        if not quiet:
            print(message, flush=True)

    say("Building the corridor ...")
    widened = build_corridor(con, RAW_DIR / "centerline.geojson", NETWORK_LINES_PATH)
    say(f"  {'widened around the published network lines' if widened else 'the A.T. alone - no network artifact'}.")
    say(f"  {load_water(con)} OSM water points inside the corridor.")
    line_tables = []
    for table, filename in LINE_SOURCES.items():
        say(f"  {load_lines(con, table, RAW_DIR / filename)} {table} lines.")
        line_tables.append(table)
    network_lines = load_network_lines(con)
    if network_lines:
        say(f"  {network_lines} network trail lines.")
        line_tables.append(NETWORK_LINE_TABLE)
    say(f"  {load_sites(con)} shelters + campsites.")

    say("Measuring distances ...")
    per_source = {label: nearest_line(con, label) for label in line_tables}
    per_source["site"] = nearest_site(con)

    records = []
    for osm_id, kind, lon, lat in con.execute("SELECT osm_id, kind, lon, lat FROM water ORDER BY osm_id").fetchall():
        found = {label: hit for label, hits in per_source.items() if (hit := hits.get(osm_id)) is not None}
        record = {
            "osm_id": osm_id,
            "kind": kind,
            "lon": lon,
            "lat": lat,
            "distances_m": {label: round(hit["dist_m"], 2) for label, hit in found.items()},
        }
        if found:
            label = min(found, key=lambda k: found[k]["dist_m"])
            hit = found[label]
            record["nearest"] = hit["site_kind"] if label == "site" else label
            if label == NETWORK_LINE_TABLE:
                # Which organization's trail it is beside. Reported, never
                # gated on - and read downstream for a different question than
                # this file's: export_poi.py withholds the A.T. mile from a
                # point whose only walk is off the A.T., because a mile is a
                # position ON the A.T. and dayPlanner.ts offers anything
                # carrying one as a stop along it.
                record["nearest_source"] = hit["src"]
            record["nearest_m"] = round(hit["dist_m"], 2)
            record["walk_to"] = {"lon": hit["lon"], "lat": hit["lat"]}
            record["passes_distance"] = hit["dist_m"] <= MATCH_RADIUS_M
            if not record["passes_distance"]:
                record["reason"] = TOO_FAR.format(
                    feature=record["nearest"].replace("_", " "),
                    distance_ft=hit["dist_m"] / M_PER_FT,
                    radius=MATCH_RADIUS_FT,
                )
        else:
            # Nothing within the ceiling. Not an error - the corridor's far edge
            # is thirty miles from the trail, and 73.5% of its water sits past
            # five of them.
            record["nearest"] = None
            record["nearest_m"] = None
            record["passes_distance"] = False
            record["reason"] = NOTHING_NEAR.format(ceiling=MEASURE_CEILING_M / 1609.344)
        records.append(record)
    return records


def apply_grade_gate(records: list[dict], limit: int | None = None, quiet: bool = False) -> None:
    """Fill in the grade verdict for every point that cleared the distance gate.

    Mutates in place, checkpointing to disk as it goes: EPQS answers in ~1.9 s
    and an interrupted run must not throw away the lookups it already paid for.
    `elevation_ft` is `fetch_trail_water.py`'s own and disk-cached, so a re-run
    over the same points costs nothing and a tightened `MAX_GRADE` costs no
    network at all.

    A point EPQS will not answer for is left NOT reachable, with a reason saying
    so - an unknown is not a pass, and it is also not a rejection this file may
    blame on terrain.
    """
    pending = [r for r in records if r["passes_distance"] and "passes_grade" not in r]
    if limit is not None:
        pending = pending[:limit]
    if not quiet:
        print(f"Grade gate: {len(pending)} points to look up (2 EPQS calls each) ...", flush=True)
    for i, record in enumerate(pending, 1):
        water_elevation = elevation_ft(record["lat"], record["lon"])
        trail_elevation = elevation_ft(record["walk_to"]["lat"], record["walk_to"]["lon"])
        if water_elevation is None or trail_elevation is None:
            record["passes_grade"] = False
            record["reason"] = NO_ELEVATION
            continue
        distance_ft = record["nearest_m"] / M_PER_FT
        drop_ft = abs(water_elevation - trail_elevation)
        # fetch_trail_water.py's gate, called rather than restated so a re-tune
        # moves this one and that one together. Below MIN_GRADE_RUN_FT it
        # declines to have an opinion, which matters far more here than there:
        # the feature a point passed on is often the trail it sits beside, and
        # that denominator is what #815 found making the ratio say anything.
        grade, walkable = grade_gate(drop_ft, distance_ft)
        record["drop_ft"] = round(drop_ft, 1)
        record["grade"] = round(grade, 3)
        record["passes_grade"] = walkable
        if walkable and grade > MAX_GRADE:
            # Only where the floor CHANGED the verdict. Recorded so the rescued
            # points stay countable from the file, and so a reader meeting a
            # grade of 1.48 beside a pass can see which number carried it.
            record["grade_floored"] = True
        if not walkable:
            record["reason"] = TOO_STEEP.format(drop_ft=drop_ft, distance_ft=distance_ft, grade=grade)
        if i % 25 == 0 and not quiet:
            print(f"  {i}/{len(pending)}", flush=True)
            write(records, guard=False)
    write(records, guard=False)


def is_reachable(record: dict) -> bool:
    """One point's verdict. Both gates, and an ungraded point is not reachable -
    see apply_grade_gate on why an unknown may not pass."""
    return bool(record["passes_distance"]) and bool(record.get("passes_grade"))


def write(records: list[dict], guard: bool = True, previous: int | None = None) -> None:
    """Write the verdict file, refusing a collapsed result when asked to guard.

    The guard is off for the checkpoints `apply_grade_gate` takes mid-run, which
    are deliberately partial - it belongs on the finished file only.

    `previous` is passed in rather than read here, and that is the whole point of
    the parameter: those mid-run checkpoints have already overwritten OUT_PATH by
    the time the guarded write happens, so a drop guard that re-read the file
    would be comparing this run against itself and could never fire. main() reads
    it once, before anything is written.
    """
    # Stamped onto each record rather than left for the reader to recompute.
    # export_poi.py is the reader, and a consumer that had to re-derive "both
    # gates, and an unknown is not a pass" from the parts is a second copy of
    # this file's judgement that could drift from it.
    for record in records:
        record["reachable"] = is_reachable(record)
    reachable = [r for r in records if r["reachable"]]
    if guard:
        if len(reachable) < MIN_REACHABLE:
            raise SystemExit(
                f"Refusing to write: {len(reachable)} reachable points is below the floor of "
                f"{MIN_REACHABLE} - see MIN_REACHABLE. Did the trail layers load?"
            )
        if previous and len(reachable) < previous * MAX_REACHABLE_DROP_RATIO:
            raise SystemExit(
                f"Refusing to overwrite {OUT_PATH.name}: {len(reachable)} reachable against "
                f"{previous} on disk is past the {MAX_REACHABLE_DROP_RATIO:.0%} drop guard."
            )
    payload = {
        "match_radius_ft": MATCH_RADIUS_FT,
        "max_grade": MAX_GRADE,
        "min_grade_run_ft": MIN_GRADE_RUN_FT,
        # Which union these verdicts were taken against (#1016). Stamped for
        # the same reason `min_grade_run_ft` is: this file is restored from the
        # last publish and resumed rather than rebuilt, so without a record of
        # what it was measured against, a run that finally HAS the network
        # lines would resume A.T.-only verdicts and publish them - the defect
        # surviving its own fix. See main().
        "measured_against_network": bool(NETWORK_LINES_PATH.exists()),
        "n_corridor": len(records),
        "n_reachable": len(reachable),
        "points": records,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    tmp.replace(OUT_PATH)


def network_union_changed(path: Path, network_path: Path | None = None) -> bool:
    """Whether the verdicts on `path` were taken against a different union than
    this run would use (#1016).

    ONE DIRECTION ONLY, deliberately: true when the file has no network behind
    it and the artifact is here now. The other direction - verdicts that
    included the network, on a run where the artifact has gone missing - is NOT
    a re-measure, because re-measuring would throw away good verdicts to
    replace them with a narrower set. Those points simply fail the export's own
    gate if their lines are no longer published, which is the safe direction
    and already how a held-back licence behaves.

    A file written before this stamp existed has no key and reads as false, so
    the first run after #1016 with an artifact present re-measures once. That is
    the intended migration and it is why absence is not treated as unknown.
    """
    network = NETWORK_LINES_PATH if network_path is None else network_path
    if not network.exists():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    return not payload.get("measured_against_network", False)


def drop_stale_grade_verdicts(records: list[dict], floor_on_disk: float | None) -> int:
    """Forget grade verdicts taken under a different floor, and say how many.

    `apply_grade_gate` skips anything already carrying `passes_grade`, which is
    what makes an interrupted run resumable - and what would otherwise make a
    changed `MIN_GRADE_RUN_FT` INERT against the file on disk. That is not a
    theoretical path: the publish workflow restores `data/raw/` from the Actions
    cache on every run (#812), so the file this resumes from will normally be an
    older run's, carrying older verdicts.

    Only a walk shorter than the wider of the two floors can change its verdict,
    so the longer walks keep theirs and their EPQS lookups. The rest are
    re-graded from the disk-cached elevations, which costs network only where
    that cache is gone too.
    """
    if floor_on_disk == MIN_GRADE_RUN_FT:
        return 0
    affected_below_ft = max(MIN_GRADE_RUN_FT, floor_on_disk or 0.0)
    cleared = 0
    for record in records:
        if "passes_grade" not in record:
            continue
        if record["nearest_m"] / M_PER_FT >= affected_below_ft:
            continue
        del record["passes_grade"]
        record.pop("grade_floored", None)
        record.pop("reason", None)
        cleared += 1
    return cleared


def read_previous_reachable_count() -> int | None:
    if not OUT_PATH.exists():
        return None
    try:
        return json.loads(OUT_PATH.read_text(encoding="utf-8")).get("n_reachable")
    except json.JSONDecodeError:
        return None


def summarise(records: list[dict]) -> None:
    n = len(records)
    passed = [r for r in records if r["passes_distance"]]
    graded = [r for r in passed if "passes_grade" in r]
    steep = [r for r in graded if not r["passes_grade"]]
    floored = [r for r in graded if r.get("grade_floored")]
    reachable = [r for r in records if is_reachable(r)]
    print(f"\n{len(passed)}/{n} clear the {MATCH_RADIUS_FT:.0f} ft union gate ({100 * len(passed) / n:.1f}%).")
    if graded:
        print(f"{len(steep)}/{len(graded)} of those graded are past the {MAX_GRADE:.0%} grade.")
    if floored:
        # Printed because it is the count #815 leaves open: these are the points
        # the floor rescued, and reading their drops is what would say whether
        # a minimum run was the right shape.
        print(f"{len(floored)} passed on the {MIN_GRADE_RUN_FT:.0f} ft floor, their run too short to grade.")
    if len(graded) < len(passed):
        print(f"{len(passed) - len(graded)} still ungraded - re-run to finish the EPQS lookups.")
    print(f"{len(reachable)} of {n} corridor water points are reachable ({100 * len(reachable) / n:.1f}%).")

    # Per organization, because #1016's whole subject is that four of them had
    # none. A source registered and drawn but showing 0 here is the same defect
    # in a new place, and a number nobody printed is a number nobody checked.
    on_network = [r for r in reachable if r.get("nearest_source")]
    if on_network:
        by_source: dict[str, int] = {}
        for record in on_network:
            by_source[record["nearest_source"]] = by_source.get(record["nearest_source"], 0) + 1
        named = ", ".join(f"{source}: {count}" for source, count in sorted(by_source.items()))
        print(f"{len(on_network)} of them are reachable from a network trail rather than the A.T. ({named}).")
    elif any(r.get("nearest") == NETWORK_LINE_TABLE for r in records):
        print("No water point is reachable from a network trail - every one measured against them is past the gate.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="cap this run's EPQS lookups (resumable)")
    parser.add_argument("--remeasure", action="store_true", help="redo the distance pass, discarding the file on disk")
    args = parser.parse_args(argv)

    # Read before anything writes: apply_grade_gate checkpoints over OUT_PATH as
    # it goes, so this is the only moment the count on disk is still the PREVIOUS
    # run's. See write().
    previous = read_previous_reachable_count()

    resumable = OUT_PATH.exists() and not args.remeasure
    if resumable and network_union_changed(OUT_PATH):
        # The distance pass has to be redone, not patched: a point that was
        # never in the corridor has no row here to re-measure, so the widened
        # union can only arrive through a full re-measure. The EPQS cache makes
        # the re-grade cheap for every point already answered for.
        print("The verdicts on disk were taken without the network lines that are here now - re-measuring (#1016).")
        resumable = False

    if resumable:
        payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        records = payload["points"]
        print(f"Resuming from {OUT_PATH.name} ({len(records)} points).")
        stale = drop_stale_grade_verdicts(records, payload.get("min_grade_run_ft"))
        if stale:
            print(f"{stale} verdicts predate the {MIN_GRADE_RUN_FT:.0f} ft floor - re-grading those.")
    else:
        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial;")
        records = measure_distances(con)

    apply_grade_gate(records, limit=args.limit)
    write(records, previous=previous)
    summarise(records)
    print(f"Wrote {OUT_PATH}")
    fetch_receipts.record("build_osm_water_reach", [OUT_PATH])
    return 0


if __name__ == "__main__":
    sys.exit(main())
