"""Where a point sits on a club's own trail: the section, the mile, and the distance off the line.

#1987 — The server computes an observation's mile and distance to the line
from the club's own section geometry, and stores both beside the raw point.

The structure inventory's rule 2 is that the phone records what it knows and
nothing it assumes, so a survey record arrives as a point and its readings,
never as a mile (features/STRUCTURE_INVENTORY.md, conflict 1). This module is
the server's half: it projects a point onto the lines a club has drawn for its
own sections, `org_sections.geometry`, and reads the mile off the section's
`start_mile` and `end_mile`. Pure Python and no PostGIS, because nothing else
in this backend does spatial maths (`app/models/org_registry.py` says why).

**A CLUB THAT HAS DRAWN NO SECTION GETS NO MILE.** The handoff proposed falling
back to the published `trails.geojson` and `trail_miles.json`. That file's
centerline is the A.T. alone, and the registry has no field that says which of
a club's trails is the A.T., so a structure on the Long Path two miles from the
A.T. would have been given an A.T. mile - confidently, and wrong. The maintainer
chose by poll on 2026-11-04 to leave the mile blank instead; the fallback is a
follow-up that starts with that missing field. Absent is "nobody knows", never
zero.

**THE MILE IS INTERPOLATED BY DRAWN LENGTH,** from `start_mile` at the line's
first coordinate to `end_mile` at its last. Two things follow, and both are in
the test file's numbers:

- It is not the phone's mile. `client/src/lib/trailPosition.ts`'s
  `locateOnTrail` reads the published mile of the nearest centerline vertex,
  on the pipeline's calibrated axis, which stretches and shrinks between
  markers where a straight interpolation cannot. `tests/test_trail_axis.py`
  holds the two to 0.05 mi on `client/src/lib/trailAxis.golden.json`, whose
  calibration runs 3% long then 2% short; the largest disagreement there is
  0.017 mi, measured 2026-11-04 on that synthetic line. **The 0.05 is
  @unvalidated** - the handoff's pick. What settles it: one real section's
  drawn line and the largest disagreement between the two along it.
- **A line drawn end to start reads its miles backwards** - mirrored inside the
  section, so wrong by up to the section's own length while looking plausible.
  Nothing on the row says which way a line was drawn: the console takes it as
  pasted text (`add_section` in `app/routers/org_registry.py`). @unvalidated:
  every drawn section is assumed to run from its start anchor to its end
  anchor. What settles it: each club's drawn sections checked against the
  published axis, which nobody has done.

**Where it runs.** Accept is meant to call `place_observation` and
`place_structure` as it accepts a record; that endpoint is #1989 — The club's
chain reviews: accept, send back, merge, not ours, each with a note and an
audit column, and a section supervisor sees only their sections, not built
yet. `scripts/inventory_place.py` runs it by hand, for records accepted
before their club drew its sections.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.inventory import InventoryObservation, InventoryStructure
from app.models.org_registry import OrgPark, OrgSection, OrgTrail

FEET_PER_MILE = 5280
# client/src/lib/trailPosition.ts's EARTH_RADIUS_FT, so the two measure a foot
# the same way.
EARTH_RADIUS_FT = 20_902_231

#: Farthest a point can be from every drawn section and still be placed.
#:
#: Reasoned, not measured: it is `MAX_OFF_TRAIL_MILES` in
#: `client/src/lib/trailPosition.ts`, the phone's own line between "a mile that
#: means something" and "we don't know where you are on the trail". The phone
#: needs exactly three miles to fit its cell search; this has no cells, and
#: takes the same number so that the server and the phone refuse the same
#: points. A structure three miles from its club's every line is not on that
#: club's trail in any sense a mile could describe.
MAX_OFF_LINE_FT = 3 * FEET_PER_MILE

#: Decimals a mile is stored to: `TRAIL_MILE_DECIMALS` in
#: pipeline/export_trails.py, the axis the miles come from. Finer than that
#: would claim more than the section's own `start_mile` carries.
MILE_DECIMALS = 3


@dataclass(frozen=True)
class Placement:
    section_id: str
    #: None when the section's line is drawn but its `start_mile` or
    #: `end_mile` is not set: the point is placed in the section and its
    #: distance off the line is known, but there is no axis to read a mile on.
    mile: float | None
    off_line_ft: float


def _finite_point(value: object) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    lon, lat = value[0], value[1]
    if isinstance(lon, bool) or isinstance(lat, bool):
        return None
    if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
        return None
    if not (math.isfinite(lon) and math.isfinite(lat)):
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return float(lon), float(lat)


def section_line(geometry: str | None) -> list[tuple[float, float]] | None:
    """The `(lon, lat)` vertices of a section's drawn line, or None.

    A GeoJSON LineString, bare or as a Feature's geometry; a third coordinate
    is ignored. None for anything else - unparseable text, another type, one
    vertex, a coordinate out of range, a line of no length. A MultiLineString
    is refused too: which of its parts comes first along the trail is not
    written anywhere, so a mile interpolated across it would be a guess.
    """
    if not geometry:
        return None
    try:
        parsed = json.loads(geometry)
    except (TypeError, ValueError):
        return None
    if isinstance(parsed, dict) and parsed.get("type") == "Feature":
        parsed = parsed.get("geometry")
    if not isinstance(parsed, dict) or parsed.get("type") != "LineString":
        return None
    raw = parsed.get("coordinates")
    if not isinstance(raw, list):
        return None
    line = [_finite_point(vertex) for vertex in raw]
    if len(line) < 2 or any(vertex is None for vertex in line):
        return None
    if all(vertex == line[0] for vertex in line):
        return None
    return line  # type: ignore[return-value]


def haversine_ft(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle feet between two `(lon, lat)` points, as the phone measures it."""
    to_rad = math.pi / 180
    d_lat = (b[1] - a[1]) * to_rad
    d_lon = (b[0] - a[0]) * to_rad
    h = math.sin(d_lat / 2) ** 2 + math.cos(a[1] * to_rad) * math.cos(b[1] * to_rad) * math.sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_FT * math.asin(min(1.0, math.sqrt(h)))


