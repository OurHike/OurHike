"""Day-boundary feasibility spike (features/HIKE_PLANNING.md, question Q1).

Answers one question, and only one: **can a plan whose days all end at a real
designated site actually hit a target day length, and how bad is the worst
day when it cannot?** That is a property of where the ATC put shelters, not
of any algorithm - so it has to be measured against the real data rather than
argued about, which is what this script is for.

It also measures two things the design leans on:

  - what campsites buy over shelters alone (280 vs 512 candidate stops), and
  - whether planning by TIME rather than by distance moves the boundaries
    enough to be worth the extra machinery (HIKE_PLANNING.md, Finding 4).

Uses only already-fetched ATC data (see fetch_all.py) - no network, same as
spike_corridor.py. The elevation half additionally wants
data/processed/elevation_profile.json (export_elevation.py); without it the
script still runs and simply skips the time-target comparison.

THIS IS A SPIKE, AND THE PLANNER BELOW IS THROWAWAY. The real one runs on a
phone, in TypeScript, over POI miles the pipeline publishes (Finding 2). The
version here exists to produce numbers, and is kept honest by tests rather
than shipped. What should survive into the client is the SHAPE - a
shortest-path over candidate stops with an asymmetric cost - not this code.

Ordering and projection come from export_elevation.py rather than being
re-derived, deliberately: HIKE_PLANNING.md's Finding 1 is that this
repository already measures "a mile" two different ways, and a spike that
invented a third would be measuring its own arithmetic.
"""

import argparse
import json
import statistics
from dataclasses import dataclass
from pathlib import Path

import duckdb
from shapely.geometry import LineString, Point

from export_elevation import (
    GEOGRAPHIC_CRS,
    METERS_PER_MILE,
    PROJECTED_CRS,
    load_merged_trail_line,
    ordered_oriented_parts,
    reproject_lines_to_meters,
)
from lib.elevation_gain import DEFAULT_THRESHOLD_FT, cumulative_gain_over_gaps

ROOT = Path(__file__).parent
CENTERLINE_PATH = ROOT / "data" / "raw" / "centerline.geojson"
PROFILE_PATH = ROOT / "data" / "processed" / "elevation_profile.json"

# The two ATC point layers a night can plausibly end at. Water and resupply
# are deliberately not here: they answer "what is along the way", which is
# TRIP_PLANNING.md's planning-assistance question, not "where does a day
# stop".
STOP_LAYERS = (("shelter", "shelters"), ("campsite", "campsites"))

DEFAULT_TARGETS_MI = (10.0, 12.0, 15.0, 18.0, 20.0)

# The longest day the planner may schedule. Not a fitness opinion - it is the
# point past which an auto-generated day stops being a suggestion and becomes
# a thing that gets someone benighted. Overridable, and the script reports
# every place the trail forces a longer one anyway.
DEFAULT_CAP_MI = 25.0

# How much worse it is to overshoot the target than to undershoot it by the
# same amount. Asymmetric because the two failures are not alike: a hiker who
# arrives early can walk on, and one who is two miles short of the shelter at
# dusk cannot. 2.25 = 1.5 squared, i.e. "overshooting by 2 miles costs what
# undershooting by 3 does".
OVER_TARGET_WEIGHT = 2.25

# How far off the centerline a site may sit and still be treated as a stop on
# it. Shelters are routinely a few hundred feet down a blue blaze; something
# half a mile off is a side trip, and counting its spur mileage as trail
# mileage would quietly inflate every day that ended there.
MAX_OFF_TRAIL_MI = 0.5

# Naismith, repeated here ONLY to measure with. client/src/lib/naismith.ts is
# where this rule lives for real; if the two ever disagree, that file is
# right and this one is a spike that went stale.
NAISMITH_KM_PER_HOUR = 5.0
KM_PER_MILE = 1.609344
METERS_PER_FOOT = 0.3048
METERS_PER_ASCENT_HOUR = 600.0

# Candidate names for the site's own label, lowercased. ATC's facility layers
# do not agree with each other on this field, and the label is decoration
# here - a stop with no readable name is still a stop, so this falls back to
# a positional id rather than failing the run.
NAME_FIELDS = ("name", "shelter_name", "facility_name", "site_name", "sitename", "label")


