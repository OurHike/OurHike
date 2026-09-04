"""Export the POIs OTHER organizations publish - NYS DEC's and NYS OPRHP's (#1097).

export_poi.py's subject is the A.T.: ATC's own facility layers plus
opentrail.org and OSM water, clipped to a 30-mile corridor around ATC's
centerline and carrying a NOBO mile from Springer. This module's subject is
everything else already on the ground - the lean-tos, campsites, privies,
vistas, parking areas and bridges two New York State agencies maintain.

A SECOND EXPORT RATHER THAN A BRANCH INSIDE THE FIRST, for the three reasons
export_nearby_trails.py already gives for doing the same thing with trail
lines: different sources, a different extent, and a different licence footing.
Folding these into `poi_*.geojson` would couple the A.T. release to another
agency's uptime - an outage at DEC would fail a release that reads no DEC bytes
- and would mix licence footings inside one artifact, which is the thing
`reaches_hikers` exists to make separable per source.

NO EXTENT OF ITS OWN, the same as export_nearby_trails.py since #1019: the
maintainer's *"Don't limit data from orgs based on geography"*. So nothing here
clips, and consequently NOTHING HERE CARRIES A MILE. export_poi.attach_miles
projects onto ATC's marker-calibrated centerline; a lean-to in the Adirondacks
has no position on it, and inventing one would print a mile marker for a place
1,200 km from the trail. `mile` is absent, and the waypoint card already reads
absent as "no mile" rather than as zero.

WHAT SHIPS, MEASURED 2026-08-27 BY spike_org_poi_coverage.py

Six of the eight POI types, from both orgs. The counts each org publishes, and
what this module actually emits, are in POI_COVERAGE_SURVEY.md §0; the
per-source totals are printed by every run and written into the manifest.

THE TWO ORG FLAGS, AND WHY THEY ARE READ DIFFERENTLY

This is the one decision in this module that a reviewer should push on, because
it looks like an inconsistency and is a measured distinction:

  - **DEC's `PUBLICUSE` FILTERS.** It splits dec_backcountry_features 7,645 Y /
    13,823 N, and the N side is genuinely internal - 4,290 culverts, gates, log
    landings, sign posts. DEC's own description calls the layer "assets on state
    lands... man-made items, which require periodic maintenance or inspection".
    So an N row is not a weaker POI, it is not a POI, and it is dropped. The
    five per-type services DEC publishes are already that Y slice (matching
    exactly on four of seven checked - POI_COVERAGE_SURVEY.md §2), and the
    filter is applied to them anyway so that a service DEC later widens cannot
    quietly bring internal assets with it.
  - **OPRHP's `ParksApp` SETS CONFIDENCE INSTEAD.** OPRHP's actual `Public`
    field reads Y on all 8,823 rows, so it filters nothing. `ParksApp` (5,822 Y
    / 3,000 N) is what discriminates, but it is a decision about what OPRHP's
    own visitor app SHOWS, not about what is real on the ground - so dropping
    its N side would throw away every one of OPRHP's 37 lean-tos, none of which
    are in that app. They ship at CONFIDENCE_LOW instead, which the map already
    draws with a broken rim, the waypoint card says in words, and the legend's
    "Verified?" filter takes off the screen. That is the schema's existing
    mechanism for "real, but nobody has vouched for it", and it fits better
    than either extreme.

WHAT DOES NOT SHIP, AND WHY EACH ONE IS A DECISION RATHER THAN AN OVERSIGHT

  - **Water, from either org.** DEC's is a measured refusal - 23 features, zero
    flagged public, and the names that sound like water are fire ponds and
    natural gas wells (sources.json's `dec_water_holdback` carries the
    evidence, tests/test_poi_coverage.py pins the verdict, and the maintainer's
    2026-08-27 decision was "Lets not use water from DEC"). OPRHP's is a
    holdback rather than a refusal: 136 spigots and 15 fountains are real, but
    the layer records no seasonal shutoff and only the 15 fountains are in
    OPRHP's own app (`oprhp_water_holdback`). Water is one of CLAUDE.md's four
    ways this app can hurt somebody and wants its own issue.
  - **`PROPOSED *` assets.** 98 rows across 27 values in DEC's layer -
    'PROPOSED LEAN-TO' x11, 'PROPOSED PIT PRIVY' x5. A hiker who walks to a
    proposed lean-to finds trees.
  - **Culverts.** 4,290 of them, and a culvert is a pipe under the tread rather
    than a thing anyone walks across.
  - **DEC's 36 `FORD` rows.** An unbridged crossing is a HAZARD, not an
    amenity, and drawing one with the same pin as a footbridge would say the
    opposite of what it means. POI_COVERAGE_SURVEY.md §8(e) raised this for
    HIKER_SAFETY.md; until that answer exists, omitting is the conservative
    direction.
  - **OPRHP's 414 `Stairs` and 15 `Vehicle Bridge`.** The survey bucketed
    Stairs under `crossing` for counting and flagged that a reviewer might want
    them separated - shipping is where that matters, so they are separated: a
    staircase is not a stream crossing, and a road bridge is not a hiker's.
    Only `Trail Bridge` ships as `crossing` from OPRHP.
  - **OPRHP's 109 resupply rows** (91 'Concession', 18 'Store'). Whether a park
    concession stand is resupply in the sense a thru-hiker means is exactly
    what #806 got wrong about opentrail's 'r' tag, where 0 of 72 published
    points turned out to be named for a store.
(Trailheads were a fourth exclusion until #1197 gave POI_TYPES a ninth
category. OPRHP's 287 ship now; DEC's 10,520 sit in a layer nobody has
registered, and NYNJTC's 26 are a featured-hikes table rather than an
inventory - POI_COVERAGE_SURVEY.md 7c has both.)

Everything a source-specific fact - which field holds the id, which the name,
which flag says public - is read from sources.json; everything that is a
JUDGEMENT about what a value means is in this file, written out value by value
so a reviewer can reject one line rather than a total.

    cd pipeline && python export_nearby_poi.py
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from lib.completeness import count_problems, fail_if_incomplete
from lib.corridor import GEOGRAPHIC_CRS, NETWORK_BUFFER_FEET, PROJECTED_CRS, count_features
from lib.hashing import sha256_file
from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES, unify_poi
from lib.source_registry import load_registry

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw" / "external"
OUT_DIR = ROOT / "data" / "processed"

ARTIFACT_NAME = "nearby_poi.geojson"
MANIFEST_NAME = "nearby_poi_manifest.json"
NETWORK_ARTIFACT_NAME = "nearby_trails.geojson"

METERS_PER_FOOT = 0.3048

#: The two types the ring does not apply to (#1113).
#:
#: MEASURED, 2026-09-04, against the published artifacts - and this exemption
#: exists because the measurement asked for it rather than because it seemed
#: kind. A 500 ft ring drops 49% of DEC's parking areas and 12% of OPRHP's,
#: which are the largest per-type losses in the whole clip; #1113 predicted
#: exactly that ("a trailhead parking area can legitimately sit further from
#: the tread than a spring does").
#:
#: What settles it is that exempting them costs NOTHING on the screen the clip
#: exists to fix. Both start hidden under #865's default, so the densest z12
#: screen is identical either way - Harriman 19, Catskills 22, Adirondacks 35,
#: run through spike_oprhp_poi_density.py --artifact both ways - while 2,493
#: more waypoints survive. A hiker who turns parking on pays for it and is a
#: hiker asking for parking.
#:
#: #981 is the supporting argument rather than this file's own: a lot is "an
#: annotation on a start, never a precondition", so the type whose whole
#: purpose is to sit off the tread is the wrong one to measure against tread.
NETWORK_RING_EXEMPT_TYPES = frozenset({"parking", "trailhead"})

# `trail_id` per org rather than export_poi.py's "AT". Nothing on the client
# reads this field today; it is the pipeline's own record of which system a row
# belongs to, and writing "AT" on a Catskills lean-to would make it wrong the
# moment something does read it. Keyed by provider, since that is what the
# registry calls an organization.
TRAIL_IDS = {
    "NYS DEC": "NYSDEC",
    "NYS OPRHP": "NYSOPRHP",
    "USFS": "USFS",
}

# DEC's ASSET values, for the two POI types DEC publishes no per-type service
# for. An ALLOWLIST rather than a prefix match: the column is free text with
# 223 trimmed values and a prefix rule would sweep in 'PROPOSED PIT PRIVY' and
# 'CULVERT ' with the trailing space. Counts are total rows on 2026-08-27; what
# actually ships is the PUBLICUSE='Y' subset of each, printed per run.
DEC_ASSET_TYPES = {
    # privy - 356 + 24 + 12 + 1
    "PIT PRIVY": "privy",
    "PORT-A-JOHN": "privy",
    "RESTROOM": "privy",
    "BATHROOM": "privy",
    # crossing - a built thing a walker gets across on. 'FORD' is deliberately
    # absent (see the module docstring), and so is 'CULVERT' at 4,290 rows.
    "BRIDGE": "crossing",
    "FOOT BRIDGE": "crossing",
    "BOARDWALK": "crossing",
    "HARDENED CROSSING": "crossing",
}

# OPRHP's Sub_Asset values. One layer carries all seven types; 'Water Spigot',
# 'Drinking Fountain', 'Concession', 'Store', 'Stairs' and 'Vehicle Bridge'
# are deliberately absent - the docstring says why for each.
#
# 'Trailhead' was the seventh absence until #1197, dropped with the named
# reason "POI_TYPES has no trailhead category". lib/poi_schema.py has one now,
# so the 287 rows OPRHP publishes ship - in the two parks the day-hike builder
# is actually used in, which is what makes them worth the schema change.
OPRHP_SUB_ASSET_TYPES = {
    "Lean-to": "shelter",
    "Campground": "campsite",
    "Group Camp": "campsite",
    "Public Restroom": "privy",
    "Pit Toilet": "privy",
    "Portable Toilet": "privy",
    "Scenic View": "viewpoint",
    "Fire Tower": "viewpoint",
    "Wildlife Viewpoint": "viewpoint",
    "Parking Area": "parking",
    "Pull Off": "parking",
    "Accessible Parking Area": "parking",
    "Trail Bridge": "crossing",
    # Where the walking starts (#1197). Kept apart from the three `parking`
    # values above rather than folded into them, which is the whole reason
    # the ninth type was worth adding: OPRHP publishes both, and a lot and
    # the trailhead it serves are frequently not the same point. Calling a
    # trailhead "parking" would put a hiker's start where their car is.
    "Trailhead": "trailhead",
}

# USFS's site_type values. FOUR MAPPED OUT OF ROUGHLY THIRTY, and the
# omissions carry more weight than the inclusions here (#1207).
#
# THE ONE THAT MATTERS IS 'CAMPING AREA', 10,783 rows - the LARGEST site_type
# in the layer, bigger than every campground in the national forest system put
# together, and deliberately absent. It is dispersed camping: development_scale
# reads 0 (undeveloped) on 8,135 of them against not one CAMPGROUND row below
# scale 2, and the names are forest-road references rather than places
# ('FS1302-03', 'RD 614 SITE 13', 'RD 201 MI 8.2'). Publishing it would break an
# editorial holdback this project already made for ATC's 2,333 user-created
# campsites - SOURCE_SURVEY.md section 3b, "publishing locations may be actively
# harmful", the ones land managers are often trying to close - at 4.6x the
# scale, and as a side effect of a change about the White Mountains rather than
# as a decision anybody took. sources.json's `usfs_dispersed_camping_holdback`
# is the full argument and what would reopen it.
#
# Also deliberately absent: 'LOOKOUT/CABIN' (815) is not a trail shelter - a
# rentable cabin a hiker cannot walk into is worse than no pin, and the
# poi_coverage shelter verdict says so as `unsuitable`; 'HOTEL, LODGE, RESORT'
# (164) is where AMC's huts would be if they were anywhere public, and is
# unprobed; and the ski, boating, fishing, target-range and OHV-staging types
# are not POI_TYPEs at all. Counts are nationwide, measured 2026-09-02.
USFS_SITE_TYPES = {
    "TRAILHEAD": "parking",
    "CAMPGROUND": "campsite",
    "GROUP CAMPGROUND": "campsite",
    "OBSERVATION SITE": "viewpoint",
}

# Which registry key gets which value map, and which field the values live in.
# Two entries rather than a `kind`, because two is what there is: adding a third
# org means one line here plus its map above, and a `kind` would be a
# generalisation invented before its second case.
TYPED_LAYERS = {
    "dec_backcountry_features": ("ASSET", DEC_ASSET_TYPES),
    "oprhp_facilities": ("Sub_Asset", OPRHP_SUB_ASSET_TYPES),
    "usfs_rec_sites": ("site_type", USFS_SITE_TYPES),
}


def _folded(mapping: dict) -> dict:
    """One org's value map, keyed for a case-insensitive lookup.

    THE MAPS ABOVE STAY IN EACH ORG'S OWN CASING because that is evidence
    about the source - DEC shouts and OPRHP does not - and a reader comparing
    a key against the live service should see what the service holds. The
    matching is a separate question, and it is case-insensitive for the reason
    sources.json's `dec_backcountry_features` note already gives: `ASSET` is
    free text carrying its own misspellings ('PRIMATIVE CAMPSITE') and
    whitespace variants, so its casing is not a thing to rely on either.

    That note has said the match is "case-insensitive and stripped" since the
    layer was registered, and until this function existed only the stripping
    was true. Nothing went wrong, because DEC writes uppercase today and
    OPRHP title case - the failure this closes is the silent one: an upstream
    edit to 'Pit Privy' would have dropped all 356 DEC privies, and the run's
    own dropped-reason line would have called them "not a published POI type"
    rather than saying anything about case.

    Collision-checked rather than assumed: folding must not merge two values
    that mean different things, so it raises here instead of resolving one
    arbitrarily at export time.
    """
    folded: dict = {}
    for value, mapped in mapping.items():
        key = value.casefold()
        if key in folded and folded[key] != mapped:
            raise ValueError(f"case-folding {value!r} collides with another value meaning {folded[key]!r}")
        folded[key] = mapped
    return folded


DEC_ASSET_TYPES_FOLDED = _folded(DEC_ASSET_TYPES)
OPRHP_SUB_ASSET_TYPES_FOLDED = _folded(OPRHP_SUB_ASSET_TYPES)
USFS_SITE_TYPES_FOLDED = _folded(USFS_SITE_TYPES)

TYPED_LAYERS_FOLDED = {
    "dec_backcountry_features": ("ASSET", DEC_ASSET_TYPES_FOLDED),
    "oprhp_facilities": ("Sub_Asset", OPRHP_SUB_ASSET_TYPES_FOLDED),
    "usfs_rec_sites": ("site_type", USFS_SITE_TYPES_FOLDED),
}

# Values excluded on purpose, counted and printed so the run says how much it
# dropped and why rather than silently emitting less. Not a filter - the
# allowlists above already exclude everything not in them - but a named reason
# for the four exclusions somebody would otherwise re-litigate from scratch.
NAMED_EXCLUSIONS = {
    "FORD": "unbridged crossing - a hazard, not an amenity (HIKER_SAFETY.md, POI_COVERAGE_SURVEY.md 8e)",
    "CULVERT": "a pipe under the tread, not a thing anyone crosses",
    "Stairs": "a staircase is not a stream crossing",
    "Vehicle Bridge": "a road bridge is not a hiker's crossing",
    "Water Spigot": "water holdback - no seasonal shutoff recorded (sources.json oprhp_water_holdback)",
    "Drinking Fountain": "water holdback - see oprhp_water_holdback",
    "WATER SUPPLY SYSTEM": "DEC water refused - see sources.json dec_water_holdback",
    "Concession": "unjudged as resupply (#806's precedent)",
    "Store": "unjudged as resupply (#806's precedent)",
}

#: Matched on the same terms as the allowlists - a value excluded on purpose
#: keeps its named reason whatever case it arrives in, or a casing change
#: would demote it to the generic "not a published POI type" line and lose
#: exactly the sentence that stops somebody re-litigating it.
NAMED_EXCLUSIONS_FOLDED = _folded(NAMED_EXCLUSIONS)


def poi_sources(registry: dict) -> list[dict]:
    """The registered layers this module exports, in registry order.

    A layer qualifies two ways: it declares `poi_type` (the whole layer is one
    category - DEC's five per-type services), or it appears in TYPED_LAYERS (a
    mixed layer read through a value map).
    """
    return [
        source for source in registry.get("sources", []) if source.get("poi_type") is not None or source["key"] in TYPED_LAYERS
    ]


def public_verdict(source: dict, properties: dict) -> tuple[bool, str]:
    """Whether this row ships, and at what confidence, per its org's own flag.

    Returns (keep, confidence). See the module docstring for why DEC's flag
    filters and OPRHP's sets confidence: the difference is that DEC's N side is
    internal assets and OPRHP's is a decision about their own app's contents.
    """
    field = source.get("public_field")
    if field is None:
        return True, CONFIDENCE_HIGH
    flagged = str(properties.get(field) or "").strip().upper() == str(source.get("public_value", "Y")).upper()
    if source.get("public_flag_sets_confidence"):
        return True, CONFIDENCE_HIGH if flagged else CONFIDENCE_LOW
    return flagged, CONFIDENCE_HIGH


def classify(source: dict, properties: dict) -> str | None:
    """This feature's poi_type, or None if the layer does not publish one for it."""
    declared = source.get("poi_type")
    if declared is not None:
        return declared
    field, value_map = TYPED_LAYERS_FOLDED[source["key"]]
    return value_map.get(str(properties.get(field) or "").strip().casefold())


