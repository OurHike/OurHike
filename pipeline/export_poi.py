"""Export the unified POI schema (ROADMAP.md Phase 1 "Unified POI schema",
TECHNICAL_ARCHITECTURE.md's Export step): join ATC shelters/campsites/
Communities and opentrail.org's water/resupply tags into one schema per
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

from lib.completeness import count_problems, fail_if_incomplete
from lib.corridor import build_corridor
from lib.photo_store import photo_key
from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES, unify_poi

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed" / "poi"

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

TRAIL_ID = "AT"

# (raw filename stem, poi_type, source name used in unified ids, field_map)
# - the three ATC sources that map ~1:1 onto one poi_type each.
DIRECT_SOURCES = (
    ("shelters", "shelter", "atc_shelters", {"id_field": "GlobalID", "name_field": "Name", "confidence": CONFIDENCE_HIGH}),
    ("campsites", "campsite", "atc_campsites", {"id_field": "GlobalID", "name_field": "Name", "confidence": CONFIDENCE_HIGH}),
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
            unified.append(unify_poi(feature, poi_type, source, trail_id, field_map))

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

    con.execute("""
        CREATE OR REPLACE TABLE poi_out (
            id VARCHAR, poi_type VARCHAR, trail_id VARCHAR, source VARCHAR,
            source_feature_id VARCHAR, name VARCHAR, lat DOUBLE, lon DOUBLE, confidence VARCHAR,
            photo_key VARCHAR, photo_page_url VARCHAR, photo_author VARCHAR, photo_license VARCHAR, photo_taken VARCHAR,
            photos VARCHAR
        )
    """)
    if records:
        con.executemany(
            "INSERT INTO poi_out VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
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

    geojson_path = OUT_DIR / f"{poi_type}.geojson"
    fgb_path = OUT_DIR / f"{poi_type}.fgb"
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
