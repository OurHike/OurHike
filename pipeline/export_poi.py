"""Export the unified POI schema (ROADMAP.md Phase 1 "Unified POI schema",
TECHNICAL_ARCHITECTURE.md's Export step): join ATC shelters/campsites/
vistas/parking/privies/Communities and opentrail.org's water/resupply tags
into one schema per
lib/poi_schema.py, clip to the 30-mile corridor, and write one GeoJSON +
one FlatGeobuf per poi_type under data/processed/poi/, with a SHA256 content
hash per artifact in a manifest (matching the "content hash per artifact"
principle TECHNICAL_ARCHITECTURE.md's Export step describes, and the same
change-aware-publish idea fetch_all.py's manifest already uses for raw
sources).

Corridor: built via lib/corridor.py's build_corridor() (shared with
export_trails.py - both used to carry an identical, verbatim-duplicated
copy of this function before that extraction) from
data/raw/centerline.geojson, mirroring spike_corridor.py's ST_Buffer(30mi) +
ST_Union_Agg pattern (including the always_xy gotcha - see README.md)
exactly, rather than reading data/spike/corridor.geojson, which is stale
proof-of-concept output.

Sources and what they feed (see README.md's source tables + real-feature
inspection, 2026-07-28):
  - shelters.geojson / campsites.geojson: ATC's own facility data, ~1:1
    with poi_type shelter/campsite. CONFIDENCE_HIGH - direct facility data.
  - viewpoints.geojson / parking.geojson / privies.geojson: three more of
    ATC's own facility layers, ~1:1 with poi_type viewpoint/parking/privy,
    CONFIDENCE_HIGH for the same reason shelters and campsites are - it is
    the maintaining organisation's inventory of things it maintains, not a
    proxy for them. Registered in sources.json since 2026-07-25 and fetched
    by fetch_all.py ever since; until this change nothing downstream read
    them. Together they roughly double the published POI count: 1,223
    vistas, 482 parking areas and 316 privies against the 2,532 already
    shipping (live counts, SOURCE_SURVEY.md 2026-08-09).
    Two things checked against the real layers rather than assumed
    (2026-08-09, all 2,021 features): `Name` is populated on 2,020 of them,
    so a nameless pin is the rare exception rather than the rule; and
    `Descriptio` is the same club-acronym-plus-name string lib/atc_notes.py
    already found unusable on shelters ("TBD" on every vista sampled), so
    their `description` is composed from the inventory columns like every
    other ATC layer's - see attach_descriptions and lib/poi_description.py.
    Not filtered by ATC's own `Status`, which on vistas takes values like
    "Primary View" (522), "Secondary View" (605), "Bypass" (23) and "OLD?"
    (4). Publishing all of them matches what every other layer here does -
    the corridor clip is the only filter - and the alternative would be
    inventing a meaning for codes ATC has not documented. Worth revisiting
    with ATC rather than by guessing.
  - communities.geojson: ATC's "official A.T. Community" towns, folded in
    as poi_type resupply at CONFIDENCE_LOW - a town being designated an
    A.T. Community isn't the same confidence as an actual tagged resupply
    point (see opentrail_at below).
  - opentrail_at.geojson: tagged via its `icon` property. Only "w" (water)
    and "r" (resupply) feed this export - matching README.md's documented
    role for this source (the water/resupply gap ATC's own data leaves).
    Real-data gotcha found while building this (2026-07-28): the `icon`
    value "s" has exactly 32 occurrences in the real file - a suspiciously
    shelter-sized count that a naive tag-count match could mistake for
    "shelter" - but every "s"-tagged feature actually inspected (title/desc)
    is a spring/stream/seasonal-water point ("Piped spring", "Seasonal Water
    Spigot", etc.), not a shelter. opentrail.org's real AT dataset has no
    shelter tag at all; ATC's own shelters.geojson is the only shelter
    source here. "s" is folded into poi_type water instead, at
    CONFIDENCE_LOW (seasonal/less reliable than the primary "w" tag) - see
    test_export_poi_opentrail_seasonal_water_tag_is_not_treated_as_shelter.
    "c" (opentrail's own campsite tag), "t" (town), "o" (other), and "j"
    (junction) aren't mapped to any poi_type here - "t"/"o"/"j" have no
    corresponding poi_type in this schema, and "c" would just be a lower-
    quality duplicate of ATC's own campsites.geojson.
  - osm_water.geojson: OSM's water point sources across the fourteen A.T.
    states (fetch_osm_water.py; #529, WATER_SOURCES.md §7 option 1), folded
    into poi_type water at CONFIDENCE_LOW - a mapped spring is somebody's
    one-time observation, not a maintained facility, and the low tier's
    dashed rim plus the card's "Unverified" sentence is exactly that claim.
    An absent file is a normal state (the fetch is conditional, like
    photos); the export ships opentrail's points alone, as it always did.
    Within WATER_DEDUP_RADIUS_M of an opentrail water point the OSM twin is
    dropped - opentrail imports OSM, so the overlap is largely the same
    node arriving twice, and the opentrail id is the one existing Reports
    may already reference.
  - trail_water.json: the two sources below, and the reason `crossing`
    stopped being an empty-but-present layer after shipping as one since it
    was declared.

Where the trail meets water (#529, build_trail_water.py): two more sources,
both read from reference/trail_water.json, both derived from the OSM state
extracts this pipeline already downloads.

  - CROSSINGS fill `crossing`, the poi_type declared in lib/poi_schema.py and
    empty since it was declared. Each is an exact geometric intersection of
    ATC's centerline with an OSM stream way - the two lines cross, so a hiker
    walking the trail walks through the water. Not a proximity guess, which
    is what #97 measured overshooting into thousands of near-misses.
  - SITE WATER folds into `water`: for each shelter and campsite, the nearest
    point on a stream, published ONLY where a hiker could reach it - inside
    100 ft and under a 35% grade, measured from real USGS elevations at both
    ends. A stream 90 ft away and 120 ft below is not a water source however
    close the map says it is. build_trail_water.py holds both gates and every
    rejection's numbers.

Neither needs a matching rule here: a published point sits at its real
coordinates, so lib/poi_sites.py's 60 m proximity fold attaches the site's
water to its pin exactly as it does an opentrail or OSM point, and #694's
synthesized CSI member yields to it automatically.

Capacity enrichment: shelter features carry `capacity`, how many people the
shelter sleeps, from reference/shelter_capacity.json. That file is checked in
rather than fetched, because ATC's shelter layer has no capacity field at all
and the numbers come from a hiker-maintained list joined to ATC's shelters by
name - a join worth reviewing in a diff. build_shelter_capacity.py builds it
and its docstring holds the provenance and the licence position. Coverage is
partial and deliberately so: a shelter the source lists only as half of a
pair exports no capacity rather than a guessed one, and the client shows
nothing rather than a number nobody stands behind.

Water-distance enrichment (#668, the CSI-distance slice of #529's
WATER_SOURCES.md): shelter and campsite features carry `water_distance_ft`,
how far ATC's Campsite Sustainability Index puts the nearest water source,
from reference/water_distance.json - the same checked-in-and-reviewed shape
as capacity, built by build_water_distance.py, whose docstring holds the
join, the provenance rule and the licence position. Feet because ATC's
figure is (CONTRIBUTING.md, "store canonical"). Where the site has no actual
water point folded in, a close-enough distance is also named among the nearby
parts - see attach_nearby - so the answer to "is there water" stops depending
on the 9 opentrail points that happen to fold. 305 of 512 features publish one
(the FarOut-measured rows joined on the maintainer's 2026-08-13
authorisation, sources.json's atc_licence block / #688); the rest have no
CSI neighbour (most of Maine) or an unreadable value, and publish nothing
rather than a neighbour's number. Wherever that entry fires, the site also
gains a water POI riding its pin - synthesize_csi_water (#694), a member at
inherited coordinates whose description says whose measurement it is and
that the spot is unmapped, yielding to any real mapped point that folds in.

Description: every ATC facility layer carries `description`, one sentence
about the place -

    "Two-storey clapboard shelter, sleeps 14, with a fireplace, a fire ring
     and a porch. Built 1915."
    "A 100° view south-east from a ridge or rock outcrop."
    "Gravel parking area, room for 12 cars."
    "Multi-seat moldering privy. Built 2019."

It is composed by lib/poi_description.py from ATC's own inventory columns
rather than copied from a text field, because ATC has no prose description:
the field aliased "Description" is the club acronym plus the feature's own
name, and `Comments` is a surveyor's notebook populated on under a third of
features (lib/atc_notes.py measures both). Composing instead of copying is
what makes the coverage 280/280 shelters, 232/232 campsites, 1,194/1,223
vistas, 480/482 parking areas and 314/316 privies. Where ATC did write a
usable comment it is appended as "ATC notes: ..." - attributed, not blended
in, since that half is a person's prose and the rest is assembled from
columns. Which types compose one is DESCRIBERS below; water and resupply do
not, having no inventory behind them.

Nearby parts (#614, #625): a site's anchor also carries `nearby`, the parts
around it as JSON rather than as prose -

    [{"phrase": "a multi-seat moldering privy", "distance_ft": 131.2},
     {"phrase": "a group campsite", "distance_ft": 82.0},
     {"phrase": "water", "distance_ft": 295.3}]

- which the client renders as its own sentence under the description, in the
units the hiker chose:

    "Nearby: a multi-seat moldering privy 130 ft away, a group campsite 82 ft
     and water 295 ft."

A separate sentence, never folded into the "with" clause - a shelter does not
have a privy and a water source inside it, and the parts are separate points a
short walk away. It exists because the site grouping below took those points
off the map: they still compose perfectly good sentences of their own, attached
to features that draw no pin.

**Published as structure because prose cannot ask the phone a question.** This
was one composed clause inside `description` until #625: the pipeline wrote
"40 m away" into it, so a hiker who chose Feet in Settings read metres on the
one card in the app that could not answer them, and re-exporting the corridor
was the only way to change a word of it. The noun phrases are still composed
here - they are ATC's inventory read aloud and nothing about them depends on
the reader - and the distance now travels as a number in ATC's own feet.

Photo enrichment: when fetch_poi_images.py has run, data/raw/poi_images.json
holds per-POI photo records (Wikimedia Commons; author, licence, capture date
and the digest of the downloaded image) keyed by the same unified ids this
export writes, and those ride along on the exported features as photo_*
properties. The feature carries `photo_key` - the bucket key our own copy is
served under (#362) - never the Commons URL, so a card never depends on
somebody else's host. The file being absent
is a normal state, not an error - the export ships photo-less features and
the client card shows its category placeholder. Per-photo licensing is why
attribution travels per-feature instead of as one registry line (see
CONTRIBUTING.md "A note on data and licences").

Site grouping (#523, features/POI_SITES.md): a shelter, its privy and its
campsites are one place with parts, and this export used to publish them as
unrelated points. The map then resolved the crowding by DELETING all but one -
`icon-allow-overlap: false` drops the pin that loses POI_PRIORITY, and at zoom
14 that left 3% of the corridor's 316 privies drawn anywhere on the trail. A
hiker saw a clean map and concluded there was no privy.

lib/poi_sites.py resolves the grouping from ATC's own naming convention
("Mt. Algo Shelter Privy") gated on proximity, and `attach_sites` writes it onto
the features as `site_id`, `site_role` and `site_name`. Measured over the live
corridor: 428 POIs fold into 291 sites, 90% of privies and 62% of campsites stop
competing for a pin and start riding one that is actually drawn. The properties
are additive, so a client built before this ignores them and behaves exactly as
it does today.

The cost, stated where the code is rather than only in the design doc: a wrong
grouping is baked into the artifacts and a hiker cannot undo it. The rule needs
name agreement AND proximity for exactly that reason - see lib/poi_sites.py for
what each gate is holding up, and what a name-only rule ships. Since #614 that
cost is louder rather than quieter: a mis-grouped privy is now named on the
wrong shelter's card, where before it was only a pin that went missing.
"""

