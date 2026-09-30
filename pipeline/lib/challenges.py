"""Turning a club's reviewed challenge files into publishable records (#1780).

A challenge is a list of places on one organization's trails, a date window,
an optional finish line and an optional reward. A hiker opts in, walks, and
tags the places at camp. features/CHALLENGES.md is the design; this module is
the half a test can run.

WHAT THIS MODULE DECIDES, AND WHAT IT DOES NOT

It decides nothing editorial. reference/challenges/<org>/<id>.json is the
judgement - which places, what counts as finished, what the club offers - and
it is committed so a diff reviews those decisions row by row, the argument
reference/highlights.json already makes. This module resolves that judgement
against published data and refuses whatever cannot be resolved honestly:

  - A place is named by a PUBLISHED POI id, never by a typed mile or a typed
    coordinate. The mile, the coordinate and the name a hiker reads are the
    published record's own, copied at export time - the same reason
    lib/highlights.py resolves its legs from POI ids: the ids have to be the
    ones already on the device, and a guidebook figure typed into a JSON file
    must not become a number the app presents as measurement.
  - A challenge is SCOPED TO ITS PUBLISHER (design principle 5). Its trail
    must be one the organization publishes, and every place must lie on that
    trail. The ATC's list is A.T.-only for that reason, not as a special case.
  - A place must lie within its own tag radius of the trail, or say outright
    that reaching it means leaving the trail (`off_trail`, a town or a
    visitor centre). export_poi.attach_miles gives a point in Ohio an A.T.
    mile - it has no failure mode - so a mile alone proves nothing about
    distance, and the check has to be made here.

AN UNRESOLVABLE ITEM IS DROPPED, LOUDLY; AN UNRESOLVABLE CHALLENGE IS TOO

An item whose POI is gone, off its trail, or malformed does not publish, and
the drop is a line in the exporter's report. The challenge publishes without
it - unless the finish line can no longer be reached, in which case the whole
challenge is dropped: a hiker joining a list whose "25 for the drawing" can
only ever be 24 has been handed a promise nobody can keep.

SEALED MYSTERY ITEMS

A mystery item may carry a `reveal_on` date. Exported before that date, its
title does not appear in the artifact in the clear: it ships as
`sealed_title`, base64 of the UTF-8 text, and `title` is null. The phone
decodes it on or after `reveal_on` with no network, which is what lets a
reveal "open on the phone on the day, with no signal" (the handoff's flow
board, round 3). **Base64 is a spoiler guard, not a secret** - the rot13 on
a puzzle answer - and features/CHALLENGES.md says so; anyone reading the
artifact with a decoder can read the item early, and nothing here pretends
otherwise. A mystery item with no title at all (the ATC's 2025 list announced
its three only on social media) ships sealed with no date, and a club reveals
it by republishing.
"""

from __future__ import annotations

import base64
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date

#: Every way an item can be matched. `self_report` is the only kind a tap
#: alone completes (the PDF's at-home Learn and Protect items); every other
#: kind moves only by being on trail - design principle 1, "days, not clicks".
MATCH_KINDS = (
    "place",
    "places_all",
    "poi_type",
    "elevation_min_ft",
    "section_walked",
    "workday",
    "self_report",
)

#: The kinds that name one or more fixed places. These are the items the
#: detail screen lists under "On the trail" and the only ones the map layer
#: can draw a pin for.
PLACE_KINDS = ("place", "places_all")

#: What a club may offer at the finish. Most challenges offer nothing - the
#: handoff's revision 3 - and `reward: null` is the common case, not a gap.
REWARD_KINDS = ("patch", "postcard", "sticker", "drawing")

#: `draft` publishes, labelled on every surface that names the challenge -
#: the maintainer's choice by poll, 2026-09-30, over never publishing a draft
#: or publishing drafts to the UA bucket only. `published` is a club standing
#: behind its own list.
STATUSES = ("draft", "published")

#: Tag radius, in metres from the POI, when a match does not give its own.
#: @unvalidated - these are the handoff's examples (150 m for a named place,
#: 60 m for "any shelter"), not a measurement. What would settle them: tag
#: prompts from real tracks, counting how often a hiker who stood at the place
#: was missed (radius too small) against how often one who walked past a
#: side trail's junction was asked (too large). Measured 2026-09-30 against
#: release 2026-09-24-2, for scale: the median ATC shelter sits 63 m from the
#: centerline and the 75th percentile 140 m, so 60 m around the shelter means
#: "went to it", not "walked past its side trail" - which is the intent.
DEFAULT_RADIUS_M = {"place": 150, "places_all": 150, "poi_type": 60}

