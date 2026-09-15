"""Do New York City's two registered layers draw the same tread twice? (#1453)

#1432 registered both of the city's walking-path layers and left this open,
as NYC_SOURCE_SURVEY.md §12e(a): 2,095 of the current greenway segments carry
`gwyjuris: DPR` - NYC Parks' own ground, which the trails layer also covers -
and nobody had measured whether the same path is drawn from both.

Every other row of §8's one-ground-many-sources table is two DIFFERENT
organizations sharing ground: OPRHP and NYNJTC over Harriman, DEC and NYNJTC
over the Catskills. New York City is the first case of ONE CITY'S TWO
AGENCIES cataloguing the same path, and its jurisdiction column says which
is which rather than leaving it to geometry - so unlike every other pair,
this one can be measured against a control.

THIS IS A SPIKE. The measurement is the deliverable; the assembly below is
throwaway. The pure halves are kept honest by tests/test_spike_nyc_overlap.py,
and the measurement half runs against real fetched data:

  - data/raw/external/nyc_parks_trails.geojson
  - data/raw/external/nyc_dot_greenways.geojson

both written by fetch_external_layers.py. Run it with no arguments after a
fetch, or point --raw at a directory holding the two files.

WHAT IT MEASURES, AND WHY A BUFFER RATHER THAN AN INTERSECTION. The two
agencies digitised the same path independently, so their lines never share a
vertex and rarely cross; "the same tread" is a question about proximity, not
topology. Each greenway segment's length is walked, and the part of it whose
BOTH endpoints lie within `radius` of any NYC Parks trail vertex counts as
overlapping. Two radii are reported because the answer should not rest on one
arbitrary number: 10 m is roughly a path's own width plus survey error, 25 m
is generous enough to absorb a boulevard's two sides being digitised apart.

THE CONTROL IS THE POINT. A dense city will put SOMETHING near everything, so
an overlap figure alone proves nothing. The same measurement is run over the
greenway segments whose jurisdiction is NOT DPR - DOT's own, plus NYSDOT, NPS,
RIOC, MTA and the rest - which share the city's density and none of its
land-management overlap. If the DPR figure is not far above that floor, there
is no finding here.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw" / "external"

PARKS_KEY = "nyc_parks_trails"
GREENWAY_KEY = "nyc_dot_greenways"

#: The jurisdiction that makes a greenway segment NYC Parks' ground as well as
#: DOT's. Read off the layer's own `gwyjuris` column rather than inferred from
#: geometry, which is what makes the control below possible.
PARKS_JURISDICTION = "DPR"

#: Reported at both, because one radius would be a number somebody picked.
#: 10 m is about a path's own width plus the survey error of two independent
#: digitisations; 25 m absorbs a divided road whose sides were captured apart.
#: Neither is validated against anything on the ground - @unvalidated, and
#: what would settle it is standing on one of the overlapping stretches.
RADII_M = (10.0, 25.0)

#: Metres per degree at New York City's latitude. A local flat approximation,
#: which over a city is worth a great deal of speed and costs nothing that
#: matters at these distances: the error across the five boroughs' ~0.4° of
#: latitude is under 0.3%, against a 10 m radius.
_LAT = 40.75
_M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(_LAT))
_M_PER_DEG_LAT = 110_570.0

#: Grid cell for the nearest-vertex index, in metres. Big enough that the
#: 25 m search reads 9 cells rather than 25, small enough that a cell over
#: Central Park does not hold thousands of points.
_CELL_M = 50.0

METRES_PER_MILE = 1609.344


def segments(feature: dict) -> list[tuple[list, list]]:
    """One feature's vertex pairs, for a LineString or a MultiLineString.

    A feature with no geometry, or with an empty coordinate list, yields
    nothing rather than raising - nine of the greenway rows are exactly that
    (sources.json's `nyc_dot_greenways` notes carries the count), and a spike
    that fell over on them would be measuring its own fragility.
    """
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    lines = coordinates if geometry.get("type") == "MultiLineString" else ([coordinates] if coordinates else [])
    pairs: list[tuple[list, list]] = []
    for line in lines:
        pairs.extend(zip(line, line[1:]))
    return pairs


def metres_between(a, b) -> float:
    """Planar distance in metres between two lon/lat points. See _LAT."""
    return math.hypot((b[0] - a[0]) * _M_PER_DEG_LON, (b[1] - a[1]) * _M_PER_DEG_LAT)


def build_vertex_index(features: list[dict], cell_m: float = _CELL_M) -> dict:
    """Every vertex of `features`, bucketed into a coarse metric grid.

    Indexing VERTICES rather than segments is the spike's one real
    approximation, and it is the conservative direction: a long straight
    segment with distant endpoints can pass within the radius midway and not
    be seen. NYC Parks' lines are densely digitised (101,340 vertices over
    7,059 segments, so ~14 per segment), which is why it is tolerable here
    and would not be on a layer drawn in kilometre-long straights.
    """
    grid: dict[tuple[int, int], list] = collections.defaultdict(list)
    for feature in features:
        for a, b in segments(feature):
            for point in (a, b):
                grid[_cell_of(point, cell_m)].append(point)
    return grid


def _cell_of(point, cell_m: float) -> tuple[int, int]:
    return (int(point[0] * _M_PER_DEG_LON // cell_m), int(point[1] * _M_PER_DEG_LAT // cell_m))


def near_index(point, grid: dict, radius_m: float, cell_m: float = _CELL_M) -> bool:
    """Whether any indexed vertex lies within `radius_m` of `point`."""
    gx, gy = _cell_of(point, cell_m)
    reach = int(radius_m // cell_m) + 1
    for dx in range(-reach, reach + 1):
        for dy in range(-reach, reach + 1):
            for candidate in grid.get((gx + dx, gy + dy), ()):
                if metres_between(point, candidate) <= radius_m:
                    return True
    return False


def overlap_report(features: list[dict], grid: dict, radius_m: float, group_field: str | None = None) -> dict:
    """How much of `features`' length lies within `radius_m` of the index.

    A segment's piece counts as overlapping only when BOTH its endpoints are
    near the index, which is the conservative reading: a path that merely
    crosses a trail contributes nothing, where one running alongside it
    contributes its whole length.
    """
    total_m = shared_m = 0.0
    mostly_shared = 0
    by_group: dict[str, list[float]] = collections.defaultdict(lambda: [0.0, 0.0])

    for feature in features:
        group = (feature.get("properties") or {}).get(group_field) or "(none)" if group_field else "(all)"
        feature_m = feature_shared_m = 0.0
        for a, b in segments(feature):
            length = metres_between(a, b)
            feature_m += length
            if near_index(a, grid, radius_m) and near_index(b, grid, radius_m):
                feature_shared_m += length
        total_m += feature_m
        shared_m += feature_shared_m
        by_group[group][0] += feature_m
        by_group[group][1] += feature_shared_m
        if feature_m > 0 and feature_shared_m / feature_m >= 0.5:
            mostly_shared += 1

    return {
        "radius_m": radius_m,
        "features": len(features),
        "total_mi": total_m / METRES_PER_MILE,
        "shared_mi": shared_m / METRES_PER_MILE,
        "shared_fraction": (shared_m / total_m) if total_m else 0.0,
        "mostly_shared_features": mostly_shared,
        "by_group": {g: {"total_mi": t / METRES_PER_MILE, "shared_mi": s / METRES_PER_MILE} for g, (t, s) in by_group.items()},
    }


def _load(raw_dir: Path, key: str) -> list[dict]:
    path = raw_dir / f"{key}.geojson"
    if not path.exists():
        raise SystemExit(f"{path} is missing - run fetch_external_layers.py first, or pass --raw at a directory holding it.")
    return json.loads(path.read_text())["features"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_DIR, help="directory holding the two fetched layers")
    args = parser.parse_args()

    parks = _load(args.raw, PARKS_KEY)
    greenways = _load(args.raw, GREENWAY_KEY)

    on_parks_land = [f for f in greenways if (f.get("properties") or {}).get("gwyjuris") == PARKS_JURISDICTION]
    elsewhere = [f for f in greenways if (f.get("properties") or {}).get("gwyjuris") != PARKS_JURISDICTION]

    print(f"{PARKS_KEY}: {len(parks):,} segments")
    print(f"{GREENWAY_KEY}: {len(greenways):,} segments - {len(on_parks_land):,} on NYC Parks land, {len(elsewhere):,} elsewhere")

    grid = build_vertex_index(parks)
    print(f"indexed {sum(len(v) for v in grid.values()):,} NYC Parks vertices into {len(grid):,} cells\n")

    for radius in RADII_M:
        subject = overlap_report(on_parks_land, grid, radius, group_field="gwsystem")
        control = overlap_report(elsewhere, grid, radius)
        print(f"--- {radius:.0f} m ---")
        print(
            f"  gwyjuris=DPR : {subject['shared_mi']:6.1f} of {subject['total_mi']:6.1f} mi "
            f"({subject['shared_fraction'] * 100:5.1f}%), {subject['mostly_shared_features']:,} of "
            f"{subject['features']:,} segments at least half covered"
        )
        print(
            f"  CONTROL      : {control['shared_mi']:6.1f} of {control['total_mi']:6.1f} mi "
            f"({control['shared_fraction'] * 100:5.1f}%), {control['mostly_shared_features']:,} of "
            f"{control['features']:,} segments"
        )
        ratio = (subject["shared_fraction"] / control["shared_fraction"]) if control["shared_fraction"] else float("inf")
        print(f"  subject is {ratio:.0f}x the control\n")

    widest = overlap_report(on_parks_land, grid, RADII_M[-1], group_field="gwsystem")
    print(f"by greenway system at {RADII_M[-1]:.0f} m, where at least a fifth of a mile overlaps:")
    for name, figures in sorted(widest["by_group"].items(), key=lambda kv: -kv[1]["shared_mi"]):
        if figures["shared_mi"] < 0.2:
            continue
        share = figures["shared_mi"] / figures["total_mi"] * 100 if figures["total_mi"] else 0.0
        print(f"  {figures['shared_mi']:5.1f} of {figures['total_mi']:5.1f} mi ({share:5.1f}%)  {name}")


if __name__ == "__main__":
    main()