import hashlib
import json
import sys
from pathlib import Path

import duckdb

from lib.atc_notes import clean_note
from lib.completeness import count_problems, fail_if_incomplete
from lib.corridor import build_corridor
from lib.photo_store import photo_key
from lib.poi_description import (
    describe_campsite,
    describe_parking,
    describe_privy,
    describe_shelter,
    describe_stream_point,
    describe_viewpoint,
    describe_water,
    nearby_parts,
)
from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES, poi_output_name, unify_poi
from lib.poi_sites import ANCHOR_TYPES, NAME_MATCH_RADIUS_M, ROLE_ANCHOR, ROLE_MEMBER, group_sites, site_properties
from lib.spurs import distance_m

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed" / "poi"

# build_shelter_capacity.py's output. Under reference/, not data/raw/, because
# it is reviewed source rather than a fetch artifact - see that script's
# docstring for why the join it encodes is checked in.
CAPACITY_PATH = ROOT / "reference" / "shelter_capacity.json"

# build_water_distance.py's output, under reference/ for the same reason.
WATER_DISTANCE_PATH = ROOT / "reference" / "water_distance.json"

# build_trail_water.py's output, under reference/ for those reasons plus one
# of its own: NHD is a frozen snapshot, so fetching it per build would
# re-download an unchanging answer (that script's docstring).
TRAIL_WATER_PATH = ROOT / "reference" / "trail_water.json"

# Metres per foot, for the places the two units meet: a site member's
# distance is measured in metres (the equirectangular gate that grouped it) and
# published in feet (what `nearby` states, and what lib/units.ts formats from).
#
# ATC's own water distance needs no conversion in either direction now - it is
# feet in the column and feet in `nearby`. It used to be turned into metres
# here purely so the pipeline could write "water 90 m" into a sentence, which
# is the round trip #625 removed: ATC published feet, an imperial hiker asked
# for feet, and this converted it away in between.
M_PER_FT = 0.3048

# How far away water may be and still be named among the nearby parts.
# lib/poi_sites.py's NAME_MATCH_RADIUS_M is the widest gate that can fold a
# real member into a site, so it is the furthest distance "Nearby" already
# claims anywhere - reusing it keeps the word meaning one thing. A distance
# beyond it still publishes as `water_distance_ft`; it just is not "Nearby".
NEARBY_WATER_MAX_FT = NAME_MATCH_RADIUS_M / M_PER_FT

# fetch_poi_images.py's output, read relative to RAW_DIR at call time (not a
# frozen module constant) so redirecting RAW_DIR - as every test here does -
# redirects this with it.
IMAGES_FILENAME = "poi_images.json"

# fetch_atc_photos.py's output, read the same way. Two photo sources, and the
# precedence between them is not a toss-up: ATC's are photographs *of the
# facility*, taken by the organisation that maintains it, where a Commons hit
# is the nearest openly-licensed file to a coordinate and measurably often a
# photograph of a plant (features/POI_PHOTOS.md). ATC wins wherever both have
# one; Commons still fills water and resupply POIs, which ATC's layers do not
# cover at all.
ATC_IMAGES_FILENAME = "poi_images_atc.json"