@dataclass(frozen=True)
class Stop:
    """A place a day could end, positioned along the trail."""

    name: str
    kind: str
    mile: float
    off_trail_mi: float


@dataclass(frozen=True)
class Day:
    start_mi: float
    end_mi: float

    @property
    def length_mi(self) -> float:
        return self.end_mi - self.start_mi


def read_points(con: duckdb.DuckDBPyConnection, path: Path, kind: str) -> list[tuple[str, Point]]:
    """Every point feature in an ATC layer, reprojected to EPSG:5070.

    always_xy on the transform for the reason README.md's "Gotcha hit and
    fixed" note gives: without it PROJ silently swaps the axes rather than
    erroring, and the failure surfaces much later as nonsense distances.
    """
    con.execute(f"CREATE OR REPLACE TABLE _stops AS SELECT * FROM ST_Read('{path.as_posix()}')")
    columns = [row[1].lower() for row in con.execute("PRAGMA table_info('_stops')").fetchall()]
    name_column = next((c for c in NAME_FIELDS if c in columns), None)
    label = f'"{name_column}"' if name_column else "NULL"

    rows = con.execute(f"""
        SELECT {label},
               ST_X(ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true)),
               ST_Y(ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true))
        FROM _stops
        WHERE geom IS NOT NULL
    """).fetchall()

    return [
        (str(name) if name else f"{kind} {i + 1}", Point(x, y))
        for i, (name, x, y) in enumerate(rows)
        if x is not None and y is not None
    ]


def locate_stops(parts_meters: list[LineString], points: list[tuple[str, Point]], kind: str) -> list[Stop]:
    """Position each point along the ordered centerline, in miles from the
    southern terminus.

    The same measurement export_elevation.py's `distance_mi` is: cumulative
    length along the ordered, oriented, merged pieces. A point is matched to
    whichever piece it is nearest, and carries how far off the line it sat -
    which is the number MAX_OFF_TRAIL_MI is applied to by the caller, not
    here, so the script can report what it dropped.

    O(stops x parts), which on the real data is ~512 x 558 shapely distance
    calls. Measured in seconds, and this runs by hand - an STRtree would be
    the fix if it ever ran anywhere that cared.
    """
    offsets: list[float] = []
    running = 0.0
    for part in parts_meters:
        offsets.append(running)
        running += part.length

    located: list[Stop] = []
    for name, point in points:
        best_part = min(range(len(parts_meters)), key=lambda i: parts_meters[i].distance(point))
        part = parts_meters[best_part]
        along_m = offsets[best_part] + part.project(point)
        located.append(
            Stop(
                name=name,
                kind=kind,
                mile=along_m / METERS_PER_MILE,
                off_trail_mi=part.distance(point) / METERS_PER_MILE,
            )
        )

    return sorted(located, key=lambda s: s.mile)


def spacing_summary(miles: list[float]) -> dict:
    """How far apart consecutive stops are. The distribution, not just the
    mean: an 8-mile average made of 3s and 20s plans very differently from an
    8-mile average made of 7s and 9s, and that difference is the entire
    question this spike exists to ask."""
    gaps = [b - a for a, b in zip(miles, miles[1:])]
    if not gaps:
        return {"count": len(miles), "gaps": 0}

    ordered = sorted(gaps)
    return {
        "count": len(miles),
        "gaps": len(gaps),
        "mean_mi": statistics.fmean(gaps),
        "median_mi": statistics.median(gaps),
        "p90_mi": ordered[int(len(ordered) * 0.9)],
        "max_mi": ordered[-1],
        "min_mi": ordered[0],
    }


def day_cost(length: float, target: float, over_weight: float = OVER_TARGET_WEIGHT) -> float:
    """What a day of this size costs against the target.

    Squared, so that one badly wrong day is worse than several slightly wrong
    ones - which is the behaviour a hiker wants and the behaviour a greedy
    "walk until you pass the target" pass does not give. See OVER_TARGET_WEIGHT
    for the asymmetry.
    """
    deviation = length - target
    weight = over_weight if deviation > 0 else 1.0
    return weight * deviation * deviation


