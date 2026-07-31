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
"""

import hashlib
import json
from pathlib import Path

import duckdb

from lib.completeness import count_problems, fail_if_incomplete
from lib.corridor import build_corridor
from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES, unify_poi

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed" / "poi"

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
            source_feature_id VARCHAR, name VARCHAR, lat DOUBLE, lon DOUBLE, confidence VARCHAR
        )
    """)
    if records:
        con.executemany(
            "INSERT INTO poi_out VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