#: Bounds a club's own radius is held to. Below 10 m a phone's own fix error
#: decides the answer; above 2 km a "place" is a region.
MIN_RADIUS_M = 10
MAX_RADIUS_M = 2000

#: The share of a walked section that counts as walking it, when the match
#: does not give its own. @unvalidated - the handoff's example value. A GPS
#: track has gaps (tunnels of rhododendron, a phone in a pocket), and 90%
#: forgives a gap of a tenth of the section without forgiving a skipped day.
DEFAULT_MIN_FRACTION = 0.9

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Resolution:
    """What one run produced, including what it refused to produce."""

    challenges: list[dict] = field(default_factory=list)
    #: (challenge id, why) for every whole challenge that did not publish.
    dropped: list[tuple[str, str]] = field(default_factory=list)
    #: (challenge id, item id, why) for every item that did not publish.
    dropped_items: list[tuple[str, str, str]] = field(default_factory=list)


def _date(value: object) -> date | None:
    if not isinstance(value, str) or not _DATE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def seal(title: str) -> str:
    """The spoiler guard: base64 of the UTF-8 title. Not a secret."""
    return base64.b64encode(title.encode("utf-8")).decode("ascii")


def unseal(sealed: str) -> str:
    return base64.b64decode(sealed.encode("ascii")).decode("utf-8")


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres, by haversine - the formula the
    client's lib/trailPosition.ts also uses (`haversineFeet`). Its radius is
    6,371,000 m spelled in feet; the 8.8 m between the two radii is about one
    part in 700,000, far below a phone's fix error, so a radius means one
    thing on both sides."""
    radius = 6_371_008.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def _radius(match: Mapping, kind: str) -> tuple[int | None, str]:
    raw = match.get("radius_m", DEFAULT_RADIUS_M[kind])
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None, "radius_m is not a number"
    if not MIN_RADIUS_M <= raw <= MAX_RADIUS_M:
        return None, f"radius_m {raw} is outside {MIN_RADIUS_M}-{MAX_RADIUS_M} m"
    return int(round(raw)), ""


def _place(
    poi_id: object,
    *,
    trail: str,
    radius_m: int,
    off_trail: bool,
    pois: Mapping[str, dict],
    trail_distance_m: Callable[[float, float], float] | None,
) -> tuple[dict | None, str]:
    """One published POI, copied into the shape an item carries, or why not."""
    if not isinstance(poi_id, str) or poi_id == "":
        return None, "names no poi"
    poi = pois.get(poi_id)
    if poi is None:
        # Either the POI is gone from the published set or the id was mistyped.
        # Both mean the place cannot be put on the phone, and guessing where it
        # was is the thing this file exists not to do.
        return None, f"poi {poi_id} is not in the published POIs"
    if poi.get("trail_id") != trail:
        return None, f"poi {poi_id} is on trail {poi.get('trail_id')!r}, not {trail!r}"
    mile, lat, lon = poi.get("mile"), poi.get("lat"), poi.get("lon")
    if not isinstance(mile, (int, float)):
        return None, f"poi {poi_id} has no published mile"
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None, f"poi {poi_id} has no coordinate"
    if not off_trail and trail_distance_m is not None:
        distance = trail_distance_m(float(lon), float(lat))
        if distance > radius_m:
            # A place its own radius cannot reach from the trail is either a
            # wrong id or a town. The file has to say which.
            far = f"{distance:.0f} m" if math.isfinite(distance) else "more than a grid cell"
            return None, (
                f"poi {poi_id} is {far} from the trail, past its {radius_m} m radius - "
                "mark the match off_trail if reaching it means leaving the trail"
            )
    return {
        "poi": poi_id,
        "name": _text(poi.get("name")),
        "poi_type": _text(poi.get("poi_type")),
        "mile": round(float(mile), 3),
        "lat": round(float(lat), 6),
        "lon": round(float(lon), 6),
    }, ""


def resolve_match(
    match: object,
    *,
    trail: str,
    known_orgs: set[str],
    poi_types: tuple[str, ...],
    pois: Mapping[str, dict],
    trail_distance_m: Callable[[float, float], float] | None,
) -> tuple[dict | None, str]:
    """An item's match in published shape, or (None, why)."""
    if not isinstance(match, Mapping):
        return None, "match is not an object"
    kind = match.get("kind")
    if kind not in MATCH_KINDS:
        return None, f"match kind {kind!r} is not one of {', '.join(MATCH_KINDS)}"

    if kind in PLACE_KINDS:
        radius, why = _radius(match, kind)
        if radius is None:
            return None, why
        off_trail = match.get("off_trail") is True
        ids = [match.get("poi")] if kind == "place" else match.get("pois")
        if not isinstance(ids, list) or (kind == "places_all" and len(ids) < 2):
            return None, "places_all names fewer than two pois"
        if len(set(map(str, ids))) != len(ids):
            return None, "names the same poi twice"
        places = []
        for poi_id in ids:
            place, why = _place(
                poi_id,
                trail=trail,
                radius_m=radius,
                off_trail=off_trail,
                pois=pois,
                trail_distance_m=trail_distance_m,
            )
            if place is None:
                # All or nothing, for places_all: "Virginia's Triple Crown"
                # with one of three peaks missing is a different item.
                return None, why
            places.append(place)
        return {"kind": kind, "radius_m": radius, "off_trail": off_trail, "places": places}, ""

    if kind == "poi_type":
        radius, why = _radius(match, kind)
        if radius is None:
            return None, why
        poi_type = match.get("type")
        if poi_type not in poi_types:
            return None, f"poi type {poi_type!r} is not a published type"
        return {"kind": kind, "type": poi_type, "radius_m": radius}, ""

    if kind == "elevation_min_ft":
        value = match.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            return None, "elevation_min_ft needs a positive value"
        return {"kind": kind, "value": float(value)}, ""

    if kind == "section_walked":
        # POI anchors only, the handoff's preference made a rule: a section
        # whose ends are typed miles is a guidebook figure presented as a
        # measurement, the thing lib/highlights.py refuses for the same reason.
        ends = []
        for label in ("from_poi", "to_poi"):
            place, why = _place(
                match.get(label),
                trail=trail,
                radius_m=MAX_RADIUS_M,
                off_trail=True,
                pois=pois,
                trail_distance_m=None,
            )
            if place is None:
                return None, f"{label} {why}"
            ends.append(place)
        low, high = sorted((ends[0]["mile"], ends[1]["mile"]))
        if high == low:
            return None, "both ends resolve to the same mile"
        fraction = match.get("min_fraction", DEFAULT_MIN_FRACTION)
        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not 0 < fraction <= 1:
            return None, "min_fraction must be in (0, 1]"
        return {
            "kind": kind,
            "trail": trail,
            "from_mile": low,
            "to_mile": high,
            "from_name": ends[0]["name"] if ends[0]["mile"] == low else ends[1]["name"],
            "to_name": ends[1]["name"] if ends[1]["mile"] == high else ends[0]["name"],
            "min_fraction": float(fraction),
        }, ""

    if kind == "workday":
        org = match.get("org")
        if org is not None and (not isinstance(org, str) or org not in known_orgs):
            return None, f"workday org {org!r} is not a known organization"
        return {"kind": kind, "org": org, "trail": trail}, ""

    return {"kind": "self_report"}, ""