def plan_days(
    miles: list[float],
    target: float,
    cap_mi: float = DEFAULT_CAP_MI,
    effort=None,
    over_weight: float = OVER_TARGET_WEIGHT,
) -> list[Day]:
    """Choose day boundaries out of the candidate stops.

    `miles` is every stop that could end a day, ascending, with the route's
    own start and end first and last - both are forced boundaries, because a
    hike starts and finishes where the hiker said it does.

    `effort(a, b)` measures a day in whatever unit `target` is in. Distance
    by default; pass a Naismith function to plan by time instead
    (HIKE_PLANNING.md, Finding 4). `cap_mi` is always in miles regardless,
    because the ceiling is physical.

    A shortest path rather than a greedy walk, and the difference is the
    point: greedy takes the best-looking first day and pays for it at the far
    end, where the trail has run out and the last day is two miles long. The
    DP spreads the unavoidable error across every day instead.

    Where the trail offers nothing at all inside the cap - and it does, in
    real places - the only reachable predecessor is taken and the resulting
    over-cap day is returned as it is. Refusing to plan there would be
    refusing to describe a stretch of trail that exists.
    """
    if len(miles) < 2:
        return []

    measure = effort if effort is not None else (lambda a, b: b - a)

    best = [0.0] + [float("inf")] * (len(miles) - 1)
    previous = [0] * len(miles)

    for j in range(1, len(miles)):
        reachable = [i for i in range(j) if miles[j] - miles[i] <= cap_mi]
        # Nowhere to stop inside the cap: the day is as long as the trail
        # makes it. Reported rather than hidden - see day_summary's over_cap.
        if not reachable:
            reachable = [j - 1]

        for i in reachable:
            candidate = best[i] + day_cost(measure(miles[i], miles[j]), target, over_weight)
            if candidate < best[j]:
                best[j] = candidate
                previous[j] = i

    boundaries = [len(miles) - 1]
    while boundaries[-1] != 0:
        boundaries.append(previous[boundaries[-1]])
    boundaries.reverse()

    return [Day(miles[a], miles[b]) for a, b in zip(boundaries, boundaries[1:])]


def day_summary(days: list[Day], target_mi: float, cap_mi: float = DEFAULT_CAP_MI) -> dict:
    """What the generated plan actually looks like, in miles."""
    lengths = [day.length_mi for day in days]
    if not lengths:
        return {"days": 0}

    within = [length for length in lengths if abs(length - target_mi) <= target_mi * 0.2]
    return {
        "days": len(days),
        "mean_mi": statistics.fmean(lengths),
        "median_mi": statistics.median(lengths),
        "shortest_mi": min(lengths),
        "longest_mi": max(lengths),
        "within_20pct": len(within) / len(lengths),
        "over_cap": sum(1 for length in lengths if length > cap_mi),
    }


def load_profile(path: Path) -> tuple[list[float], list[float | None]] | None:
    """export_elevation.py's published profile as two parallel lists, or None
    if this checkout has not built one."""
    if not path.exists():
        return None

    samples = json.loads(path.read_text())
    distances = [s["distance_mi"] for s in samples]
    elevations = [s.get("elevation_ft") for s in samples]
    return distances, elevations


def gain_between(profile: tuple[list[float], list[float | None]], start_mi: float, end_mi: float) -> float:
    """Confirmed ascent between two mileposts, through the same dead-banded
    counter export_elevation.py publishes its totals with. Not a fresh
    implementation: an inflated gain becomes an inflated day, which is the
    whole reason lib/elevation_gain.py is pinned to a reference table.

    The threshold is passed explicitly rather than defaulted, because that
    module makes it a required argument on purpose: the profile is in feet
    and the dead band is defined in metres, and a caller that forgets which
    is which gets a number that looks plausible and is not."""
    distances, elevations = profile
    window = [e for d, e in zip(distances, elevations) if start_mi <= d <= end_mi]
    return cumulative_gain_over_gaps(window, DEFAULT_THRESHOLD_FT)


