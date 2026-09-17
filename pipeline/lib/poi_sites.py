"""Resolving co-located waypoints into SITES - a shelter with its privy, its
campsites and its water source, modelled as one place with parts (#523).

Design: ../../features/POI_SITES.md. Every number in this module was measured
against the live ATC FeatureServer, and the measurements are recorded next to
the constant they justify rather than in a commit message.

Pure module - no I/O, no DuckDB, no network. export_poi.py wires this up
against real unified records and publishes the result as three properties.

WHY THIS IS IN THE PIPELINE AND NOT THE CLIENT

A site is the thing a report, a closure or a field note references, and
lib/poi_schema.py's `unify_poi` already commits to ids that "stay stable across
repeated pipeline runs" for exactly that reason. A group computed on a phone has
no id that survives a pan, re-clusters at every zoom, and answers "how many"
when the question at a shelter is "is there a privy".

The grouping evidence is also upstream: it is ATC's own naming convention, which
lives in the raw `Name` column export_poi.py reads and the client never sees.

WHAT THE MAP DOES WITHOUT THIS

`icon-allow-overlap: false` means MapLibre never draws two colliding pins - it
drops the one that loses POI_PRIORITY, and privies lose to shelters. At zoom 14,
3% of the A.T.'s 316 privies are drawn anywhere on the trail, so the hiker sees a
clean map and concludes there is no privy. A privy sits a median 42 m from its
shelter and cannot be drawn until zoom 16; BASEMAP_MAX_ZOOM is 14. Sites remove
the pins that were colliding rather than permitting overlap, so 90% of privies
stop competing for a pin and start riding one that is actually drawn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lib.spurs import distance_m

# Which types can be the one anchor of a site, in the order they win it. A
# campsite anchors only what no shelter claimed - which is what makes "exactly
# one anchor per site" decidable rather than a race between two passes.
ANCHOR_TYPES = ("shelter", "campsite")

# Which types can ride an anchor's pin. `campsite` is in both tuples on purpose:
# it is a member of a shelter's site and an anchor of its own when there is no
# shelter.
MEMBER_TYPES = ("privy", "campsite", "water")

# `viewpoint`, `parking` and `resupply` are deliberately in NEITHER tuple, and
# this is the constraint that rules out grouping by distance alone. At 60 m the
# corridor holds 64 viewpoint+viewpoint clusters - two overlooks that close are
# two overlooks, not one place with parts, and a blind radius merges them.
# `parking + resupply` (26 clusters) is a trailhead: a different feature with a
# different card, and out of scope for v1 (POI_SITES.md open question 2).

# How far a name match may reach. Loose because the NAME is carrying the
# argument: every one of the name-matched privies measured is within 150 m of
# its named parent and 98% are within 100 m, so name and geometry agree
# independently on the same answer.
NAME_MATCH_RADIUS_M = 150.0

# How far proximity alone may reach, with no naming evidence at all. Tight
# because geometry is all it has. A name-only rule, by contrast, ships a
# 903 km match - a generic campsite name colliding with a same-named place at
# the far end of the trail - which is why neither gate stands alone.
PROXIMITY_RADIUS_M = 60.0

# An absolute ceiling on a site's radius, whatever gate admitted the member.
# One mile, requested on the #523 pull request.
#
# IT CANNOT BIND TODAY, AND THAT IS THE POINT OF IT. The widest gate above is
# 150 m, and the furthest member measured over the whole corridor is 143 m, so
# every real pairing clears this by a factor of ten. What it guards is the next
# edit: nothing else here stops someone raising NAME_MATCH_RADIUS_M to 2 km on a
# hunch, and the failure that reappears the moment they do is the 903 km match -
# a privy attached to a shelter at the other end of the Appalachian Trail,
# published into artifacts, with a hiker unable to undo it.
#
# So it is applied as `min()` against each gate rather than as a separate check
# further down. A guard the gates are compared against cannot be bypassed by
# widening a gate, which is the one way this particular mistake gets made.
#
# A mile is far looser than the evidence would justify as a working radius, and
# deliberately: this is a backstop, not the rule. The rule is the two gates.
MAX_SITE_RADIUS_M = 1609.344

# The trailing words ATC appends to a child's name, stripped to recover the
# parent's: "Mt. Algo Shelter Privy" -> "mt algo".
#
# EVERY ENTRY HERE IS ONE THE CORRIDOR PAYS FOR. Measured by ablation against
# all 828 shelters/campsites/privies, each word added alone on top of the first
# three:
#
#   shelters   +2 campsites, +1 site   ATC names a campsite after a PAIR:
#                                      "Tumbling Run Shelters Campsite"
#   group      +4 privies, +7 campsites, +4 sites
#                                      "Eckville Shelter Group Campsite",
#                                      "Osgood Tentsite Group Campsite"
#
# And eight that bought exactly nothing, listed so nobody adds them back on
# intuition: privies, campsites, tentsite, tentsites, campground, leanto, hut,
# cabin, site. POI_SITES.md names "Tentsite vs Campsite" as a suspected cause of
# the unresolved tail; measured, it is not one - the parent is named
# "Osgood Tentsite Group Campsite" and the child "Osgood Tentsite Privy", so
# stripping `tentsite` from BOTH sides changes nothing and stripping it from one
# would break the match.
#
# Nor is "Lean-to vs Lean to", the other suspect: punctuation is already
# collapsed to spaces before this list is consulted, so both spell "lean to" and
# folding them is dead code. It was written, measured at zero, and deleted.
TYPE_WORDS = frozenset({"privy", "campsite", "shelter", "shelters", "group"})

# Trailing digits go too: ATC numbers siblings ("Mt. Wilcox South Shelter 1",
# "Grafton Notch Parking Area Privy 2"), and 53 of the 828 names end in one.
# This is the single biggest normalisation win - privies matched go from 86% to
# 89% - and the one POI_SITES.md correctly predicted.

_NOT_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")

# What `site_role` says on a published feature.
ROLE_ANCHOR = "anchor"
ROLE_MEMBER = "member"


@dataclass
class Site:
    """One place with parts: an anchor POI and the members riding its pin.

    A site with no members is not a site and `group_sites` never returns one -
    a lone shelter is just a shelter, and writing site properties onto it would
    tell the client to render a composition of one.
    """

    anchor: dict
    members: list[dict] = field(default_factory=list)

    @property
    def site_id(self) -> str:
        """The anchor's own POI id - deterministic, and already stable across
        runs because unify_poi made it so."""
        return self.anchor["id"]

    @property
    def site_name(self) -> str | None:
        return self.anchor.get("name")

    def size(self) -> int:
        return 1 + len(self.members)


def normalise_name(name: str | None) -> str:
    """Lowercase, punctuation to spaces, whitespace collapsed.

    Punctuation-to-spaces rather than punctuation-deleted, because deleting it
    would run words together: "Mt.Algo" matches nothing, while "mt algo" is what
    the shelter's own name normalises to.
    """
    if not name:
        return ""
    return " ".join(_NOT_ALPHANUMERIC.sub(" ", name.lower()).split())


def base_name(name: str | None) -> str:
    """The parent name inside a child's name: normalised, with trailing type
    words and sibling numbers removed.

    Repeated rather than single-pass, because the tokens stack - "Bald Mtn Brook
    Lean-to Privy 2" sheds a digit and then a type word to reach "bald mtn brook
    lean to", which is what the shelter's own name reduces to.
    """
    tokens = normalise_name(name).split()
    while tokens and (tokens[-1] in TYPE_WORDS or tokens[-1].isdigit()):
        tokens.pop()
    return " ".join(tokens)


def _candidate_anchors(member: dict, anchors: list[dict], by_base_name: dict[str, list[dict]]) -> list[tuple]:
    """Every anchor this member could belong to, best first.

    Sort key, in order:

    1. **Name evidence beats proximity.** A named parent is the better signal
       and the radius reflects that; a 60 m neighbour with a different name is
       the fallback, not the answer.
    2. **A contained name beats a merely reduced one.** This is the tie-break
       the corridor asked for. Stripping `group` makes "Laurel Ridge Campsite"
       and "Laurel Ridge Group Campsite" reduce to the same base, so "Laurel
       Ridge Campsite Privy" matches both - and nearest-wins picked the group
       site, 10 m closer and not what the privy is called. Preferring the anchor
       whose whole name the member's name contains picks the one ATC named it
       after.
    3. **Then nearest**, which is all geometry can offer.
    """
    member_full = normalise_name(member.get("name"))
    named: list[tuple] = []
    for candidate in by_base_name.get(base_name(member.get("name")), ()):
        if candidate["id"] == member["id"]:
            continue
        metres = distance_m(member["lat"], member["lon"], candidate["lat"], candidate["lon"])
        if metres <= min(NAME_MATCH_RADIUS_M, MAX_SITE_RADIUS_M):
            candidate_full = normalise_name(candidate.get("name"))
            contained = bool(candidate_full) and member_full.startswith(candidate_full)
            named.append((0 if contained else 1, metres, candidate))
    if named:
        return sorted(named, key=lambda entry: (entry[0], entry[1]))

    nearby: list[tuple] = []
    for candidate in anchors:
        if candidate["id"] == member["id"]:
            continue
        metres = distance_m(member["lat"], member["lon"], candidate["lat"], candidate["lon"])
        if metres <= min(PROXIMITY_RADIUS_M, MAX_SITE_RADIUS_M):
            nearby.append((1, metres, candidate))
    return sorted(nearby, key=lambda entry: (entry[0], entry[1]))


def _index_by_base_name(anchors: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for anchor in anchors:
        key = base_name(anchor.get("name"))
        if key:
            index.setdefault(key, []).append(anchor)
    return index


def group_sites(records: list[dict]) -> list[Site]:
    """Fold co-located waypoints into sites.

    Two passes, shelters then the campsites no shelter claimed, which is how
    ANCHOR_TYPES' ordering becomes "exactly one anchor per site" rather than a
    contest. A member is folded once and never reconsidered: reopening a
    resolved member in the second pass would let a campsite steal a privy from
    the shelter it is named after.

    Anchors are never members of each other. Two shelters 40 m apart - Horns
    Pond has two lean-tos and is genuinely one place - stay two pins in v1,
    which is safe and slightly wrong there (POI_SITES.md open question 1).

    Returns sites in a deterministic order: by anchor id, and members by their
    own id, so repeated runs over unchanged input publish byte-identical
    properties. Stability is not cosmetic here - `verify_release.py` compares
    hashes, and a set-iteration order would rewrite every artifact for nothing.
    """
    sites: dict[str, Site] = {}
    folded: set[str] = set()

    def fold(members: list[dict], anchors: list[dict]) -> None:
        if not anchors:
            return
        by_base_name = _index_by_base_name(anchors)
        anchor_ids = {anchor["id"] for anchor in anchors}
        for member in sorted(members, key=lambda record: record["id"]):
            if member["id"] in folded or member["id"] in anchor_ids:
                continue
            candidates = _candidate_anchors(member, anchors, by_base_name)
            if not candidates:
                continue
            _, _, anchor = candidates[0]
            sites.setdefault(anchor["id"], Site(anchor=anchor)).members.append(member)
            folded.add(member["id"])

    shelters = [r for r in records if r["poi_type"] == "shelter"]
    campsites = [r for r in records if r["poi_type"] == "campsite"]
    members = [r for r in records if r["poi_type"] in MEMBER_TYPES]

    fold(members, shelters)
    # Only campsites that are not themselves members can anchor. A campsite
    # folded into a shelter's site is a part of that place, and a part cannot
    # hold parts of its own.
    fold(members, [c for c in campsites if c["id"] not in folded])

    return [sites[anchor_id] for anchor_id in sorted(sites)]


def site_properties(sites: list[Site]) -> dict[str, dict]:
    """POI id -> the three published properties, for every anchor and member.

    Additive by design (POI_SITES.md §3): a client built before this ignores
    them and behaves exactly as it does today, which is the same
    backward-compatibility rule `mile`, `capacity`, `description` and `photos`
    are already held to. A POI in no site appears nowhere in this mapping, and
    export_poi.py writes NULL for it - which is most POIs.
    """
    properties: dict[str, dict] = {}
    for site in sites:
        for record, role in [(site.anchor, ROLE_ANCHOR), *[(m, ROLE_MEMBER) for m in site.members]]:
            properties[record["id"]] = {
                "site_id": site.site_id,
                "site_role": role,
                "site_name": site.site_name,
            }
    return properties


# ---------------------------------------------------------------------------
# A SECOND GROUPING, FOR GROUND WHERE NOBODY NAMED THE PARTS (#1536)
#
# Everything above resolves ATC's naming convention: "Mt. Algo Shelter Privy"
# names its parent, so the NAME carries the argument and PROXIMITY_RADIUS_M is
# only the sanity check on it. New York City's fountains have no such
# convention and no parent to name - 3,148 of them carry a park name, 912
# distinct, and Central Park's 137 all carry the same one. A park name says
# "same property", not "same place".
#
# So the two gates swap weights. Geometry carries the argument here and the
# name is the sanity check, which is why this is a second function rather than
# a looser radius on the first: widening NAME_MATCH_RADIUS_M would loosen
# ATC's grouping too, and the 903 km match its docstring warns about is exactly
# what a name-led rule ships when the name stops being specific.


#: How far apart two waypoints on one property may be and still be one place.
#:
#: MEASURED against the fountains this exists for, 2026-09-17, release
#: 2026-09-16-4: over the 2,823 nearest-neighbour distances between fountains
#: sharing a park property, p25 is 24 m, the MEDIAN IS 41 m, p75 is 73 m and
#: p90 is 124 m. So 80 m sits just above the third quartile - it folds the
#: banks of fountains a playground or a plaza holds, and leaves the quarter of
#: pairings that are genuinely spread across a park.
#:
#: Wider was available and refused. A 150 m gate admits 93% of pairings rather
#: than 78%, and 150 m is what NAME_MATCH_RADIUS_M already allows above - but
#: it allows it on ATC's evidence, where the name names one parent. Here the
#: same 150 m would start folding opposite ends of a playground into one mark
#: on the strength of both being in the same park, which is not evidence that
#: they are one place.
#:
#: The failure this bounds is a hiker walking to a pin and not finding the
#: fountain. That is bounded by the anchor rule rather than by this number -
#: see `group_place_sites`, which draws the pin on a REAL member and never on
#: a centroid - but a tighter gate keeps the walk from the pin to the next
#: member short as well.
PLACE_PROXIMITY_RADIUS_M = 80.0


def group_place_sites(
    records: list[dict],
    radius_m: float = PLACE_PROXIMITY_RADIUS_M,
    types: tuple[str, ...] = ("water", "privy"),
) -> list[Site]:
    """Fold waypoints of ONE type that share a place name and stand together.

    Single-link within each (name, type) group, so a line of fountains down a
    boardwalk folds as one site instead of a chain of overlapping pairs - the
    Coney Island case, where no two ends are within the radius of each other
    but every step is.

    THE ANCHOR IS A REAL WAYPOINT, NEVER A CENTROID, and that is the safety
    rule of this whole function. A hiker walks to the pin. A centroid of twelve
    fountains is a point on a lawn with no fountain on it, which is the
    confidently wrong answer FEATURES.md calls more dangerous than an honest
    unknown. The anchor is the member CLOSEST to the group's centre - the most
    central fountain that actually exists - so the pin is always somewhere a
    hiker can arrive and find water.

    Ties break on the id, so the same input gives the same site id on every
    run - which is what a report or a field note pointing at a site needs.
    """
    wanted = set(types)
    groups: dict[tuple[str, str], list[dict]] = {}
    for record in records:
        if record.get("poi_type") not in wanted:
            continue
        name = record.get("name")
        if not name:
            # No name is no gate. Geometry alone is what PROXIMITY_RADIUS_M
            # above exists to refuse - two overlooks that close are two
            # overlooks - and an unnamed fountain has nothing to pair that
            # geometry with, so it keeps its own pin.
            continue
        groups.setdefault((normalise_name(name), record["poi_type"]), []).append(record)

    sites: list[Site] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        for cluster in _single_link(members, radius_m):
            if len(cluster) < 2:
                continue
            anchor = _most_central(cluster)
            sites.append(Site(anchor=anchor, members=[m for m in cluster if m is not anchor]))
    return sites


def _single_link(records: list[dict], radius_m: float) -> list[list[dict]]:
    """Union-find over the pairs within `radius_m`, returning each component."""
    parent = list(range(len(records)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            here, there = records[i], records[j]
            if distance_m(here["lat"], here["lon"], there["lat"], there["lon"]) <= radius_m:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b

    clusters: dict[int, list[dict]] = {}
    for index, record in enumerate(records):
        clusters.setdefault(find(index), []).append(record)
    return list(clusters.values())


def _most_central(cluster: list[dict]) -> dict:
    """The member nearest the cluster's mean position, id breaking ties."""
    mid_lat = sum(r["lat"] for r in cluster) / len(cluster)
    mid_lon = sum(r["lon"] for r in cluster) / len(cluster)
    return min(cluster, key=lambda r: (distance_m(r["lat"], r["lon"], mid_lat, mid_lon), str(r["id"])))
