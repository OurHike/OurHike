"""Turning the curated highlight list into publishable records (#595).

A highlight is a stretch of trail somebody says is worth going to.
features/CORRIDOR_VIEW.md carries the argument; the short version is that
"popular" is three questions with completely different evidence behind them,
so a highlight names its BASIS and the app never says "popular" flatly.

WHAT THIS MODULE DOES AND DOES NOT DECIDE

It decides nothing editorial. reference/highlights.json is the judgement -
which stretches, and why - reviewed row by row, which is what earns it a place
in a committed reference file. This module only resolves that judgement against
data: two POI ids become two miles, two miles become a leg, and a leg lands in
some club's section.

WHY A LEG AND NOT A MILE RANGE

The maintainer's decision, 2026-08-19: a Highlight is its own entity and may
cross trails. A mile only means something relative to ONE trail -
features/NEARBY_TRAILS.md settled on 2026-08-18 that the map's subject is one
chosen trail at a time and that switching trails swaps the mile frame - so the
range moves down a level, into an ordered list of legs each carrying its own
trail. Every entry on the list today has one leg on the A.T.; the shape is what
lets the first cross-trail loop be added without a migration.

The word `stretch` is deliberately not used for this. It belongs to the ~50-mile
offline download unit cut_stretches.py cuts (#552, decided 2026-08-18).

WHY THE MILES COME FROM THE PUBLISHED POIs

Same reason export_spurs.py resolves a spur's destination against published
records rather than raw ATC points: the ids have to be the ones already on the
device. It also keeps a guidebook figure typed into a JSON file from becoming a
number the app presents as measurement - the mile range is ATC's own, arrived at
by the same `attach_miles` projection every published POI uses.

AN UNRESOLVABLE HIGHLIGHT IS DROPPED, LOUDLY

If either anchor is missing from the published POIs, or carries no mile, the
highlight does not publish. It is not published with one end guessed, and it is
not published with a range somebody typed. A dropped entry is a line on stderr
and a non-zero count in the exporter's summary, because a curated list quietly
shrinking is exactly the failure nobody notices.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The only basis this module can produce. `published` cites ATC's own day-hike
#: material and waits on that source being registered (features/SOURCE_REGISTRY
#: .md); `visited` is a count across hikers and is #596's, and now also needs an
#: explicit decision about features/EVENTING.md rule 2 - see CORRIDOR_VIEW.md's
#: own note. Neither is produced here, and neither is faked.
NAMED_BASIS = "named"

#: What a leg's `trail` must say to mean the A.T. - export_poi.py's TRAIL_ID,
#: which is what every published POI carries. Restated rather than imported so
#: this module stays free of the exporter; test_lib_highlights.py pins the two
#: to each other.
AT_TRAIL_ID = "AT"


@dataclass(frozen=True)
class Leg:
    """One trail's share of a highlight, in that trail's own miles."""

    trail: str
    start_mile: float
    end_mile: float

    @property
    def miles(self) -> float:
        return self.end_mile - self.start_mile


@dataclass(frozen=True)
class Highlight:
    id: str
    name: str
    legs: tuple[Leg, ...]
    note: str
    reviewed: str
    #: The maintaining club the first leg begins in, derived rather than
    #: written down - so "one per club" is a fact the exporter can check
    #: instead of a claim the reference file makes about itself. None where
    #: the club sections do not cover it, which is the 38.5 unattributed miles.
    club: str | None = None

    @property
    def miles(self) -> float:
        return sum(leg.miles for leg in self.legs)


@dataclass
class Resolution:
    """What one run produced, including what it refused to produce."""

    highlights: list[Highlight] = field(default_factory=list)
    #: (highlight id, why) for everything dropped. Never silent.
    dropped: list[tuple[str, str]] = field(default_factory=list)


def poi_miles(published_pois: list[dict]) -> dict[str, float]:
    """`{poi id: mile}` for every published POI that has one.

    A POI with no mile is absent rather than zero. `attach_miles` leaves the
    field None where a point could not be projected onto the ordered
    centerline, and mile 0.0 is Springer Mountain - a real place a highlight
    could legitimately start.
    """
    miles: dict[str, float] = {}
    for poi in published_pois:
        poi_id = poi.get("id")
        mile = poi.get("mile")
        if isinstance(poi_id, str) and isinstance(mile, (int, float)):
            miles[poi_id] = float(mile)
    return miles


def _leg_from(entry: dict, miles: dict[str, float]) -> tuple[Leg | None, str]:
    """One leg, or (None, why not)."""
    trail = entry.get("trail")
    if not isinstance(trail, str) or trail == "":
        return None, "a leg names no trail"

    from_poi, to_poi = entry.get("from_poi"), entry.get("to_poi")
    for label, poi_id in (("from_poi", from_poi), ("to_poi", to_poi)):
        if not isinstance(poi_id, str) or poi_id == "":
            return None, f"a leg names no {label}"
        if poi_id not in miles:
            # Either the POI is gone from the published set, or it published
            # without a mile. Both mean the same thing here: this end of the
            # walk cannot be placed, and placing it anyway would be inventing
            # the number the whole file exists to avoid inventing.
            return None, f"{label} {poi_id} has no published mile"

    low, high = sorted((miles[from_poi], miles[to_poi]))
    if high == low:
        return None, "both ends resolve to the same mile"
    return Leg(trail=trail, start_mile=low, end_mile=high), ""


def club_for_mile(club_runs: list[dict], mile: float) -> str | None:
    """Which club's section a mile falls in, or None.

    Reads `club_sections.json`'s own shape: a list of clubs, each with the
    `stretches` key that artifact publishes. Half-open like the client's
    lookup (client/src/lib/clubSections.ts), so a mile two clubs share
    resolves northbound and never to both.
    """
    for club in club_runs:
        acronym = club.get("acronym")
        for run in club.get("stretches") or []:
            start, end = run.get("start_mile"), run.get("end_mile")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                continue
            if start <= mile < end:
                return acronym if isinstance(acronym, str) else None
    return None


def resolve(
    curated: list[dict],
    published_pois: list[dict],
    club_runs: list[dict] | None = None,
) -> Resolution:
    """The curated list, resolved against published data.

    Order is the reference file's, not mile order: the file is a thing a human
    maintains, and a diff that reshuffles when a mile changes upstream is a
    diff nobody can read.
    """
    miles = poi_miles(published_pois)
    clubs = club_runs or []
    out = Resolution()
    seen: set[str] = set()

    for entry in curated:
        highlight_id = entry.get("id")
        if not isinstance(highlight_id, str) or highlight_id == "":
            out.dropped.append(("<no id>", "entry has no id"))
            continue
        if highlight_id in seen:
            # Two rows claiming one id is an editing accident, and the second
            # would silently win a dict-keyed consumer.
            out.dropped.append((highlight_id, "duplicate id"))
            continue
        seen.add(highlight_id)

        name = entry.get("name")
        if not isinstance(name, str) or name == "":
            out.dropped.append((highlight_id, "entry has no name"))
            continue

        raw_legs = entry.get("legs")
        if not isinstance(raw_legs, list) or raw_legs == []:
            out.dropped.append((highlight_id, "entry has no legs"))
            continue

        legs: list[Leg] = []
        failure = ""
        for raw in raw_legs:
            if not isinstance(raw, dict):
                failure = "a leg is not an object"
                break
            leg, why = _leg_from(raw, miles)
            if leg is None:
                failure = why
                break
            legs.append(leg)
        if failure:
            # All or nothing: half a walk drawn is a walk that ends where
            # nothing ends.
            out.dropped.append((highlight_id, failure))
            continue

        out.highlights.append(
            Highlight(
                id=highlight_id,
                name=name,
                legs=tuple(legs),
                note=entry.get("note") if isinstance(entry.get("note"), str) else "",
                reviewed=entry.get("reviewed") if isinstance(entry.get("reviewed"), str) else "",
                club=club_for_mile(clubs, legs[0].start_mile),
            )
        )

    return out


def clubs_without_a_highlight(highlights: list[Highlight], club_runs: list[dict]) -> list[str]:
    """Which maintaining clubs the list still says nothing about.

    features/CORRIDOR_VIEW.md's target is one per club, about thirty, because
    that is the unit that maps to volunteering. This is what makes the gap
    visible on every run instead of only when somebody counts - and it is
    deliberately a REPORT rather than a failure: a club with no well-known
    stretch is a fact about the trail, not a bug, and filling the list with
    entries nobody stands behind to silence a check would be worse than the
    gap.
    """
    covered = {h.club for h in highlights if h.club is not None}
    named = [club.get("acronym") for club in club_runs if isinstance(club.get("acronym"), str)]
    return sorted(acronym for acronym in named if acronym not in covered)


def as_published(highlight: Highlight) -> dict:
    """One record, in the shape the artifact publishes.

    Length, ascent and Naismith time are NOT here, deliberately: the phone
    derives them from the elevation profile it already holds (elevationGain.ts
    into naismith.ts), which keeps one number in one place and means a better
    profile improves every highlight without a republish.
    """
    return {
        "id": highlight.id,
        "name": highlight.name,
        "bases": [NAMED_BASIS],
        "citations": {
            NAMED_BASIS: {
                "by": "OurHike",
                "note": highlight.note,
                "reviewed": highlight.reviewed,
            }
        },
        "legs": [
            {
                "trail": leg.trail,
                "start_mile": round(leg.start_mile, 2),
                "end_mile": round(leg.end_mile, 2),
            }
            for leg in highlight.legs
        ],
        "club": highlight.club,
    }
