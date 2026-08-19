"""The census #749 asked for before a reachability threshold was written (#749).

#749 settles the NUMBER - 100 ft to the nearest of the centerline, any side
trail, or any shelter or campsite, the maintainer's decision of 2026-08-17 -
and is explicit that **what it costs is not settled**, that the census must be
run before the gate ships, and that the distribution belongs on the issue.
This is that census. It answers the three `@unvalidated` bullets under the
issue's "What still needs measuring".

WHY THIS IMPORTS THE GATE RATHER THAN REIMPLEMENTING IT

`build_osm_water_reach.py` is the gate `export_poi.py` reads. If this spike
measured the gate with its own copy of the geometry, the census could agree
with a gate that no longer exists - which is the failure mode the whole "run
the census first" instruction is trying to avoid. So this reads that module's
own verdict file, or calls its own measurement when the file is not built yet,
and adds only what a census adds: the distribution.

WHAT A DISTRIBUTION ADDS THAT A PASS RATE DOES NOT

The issue's third open question is whether the density that reads as clutter
was ever the far-away points at all - "it is possible much of it sits near town
approaches, close to the trail and genuinely useful". A gate that removes 1,430
pins is only good news if those 1,430 were pins a hiker could not reach, and
only the bands can say. They also price the alternative: the count in each band
is what moving the gate to 250 ft or 0.2 mi would buy or cost, without re-running
anything.

## Results, measured 2026-08-18

Against the live ATC layers and a same-day OSM scan (7,593 point-source nodes
across the fourteen states, against 7,574 on 2026-08-13):

    1,576 OSM water points inside the 30-mile corridor
      146 (9.3%) clear the 100 ft union gate
    1,159 (73.5%) sit further than five miles from anything a hiker walks

**The clutter was the far-away points.** Only 232 of the 1,576 are within
0.2 mi of the trail, a side trail, a shelter or a campsite at all; the gate
keeps 146 of those 232. So of the 1,430 points it removes, 1,344 are further
than a fifth of a mile from anywhere a hiker walks, and the contested deletions
are the 86 in between - 55 of which are springs.

Two figures worth carrying into any argument about the radius:

  - **Springs are 121 of the 146 survivors** and 23% of corridor springs pass,
    against 2.4% of `drinking_water` points. The gate is doing what it was
    meant to: town taps go, mapped springs near the trail stay.
  - **`spike_guide_water_check.py` measured (2026-08-14) that springs are the
    structural gap** in our water - a crossing cannot find a spring by
    construction, and OSM's points are the only reason spring coverage against
    a commercial guide reaches 37%. This gate takes near-trail springs from 176
    to 121, so the cost lands squarely on the class with the least redundancy.

**@unvalidated** - whether those 55 springs are water a guidebook actually
lists. `spike_guide_water_check.py` is the instrument and needs the
maintainer's own copy of The A.T. Guide, which lives on one machine (see that
file's copyright section). Running it against this gate's rejects is the check
that would settle it, and until somebody does, "the gate deletes 55 springs" is
a count of OSM nodes rather than a count of water.

Run:  python spike_osm_water_gate.py
"""

from __future__ import annotations

import json
import sys

import duckdb

from build_osm_water_reach import (
    MATCH_RADIUS_FT,
    MATCH_RADIUS_M,
    MAX_GRADE,
    MEASURE_CEILING_M,
    OUT_PATH,
    is_reachable,
    measure_distances,
)

M_PER_MILE = 1609.344
M_PER_FT = 0.3048

# The bands the distribution is reported in, as (label, upper bound in metres).
#
# The gate's own radius is a band EDGE rather than a number falling inside one -
# otherwise the table cannot price a move to a different radius. The sub-gate
# bands exist because of the issue's third question: if most of the corridor's
# water turned out to sit within 30 m of something, the far points were never
# the clutter and the gate is not the lever. (They do not, and it is.)
BANDS = [
    ("<= 25 ft", 25 * M_PER_FT),
    ("25-50 ft", 50 * M_PER_FT),
    ("50-100 ft", MATCH_RADIUS_M),
    ("100-250 ft", 250 * M_PER_FT),
    ("250-500 ft", 500 * M_PER_FT),
    ("500 ft - 0.25 mi", 0.25 * M_PER_MILE),
    ("0.25-0.5 mi", 0.5 * M_PER_MILE),
    ("0.5-1 mi", 1.0 * M_PER_MILE),
    ("1-5 mi", MEASURE_CEILING_M),
    ("> 5 mi", float("inf")),
]