# The values DEC writes where a real value is missing. '-99' is DEC's own null
# sentinel (already documented on dec_hiking_trails for its MARKER column) and
# a bare space is what an empty ArcGIS text cell arrives as. Neither may reach
# a card: "-99" rendered under a shelter's name is worse than no line at all.
DIRT = frozenset({"", "-99", "N/A", "NA", "NONE", "UNKNOWN", "TBD"})


def clean(value) -> str | None:
    """One of the org's own strings, or None if what arrived was dirt."""
    text = str(value or "").strip()
    return None if text.upper() in DIRT else text


def compose_description(source: dict, properties: dict) -> str | None:
    """One sentence about the place, from the org's OWN columns.

    lib/poi_description.py's argument, applied to two more orgs: the sentence a
    hiker wants is not a field to be found, it is a sentence to be assembled out
    of facts the org states. Neither agency writes prose about a privy, but both
    state what it is and which unit it is in, and those two together are worth
    more than the blank they otherwise leave.

    That matters most on OPRHP, where `Name` is populated on 18% of rows: a pin
    reading "Unnamed" with no card line at all would be the whole feature for
    3,676 of these, and "Trail Bridge in Beaver Island State Park." is two facts
    OPRHP publishes rather than anything composed here.

    Every clause is the org's word. The only editorialising is `.title()` on
    DEC's ALL-CAPS asset values, which is formatting rather than meaning, and it
    is applied to DEC's vocabulary only - OPRHP's is already title case, and
    running it through .title() would turn 'Lean-to' into 'Lean-To'.

    DEC'S `DESCRIP` IS DELIBERATELY NOT IN THE SENTENCE, and this paragraph
    exists because the first version of this function appended it and produced
    "Observation Platform in Mcdonough State Forest. 12'." Measured 2026-08-27
    across the five DEC layers here: DESCRIP is populated on 14,303 rows, **27%
    of them under twelve characters**, and the content is a maintenance
    surveyor's notebook rather than prose about a place - '18" X 24 Metal',
    '12" Good', 'Saloon Style Gate', 'Permanent Plastic Culvert with Cast
    Cement Headwalls'. That is the same finding lib/atc_notes.py already
    recorded about ATC's own `Comments` column, on another agency's data, and
    it gets the same answer.

    One thing inside it is genuinely useful and is left on the table on
    purpose: parking rows carry '3 Vehicle Capacity', '1 Vehicle Capacity',
    which is exactly what a hiker planning a trailhead start wants. Getting it
    out means parsing free text against a pattern nobody has measured coverage
    for - #806's lesson is that a plausible read of an uncounted column ships
    wrong data quietly - so it is worth an issue rather than a regex here.
    """
    facility = clean(properties.get(source.get("facility_field")))
    asset = clean(properties.get(source.get("asset_field")))
    if asset and asset.isupper():
        asset = asset.title()
    if not asset:
        return None
    return f"{asset} in {facility}." if facility else f"{asset}."