def _mystery(raw: object, today: date) -> tuple[dict | None, str]:
    if raw is None:
        return None, ""
    if not isinstance(raw, Mapping):
        return None, "mystery is not an object"
    number = raw.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        return None, "mystery needs a number from 1"
    reveal = raw.get("reveal_on")
    if reveal is not None and _date(reveal) is None:
        return None, "mystery reveal_on is not a YYYY-MM-DD date"
    return {"number": number, "reveal_on": reveal}, ""


def resolve_item(
    raw: object,
    *,
    trail: str,
    section_ids: set[str],
    known_orgs: set[str],
    poi_types: tuple[str, ...],
    pois: Mapping[str, dict],
    trail_distance_m: Callable[[float, float], float] | None,
    today: date,
) -> tuple[dict | None, str]:
    if not isinstance(raw, Mapping):
        return None, "item is not an object"
    section = raw.get("section")
    if not isinstance(section, str) or section not in section_ids:
        return None, f"section {section!r} is not declared"

    mystery, why = _mystery(raw.get("mystery"), today)
    if why:
        return None, why
    title = _text(raw.get("title"))
    if title == "" and mystery is None:
        return None, "item has no title"

    match, why = resolve_match(
        raw.get("match"),
        trail=trail,
        known_orgs=known_orgs,
        poi_types=poi_types,
        pois=pois,
        trail_distance_m=trail_distance_m,
    )
    if match is None:
        return None, why

    out: dict = {
        "id": raw["id"],
        "section": section,
        "title": title or None,
        "note": _text(raw.get("note")) or None,
        "note_by": _text(raw.get("note_by")) or None,
        "photo": _text(raw.get("photo")) or None,
        "match": match,
    }
    if mystery is not None:
        out["mystery"] = mystery
        reveal = _date(mystery["reveal_on"])
        if title and reveal is not None and reveal > today:
            # Sealed until the date: the clear title never enters the artifact.
            out["title"] = None
            out["sealed_title"] = seal(title)
        elif not title:
            out["title"] = None
    return out, ""


