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
  - crossing: declared in lib/poi_schema.POI_TYPES but always exported with
    zero features - there's no NHD-crossing fetch script yet (ROADMAP.md
    still calls that exploratory/undecided). Shipping an empty-but-present
    layer (rather than omitting the poi_type, or inventing fake crossings)
    keeps the schema honest about what's actually populated.

Capacity enrichment: shelter features carry `capacity`, how many people the
shelter sleeps, from reference/shelter_capacity.json. That file is checked in
rather than fetched, because ATC's shelter layer has no capacity field at all
and the numbers come from a hiker-maintained list joined to ATC's shelters by
name - a join worth reviewing in a diff. build_shelter_capacity.py builds it
and its docstring holds the provenance and the licence position. Coverage is
partial and deliberately so: a shelter the source lists only as half of a
pair exports no capacity rather than a guessed one, and the client shows
nothing rather than a number nobody stands behind.

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
"""

import hashlib
import json
from pathlib import Path

import duckdb

from lib.atc_notes import clean_note
from lib.completeness import count_problems, fail_if_incomplete
from lib.corridor import build_corridor
from lib.photo_store import photo_key
from lib.poi_description import describe_campsite, describe_parking, describe_privy, describe_shelter, describe_viewpoint
from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES, poi_output_name, unify_poi

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed" / "poi"

# build_shelter_capacity.py's output. Under reference/, not data/raw/, because
# it is reviewed source rather than a fetch artifact - see that script's
# docstring for why the join it encodes is checked in.
CAPACITY_PATH = ROOT / "reference" / "shelter_capacity.json"

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
    # One sentence about the place, composed from ATC's own inventory by
    # lib/poi_description.py. Shelters and campsites only; NULL elsewhere.
    ("description", "VARCHAR"),
    ("photo_key", "VARCHAR"),
    ("photo_page_url", "VARCHAR"),
    ("photo_author", "VARCHAR"),
    ("photo_license", "VARCHAR"),
    ("photo_taken", "VARCHAR"),
    # Every photo for this POI as JSON, card photo first. A string rather than
    # a nested array because FlatGeobuf property values are scalars - see
    # attach_photos, and note GDAL re-expands it to real JSON in the .geojson.
    ("photos", "VARCHAR"),
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
    ("campsites", "campsite", "atc_campsites", ATC_FACILITY_FIELDS),
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


# Which poi_types compose a `description`, and with what. Every ATC facility
# layer is here; water and resupply are absent because they come from
# opentrail.org and ATC's Communities layer, neither of which carries an
# inventory to compose from.
#
# One signature - (properties, capacity, note) - so the dispatch is a lookup
# rather than a chain of branches. Only the shelter needs the capacity, and it
# is not ATC's number (reference/shelter_capacity.json), which is why it is
# passed rather than read from the properties.
DESCRIBERS = {
    "shelter": lambda properties, capacity, note: describe_shelter(properties, capacity, note),
    "campsite": lambda properties, _capacity, note: describe_campsite(properties, note),
    "viewpoint": lambda properties, _capacity, note: describe_viewpoint(properties, note),
    "parking": lambda properties, _capacity, note: describe_parking(properties, note),
    "privy": lambda properties, _capacity, note: describe_privy(properties, note),
}


def attach_descriptions(records: list[dict]) -> int:
    """Compose `description` for every POI type that has one, returning how
    many got one.

    Runs after attach_capacity, because "sleeps 8" is a clause in the
    shelter sentence and the number is not ATC's - it comes from
    reference/shelter_capacity.json. A shelter with no capacity gets the
    same sentence without that clause rather than a gap.
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


def unify_all_sources(trail_id: str = TRAIL_ID) -> list[dict]:
    """Load and unify every configured source (reading RAW_DIR at call
    time, not a pre-baked path, so tests can point it at a tmp_path fixture
    dir) into one flat list of unified POI dicts - no corridor clip applied
    yet, see clip_to_corridor."""
    unified = []
    for stem, poi_type, source, field_map in DIRECT_SOURCES:
        for feature in load_features(RAW_DIR / f"{stem}.geojson"):
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
        poi_type, confidence = mapping
        field_map = {**OPENTRAIL_FIELD_MAP_BASE, "confidence": confidence}
        unified.append(unify_poi(feature, poi_type, OPENTRAIL_SOURCE, trail_id, field_map))

    return unified


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
                    r.get("description"),
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


def main() -> dict:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    print("Building 30-mile corridor from centerline...")
    build_corridor(con, RAW_DIR / "centerline.geojson")

    print("Unifying POI sources...")
    unified = unify_all_sources(TRAIL_ID)
    print(f"  {len(unified)} POIs unified across all sources (pre-clip).")

    clipped = clip_to_corridor(con, unified)
    print(f"  {len(clipped)}/{len(unified)} within the corridor.")

    # CAPACITY_PATH read here rather than defaulted in the signature, so that
    # redirecting the module constant - as the tests do - redirects the read.
    capacities = load_capacities(CAPACITY_PATH)
    if capacities:
        attached = attach_capacity(clipped, capacities)
        print(f"  {attached} shelters carry a capacity (from {CAPACITY_PATH.name}).")
    else:
        print(f"  No {CAPACITY_PATH.name} - exporting without shelter capacities.")

    # After the capacity attach, not before: "sleeps 8" is a clause in the
    # composed sentence and that number is not ATC's.
    described = attach_descriptions(clipped)
    print(f"  {described} POIs carry a description (of the {len(DESCRIBERS)} types that compose one).")

    commons_photos = load_photo_records(RAW_DIR / IMAGES_FILENAME)
    atc_photos = load_photo_records(RAW_DIR / ATC_IMAGES_FILENAME)
    photos = {**commons_photos, **atc_photos}  # ATC last: it wins any overlap
    if photos:
        attached = attach_photos(clipped, photos)
        print(f"  {attached} POIs carry a photo ({len(atc_photos)} ATC, {len(commons_photos)} Commons; ATC wins overlaps).")
    else:
        print(f"  No {IMAGES_FILENAME} or {ATC_IMAGES_FILENAME} - exporting without photos.")

    manifest = {}
    counts = {}
    for poi_type in POI_TYPES:
        records = [r for r in clipped if r["poi_type"] == poi_type]
        counts[poi_type] = len(records)
        manifest[poi_type] = write_poi_type(con, poi_type, records)
        print(f"  {poi_type}: {len(records)} features -> {OUT_DIR / poi_type}.{{geojson,fgb}}")

    # Completeness check: every poi_type must produce at least one feature -
    # a genuinely broken source (e.g. shelter silently returning 0 after an
    # upstream schema change) would otherwise be structurally indistinguishable
    # from crossing's expected, intentional emptiness (see module docstring)
    # and ship silently. crossing is the only poi_type allowed to be 0.
    problems = count_problems(counts, minimums={"crossing": 0})
    fail_if_incomplete(problems, label="Incomplete POI export")

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest -> {manifest_path}")

    return manifest


if __name__ == "__main__":
    main()
