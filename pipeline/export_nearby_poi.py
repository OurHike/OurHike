"""Export the POIs OTHER organizations publish - NYS DEC's and NYS OPRHP's (#1097).

export_poi.py's subject is the A.T.: ATC's own facility layers plus
opentrail.org and OSM water, clipped to a 30-mile corridor around ATC's
centerline and carrying a NOBO mile from Springer. This module's subject is
everything else already on the ground - the lean-tos, campsites, privies,
vistas, parking areas and trailheads two New York State agencies maintain.
(Their bridges shipped too, as `crossing`, until #1674 withdrew that type.)

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

Six of the eight POI types, from both orgs - five since #1674 withdrew
`crossing`, which was their bridges. The counts each org publishes, and what
this module actually emits, are in POI_COVERAGE_SURVEY.md §0 (as measured,
bridges included); the per-source totals are printed by every run and written
into the manifest.

A THIRD INPUT SINCE 2026-09-08 (#1288), AND THE FIRST THAT IS NOT A LAYER:
NYNJTC's Long Path section guide, forty web pages fetch_nynjtc_long_path_guide.py
caches and lib/nynjtc_long_path_guide.py reads into waypoints - 271 on the day
it landed: parking lots at NYNJTC's own coordinates, and lean-tos, springs,
campsites, lookouts and restrooms placed by walking the guide's mile along the
registered Long Path line at low confidence with a measured error. guide_records
below is the whole of it; the gate is the entry's own reaches_hikers, and what
that gate holding back must NOT do to everybody else's waypoints is that
function's docstring.

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
    `Trail Bridge` was the one OPRHP value that shipped as `crossing`.
  - **Every bridge, since #1674.** The maintainer had the `crossing` type
    taken off the map ("Crossings are cluttering the map"), and DEC's
    BRIDGE, FOOT BRIDGE, BOARDWALK and HARDENED CROSSING rows and OPRHP's
    Trail Bridge were that type here. They drop with a named reason, like
    every other refusal, rather than falling through as unknown values.
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
from lib.corridor import (
    NETWORK_BUFFER_FEET,
    inside_boundary_sql,
    load_boundary_polygons,
    load_network_lines,
    near_network_sql,
)
from lib.hashing import sha256_file
from lib.manifest_paths import to_manifest_path
from lib.nynjtc_long_path_guide import LINE_SOURCE_KEY as GUIDE_LINE_KEY
from lib.nynjtc_long_path_guide import SOURCE_KEY as GUIDE_KEY
from lib.nynjtc_long_path_guide import Section
from lib.nynjtc_long_path_guide import build_records as build_guide_records
from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES, unify_poi
from lib.poi_sites import PLACE_PROXIMITY_RADIUS_M, group_place_sites, site_properties
from lib.source_registry import find_source, load_registry

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw" / "external"
OUT_DIR = ROOT / "data" / "processed"

ARTIFACT_NAME = "nearby_poi.geojson"
MANIFEST_NAME = "nearby_poi_manifest.json"
NETWORK_ARTIFACT_NAME = "nearby_trails.geojson"

#: Where fetch_nynjtc_long_path_guide.py leaves its parse, and where a
#: held-back guide's records are written FOR REVIEW - a file publish.py never
#: collects, so a reviewer can put the pins on a map before anybody decides
#: whether hikers may see them.
GUIDE_RAW_DIR = ROOT / "data" / "raw" / "nynjtc_long_path_guide"
GUIDE_REVIEW_NAME = "long_path_guide_poi.review.geojson"

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
    "NYC Parks": "NYCPARKS",
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
    # BRIDGE, FOOT BRIDGE, BOARDWALK and HARDENED CROSSING mapped to
    # `crossing` here until #1674 withdrew the type - see NAMED_EXCLUSIONS.
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
    # 'Trail Bridge' was `crossing` until #1674 - see NAMED_EXCLUSIONS.
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
    # `trailhead` since #1218, and `parking` for the sixteen days before it.
    #
    # #1207 wrote `parking` on 2026-09-02 and was right to: POI_TYPES had eight
    # entries that morning and parking was the nearest honest home for a place
    # where the walking begins. #1197 landed the ninth the same afternoon, and
    # nobody had gone back to the mapping since - so 7,358 nationwide USFS
    # trailheads reached hikers as a "P" glyph on a category the app had by
    # then decided is a different thing.
    #
    # MOVING IT EMPTIES USFS'S PARKING CELL, and that is measured rather than
    # assumed. #1218 would not close on the White Mountains census (335 rows of
    # 31,405) that pointed this way. Re-run nationwide 2026-09-04 by group-by
    # statistics on site_type: 33 distinct values over 31,406 features, and NO
    # `PARKING` among them. The nearest things to one are SNOWPARK (318),
    # OHV STAGING AREA (181) and DAY USE AREA (1,034), none of which is a
    # parking lot. So this layer publishes no parking, and sources.json's
    # `parking` cell says `absent` on that measurement.
    #
    # (31,406 rather than #1207's 31,405: the layer gained one row in two days.
    # Recorded because a figure that quietly moves is worth a reader knowing
    # about, not because one row matters.)
    #
    # #981 settled the direction this goes in - "a dayhike should be able to
    # start anywhere - not just the parking lot" - and #1197 carried the
    # consequence: a lot is an annotation on a start, never a precondition.
    # 7,358 pins said the opposite by their glyph.
    "TRAILHEAD": "trailhead",
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
WITHDRAWN_CROSSING = "the crossing type was withdrawn (#1674, lib/poi_schema.WITHDRAWN_POI_TYPES)"

NAMED_EXCLUSIONS = {
    "FORD": "unbridged crossing - a hazard, not an amenity (HIKER_SAFETY.md, POI_COVERAGE_SURVEY.md 8e)",
    "CULVERT": "a pipe under the tread, not a thing anyone crosses",
    "Stairs": "a staircase is not a stream crossing",
    "Vehicle Bridge": "a road bridge is not a hiker's crossing",
    # The five values that were `crossing` until the maintainer withdrew that
    # type (#1674). Named rather than dropped from the allowlists alone, so a
    # run still says it held back the bridges on purpose.
    "BRIDGE": WITHDRAWN_CROSSING,
    "FOOT BRIDGE": WITHDRAWN_CROSSING,
    "BOARDWALK": WITHDRAWN_CROSSING,
    "HARDENED CROSSING": WITHDRAWN_CROSSING,
    "Trail Bridge": WITHDRAWN_CROSSING,
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


def boundary_paths_for(sources: list[dict]) -> dict[str, Path]:
    """`{POI source key: the park-boundary layer it names}` (#1493).

    A source opts in by naming a registered layer in `boundary_source`; the
    path is where `fetch_external_layers.py` puts that layer, the same
    `RAW_DIR / f"{key}.geojson"` every other external read here uses.

    NOT VALIDATED AGAINST THE REGISTRY ON PURPOSE, and this is the direction
    rather than an omission: a `boundary_source` naming a layer nobody
    registered yields a path that does not exist, `clip_to_network` loads no
    polygons for it, and the ring alone decides - which is the clip this file
    had before #1493. A typo therefore costs coverage and cannot invent it.
    `confidence_floor` raises on a value it does not recognise for the opposite
    reason: getting that wrong ships a confident claim, where getting this
    wrong ships fewer pins.
    """
    return {
        source["key"]: RAW_DIR / f"{source['boundary_source']}.geojson" for source in sources if source.get("boundary_source")
    }


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


def confidence_for(source: dict, verdict: str) -> str:
    """`verdict` unless the whole layer is registered as low confidence.

    A FLOOR, NOT A FLAG, and the difference is the reason it exists (#1461).
    `public_field` above answers a per-ROW question - this org says this one
    is not for the public - and there was no way to say the LAYER cannot
    support a confident claim about any of its rows. New York City's drinking
    fountains are exactly that: `featuresta` reads `Active` on all 3,849, so
    the column carries nothing about whether any given fountain works, and
    shipping them at CONFIDENCE_HIGH would assert of every one of them the
    thing the source cannot say about a single one.

    It only ever lowers. A source that declares the floor and also has a
    public flag keeps the flag's LOW answers - there is nowhere lower to go -
    and cannot be raised back to HIGH by it.

    AN UNRECOGNISED VALUE RAISES RATHER THAN BEING IGNORED, which is the half
    of this that review added and the half worth reading. The floor is read
    here and nowhere else, by string equality, against a key sources.json has
    no schema for - lib/source_registry.py's header records that
    `discover_sources.py` carries unknown fields through, so nothing rejects a
    key or a value it does not know. A floor written "Low", "lower", or as
    anything else somebody reasonably invents would have compared False and
    shipped all 3,195 of New York City's drinking fountains at
    CONFIDENCE_HIGH - asserting working water at every one of them from a
    source whose `featuresta` says nothing about any of them. Silently, with
    CI green, on `out of water`.

    sources.json's own comment called that "one careless edit from being
    undone". It was right, and a comment is not a guard; this is.

    WHAT THIS STILL DOES NOT CATCH, stated because the gap is invisible from
    here: a misspelled KEY. `confidence_flor` reads as absent and the layer
    ships at whatever the row said. Closing that needs an allowed-key schema
    over the whole registry, which is a change to every source rather than to
    this one and is not attempted here.
    """
    declared = source.get("confidence_floor")
    if declared is None:
        return verdict
    if declared != CONFIDENCE_LOW:
        raise ValueError(
            f"{source.get('key', '?')}: confidence_floor must be {CONFIDENCE_LOW!r}, got {declared!r}. "
            f"The floor only ever lowers, so {CONFIDENCE_LOW!r} is the only value it can mean - "
            "and a value this does not recognise would silently ship the layer at full confidence."
        )
    return CONFIDENCE_LOW


def low_confidence_reason(source: dict) -> str:
    """Why this source's low-confidence records are low, for the run log.

    TWO MECHANISMS NOW, AND THIS LINE ASSUMED ONE. It read
    `source['public_field']` unconditionally, which was true while the only
    way to be low was OPRHP's per-row flag - and became a KeyError the moment
    `confidence_floor` shipped a layer that is low WITHOUT a public field.
    The UA publish after #1474 died here, 17 minutes in, having already
    exported all 3,195 fountains and 975 restrooms correctly: the export was
    right and the sentence describing it was not.

    So the reason is chosen rather than assumed, and the two do not mean the
    same thing - "ParksApp says not in the org's own app" is a claim about
    3,195 New York fountains that no NYC column makes.

    NOTHING HERE RAISES. A progress line is not worth a pipeline: an
    unrecognised combination prints that it is unrecognised, because losing
    the publish to a print is exactly the trade this function exists to stop
    making. The guarantee that a floor is real lives in `confidence_for`,
    which does raise.
    """
    if source.get("confidence_floor") == CONFIDENCE_LOW:
        return f"confidence_floor - the layer cannot support a confident claim about any row ({source['key']})"
    field = source.get("public_field")
    if field:
        return f"{field} says not in the org's own app"
    return "reason not recorded - a source lowered confidence by a route this line does not know"


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
    3,676 of these, and "Lean-to in Allegany State Park." is two facts OPRHP
    publishes rather than anything composed here.

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

        confidence = confidence_for(source, confidence)
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


def clip_to_network(
    records: list[dict],
    network_path: Path,
    boundary_paths: dict[str, Path] | None = None,
) -> tuple[list[dict], dict]:
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

    A BOUNDARY IS THE SECOND WAY IN (#1493), and it is an OR rather than a
    replacement. `boundary_paths` maps a POI source key to the park-boundary
    layer its registry entry names in `boundary_source`; a candidate inside one
    of those boundaries is kept however far it sits from a line. The ring asks
    how far this point is from a path, which is the right question on a
    corridor and the wrong one in a city - in a park the PARK is the
    destination and the path through it is incidental. Measured 2026-09-15
    against the UA release: the ring admits 982 of 3,195 NYC fountains and 249
    of 975 restrooms, and in Central Park alone 182 of 221 points do not ship.

    KEPT AS AN OR BECAUSE REPLACING IT WOULD LOSE 34 FOUNTAINS that ship today
    from outside any boundary - near a line, outside a property. A rule that
    only asked the boundary question would drop them, which is the direction
    this whole function is built not to go.

    NOT CLIPPING IS THE FAILURE DIRECTION. A missing or empty network artifact
    returns every record untouched with `ran: False` rather than dropping
    everything - an empty artifact is an ordinary state (the licence gate
    having held every steward's lines back, the reading `lib/corridor.py`
    already gives it), and reading "no lines to measure against" as "nothing is
    near a line" would empty the map on a state that is not an error.
    """
    boundary_paths = boundary_paths or {}
    stats = {
        "ran": False,
        "ring_feet": NETWORK_BUFFER_FEET,
        "exempt_types": sorted(NETWORK_RING_EXEMPT_TYPES),
        "kept": len(records),
        "dropped": 0,
        "dropped_by_source_type": {},
        "boundary_kept": {},
    }
    if not records:
        return records, stats

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    # The same indexed line table and the same ring query lib/corridor.py
    # clips POIs and water with (#1311) - this file had them first, and
    # sharing them is what stopped the corridor building a nationwide union.
    if not load_network_lines(con, network_path):
        stats["reason"] = f"{network_path.name} holds no lines, so there is no ring to measure against"
        return records, stats

    # Only the types the ring applies to are measured - the exempt ones never
    # reach this table, so an exemption costs no query time and cannot be
    # accidentally undone by a later filter.
    candidates = [(at, record) for at, record in enumerate(records) if record["poi_type"] not in NETWORK_RING_EXEMPT_TYPES]
    con.execute("CREATE TABLE candidate (idx INTEGER, lon DOUBLE, lat DOUBLE)")
    con.executemany(
        "INSERT INTO candidate VALUES (?, ?, ?)",
        [(at, record["lon"], record["lat"]) for at, record in candidates],
    )

    inside = {row[0] for row in con.execute(near_network_sql("candidate", "idx", "lon", "lat")).fetchall()}

    # Then the boundaries, one layer at a time. Only the candidates the ring
    # ALREADY REJECTED are asked, so the cost is proportional to what the ring
    # dropped rather than to the layer, and a source whose boundary file is
    # missing simply admits nobody - the same direction an absent network
    # takes above.
    # `boundary_paths` is keyed by POI SOURCE, so several sources may name one
    # layer; group by the layer so its polygons are loaded once.
    by_layer: dict[Path, set[str]] = {}
    for source_key, path in boundary_paths.items():
        by_layer.setdefault(path, set()).add(source_key)

    for boundary_path, source_keys in sorted(by_layer.items()):
        outstanding = [(at, r) for at, r in candidates if at not in inside and r["source"] in source_keys]
        if not outstanding:
            continue
        if not load_boundary_polygons(con, boundary_path if boundary_path.exists() else None):
            continue
        con.execute("CREATE OR REPLACE TABLE boundary_candidate (idx INTEGER, lon DOUBLE, lat DOUBLE)")
        con.executemany(
            "INSERT INTO boundary_candidate VALUES (?, ?, ?)",
            [(at, r["lon"], r["lat"]) for at, r in outstanding],
        )
        admitted = {row[0] for row in con.execute(inside_boundary_sql("boundary_candidate", "idx", "lon", "lat")).fetchall()}
        if admitted:
            stats["boundary_kept"][boundary_path.stem] = len(admitted)
        inside |= admitted

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


def guide_records(registry: dict, raw_dir: Path = GUIDE_RAW_DIR, lines_dir: Path = RAW_DIR) -> tuple[list[dict], dict | None]:
    """NYNJTC's Long Path section guide, read as waypoints - and whether they may ship.

    The third input to this artifact and the first that is not an ArcGIS
    layer: forty web pages, parsed by lib/nynjtc_long_path_guide.py into
    parking lots with NYNJTC's own coordinates and lean-tos, springs,
    campsites and lookouts placed by walking the guide's mile along the
    registered `nynjtc_long_path` line. That module's docstring carries what
    is placed, what is not, and the measured error on the estimate.

    Returns (records, stats), where stats is None when the source is not
    registered at all. THE GATE IS THE ENTRY'S OWN `reaches_hikers`, read
    here the way every layer's is, but with one difference in how `main`
    treats the answer: a held-back guide is kept OUT of the manifest's
    `sources`. publish.py's gate on this artifact is all-or-nothing over that
    dict - one steward held back holds back every steward's points - and it
    is right to be, for lines and points a steward may still refuse. It
    would be wrong here: DEC's, OPRHP's and USFS's waypoints must not vanish
    from every phone because a fourth source is waiting on a licence
    answer. So a held-back guide's stats go under the manifest's
    `held_back_sources` instead, its records go to the review file, and the
    artifact is what it was before this source existed.

    A published guide (reaches_hikers true) with no cache on disk raises, as
    a missing layer does: the alternative is an artifact silently short of a
    source it is meant to carry. A held-back one with no cache is a line in
    the log - there was nothing to review and nothing to publish.
    """
    source = find_source(registry, GUIDE_KEY)
    if source is None:
        return [], None
    publishable = bool(source.get("reaches_hikers"))
    sections_path = raw_dir / "sections.json"
    lines_path = lines_dir / f"{GUIDE_LINE_KEY}.geojson"
    missing = [path for path in (sections_path, lines_path) if not path.exists()]
    base = {
        "steward": source.get("steward"),
        "attribution": source.get("attribution"),
        "reaches_hikers": publishable,
    }
    if missing:
        names = ", ".join(path.name for path in missing)
        if publishable:
            raise FileNotFoundError(
                f"{names} missing - {GUIDE_KEY} carries reaches_hikers: true, so this artifact must carry it. "
                "Run fetch_nynjtc_long_path_guide.py (the guide) and fetch_external_layers.py (the line it is placed along) first."
            )
        return [], {**base, "kept": 0, "reason": f"{names} not on disk; nothing to review"}
    sections = [Section.from_dict(data) for data in json.loads(sections_path.read_text(encoding="utf-8"))]
    features = json.loads(lines_path.read_text(encoding="utf-8")).get("features", [])
    records, stats = build_guide_records(sections, features)
    return records, {**base, **stats}


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


def write_artifact(records: list[dict], per_source: dict, ring: dict | None = None, held_back: dict | None = None) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / ARTIFACT_NAME
    path.write_text(json.dumps(records_to_geojson(records), separators=(",", ":")))

    by_type: dict[str, int] = {}
    for record in records:
        by_type[record["poi_type"]] = by_type.get(record["poi_type"], 0) + 1

    return {
        "path": to_manifest_path(path),
        "sha256": sha256_file(path),
        "feature_count": len(records),
        "by_type": {poi_type: by_type.get(poi_type, 0) for poi_type in POI_TYPES if by_type.get(poi_type)},
        "sources": per_source,
        # What the ring did, in the manifest rather than only in the log. Each
        # `sources` entry counts what its own layer contributed BEFORE the clip
        # (see main), so without this block the manifest's per-source figures
        # and its feature_count would disagree with no way to see why.
        **({"network_ring": ring} if ring is not None else {}),
        # Sources read and NOT carried, with why - outside `sources` so that
        # publish.py's all-or-nothing gate over that dict sees only what the
        # artifact actually holds (see guide_records).
        **({"held_back_sources": held_back} if held_back else {}),
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
            print(f"      {stats['low_confidence']:,} at low confidence ({low_confidence_reason(source)})")
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

    # NYNJTC's Long Path section guide - the one input here that is not a
    # layer. See guide_records for why a held-back guide stays out of
    # `per_source` and goes to a review file instead.
    held_back_sources: dict[str, dict] = {}
    guide, guide_stats = guide_records(registry)
    if guide_stats is not None:
        if "reason" in guide_stats:
            print(f"  {GUIDE_KEY}: {guide_stats['reason']}")
        else:
            print(
                f"  {GUIDE_KEY}: {guide_stats['kept']:,} waypoints from {guide_stats['sections']} section pages  {guide_stats['by_type']}"
            )
            print(
                f"      {guide_stats['entries_placed']['stated']:,} at NYNJTC's own coordinates, "
                f"{guide_stats['entries_placed']['interpolated']:,} placed by mile along the line (low confidence), "
                f"{guide_stats['duplicates_merged']:,} repeats merged"
            )
            for reason, count in guide_stats["skipped"].items():
                print(f"      skipped {count:>6,}  {reason}")
        if guide_stats["reaches_hikers"]:
            counts[GUIDE_KEY] = guide_stats["kept"]
            per_source[GUIDE_KEY] = guide_stats
            all_records.extend(guide)
        else:
            held_back_sources[GUIDE_KEY] = guide_stats
            if guide:
                OUT_DIR.mkdir(parents=True, exist_ok=True)
                review_path = OUT_DIR / GUIDE_REVIEW_NAME
                review_path.write_text(json.dumps(records_to_geojson(guide), separators=(",", ":")))
                print(
                    f"      HELD BACK: reaches_hikers is false, so none of these enter {ARTIFACT_NAME}; written for review to {review_path}"
                )

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
    all_records, ring = clip_to_network(
        all_records,
        OUT_DIR / NETWORK_ARTIFACT_NAME,
        boundary_paths_for(sources),
    )
    if ring["ran"]:
        print(
            f"\n  ring: {ring['dropped']:,} of {before:,} dropped further than "
            f"{ring['ring_feet']} ft from a published line "
            f"({', '.join(ring['exempt_types'])} exempt - see NETWORK_RING_EXEMPT_TYPES)"
        )
        for layer, admitted in sorted(ring.get("boundary_kept", {}).items()):
            print(f"      {admitted:,} kept by {layer} that the ring alone would have dropped")
        for key, count in list(ring["dropped_by_source_type"].items())[:8]:
            print(f"      dropped {count:>6,}  {key}")
    else:
        print(f"\n  ring: not applied - {ring.get('reason', 'no network artifact')}")

    # AFTER the ring, and the order is the argument again: a site must be
    # composed of waypoints that actually ship. Folding first would anchor a
    # site on a fountain the ring then removed, and the client would draw
    # nothing for the members riding a pin that is not in the artifact.
    sites = group_place_sites(all_records)
    site_props = site_properties(sites)
    folded = sum(len(site.members) for site in sites)
    for record in all_records:
        record.update(site_props.get(record["id"], {}))
    if sites:
        by_type: dict[str, int] = {}
        for site in sites:
            by_type[site.anchor["poi_type"]] = by_type.get(site.anchor["poi_type"], 0) + 1
        print(
            f"\n  sites: {len(all_records) - folded:,} marks from {len(all_records):,} waypoints - "
            f"{folded:,} fold onto {len(sites):,} pins at {PLACE_PROXIMITY_RADIUS_M:.0f} m "
            f"on a shared place name {by_type}"
        )
        largest = max(sites, key=lambda s: s.size())
        print(f"      largest: {largest.size()} at {largest.site_name!r}")

    manifest = write_artifact(all_records, per_source, ring, held_back_sources)
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