def resolve_challenge(
    raw: object,
    *,
    org_trails: Mapping[str, set[str]],
    poi_types: tuple[str, ...],
    pois: Mapping[str, dict],
    trail_distance_m: Callable[[float, float], float] | None,
    today: date,
) -> tuple[dict | None, list[tuple[str, str]], str]:
    """One challenge in published shape.

    Returns (record or None, [(item id, why) dropped], why the whole
    challenge did not publish or "")."""
    if not isinstance(raw, Mapping):
        return None, [], "file is not an object"
    challenge_id = raw.get("id")
    if not isinstance(challenge_id, str) or not _ID.match(challenge_id):
        return None, [], "id must be lowercase words joined by hyphens"

    # isinstance before `in` on the org, the trail, a section and a workday's
    # org: a list typed where a string belongs is unhashable, and the set or
    # dict lookup would raise TypeError - failing the whole publish job over
    # one malformed file instead of dropping that file and saying why.
    org = raw.get("org")
    if not isinstance(org, str) or org not in org_trails:
        return None, [], f"org {org!r} is not a known organization"
    trail = raw.get("trail")
    if not isinstance(trail, str) or trail not in org_trails[org]:
        # Principle 5, and the whole of it: a club's list lives on its trails.
        return None, [], f"trail {trail!r} is not one {org!r} publishes"

    name = _text(raw.get("name"))
    if name == "":
        return None, [], "challenge has no name"
    status = raw.get("status")
    if status not in STATUSES:
        return None, [], f"status must be one of {', '.join(STATUSES)}"

    window = raw.get("window")
    if not isinstance(window, Mapping):
        return None, [], "window is not an object"
    opens_raw, closes_raw = window.get("opens"), window.get("closes")
    opens = _date(opens_raw) if opens_raw is not None else None
    closes = _date(closes_raw) if closes_raw is not None else None
    if (opens_raw is not None and opens is None) or (closes_raw is not None and closes is None):
        return None, [], "window dates must be YYYY-MM-DD or null"
    if opens is not None and closes is not None and closes <= opens:
        return None, [], "window closes on or before it opens"

    sections_raw = raw.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        return None, [], "challenge declares no sections"
    sections = []
    for section in sections_raw:
        if not isinstance(section, Mapping) or not isinstance(section.get("id"), str) or not _ID.match(section["id"]):
            return None, [], "a section has no usable id"
        title = _text(section.get("title"))
        if title == "":
            return None, [], f"section {section.get('id')} has no title"
        sections.append({"id": section["id"], "title": title, "short": _text(section.get("short")) or title})
    section_ids = {s["id"] for s in sections}
    if len(section_ids) != len(sections):
        return None, [], "two sections share an id"

    items_raw = raw.get("items")
    if not isinstance(items_raw, list) or not items_raw:
        return None, [], "challenge has no items"

    known_orgs = set(org_trails)
    items: list[dict] = []
    dropped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in items_raw:
        item_id = item.get("id") if isinstance(item, Mapping) else None
        if not isinstance(item_id, str) or not _ID.match(item_id):
            dropped.append(("<no id>", "item id must be lowercase words joined by hyphens"))
            continue
        if item_id in seen:
            # Tags are keyed by item id; a second row with the same id would
            # silently take the first one's tags.
            dropped.append((item_id, "duplicate item id"))
            continue
        seen.add(item_id)
        resolved, why = resolve_item(
            item,
            trail=trail,
            section_ids=section_ids,
            known_orgs=known_orgs,
            poi_types=poi_types,
            pois=pois,
            trail_distance_m=trail_distance_m,
            today=today,
        )
        if resolved is None:
            dropped.append((item_id, why))
            continue
        items.append(resolved)

    finish = raw.get("finish")
    if finish is not None:
        if not isinstance(finish, Mapping):
            return None, dropped, "finish is not an object"
        count = finish.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            return None, dropped, "finish count must be a whole number from 1"
        if count > len(items):
            # The promise-nobody-can-keep case from the module docstring.
            return None, dropped, f"finish needs {count} items and only {len(items)} resolved"
        finish = {"count": count, "label": _text(finish.get("label")) or None}

    reward = raw.get("reward")
    if reward is not None:
        if not isinstance(reward, Mapping) or reward.get("kind") not in REWARD_KINDS:
            return None, dropped, f"reward kind must be one of {', '.join(REWARD_KINDS)}"
        if finish is None:
            # Independent in the sense that a finish needs no reward. A reward
            # with no finish line has no moment at which to claim it.
            return None, dropped, "a reward needs a finish line to be claimed at"
        rules_url = _text(reward.get("rules_url"))
        if rules_url and not rules_url.startswith("https://"):
            return None, dropped, "reward rules_url must be https"
        reward = {"kind": reward["kind"], "rules_url": rules_url or None, "art": _text(reward.get("art")) or None}

    reviewed = raw.get("reviewed")
    if _date(reviewed) is None:
        return None, dropped, "reviewed must be a YYYY-MM-DD date"

    return (
        {
            "id": challenge_id,
            "org": org,
            "trail": trail,
            "name": name,
            "status": status,
            "summary": _text(raw.get("summary")) or None,
            "window": {"opens": opens_raw, "closes": closes_raw},
            "finish": finish,
            "reward": reward,
            "photo": _text(raw.get("photo")) or None,
            "sections": sections,
            "items": items,
            "reviewed": reviewed,
        },
        dropped,
        "",
    )