# What travels from a fetched photo record onto the exported feature. Kept to
# what the card actually renders (credit line + link) plus the capture date -
# honesty about a photo's age is data, not decoration (OurHikeValues.md #4).
# `url` is deliberately absent: it is the Commons source of the bytes, kept
# in the raw fetch record as provenance, but the card must never fetch it -
# that is the hotlink #362 removed. `photo_key` is added separately by
# attach_photos, derived from the digest rather than copied.
PHOTO_FIELDS = ("page_url", "author", "license", "taken")

# The published column list, in order, as (name, DuckDB type). One list
# rather than a DDL string beside a hand-counted row of `?` placeholders,
# which is what this was until capacity needed adding to all three places at
# once. The reason to collapse them is that the mismatch does not raise: add
# a column to the DDL and forget the value tuple and every column after it
# shifts by one, exporting a photo credit as a capacity in valid GeoJSON.
POI_COLUMNS = (
    ("id", "VARCHAR"),
    ("poi_type", "VARCHAR"),
    ("trail_id", "VARCHAR"),
    ("source", "VARCHAR"),
    ("source_feature_id", "VARCHAR"),
    ("name", "VARCHAR"),
    ("lat", "DOUBLE"),
    ("lon", "DOUBLE"),
    ("confidence", "VARCHAR"),
    # How many people the shelter sleeps; NULL on every other poi_type and on
    # shelters nobody has published a usable number for.
    ("capacity", "INTEGER"),
    # How far ATC's Campsite Sustainability Index puts the nearest water
    # source, in feet because ATC's figure is. Shelters and campsites only;
    # NULL wherever reference/water_distance.json states a refusal instead of
    # a number (#668, build_water_distance.py).
    ("water_distance_ft", "INTEGER"),
    # One sentence about the place, composed from ATC's own inventory by
    # lib/poi_description.py - every ATC facility layer, which is DESCRIBERS
    # below; NULL on water and resupply, which have no inventory to compose
    # from.
    ("description", "VARCHAR"),
    # The parts around a site's anchor, as JSON: a noun phrase per part and how
    # far it is in feet, nearest-first within lib/poi_description.NEARBY_ORDER
    # (#614, #625). NULL on every POI that anchors no site.
    #
    # STRUCTURE, NOT THE SENTENCE. This carried its own prose inside
    # `description` until a hiker who had chosen Feet in Settings read metres
    # off it - published prose cannot ask a phone anything. The client composes
    # the sentence (client/src/lib/nearbyClause.ts) and writes the distance in
    # the system that hiker chose; the words that do not depend on the reader
    # are still ATC's inventory, still composed here.
    #
    # A string rather than a nested array for the reason `photos` is one:
    # FlatGeobuf property values are scalars, and GDAL re-expands a JSON-shaped
    # string into real JSON when it writes the .geojson - so the two artifacts
    # genuinely disagree about this field's type and the client reads both.
    ("nearby", "VARCHAR"),
    ("photo_key", "VARCHAR"),
    ("photo_page_url", "VARCHAR"),
    ("photo_author", "VARCHAR"),
    ("photo_license", "VARCHAR"),
    ("photo_taken", "VARCHAR"),
    # Every photo for this POI as JSON, card photo first. A string rather than
    # a nested array because FlatGeobuf property values are scalars - see
    # attach_photos, and note GDAL re-expands it to real JSON in the .geojson.
    ("photos", "VARCHAR"),
    # Which SITE this POI belongs to - a shelter with its privy and campsites,
    # modelled as one place with parts (#523, lib/poi_sites.py). The anchor's own
    # id, its `anchor`/`member` role, and the anchor's display name.
    #
    # NULL on every POI that is not in a site, which is most of them: 719 of the
    # corridor's points carry these and the rest do not. Additive on purpose - a
    # client built before this ignores them and behaves exactly as it does today,
    # the same rule `mile`, `capacity`, `description` and `photos` are held to.
    ("site_id", "VARCHAR"),
    ("site_role", "VARCHAR"),
    ("site_name", "VARCHAR"),
)

TRAIL_ID = "AT"

# Where unify_all_sources parks a feature's own ATC attributes so
# attach_descriptions can compose from them. Underscored because it is
# scaffolding between two steps of this module, not part of the schema:
# write_poi_type reads POI_COLUMNS and never sees it.
RAW_PROPERTIES_KEY = "_source_properties"

# ATC's free-text column on the shelter and campsite layers. Named `Comments`,
# not `Descriptio` - see lib/atc_notes.py for why the field actually aliased
# "Description" is unusable (it is the club acronym plus the feature's name).
ATC_NOTE_FIELD = "Comments"

# The source name ATC shelters get in unified ids. Named rather than repeated
# because shelter_capacity.json stores bare ATC GlobalIDs, and the id it must
# be joined on is composed from this - in one place, the way unify_poi
# composes every other id.
SHELTER_SOURCE = "atc_shelters"

# The campsite twin, for the same reason: water_distance.json stores bare
# GlobalIDs against a `layer` name, and load_water_distances composes the
# unified id from these two constants.
CAMPSITE_SOURCE = "atc_campsites"

# water_distance.json's `layer` values (sources.json keys) -> the source name
# unified ids are built from.
WATER_DISTANCE_SOURCES = {"shelters": SHELTER_SOURCE, "campsites": CAMPSITE_SOURCE}

# The source stamped on the water POIs synthesize_csi_water builds from those
# distances (#694). ATC's CSI states how FAR water is from a site and never
# WHERE, so the point inherits its anchor's coordinates and rides the site as
# a member - drawing no pin of its own (#524) - while its description says
# exactly what is known: the distance, whose measurement it is, and that the
# spot is unmapped. Everything that must tell a real water point from this
# kind keys on this constant: the nearby clause reads coordinates only from
# real members, synthesis yields to a real member, and
# client/src/chrome/poiSources.ts turns it into words on the card.
CSI_WATER_SOURCE = "atc_csi"

# (raw filename stem, poi_type, source name used in unified ids, field_map)
# - the ATC sources that map ~1:1 onto one poi_type each.
#
# The five facility layers share a field_map exactly, because they share a
# schema exactly: every layer on ATC's ANST_Facilities service carries the
# same `GlobalID`/`Name` pair (checked against the live service 2026-08-09).
# Spelled out per source rather than collapsed to a loop, so a layer that
# turns out to differ can differ here instead of somewhere clever.
ATC_FACILITY_FIELDS = {"id_field": "GlobalID", "name_field": "Name", "confidence": CONFIDENCE_HIGH}

DIRECT_SOURCES = (
    ("shelters", "shelter", SHELTER_SOURCE, ATC_FACILITY_FIELDS),
    ("campsites", "campsite", CAMPSITE_SOURCE, ATC_FACILITY_FIELDS),
    ("viewpoints", "viewpoint", "atc_viewpoints", ATC_FACILITY_FIELDS),
    ("parking", "parking", "atc_parking", ATC_FACILITY_FIELDS),
    ("privies", "privy", "atc_privies", ATC_FACILITY_FIELDS),
    (
        "communities",
        "resupply",
        "atc_communities",
        {"id_field": "GlobalID", "name_field": "NAME", "confidence": CONFIDENCE_LOW},
    ),
)

# opentrail.org's `icon` property -> (poi_type, confidence). See the module
# docstring for why "s" maps to water (not shelter) and why "c"/"t"/"o"/"j"
# aren't mapped at all.
OPENTRAIL_ICON_MAP = {
    "w": ("water", CONFIDENCE_HIGH),
    "s": ("water", CONFIDENCE_LOW),
    "r": ("resupply", CONFIDENCE_HIGH),
}
OPENTRAIL_SOURCE = "opentrail_at"
OPENTRAIL_FIELD_MAP_BASE = {"id_field": "dbid", "name_field": "title"}