def project_onto_line(line: Sequence[tuple[float, float]], lon: float, lat: float) -> tuple[float, float]:
    """`(fraction of the line's length before the nearest point, feet to it)`.

    The nearest point on each segment is found in a flat plane centred on the
    point being placed, which is exact enough over the few miles a section
    spans and is only used to choose where along the segment to stop. Both
    numbers returned are great-circle: the distance to that spot, and the
    length walked to reach it, summed segment by segment the way the phone
    sums its own miles.
    """
    feet_per_degree_lat = EARTH_RADIUS_FT * math.pi / 180
    feet_per_degree_lon = feet_per_degree_lat * math.cos(lat * math.pi / 180)

    walked = 0.0
    best_feet = math.inf
    best_along = 0.0
    for a, b in zip(line, line[1:]):
        ax, ay = (a[0] - lon) * feet_per_degree_lon, (a[1] - lat) * feet_per_degree_lat
        dx, dy = (b[0] - a[0]) * feet_per_degree_lon, (b[1] - a[1]) * feet_per_degree_lat
        length_squared = dx * dx + dy * dy
        t = 0.0 if length_squared == 0 else min(1.0, max(0.0, -(ax * dx + ay * dy) / length_squared))
        foot = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        segment_feet = haversine_ft(a, b)
        feet = haversine_ft((lon, lat), foot)
        if feet < best_feet:
            best_feet = feet
            best_along = walked + segment_feet * t
        walked += segment_feet
    return best_along / walked, best_feet


def _mile(section: OrgSection, fraction: float) -> float | None:
    if section.start_mile is None or section.end_mile is None:
        return None
    return round(section.start_mile + (section.end_mile - section.start_mile) * fraction, MILE_DECIMALS)


def place(db: Session, club_id: str, lat: float, lon: float) -> Placement | None:
    """The club's drawn section nearest the point, the mile on it, and how far off it is.

    None when the club has drawn no section this module can read, or when
    the point is farther than `MAX_OFF_LINE_FT` from every one it has. Only
    this club's sections are searched: a point is never placed on another
    club's trail, however close it is.
    """
    sections = (
        db.query(OrgSection)
        .join(OrgTrail, OrgSection.trail_id == OrgTrail.id)
        .join(OrgPark, OrgTrail.park_id == OrgPark.id)
        .filter(OrgPark.club_id == club_id, OrgSection.geometry.is_not(None))
        .all()
    )
    best: tuple[float, str, OrgSection, float] | None = None
    for section in sections:
        line = section_line(section.geometry)
        if line is None:
            continue
        fraction, feet = project_onto_line(line, lon, lat)
        # The id breaks a tie, so two sections meeting at a shared vertex
        # place a point there the same way on every run.
        candidate = (feet, section.id, section, fraction)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None or best[0] > MAX_OFF_LINE_FT:
        return None
    feet, _, section, fraction = best
    return Placement(section_id=section.id, mile=_mile(section, fraction), off_line_ft=round(feet))


def place_observation(db: Session, observation: InventoryObservation) -> Placement | None:
    """Fills an observation's `mile` and `off_line_ft` from its own point.

    The point itself is never touched: the mile is stored beside it, so a
    section redrawn later can be placed against again from what the phone
    recorded. Leaves both columns as they were when the point cannot be
    placed.
    """
    placement = place(db, observation.club_id, observation.lat, observation.lon)
    if placement is not None:
        observation.mile = placement.mile
        observation.off_line_ft = placement.off_line_ft
    return placement


def place_structure(db: Session, structure: InventoryStructure) -> Placement | None:
    """Fills a structure's `section_id`, `mile` and `off_line_ft` from its current point.

    A structure's point moves to its latest accepted observation's on each
    accept, so this runs after that move. A structure that cannot be placed
    keeps the section it had: losing a placement because a line was deleted
    is not evidence the structure moved.
    """
    placement = place(db, structure.club_id, structure.lat, structure.lon)
    if placement is not None:
        structure.section_id = placement.section_id
        structure.mile = placement.mile
        structure.off_line_ft = placement.off_line_ft
    return placement