def resolve(
    files: list[tuple[str, object]],
    *,
    org_trails: Mapping[str, set[str]],
    poi_types: tuple[str, ...],
    pois: Mapping[str, dict],
    trail_distance_m: Callable[[float, float], float] | None,
    today: date,
) -> Resolution:
    """Every reviewed file, resolved.

    `files` is (path stem, parsed JSON) in path order - the order a human
    maintains them in, so the artifact does not reshuffle when a mile moves
    upstream. The stem must equal the challenge id: a file renamed without its
    id changing (or the reverse) is an editing accident that would otherwise
    publish a hiker's tags under a new name.
    """
    out = Resolution()
    seen: set[str] = set()
    for stem, raw in files:
        record, dropped_items, why = resolve_challenge(
            raw,
            org_trails=org_trails,
            poi_types=poi_types,
            pois=pois,
            trail_distance_m=trail_distance_m,
            today=today,
        )
        label = record["id"] if record else (raw.get("id") if isinstance(raw, Mapping) else None) or stem
        for item_id, item_why in dropped_items:
            out.dropped_items.append((str(label), item_id, item_why))
        if record is None:
            out.dropped.append((str(label), why))
            continue
        if record["id"] != stem:
            out.dropped.append((record["id"], f"file is named {stem}.json but its id is {record['id']}"))
            continue
        if record["id"] in seen:
            out.dropped.append((record["id"], "duplicate challenge id"))
            continue
        seen.add(record["id"])
        out.challenges.append(record)
    return out


def trail_distance_index(lines: list[list[tuple[float, float]]], cell_deg: float = 0.05) -> Callable[[float, float], float]:
    """A nearest-vertex distance function over trail polylines.

    Nearest VERTEX, not nearest segment. The published centerline carries
    216,767 vertices over ~2,198 miles (release 2026-09-24-2), a MEAN gap of
    ~16 m, so where the spacing is typical the error is at most half that -
    about 8 m - against radii of 60 m and up. The largest gap has not been
    measured, and a long straight stretch (a bridge, a road walk) can have a
    wider one. The error only runs one way - no vertex is nearer than the line
    through it - so a sparse stretch can refuse a place really inside its
    radius, never accept one outside it, and a refusal is a printed drop.

    Grid-bucketed at `cell_deg` so the whole A.T. answers in milliseconds.
    Only the 3x3 cells around the point are searched, so a point more than
    one cell from every vertex reads as infinitely far. That is the right
    answer for a radius check only while one cell is wider than
    MAX_RADIUS_M, and at the default it is: 0.05 degrees of longitude is
    ~3.9 km at Katahdin (45.9 N, the A.T.'s northern end), against 2 km.
    """
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for line in lines:
        for lon, lat in line:
            grid.setdefault((int(lon // cell_deg), int(lat // cell_deg)), []).append((lon, lat))

    def distance(lon: float, lat: float) -> float:
        cx, cy = int(lon // cell_deg), int(lat // cell_deg)
        best = math.inf
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for vlon, vlat in grid.get((cx + dx, cy + dy), ()):
                    best = min(best, haversine_m(lon, lat, vlon, vlat))
        return best

    return distance