# fetch_osm_water.py's output. CONFIDENCE_LOW on every point - a mapped
# spring is one contributor's observation on one day, which is precisely the
# claim the low tier's dashed rim and "Unverified" card sentence make. Most
# springs are unnamed, so `name` is simply absent on most features and the
# card leads with its type line, as it does for opentrail's unnamed points.
OSM_WATER_SOURCE = "osm_water"
OSM_WATER_FILENAME = "osm_water.geojson"
OSM_WATER_FIELD_MAP = {"id_field": "osm_id", "name_field": "name", "confidence": CONFIDENCE_LOW}

# build_trail_water.py's two products (#529). Both CONFIDENCE_LOW, and for
# the same reason as OSM's points rather than a weaker one: nobody stood at
# either. A crossing is where two independently digitised lines meet, and a
# site's water is where geometry says a stream runs nearest a shelter - both
# are derivations, and the dashed rim plus the card's "Unverified" line is
# exactly what a derivation is worth until somebody walks it.
NHD_CROSSING_SOURCE = "nhd_crossing"
NHD_STREAM_SOURCE = "nhd_stream"

# A crossing's identity is WHERE it is, not which reach it belongs to: NHD
# splits reaches at confluences, so one reach can cross the trail twice and
# a reach id alone would collide. Five decimal places is about a metre -
# finer than the geometry, coarse enough that the id is stable while the
# snapshot is frozen (which is forever, per build_trail_water.py).
CROSSING_ID_PRECISION = 5

# How close an OSM water point must sit to an opentrail one to be its twin.
# Measured before choosing (2026-08-13, 174 opentrail water points against
# all 7,574 OSM nodes): 37 opentrail points have an OSM node within 15 m and
# 41 within 25 m, then the tail thins to real neighbours - by 50-100 m the
# pairs are plausibly a spring and a separate stream access, two facts a
# hiker wants both of. 25 m keeps the measured duplicate cluster and nothing
# past it. The opentrail record is the one kept: its id is the one already
# published, so a Report filed against it stays attached.
WATER_DEDUP_RADIUS_M = 25.0