def naismith_minutes(distance_mi: float, ascent_ft: float) -> float:
    """Distance plus ascent as one number, so a day in the Whites and a day
    in Virginia can be compared. Unrounded - the five-minute rounding in
    naismith.ts is a display rule, and rounding inside a cost function would
    flatten differences the planner is trying to see."""
    walking = (distance_mi * KM_PER_MILE / NAISMITH_KM_PER_HOUR) * 60
    climbing = (ascent_ft * METERS_PER_FOOT / METERS_PER_ASCENT_HOUR) * 60
    return walking + climbing


def _print_row(label: str, summary: dict) -> None:
    if not summary.get("days"):
        print(f"  {label:<28} no plan")
        return
    print(
        f"  {label:<28} {summary['days']:>4} days   "
        f"mean {summary['mean_mi']:>5.1f} mi   "
        f"median {summary['median_mi']:>5.1f}   "
        f"range {summary['shortest_mi']:>4.1f}-{summary['longest_mi']:<5.1f}   "
        f"within 20% {summary['within_20pct']:>5.0%}   "
        f"over cap {summary['over_cap']:>2}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--targets", default=",".join(str(t) for t in DEFAULT_TARGETS_MI), help="Target miles per day, comma separated."
    )
    parser.add_argument("--cap", type=float, default=DEFAULT_CAP_MI, help="Longest day the planner may schedule, in miles.")
    args = parser.parse_args()

    targets = [float(t) for t in args.targets.split(",")]

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    print(f"Reading {CENTERLINE_PATH.name} and ordering it south to north...")
    parts = ordered_oriented_parts(load_merged_trail_line(con, CENTERLINE_PATH))
    parts_meters = reproject_lines_to_meters(con, parts)
    trail_miles = sum(part.length for part in parts_meters) / METERS_PER_MILE
    print(f"  {len(parts)} connected pieces, {trail_miles:,.1f} miles end to end.\n")

    stops: list[Stop] = []
    for kind, layer in STOP_LAYERS:
        path = ROOT / "data" / "raw" / f"{layer}.geojson"
        located = locate_stops(parts_meters, read_points(con, path, kind), kind)
        near = [s for s in located if s.off_trail_mi <= MAX_OFF_TRAIL_MI]
        print(f"  {layer:<12} {len(located):>4} features, {len(near):>4} within {MAX_OFF_TRAIL_MI} mi of the centerline")
        stops.extend(near)

    stops.sort(key=lambda s: s.mile)
    shelters = [s for s in stops if s.kind == "shelter"]

    print("\nSpacing of designated stops along the trail")
    for label, group in (("shelters only", shelters), ("shelters + campsites", stops)):
        summary = spacing_summary([s.mile for s in group])
        print(
            f"  {label:<22} {summary['count']:>4} stops   "
            f"mean {summary['mean_mi']:>5.1f} mi   median {summary['median_mi']:>5.1f}   "
            f"p90 {summary['p90_mi']:>5.1f}   max {summary['max_mi']:>5.1f}"
        )

    print("\nGenerated plans, whole trail, by DISTANCE target")
    for target in targets:
        print(f"\n target {target:.0f} mi/day, cap {args.cap:.0f} mi")
        for label, group in (("shelters only", shelters), ("shelters + campsites", stops)):
            days = plan_days([s.mile for s in group], target, cap_mi=args.cap)
            _print_row(label, day_summary(days, target, args.cap))

    profile = load_profile(PROFILE_PATH)
    if profile is None:
        print(f"\nNo {PROFILE_PATH.name} in this checkout - skipping the time-target comparison.")
        print("Run export_elevation.py to include it; it is what makes Finding 4 measurable.")
        return

    print("\nGenerated plans, whole trail, by TIME target (Naismith walking hours)")
    for hours in (6.0, 7.0, 8.0):
        target_minutes = hours * 60
        days = plan_days(
            [s.mile for s in stops],
            target_minutes,
            cap_mi=args.cap,
            effort=lambda a, b: naismith_minutes(b - a, gain_between(profile, a, b)),
        )
        summary = day_summary(days, statistics.fmean([d.length_mi for d in days]) if days else 0.0, args.cap)
        print(f"\n target {hours:.0f}h/day of walking")
        _print_row("shelters + campsites", summary)


if __name__ == "__main__":
    main()