# The tolerance spike_guide_water_check.py compares at (+/- 0.2 mi along the
# trail). Used here as "near enough that a guidebook could plausibly be talking
# about this point", which is what makes the 100 ft - 0.2 mi band the contested
# one rather than merely the next one out.
GUIDE_FRAME_M = 0.2 * M_PER_MILE


def band_of(distance_m: float | None) -> str:
    if distance_m is None:
        return "> 5 mi"
    for label, upper in BANDS:
        if distance_m <= upper:
            return label
    return "> 5 mi"


def load_records() -> list[dict]:
    """The gate's own verdicts, built if they are not on disk yet.

    Distance only when it has to build them: the grade half costs two EPQS
    round trips per survivor, and every figure this census reports is a
    distance figure. `build_osm_water_reach.py` is where the grade gate is run
    for real.
    """
    if OUT_PATH.exists():
        payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        print(f"reading {OUT_PATH.name} ({payload['n_corridor']} corridor points)")
        return payload["points"]
    print(f"{OUT_PATH.name} not built - measuring distances directly.")
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    return measure_distances(con)


def report(records: list[dict]) -> None:
    n = len(records)
    print(f"\n{'=' * 74}\nOSM water in the corridor, against #749's union gate (n={n})\n{'=' * 74}")
    print(f"Gate: nearest of centerline / side trail / shelter / campsite <= {MATCH_RADIUS_FT:.0f} ft ({MATCH_RADIUS_M:.1f} m)")

    print("\nDistance to the nearest of the three, by band:")
    print(f"  {'band':<18} {'points':>7} {'share':>7} {'cumulative':>11}")
    cumulative = 0
    for label, _ in BANDS:
        count = sum(1 for r in records if band_of(r["nearest_m"]) == label)
        cumulative += count
        print(f"  {label:<18} {count:>7} {100 * count / n:>6.1f}% {100 * cumulative / n:>10.1f}%")

    passed = [r for r in records if r["passes_distance"]]
    print(f"\nDistance gate: {len(passed)}/{n} pass ({100 * len(passed) / n:.1f}%), {n - len(passed)} removed.")

    print("\nWhich of the three the survivors passed on:")
    for label in ("centerline", "side_trail", "shelter", "campsite"):
        count = sum(1 for r in passed if r["nearest"] == label)
        if count:
            print(f"  {label:<18} {count:>7} {100 * count / len(passed):>6.1f}%")

    print("\nBy OSM class (pass / corridor total):")
    for kind in sorted({r["kind"] for r in records}):
        rows = [r for r in records if r["kind"] == kind]
        keep = sum(1 for r in rows if r["passes_distance"])
        print(f"  {kind:<18} {keep:>5} / {len(rows):<5} {100 * keep / len(rows):>6.1f}%")

    # The question the pass rate cannot answer: of the points near enough that
    # anybody would argue about them, how many does the gate take?
    frame = [r for r in records if r["nearest_m"] is not None and r["nearest_m"] <= GUIDE_FRAME_M]
    kept = [r for r in frame if r["passes_distance"]]
    print(f"\nInside {GUIDE_FRAME_M / M_PER_MILE:.1f} mi - the frame a guidebook comparison works in:")
    print(f"  {len(frame)} points, of which the gate keeps {len(kept)} ({100 * len(kept) / len(frame):.0f}%).")
    print(f"  So {n - len(frame)} of the {n - len(kept)} removals are past {GUIDE_FRAME_M / M_PER_MILE:.1f} mi,")
    print(f"  and the contested deletions are the {len(frame) - len(kept)} in between:")
    for kind in sorted({r["kind"] for r in frame}):
        rows = [r for r in frame if r["kind"] == kind]
        lost = sum(1 for r in rows if not r["passes_distance"])
        print(f"    {kind:<18} {lost:>4} lost of {len(rows):<4} near-trail")

    graded = [r for r in passed if "passes_grade" in r]
    if graded:
        steep = [r for r in graded if not r["passes_grade"]]
        reachable = [r for r in records if is_reachable(r)]
        print(f"\nGrade gate (<= {MAX_GRADE:.0%}), on the {len(graded)} distance-survivors graded so far:")
        print(f"  {len(steep)} removed as too steep ({100 * len(steep) / len(graded):.1f}%).")
        print(f"\nBOTH GATES: {len(reachable)} of {n} corridor water points reachable ({100 * len(reachable) / n:.1f}%).")
    else:
        print("\nGrade gate not run - see build_osm_water_reach.py. The figures above are an UPPER BOUND on survivors.")


def main() -> int:
    report(load_records())
    return 0


if __name__ == "__main__":
    sys.exit(main())