def load_features(path: Path) -> list[dict]:
    """Read a raw GeoJSON file's features as plain Python dicts."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("features", [])


def load_photo_records(path: Path) -> dict[str, list[dict]]:
    """A fetch's found photos keyed by unified POI id, or {} when that script
    hasn't run - which is a normal, exportable state, not an error. Only
    "found" outcomes matter here; a recorded miss and an unchecked POI both
    export the same way, photo-less.

    Always a list, whichever shape the outcome file uses. fetch_poi_images.py
    records one `photo` per POI (Commons gives one nearest match);
    fetch_atc_photos.py records a `photos` list (ATC gives up to ten). Reading
    both here means the rest of the export has one shape to think about."""
    if not path.exists():
        return {}
    outcomes = json.loads(path.read_text(encoding="utf-8")).get("pois", {})
    found = {}
    for poi_id, record in outcomes.items():
        if record.get("status") != "found":
            continue
        photos = record["photos"] if "photos" in record else ([record["photo"]] if "photo" in record else [])
        if photos:
            found[poi_id] = photos
    return found


def load_capacities(path: Path) -> dict[str, int]:
    """shelter_capacity.json's known capacities, keyed by the same unified
    POI id this export writes.

    Only records that state a capacity are returned. The file lists every ATC
    shelter, most of the blanks carrying a reason the source could not be
    split or read (see build_shelter_capacity.py); to this export a blank and
    an absent record are the same thing - no capacity to publish.

    A missing file is a normal state, not an error, for the same reason
    load_photo_records tolerates one: the export's job is to ship what exists.
    """
    if not path.exists():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    return {
        f"{SHELTER_SOURCE}:{record['atc_global_id']}": record["capacity"]
        for record in document.get("shelters", [])
        if record.get("capacity") is not None
    }


def attach_capacity(records: list[dict], capacities: dict[str, int]) -> int:
    """Copy each matched shelter's capacity onto its unified POI record,
    returning how many matched. Unmatched records are left without the key -
    write_poi_type reads it with .get(), and NULL is the honest export of
    "nobody has said", which is not the same as a small shelter."""
    attached = 0
    for record in records:
        capacity = capacities.get(record["id"])
        if capacity is None:
            continue
        record["capacity"] = capacity
        attached += 1
    return attached


def load_water_distances(path: Path) -> dict[str, int]:
    """water_distance.json's known distances, keyed by the same unified POI
    id this export writes.

    Only records that state a distance are returned - the file lists every
    shelter and campsite, the blanks carrying the reason there is no number
    (no CSI row nearby, a 0 ft value nobody can read; see
    build_water_distance.py). To this export a blank and an absent record are
    the same thing: no distance to publish.

    A missing file is a normal state, not an error, exactly as it is for
    capacities and photos: the export's job is to ship what exists.
    """
    if not path.exists():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    distances = {}
    for record in document.get("sites", []):
        source = WATER_DISTANCE_SOURCES.get(record.get("layer"))
        if source is None or record.get("distance_ft") is None:
            continue
        distances[f"{source}:{record['atc_global_id']}"] = record["distance_ft"]
    return distances


def attach_water_distance(records: list[dict], distances: dict[str, int]) -> int:
    """Copy each matched feature's water distance onto its unified POI
    record, returning how many matched - same contract as attach_capacity,
    and NULL means the same thing: nobody has said, which is not the same as
    a dry site."""
    attached = 0
    for record in records:
        distance = distances.get(record["id"])
        if distance is None:
            continue
        record["water_distance_ft"] = distance
        attached += 1
    return attached


def _is_real_water(member: dict) -> bool:
    """A water member that is an actual mapped point, as opposed to one this
    export synthesized from a distance. The two make different claims - a
    point knows where, a synthesized member only how far - and every place
    that treats members as coordinates has to ask this first."""
    return member["poi_type"] == "water" and member.get("source") != CSI_WATER_SOURCE


def synthesize_csi_water(records: list[dict]) -> int:
    """Give every card that says "Nearby: water N m" a water POI riding its
    site (#694), returning how many were added.

    The nearby entry attach_nearby publishes from `water_distance_ft` used to
    be the only trace of ATC's distance: the pin's footer strip and the
    card's chip strip are built from site MEMBERS, and no member existed -
    CSI publishes no coordinates to make one from, and no real mapped point
    sits near most of these sites (measured 2026-08-13: of 247 spliced cards,
    16 have any real water point within 150 m). So the maintainer's call: the
    point INHERITS THE ANCHOR'S COORDINATES and says so. A member draws no
    pin of its own (#524), so the inherited location is never drawn as a dot
    somewhere water is not; what a hiker sees is the water glyph on the pin,
    a chip that opens a card, and a card saying whose measurement it is and
    that the spot is unmapped. PoiCard's chip prints the member's own
    `water_distance_ft` rather than the zero the inherited coordinates would
    measure - in the hiker's own units since #625, which is also why the
    figure is no longer written into the description below.

    One per site, and only where the sentence fired: a distance beyond
    NEARBY_WATER_MAX_FT stays a column (a site is a sub-150 m place, and a
    member half a kilometre off is not a part of it). A site holding a REAL
    water member never gets one, so the moment an actual mapped point folds
    in - opentrail today, OSM when #529's fetch lands - the synthesized
    member stops being produced and the real point speaks. CONFIDENCE_LOW,
    because the client's dashed rim and "Unverified" line are the right
    posture for a point nobody can stand at.

    Runs after attach_sites and attach_water_distance (it reads both) and
    before attach_nearby (which must know these members carry no coordinate
    worth measuring).
    """
    members_by_site = site_members(records)
    synthesized = []
    for record in records:
        if record["poi_type"] not in ANCHOR_TYPES or record.get("site_role") == ROLE_MEMBER:
            continue
        distance_ft = record.get("water_distance_ft")
        if distance_ft is None:
            continue
        # The same gate attach_nearby applies, in the same unit, so synthesis
        # fires exactly where the nearby entry does. That is the invariant this
        # whole function rests on - a member for every card that promises water
        # and none for a card that does not - and two spellings of one distance
        # is how it would quietly stop holding.
        if distance_ft > NEARBY_WATER_MAX_FT:
            continue
        if any(_is_real_water(member) for member in members_by_site.get(record.get("site_id"), ())):
            continue

        # A lone shelter becomes a two-part site: the glyph and the chip both
        # hang off site properties, and the anchor may not have had any.
        if record.get("site_id") is None:
            record["site_id"] = record["id"]
            record["site_role"] = ROLE_ANCHOR
            record["site_name"] = record.get("name")

        anchor_name = record.get("name")
        placed_on = f"the {record['poi_type']}" if not anchor_name else anchor_name
        synthesized.append(
            {
                "id": f"{CSI_WATER_SOURCE}:{record['source_feature_id']}",
                "poi_type": "water",
                "trail_id": record["trail_id"],
                "source": CSI_WATER_SOURCE,
                "source_feature_id": record["source_feature_id"],
                "name": f"Water near {anchor_name}" if anchor_name else "Water",
                "lat": record["lat"],
                "lon": record["lon"],
                "confidence": CONFIDENCE_LOW,
                "water_distance_ft": distance_ft,
                # THE DISTANCE IS NOT IN THE SENTENCE, and that is #625 applied
                # to #694 rather than a change of mind about either. This read
                # "About 37 m from Chairback Gap Lean-to." until the merge, and
                # a metre is a metre in published prose however the hiker set
                # Settings - which is the whole defect #625 exists to close, on
                # a card that would have been the last one still showing it.
                #
                # Nothing is lost by taking it out: `water_distance_ft` rides
                # this member as its own column, so the chip directly above this
                # sentence prints the same figure in the hiker's own units, and
                # so does the anchor's nearby line. What stays here is what only
                # this sentence can say - whose measurement it is, and that the
                # spot itself is unmapped.
                "description": (
                    f"ATC measured how far water is from {placed_on}; the spot itself is not mapped, "
                    f"so this point sits on the {record['poi_type']}."
                ),
                "site_id": record["site_id"],
                "site_role": ROLE_MEMBER,
                "site_name": record.get("site_name"),
            }
        )
    records.extend(synthesized)
    return len(synthesized)


# Which poi_types compose a `description`, and with what. Every ATC facility
# layer is here; water and resupply are absent because they come from
# opentrail.org and ATC's Communities layer, neither of which carries an
# inventory to compose from.
#
# One signature - (properties, capacity, note) - so the dispatch is a lookup
# rather than a chain of branches. Only the shelter needs the capacity, and it
# is not ATC's number (reference/shelter_capacity.json), which is why it is
# passed rather than read from the properties; the lambdas absorb the
# difference, which is what they are here for.
#
# `nearby` was a fourth argument until #625 took the parts out of the sentence.
# It is attach_nearby's own column now, and no describer knows about it.
DESCRIBERS = {
    "shelter": lambda properties, capacity, note: describe_shelter(properties, capacity, note),
    "campsite": lambda properties, _capacity, note: describe_campsite(properties, note),
    "viewpoint": lambda properties, _capacity, note: describe_viewpoint(properties, note),
    "parking": lambda properties, _capacity, note: describe_parking(properties, note),
    "privy": lambda properties, _capacity, note: describe_privy(properties, note),
    # Composes for OSM points (whose tags carry `kind` and the reliability
    # tags) and for build_trail_water.py's stream points (which carry NHD's
    # flow class); an opentrail point has an icon and a title and composes
    # None, exactly as before this entry existed.
    "water": lambda properties, _capacity, _note: describe_water(properties),
    "crossing": lambda properties, _capacity, _note: describe_stream_point(properties),
}


def attach_sites(records: list[dict]) -> tuple[int, int]:
    """Group co-located waypoints into sites and write the three site
    properties onto every anchor and member (#523, lib/poi_sites.py).

    Returns (sites, folded members) for the run log, because a count that moves
    between releases is the thing to notice: this grouping is baked into the
    artifacts and a hiker cannot undo it, so a jump in either number means ATC's
    naming changed under us.

    Runs before the capacity, description and photo attaches, and that is not
    arbitrary. The grouping depends on exactly two fields - `name` and the
    position - both of which exist the moment the sources are unified, so
    nothing any enrichment step does can perturb it. Placing it first is what
    makes that independence visible rather than merely true today.
    """
    sites = group_sites(records)
    properties = site_properties(sites)
    for record in records:
        record.update(properties.get(record["id"], {}))
    return len(sites), sum(len(site.members) for site in sites)


def site_members(records: list[dict]) -> dict[str, list[dict]]:
    """Site id -> the records riding that site's anchor.

    Read back off the three properties attach_sites already published rather
    than threaded through from the Site objects, and that is the point of doing
    it this way: `site_id` and `site_role` are the interface the client reads,
    so a sentence composed from them cannot describe a grouping different from
    the one the map draws. It also leaves attach_sites' signature alone.

    Empty when attach_sites has not run, which is how a caller that only wants
    descriptions - and every test written before sites existed - still gets
    exactly the sentences it got before.
    """
    members: dict[str, list[dict]] = {}
    for record in records:
        if record.get("site_role") == ROLE_MEMBER and record.get("site_id"):
            members.setdefault(record["site_id"], []).append(record)
    return members


def attach_descriptions(records: list[dict]) -> int:
    """Compose `description` for every POI type that has one, returning how
    many got one.

    Runs after attach_capacity, because "sleeps 8" is a clause in the composed
    sentence and that number is not on the feature ATC published - it comes
    from reference/shelter_capacity.json. A record without one gets the same
    sentence without that clause rather than a gap.

    It no longer needs attach_sites or attach_water_distance to have run: the
    parts around an anchor are attach_nearby's column since #625, and this
    sentence says nothing about them.
    """
    attached = 0
    for record in records:
        describe = DESCRIBERS.get(record["poi_type"])
        if describe is None:
            continue
        properties = record.get(RAW_PROPERTIES_KEY) or {}
        description = describe(properties, record.get("capacity"), clean_note(properties.get(ATC_NOTE_FIELD)))
        if description is None:
            continue
        record["description"] = description
        attached += 1
    return attached


def attach_nearby(records: list[dict]) -> int:
    """Publish `nearby` on every anchor that has parts around it, returning how
    many got one.

    Runs after attach_sites (#614), because these ARE the site's members, and
    after attach_water_distance, because ATC's distance-to-water is one of the
    parts. Run without either and nothing here is reachable: no record carries
    a site role, the loop writes nothing, and every card is what it was before
    sites existed. And after synthesize_csi_water (#694), whose members are
    skipped here rather than measured - they sit ON the anchor, so their
    position is not a distance.

    Its own pass rather than a branch inside attach_descriptions (#625), and
    the split is the point rather than tidiness. That function composes a
    sentence; this one publishes measurements. They were one pass while the
    measurements WERE part of the sentence, which is exactly the coupling that
    made a hiker's unit preference unanswerable - the distance could not reach
    the phone without the words already wrapped around it.
    """
    members_by_site = site_members(records)
    attached = 0
    for record in records:
        parts = []
        if record.get("site_role") == ROLE_ANCHOR:
            parts = [
                # Measured from the anchor, which is the one point of this
                # site a hiker can see - it is the only pin drawn - and so
                # the only place the distance is a distance from. A
                # synthesized water member is excluded exactly because it has
                # no coordinate worth measuring - it SITS on the anchor
                # (#694), and reading its position as a distance would print
                # "water 3 ft" on a card whose truth is the entry below.
                (
                    member["poi_type"],
                    distance_m(record["lat"], record["lon"], member["lat"], member["lon"]) / M_PER_FT,
                    member.get(RAW_PROPERTIES_KEY) or {},
                )
                for member in members_by_site.get(record["site_id"], ())
                if member.get("source") != CSI_WATER_SOURCE
            ]
        # ATC's own distance-to-water fills in where no actual water point
        # folded into the site (#668) - which is nearly everywhere, since only
        # 9 opentrail points fold over the whole corridor. Anchors and POIs in
        # no site both take it; a member does not, because its site's anchor
        # already answers "is there water" for the one pin a hiker can see.
        # Never beside a real water member: one site, one water distance.
        # (The synthesized member #694 adds for this same distance is not a
        # real one - it is excluded above, and this entry is what speaks.)
        if (
            record["poi_type"] in ANCHOR_TYPES
            and record.get("site_role") != ROLE_MEMBER
            and record.get("water_distance_ft") is not None
            and not any(poi_type == "water" for poi_type, _, _ in parts)
        ):
            # Straight through in ATC's own feet. Beyond the widest radius a
            # site can reach, "Nearby" would be a word meaning something
            # different on this one card; the column still publishes, the
            # sentence stays honest.
            if record["water_distance_ft"] <= NEARBY_WATER_MAX_FT:
                parts.append(("water", float(record["water_distance_ft"]), {}))
        if not parts:
            continue
        # JSON on the record, for the reason attach_photos writes a string:
        # FlatGeobuf property values are scalars, so a nested array cannot be a
        # column at all.
        record["nearby"] = json.dumps(nearby_parts(parts))
        attached += 1
    return attached


def attach_photos(records: list[dict], photos: dict[str, list[dict]]) -> int:
    """Copy each matched POI's photos onto its unified record, returning how
    many POIs matched. Unmatched records are left without the keys entirely -
    write_poi_type reads them with .get(), and a NULL column is the honest
    export of "no photo", the same shape the client's card treats as its
    placeholder.

    Two shapes go out, and the duplication is deliberate:

    - **The flat `photo_*` fields describe the first photo**, exactly as they
      always have. A client built before galleries existed keeps rendering the
      card photo instead of breaking on a shape it has never seen.
    - **`photos` is the whole list, JSON-encoded.** FlatGeobuf property values
      are scalars, so a nested array cannot be a column at all; a JSON string
      is what fits through both .fgb and .geojson unchanged.

    A photo with no `digest` is skipped rather than exported: since #362 the
    image is served from our own bucket, and the digest is the only thing that
    names it there. A record without one predates the download step, so there
    is nothing for a card to point at - and exporting the upstream URL instead
    would silently reintroduce the hotlink that change removed.
    """
    attached = 0
    for record in records:
        usable = [photo for photo in photos.get(record["id"], []) if photo.get("digest")]
        if not usable:
            continue
        first = usable[0]
        for field in PHOTO_FIELDS:
            record[f"photo_{field}"] = first.get(field)
        # The bucket key, not a URL: the host a hiker fetches from is the
        # client's build-time VITE_DATA_BASE_URL, and baking one into
        # published data would break every card the day the bucket or CDN
        # in front of it changes. Every other artifact is named the same way.
        record["photo_key"] = photo_key(first["digest"])
        record["photos"] = json.dumps(
            [{"key": photo_key(photo["digest"]), **{field: photo.get(field) for field in PHOTO_FIELDS}} for photo in usable],
            separators=(",", ":"),
        )
        attached += 1
    return attached


def has_geometry(feature: dict) -> bool:
    """Whether a raw feature carries a location at all.

    ATC's layers contain the occasional empty row - one parking feature
    (`ebb7706f-ed9a-432e-87b1-8d949917f66c`) has no geometry, no name and no
    attributes, and is the only one of the 2,533 features across all five
    facility layers. A row like that is not a POI: it cannot be drawn, found
    by search, or reported against, and verify_release.py fails a release
    that publishes a feature with no geometry.

    Skipped rather than fatal, which is the distinction unify_poi cannot
    make on its own. **A feature with no geometry is bad data upstream; a
    feature with a non-Point geometry is a wiring mistake here** - the wrong
    layer plugged into a point source - so that one still raises. Before
    this split, the empty parking row took down the whole export, and with
    it every artifact of the release behind it.
    """
    return bool((feature.get("geometry") or {}).get("type"))


def unify_all_sources(trail_id: str = TRAIL_ID, skipped: list[str] | None = None) -> list[dict]:
    """Load and unify every configured source (reading RAW_DIR at call
    time, not a pre-baked path, so tests can point it at a tmp_path fixture
    dir) into one flat list of unified POI dicts - no corridor clip applied
    yet, see clip_to_corridor.

    Features with no geometry are skipped and counted - see has_geometry.
    The count is returned to the caller through `skipped`, a list it owns,
    because a source that starts shedding rows is a thing to notice across a
    whole run and this function's return shape is load-bearing (
    fetch_poi_images.py and fetch_atc_photos.py both call it).
    """
    unified = []
    for stem, poi_type, source, field_map in DIRECT_SOURCES:
        for feature in load_features(RAW_DIR / f"{stem}.geojson"):
            if not has_geometry(feature):
                if skipped is not None:
                    skipped.append(f"{source}:{(feature.get('properties') or {}).get('GlobalID')}")
                continue
            record = unify_poi(feature, poi_type, source, trail_id, field_map)
            # The source feature's own attributes, kept for attach_descriptions
            # to compose from. Underscored and dropped before write_poi_type -
            # nothing here is published. It rides on the record rather than
            # being returned alongside because fetch_poi_images.py calls this
            # function for its POI list and would break on a new return shape.
            record[RAW_PROPERTIES_KEY] = feature.get("properties") or {}
            unified.append(record)

    for feature in load_features(RAW_DIR / "opentrail_at.geojson"):
        icon = (feature.get("properties") or {}).get("icon")
        mapping = OPENTRAIL_ICON_MAP.get(icon)
        if mapping is None:
            continue
        # Same guard as the ATC layers above. opentrail.org has no empty row
        # today, and "today" is exactly the qualifier that made this an
        # outage: the shelter and campsite layers had none either, right up
        # until three more layers were added beside them.
        if not has_geometry(feature):
            if skipped is not None:
                skipped.append(f"{OPENTRAIL_SOURCE}:{(feature.get('properties') or {}).get('dbid')}")
            continue
        poi_type, confidence = mapping
        field_map = {**OPENTRAIL_FIELD_MAP_BASE, "confidence": confidence}
        unified.append(unify_poi(feature, poi_type, OPENTRAIL_SOURCE, trail_id, field_map))

    # Absent is a normal state, not an error: fetch_osm_water.py is a
    # conditional fetcher (a multi-gigabyte extract download), so a run that
    # did not ask for it exports opentrail's water points alone, exactly as
    # every run did before this source existed - the same tolerance the
    # photo files get, for the same reason.
    osm_water_path = RAW_DIR / OSM_WATER_FILENAME
    if osm_water_path.exists():
        for feature in load_features(osm_water_path):
            if not has_geometry(feature):
                if skipped is not None:
                    skipped.append(f"{OSM_WATER_SOURCE}:{(feature.get('properties') or {}).get('osm_id')}")
                continue
            record = unify_poi(feature, "water", OSM_WATER_SOURCE, trail_id, OSM_WATER_FIELD_MAP)
            # Kept for describe_water: `kind` and the reliability tags are
            # what the card's sentence is composed from.
            record[RAW_PROPERTIES_KEY] = feature.get("properties") or {}
            unified.append(record)

    # Read at call time from the module constant, like every path here, so a
    # test pointing it elsewhere redirects it.
    unified.extend(load_trail_water(TRAIL_WATER_PATH, trail_id))

    return unified


def load_trail_water(path: Path, trail_id: str = TRAIL_ID) -> list[dict]:
    """build_trail_water.py's crossings and site water, as unified POIs.

    Two poi_types out of one file because they answer the same question in
    two places: where the walking route meets water, and which overnight
    sites have water they can reach. Both are derived from the same frozen
    NHD snapshot and both enter at CONFIDENCE_LOW.

    A record whose `water` is null is a site the gates REFUSED - too far, too
    steep, or no stream at all - and it publishes nothing here. Its reason
    stays in the reference file where a human can read it and decide whether
    a gate is wrong, which is the whole point of writing rejections down.

    A missing file is a normal state, exactly as it is for capacities,
    distances and photos: the export ships without crossings rather than
    failing.
    """
    if not path.exists():
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    records = []

    for crossing in document.get("crossings", []):
        lat, lon = crossing["lat"], crossing["lon"]
        feature = {
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "crossing_id": f"{lat:.{CROSSING_ID_PRECISION}f},{lon:.{CROSSING_ID_PRECISION}f}",
                "sources": crossing.get("sources"),
                "name": crossing.get("name"),
                "flow": crossing.get("flow"),
                "flow_source": crossing.get("flow_source"),
            },
        }
        record = unify_poi(
            feature,
            "crossing",
            NHD_CROSSING_SOURCE,
            trail_id,
            {"id_field": "crossing_id", "name_field": "name", "confidence": CONFIDENCE_LOW},
        )
        record[RAW_PROPERTIES_KEY] = {**feature["properties"], "crossing": True}
        records.append(record)

    for site in document.get("sites", []):
        water = site.get("water")
        if water is None:
            continue
        feature = {
            "geometry": {"type": "Point", "coordinates": [water["lon"], water["lat"]]},
            "properties": {
                # The site this water belongs to, which is also what makes the
                # id stable: one reachable stream point per site by
                # construction, so the site's own GlobalID names it.
                "site_global_id": site["atc_global_id"],
                "sources": water.get("sources"),
                "name": water.get("name"),
                "flow": water.get("flow"),
                "flow_source": water.get("flow_source"),
            },
        }
        record = unify_poi(
            feature,
            "water",
            NHD_STREAM_SOURCE,
            trail_id,
            {"id_field": "site_global_id", "name_field": "name", "confidence": CONFIDENCE_LOW},
        )
        record[RAW_PROPERTIES_KEY] = feature["properties"]
        records.append(record)

    return records


def dedupe_water(records: list[dict]) -> list[dict]:
    """Drop each OSM water point that sits within WATER_DEDUP_RADIUS_M of an
    opentrail one - opentrail imports OSM, so the pair is largely one node
    arriving through two doors (the measurement is on the constant).

    Direction matters and is fixed, not nearest-wins: the opentrail record
    keeps its published id, so anything already referencing it stays
    attached, and the export's counts stay comparable with every release
    before this source existed.
    """
    opentrail_water = [r for r in records if r["poi_type"] == "water" and r["source"] == OPENTRAIL_SOURCE]
    if not opentrail_water:
        return records

    def is_twin(record: dict) -> bool:
        if record["poi_type"] != "water" or record["source"] != OSM_WATER_SOURCE:
            return False
        return any(
            distance_m(record["lat"], record["lon"], kept["lat"], kept["lon"]) <= WATER_DEDUP_RADIUS_M for kept in opentrail_water
        )

    return [record for record in records if not is_twin(record)]


def clip_to_corridor(con: duckdb.DuckDBPyConnection, unified: list[dict]) -> list[dict]:
    """Keep only unified POIs whose point intersects the already-built
    'corridor' table - the same clip spike_corridor.py proved on real
    campsites/shelters, generalized to any unified POI list."""
    if not unified:
        return []

    con.execute("CREATE OR REPLACE TABLE poi_points (id VARCHAR, lat DOUBLE, lon DOUBLE)")
    con.executemany("INSERT INTO poi_points VALUES (?, ?, ?)", [(r["id"], r["lat"], r["lon"]) for r in unified])

    rows = con.execute("""
        SELECT poi_points.id FROM poi_points, corridor
        WHERE ST_Intersects(ST_Point(poi_points.lon, poi_points.lat), corridor.geom)
    """).fetchall()
    kept_ids = {row[0] for row in rows}
    return [r for r in unified if r["id"] in kept_ids]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_poi_type(con: duckdb.DuckDBPyConnection, poi_type: str, records: list[dict]) -> dict:
    """Write one poi_type's unified+clipped records to GeoJSON + FlatGeobuf
    under OUT_DIR, even when records is empty (e.g. `crossing`, pending NHD
    ingestion - this deliberately ships an empty-but-present layer rather
    than omitting the poi_type or inventing data). Returns this poi_type's
    manifest entry: per-artifact path/sha256/feature_count."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    columns = ", ".join(f"{name} {sql_type}" for name, sql_type in POI_COLUMNS)
    con.execute(f"CREATE OR REPLACE TABLE poi_out ({columns})")
    if records:
        placeholders = ", ".join("?" * len(POI_COLUMNS))
        con.executemany(
            f"INSERT INTO poi_out VALUES ({placeholders})",
            [
                # Same order as POI_COLUMNS, which is what the placeholders
                # were counted from - a value added here and not there is a
                # column shift rather than an error, so
                # test_export_poi_exported_properties_are_exactly_the_declared_columns
                # pins the pair.
                (
                    r["id"],
                    r["poi_type"],
                    r["trail_id"],
                    r["source"],
                    str(r["source_feature_id"]),
                    r["name"],
                    r["lat"],
                    r["lon"],
                    r["confidence"],
                    # .get for the same reason as the photo fields below: a
                    # POI arrives without one both when nothing matched and
                    # when a caller never ran the attach step.
                    r.get("capacity"),
                    r.get("water_distance_ft"),
                    r.get("description"),
                    # The parts as JSON - see attach_nearby, and note the same
                    # scalar-only reason the photo list below is a string.
                    r.get("nearby"),
                    # .get, not [] - records arrive photo-less both when
                    # attach_photos found no match and when a caller (or an
                    # older test) never ran the attach step at all.
                    r.get("photo_key"),
                    r.get("photo_page_url"),
                    r.get("photo_author"),
                    r.get("photo_license"),
                    r.get("photo_taken"),
                    # The whole list as JSON - see attach_photos. Scalar-only
                    # FlatGeobuf properties are why this is a string column.
                    r.get("photos"),
                    # .get for the same reason as every optional above: NULL on
                    # a POI in no site, which is most of them.
                    r.get("site_id"),
                    r.get("site_role"),
                    r.get("site_name"),
                )
                for r in records
            ],
        )
    con.execute("CREATE OR REPLACE TABLE poi_geom AS SELECT *, ST_Point(lon, lat) AS geom FROM poi_out")

    geojson_path = OUT_DIR / poi_output_name(poi_type, "geojson")
    fgb_path = OUT_DIR / poi_output_name(poi_type, "fgb")
    # COPY TO refuses to overwrite an existing file for these drivers, and
    # this needs to be safely re-runnable.
    geojson_path.unlink(missing_ok=True)
    fgb_path.unlink(missing_ok=True)

    con.execute(f"COPY poi_geom TO '{geojson_path.as_posix()}' WITH (FORMAT GDAL, DRIVER 'GeoJSON')")
    con.execute(f"COPY poi_geom TO '{fgb_path.as_posix()}' WITH (FORMAT GDAL, DRIVER 'FlatGeobuf')")

    return {
        "geojson": {"path": str(geojson_path), "sha256": sha256_file(geojson_path), "feature_count": len(records)},
        "fgb": {"path": str(fgb_path), "sha256": sha256_file(fgb_path), "feature_count": len(records)},
    }


def read_sources(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Every source read, unified and clipped to the corridor - the whole of
    this export that depends on the raw data and none of what depends on the
    photo fetches.

    Split out so `--check` can run exactly this and nothing else. That is the
    point of it: the two defects that cost this pipeline an hour each landed
    here, in the reading, while the step sits behind ~55 minutes of photo
    fetching it has no need of. Sharing the function rather than
    reimplementing it is what makes the preflight a real rehearsal - a check
    that read the sources its own way could pass while the export failed.
    """
    print("Building 30-mile corridor from centerline...")
    build_corridor(con, RAW_DIR / "centerline.geojson")

    print("Unifying POI sources...")
    skipped: list[str] = []
    unified = unify_all_sources(TRAIL_ID, skipped)
    print(f"  {len(unified)} POIs unified across all sources (pre-clip).")
    if skipped:
        # Said out loud: a row upstream lost its geometry, and a count that
        # grows run over run is a source going wrong rather than one empty
        # record ATC has always had.
        print(f"  {len(skipped)} source row(s) had no geometry and were skipped: {', '.join(skipped[:5])}")

    clipped = clip_to_corridor(con, unified)
    print(f"  {len(clipped)}/{len(unified)} within the corridor.")

    deduped = dedupe_water(clipped)
    if len(deduped) != len(clipped):
        print(f"  {len(clipped) - len(deduped)} OSM water twin(s) of opentrail points dropped (<= {WATER_DEDUP_RADIUS_M:.0f} m).")
    return deduped


def poi_counts(records: list[dict]) -> dict[str, int]:
    """How many records each declared poi_type has, including the zeroes.

    Built from POI_TYPES rather than from what the records happen to contain,
    so a type that vanished entirely counts 0 and fails the gate below
    instead of quietly not appearing in the tally.
    """
    return {poi_type: sum(1 for record in records if record["poi_type"] == poi_type) for poi_type in POI_TYPES}


def fail_if_any_type_is_empty(counts: dict[str, int], label: str) -> None:
    """Every poi_type must produce at least one feature - a genuinely broken
    source (e.g. shelter silently returning 0 after an upstream schema
    change) would otherwise be structurally indistinguishable from crossing's
    expected, intentional emptiness (see module docstring) and ship silently.
    crossing is the only poi_type allowed to be 0."""
    fail_if_incomplete(count_problems(counts, minimums={"crossing": 0}), label=label)


def check_sources() -> dict[str, int]:
    """Read the sources, clip them, and gate on the counts - writing nothing.

    The preflight the publish workflow runs BEFORE the photo fetches. It
    costs seconds and catches the whole class of failure that has actually
    bitten this pipeline: a row ATC left empty, a source that came back
    without the layer, a schema change that empties a type. Discovering any
    of those after the fetches costs an hour and a photo cache.
    """
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    counts = poi_counts(read_sources(con))
    for poi_type, count in counts.items():
        print(f"  {poi_type}: {count} features")
    fail_if_any_type_is_empty(counts, label="POI sources are not exportable")
    print("Sources read cleanly - the export has what it needs.")
    return counts


def main() -> dict:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    clipped = read_sources(con)

    sites, folded = attach_sites(clipped)
    print(f"  {folded} POIs fold into {sites} sites (a shelter with its privy and campsites - #523).")

    # CAPACITY_PATH read here rather than defaulted in the signature, so that
    # redirecting the module constant - as the tests do - redirects the read.
    capacities = load_capacities(CAPACITY_PATH)
    if capacities:
        attached = attach_capacity(clipped, capacities)
        print(f"  {attached} shelters carry a capacity (from {CAPACITY_PATH.name}).")
    else:
        print(f"  No {CAPACITY_PATH.name} - exporting without shelter capacities.")

    water_distances = load_water_distances(WATER_DISTANCE_PATH)
    if water_distances:
        attached = attach_water_distance(clipped, water_distances)
        print(f"  {attached} shelters and campsites carry a water distance (from {WATER_DISTANCE_PATH.name}).")
        synthesized = synthesize_csi_water(clipped)
        print(f"  {synthesized} water points synthesized onto those sites from the distances (#694).")
    else:
        print(f"  No {WATER_DISTANCE_PATH.name} - exporting without water distances.")

    # After the capacity attach, not before: "sleeps 8" is a clause in the
    # composed sentence and that number is not on the feature ATC published.
    described = attach_descriptions(clipped)
    print(f"  {described} POIs carry a description (of the {len(DESCRIBERS)} types that compose one).")

    # After the site and water attaches, which are where both kinds of part
    # come from (#614, #668). Its own line in the log because it is its own
    # fact: a jump in it means ATC's naming moved a member in or out of a site.
    nearby = attach_nearby(clipped)
    print(f"  {nearby} anchors name the parts around them (#625 - the phone writes the sentence).")

    commons_photos = load_photo_records(RAW_DIR / IMAGES_FILENAME)
    atc_photos = load_photo_records(RAW_DIR / ATC_IMAGES_FILENAME)
    photos = {**commons_photos, **atc_photos}  # ATC last: it wins any overlap
    if photos:
        attached = attach_photos(clipped, photos)
        print(f"  {attached} POIs carry a photo ({len(atc_photos)} ATC, {len(commons_photos)} Commons; ATC wins overlaps).")
    else:
        print(f"  No {IMAGES_FILENAME} or {ATC_IMAGES_FILENAME} - exporting without photos.")

    manifest = {}
    for poi_type in POI_TYPES:
        records = [r for r in clipped if r["poi_type"] == poi_type]
        manifest[poi_type] = write_poi_type(con, poi_type, records)
        print(f"  {poi_type}: {len(records)} features -> {OUT_DIR / poi_type}.{{geojson,fgb}}")

    # The same gate `--check` ran before any of the fetching, run again on
    # what was actually written. Not redundant: the preflight can only speak
    # for the data as it was read, and this one speaks for the artifacts.
    fail_if_any_type_is_empty(poi_counts(clipped), label="Incomplete POI export")

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest -> {manifest_path}")

    return manifest


def run(argv: list[str]) -> None:
    """Flag handling split from main() so tests can drive each side alone -
    same shape as fetch_atc_photos.py's, including refusing a flag it does
    not know rather than silently exporting when a preflight was asked for."""
    if argv == ["--check"]:
        check_sources()
        return
    if argv:
        print(f"Unknown flag {argv[0]!r} - usage: python export_poi.py [--check]")
        raise SystemExit(2)
    main()


if __name__ == "__main__":
    run(sys.argv[1:])