def build_records(source: dict, features: list[dict]) -> tuple[list[dict], dict]:
    """Unify one layer's features into POI records, with a per-reason drop tally."""
    key = source["key"]
    trail_id = TRAIL_IDS[source["provider"]]
    field_map = {
        "id_field": source.get("id_field", "OBJECTID"),
        "name_field": source.get("name_field", "NAME"),
    }
    type_field = TYPED_LAYERS.get(key, (None, None))[0]

    records: list[dict] = []
    dropped: dict[str, int] = {}
    by_type: dict[str, int] = {}
    low_confidence = 0
    unnamed = 0

    for feature in features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point" or len(geometry.get("coordinates") or ()) < 2:
            # Two failures, one drop, because they mean the same thing to a
            # hiker: this row cannot be drawn. The second is not hypothetical -
            # 14 rows across three layers arrive as a Point with an EMPTY
            # coordinate array (measured 2026-08-27: 12 in
            # dec_backcountry_features, 1 in dec_primitive_campsites, 1 in
            # oprhp_facilities), which is an agency's null island written the
            # honest way. Dropped and counted rather than crashing the run or
            # being published at 0,0 - lib/trailData.ts drops a POI with no
            # coordinates for the same reason at the other end.
            dropped["no usable point geometry"] = dropped.get("no usable point geometry", 0) + 1
            continue

        raw_value = str(properties.get(type_field) or "").strip() if type_field else ""
        poi_type = classify(source, properties)
        if poi_type is None:
            # The label keeps the org's own casing (`raw_value`) while the
            # lookup is folded - so the run's dropped line quotes what DEC
            # actually wrote, and still finds the reason if they reshape it.
            reason = NAMED_EXCLUSIONS_FOLDED.get(raw_value.casefold())
            label = f"excluded: {raw_value} - {reason}" if reason else "not a published POI type"
            dropped[label] = dropped.get(label, 0) + 1
            continue

        keep, confidence = public_verdict(source, properties)
        if not keep:
            dropped[f"{source['public_field']} says not public"] = dropped.get(f"{source['public_field']} says not public", 0) + 1
            continue

        record = unify_poi(feature, poi_type, key, trail_id, {**field_map, "confidence": confidence})
        # export_poi.py attaches a mile by projecting onto ATC's centerline.
        # These points are not on it, so the key is removed rather than
        # published as null - one fewer field on 8,000 features saying nothing.
        record.pop("mile", None)
        # Both orgs leave names blank, and DEC writes '-99' into them. The
        # client renders a missing name as "Unnamed", which is the honest
        # outcome; publishing DEC's sentinel would put "-99" on a hiker's card.
        record["name"] = clean(record.get("name"))
        description = compose_description(source, properties)
        if description:
            record["description"] = description
        if record["name"] is None:
            unnamed += 1

        records.append(record)
        by_type[poi_type] = by_type.get(poi_type, 0) + 1
        low_confidence += int(confidence == CONFIDENCE_LOW)

    return records, {
        "kept": len(records),
        "dropped": dropped,
        "by_type": by_type,
        "low_confidence": low_confidence,
        "unnamed": unnamed,
        "described": sum(1 for r in records if r.get("description")),
    }


def clip_to_network(records: list[dict], network_path: Path) -> tuple[list[dict], dict]:
    """Drop amenity waypoints further than NETWORK_BUFFER_FEET from a published line.

    THE COLLISION THIS CLOSES (#1113). features/NEARBY_TRAILS.md's decisions
    table says amenity POIs are chosen-trail-only and safety POIs are drawn for
    every trail on screen; #1097 then shipped 8,480 DEC and OPRHP waypoints
    clipped to nothing at all. The maintainer took that knowingly and asked for
    the collision to be recorded rather than quietly resolved. This is the
    other half.

    THE SAME RING WATER ALREADY USES, deliberately - `NETWORK_BUFFER_FEET`, one
    number with one home, rather than a second radius here that could drift
    from it. NEARBY_TRAILS.md section 11 buffers a nearby trail's water by that
    500 ft; this buffers its amenities by the same.

    MEASURED, 2026-09-04, against the published `nearby_poi.geojson` (21,379
    waypoints) and `nearby_trails.geojson` (112,378 lines), through
    `spike_oprhp_poi_density.py --artifact` on both sides so the before and
    after are the same arithmetic. Densest z12 screen at default visibility:

        region        published   after
        Harriman             26      19
        Catskills            22      22
        Adirondacks         107      35

    The ring is TARGETED, which is what makes it worth doing: the Adirondack
    screen falls by two thirds - it is 105 DEC primitive tent sites along the
    Saranac lake shores, reached by water rather than by trail - while the
    Catskills does not move at all.

    AND IT DOES NOT REACH POI_VISIBILITY.md's ~16 PINS, said here because "clip
    to the ring" reads like a fix and is an improvement. Sweeping every window
    rather than the three named regions, the worst screen as published is the
    Adirondacks at 106 (default visibility); after the clip the worst is
    Allegany at 53, filled by OPRHP crossings, campsites and privies that
    survive because they genuinely are trail-adjacent. #1105's "fifty is too
    many" is still open for that screen and this does not answer it.

    NOT CLIPPING IS THE FAILURE DIRECTION. A missing or empty network artifact
    returns every record untouched with `ran: False` rather than dropping
    everything - an empty artifact is an ordinary state (the licence gate
    having held every steward's lines back, the reading `lib/corridor.py`
    already gives it), and reading "no lines to measure against" as "nothing is
    near a line" would empty the map on a state that is not an error.
    """
    stats = {
        "ran": False,
        "ring_feet": NETWORK_BUFFER_FEET,
        "exempt_types": sorted(NETWORK_RING_EXEMPT_TYPES),
        "kept": len(records),
        "dropped": 0,
        "dropped_by_source_type": {},
    }
    if not records:
        return records, stats

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    if not count_features(con, network_path):
        stats["reason"] = f"{network_path.name} holds no lines, so there is no ring to measure against"
        return records, stats

    con.execute(f"""
        CREATE TABLE network AS
        SELECT ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS g
        FROM ST_Read('{network_path.as_posix()}')
    """)
    con.execute("CREATE INDEX network_ring ON network USING RTREE (g)")

    # Only the types the ring applies to are measured - the exempt ones never
    # reach this table, so an exemption costs no query time and cannot be
    # accidentally undone by a later filter.
    candidates = [(at, record) for at, record in enumerate(records) if record["poi_type"] not in NETWORK_RING_EXEMPT_TYPES]
    con.execute("CREATE TABLE candidate (idx INTEGER, lon DOUBLE, lat DOUBLE)")
    con.executemany(
        "INSERT INTO candidate VALUES (?, ?, ?)",
        [(at, record["lon"], record["lat"]) for at, record in candidates],
    )

    radius_m = NETWORK_BUFFER_FEET * METERS_PER_FOOT
    inside = {
        row[0]
        for row in con.execute(f"""
            SELECT c.idx
            FROM candidate c
            JOIN network n
              ON ST_Intersects(
                   n.g,
                   ST_Buffer(
                     ST_Transform(ST_Point(c.lon, c.lat), '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}',
                                  always_xy := true),
                     {radius_m}
                   )
                 )
            GROUP BY c.idx
        """).fetchall()
    }

    dropped_by: dict[str, int] = {}
    kept: list[dict] = []
    for at, record in enumerate(records):
        if record["poi_type"] in NETWORK_RING_EXEMPT_TYPES or at in inside:
            kept.append(record)
            continue
        key = f"{record['source']}/{record['poi_type']}"
        dropped_by[key] = dropped_by.get(key, 0) + 1

    stats.update(
        ran=True,
        kept=len(kept),
        dropped=len(records) - len(kept),
        dropped_by_source_type=dict(sorted(dropped_by.items(), key=lambda kv: -kv[1])),
    )
    return kept, stats


def records_to_geojson(records: list[dict]) -> dict:
    """One FeatureCollection, mixed poi_types.

    Mixed rather than one file per type, which is what `poi_*.geojson` does,
    and the difference is deliberate: that namespace carries the invariant "live
    rows of one poi_type" and the client's download list is built from it. This
    artifact is one more key alongside nearby_trails.geojson, read once. Every
    feature carries its own `poi_type`, which is what lib/trailData.ts's
    readPois reads per feature anyway.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [record["lon"], record["lat"]]},
                "properties": {key: value for key, value in record.items() if value is not None},
            }
            for record in records
        ],
    }


def write_artifact(records: list[dict], per_source: dict, ring: dict | None = None) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / ARTIFACT_NAME
    path.write_text(json.dumps(records_to_geojson(records), separators=(",", ":")))

    by_type: dict[str, int] = {}
    for record in records:
        by_type[record["poi_type"]] = by_type.get(record["poi_type"], 0) + 1

    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "feature_count": len(records),
        "by_type": {poi_type: by_type.get(poi_type, 0) for poi_type in POI_TYPES if by_type.get(poi_type)},
        "sources": per_source,
        # What the ring did, in the manifest rather than only in the log. Each
        # `sources` entry counts what its own layer contributed BEFORE the clip
        # (see main), so without this block the manifest's per-source figures
        # and its feature_count would disagree with no way to see why.
        **({"network_ring": ring} if ring is not None else {}),
    }


def main() -> dict:
    registry = load_registry(ROOT / "sources.json")
    sources = poi_sources(registry)

    all_records: list[dict] = []
    counts: dict[str, int] = {}
    per_source: dict[str, dict] = {}

    for source in sources:
        key = source["key"]
        raw_path = RAW_DIR / f"{key}.geojson"
        if not raw_path.exists():
            raise FileNotFoundError(
                f"{raw_path} is missing - run fetch_external_layers.py first. "
                f"({key} is registered as an external layer, so it is not part of fetch_all.py's A.T. fetch.)"
            )
        features = json.loads(raw_path.read_text(encoding="utf-8")).get("features", [])
        records, stats = build_records(source, features)

        print(f"  {key}: {stats['kept']:,} of {len(features):,} features kept  {stats['by_type']}")
        if stats["low_confidence"]:
            print(f"      {stats['low_confidence']:,} at low confidence ({source['public_field']} says not in the org's own app)")
        if stats["kept"]:
            print(f"      {stats['unnamed']:,} unnamed, {stats['described']:,} carry a composed description")
        for reason, count in sorted(stats["dropped"].items(), key=lambda kv: -kv[1])[:8]:
            print(f"      dropped {count:>6,}  {reason}")

        counts[key] = stats["kept"]
        per_source[key] = {
            "steward": source.get("steward"),
            "attribution": source.get("attribution"),
            "reaches_hikers": source.get("reaches_hikers"),
            **stats,
        }
        all_records.extend(records)

    # export_nearby_trails.py's gate, for the same reason it has one: a source
    # that silently returns zero - an ArcGIS schema change, a renamed asset
    # value - must fail the run rather than quietly shrink the map.
    fail_if_incomplete(count_problems(counts), label="Incomplete nearby-POI export")

    # AFTER the gate, not before, and the order is the argument: that gate
    # exists to catch a source that silently returned zero - an ArcGIS schema
    # change, a renamed asset value - and it reads the per-layer counts to do
    # it. The ring legitimately removes most of some layers (57% of DEC's
    # primitive tent sites), so clipping first would let a deliberate,
    # measured drop fail the run wearing a fetch failure's name.
    before = len(all_records)
    all_records, ring = clip_to_network(all_records, OUT_DIR / NETWORK_ARTIFACT_NAME)
    if ring["ran"]:
        print(
            f"\n  ring: {ring['dropped']:,} of {before:,} dropped further than "
            f"{ring['ring_feet']} ft from a published line "
            f"({', '.join(ring['exempt_types'])} exempt - see NETWORK_RING_EXEMPT_TYPES)"
        )
        for key, count in list(ring["dropped_by_source_type"].items())[:8]:
            print(f"      dropped {count:>6,}  {key}")
    else:
        print(f"\n  ring: not applied - {ring.get('reason', 'no network artifact')}")

    manifest = write_artifact(all_records, per_source, ring)
    size = Path(manifest["path"]).stat().st_size
    print(f"\n  {manifest['feature_count']:,} features -> {manifest['path']} ({size:,} bytes)")
    print(f"  by type: {manifest['by_type']}")

    held_back = [k for k, s in per_source.items() if not s["reaches_hikers"]]
    if held_back:
        print(
            f"  HELD BACK: {', '.join(held_back)} carry reaches_hikers: false, so publish.py "
            f"will not upload this artifact. See sources.json's licence blocks."
        )

    manifest_path = OUT_DIR / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"  manifest -> {manifest_path}")
    return manifest


if __name__ == "__main__":
    main()
