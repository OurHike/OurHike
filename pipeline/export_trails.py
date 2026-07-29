"""Export trail-line data (centerline + side_trails) with a normalized
`blaze_color` property on every feature, per features/TRAIL_BLAZE_COLORS.md
and lib/blaze.py: decode each blaze_field source's raw value against its
real ArcGIS coded domain (lib/arcgis.py's get_field_coded_domain - derived
from the FeatureServer's own field metadata, not hand-copied), or apply a
flat blaze_default for a source with no per-feature field at all. Clip to
the 30-mile corridor and write one combined GeoJSON + FlatGeobuf artifact,
with a SHA256 content hash per artifact in a manifest - same
"content hash per artifact" pattern export_poi.py already uses.

Corridor: computed fresh here from data/raw/centerline.geojson, mirroring
spike_corridor.py's/export_poi.py's ST_Buffer(30mi) + ST_Union_Agg pattern
exactly, including the always_xy gotcha (see README.md).

Line sources: any sources.json entry carrying blaze metadata (`blaze_field`
or `blaze_default`) - today that's `centerline` (blaze_default: "White",
since the AT itself is uniformly white-blazed with no per-segment field) and
`side_trails` (blaze_field: "Blaze", a real ArcGIS coded-value domain). A
future imported trail-line source picks up this export automatically just by
carrying one of those two keys in sources.json - no source-specific branch
needed here.

Real-data gotcha confirmed live against side_trails' actual FeatureServer
(2026-07-25) and worth naming since it's easy to get backwards: the `Blaze`
field is `esriFieldTypeString` with a codedValue domain whose codes are
themselves strings ("0".."9"), not integers - and the raw feature values in
the real downloaded side_trails.geojson are the string "1", not the int 1.
get_field_coded_domain's return type just mirrors whatever the live service
declares, so this module never coerces raw values or domain keys to a
particular type - it passes both straight through to
normalize_blaze_color's generic `in` lookup, which only works if the two
sides' types already match (they do, on live data, since both come from the
same ArcGIS field).
"""

import hashlib
import json
from pathlib import Path

import duckdb

from lib.arcgis import get_field_coded_domain
from lib.blaze import normalize_blaze_color

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"
SOURCES_PATH = ROOT / "sources.json"

BUFFER_MILES = 30
METERS_PER_MILE = 1609.344

# Same CRS choice as spike_corridor.py/export_poi.py, for the same reason:
# EPSG:5070 (NAD83 / Conus Albers) is equal-area, meters, and appropriate for
# a CONUS-spanning buffer operation.
PROJECTED_CRS = "EPSG:5070"
GEOGRAPHIC_CRS = "EPSG:4326"


def load_line_sources(sources_path: Path | None = None) -> list[dict]:
    """Every sources.json entry carrying blaze metadata (`blaze_field` or
    `blaze_default`) - the line-geometry trail sources this export
    processes (today: centerline, side_trails). Reads SOURCES_PATH at call
    time when no path is given - not as the parameter's default value,
    which would bind once at function-definition time and silently ignore a
    test's `monkeypatch.setattr(export_trails, "SOURCES_PATH", ...)`."""
    path = sources_path if sources_path is not None else SOURCES_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    return [s for s in data["sources"] if "blaze_field" in s or "blaze_default" in s]


def load_features(path: Path) -> list[dict]:
    """Read a raw GeoJSON file's features as plain Python dicts."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("features", [])


def normalize_source_features(source: dict, features: list[dict]) -> list[dict]:
    """Attach a normalized blaze_color to every feature of one line source,
    per lib/blaze.py's normalize_blaze_color contract:
    - a `blaze_field` source: fetch that field's real coded domain from the
      live FeatureServer and decode each feature's raw value against it.
    - a `blaze_default`-only source (no field): apply the flat default to
      every feature - always decodes, since there's no per-feature value
      that could fail to decode.

    Any feature that fails to decode gets a loud warning naming the source
    and feature - never a silent fallback (matching fetch_topo_quads.py's
    corrupted-quad warning convention - see TESTING.md/README.md)."""
    key = source["key"]
    blaze_field = source.get("blaze_field")
    coded_domain = get_field_coded_domain(source["url"], blaze_field) if blaze_field else None

    normalized = []
    for feature in features:
        properties = feature.get("properties") or {}
        raw_value = properties.get(blaze_field) if blaze_field else None
        blaze_color, decoded = normalize_blaze_color(raw_value, coded_domain, source.get("blaze_default"))
        if not decoded:
            feature_id = properties.get("GlobalID", feature.get("id"))
            print(
                f"WARNING: {key} feature {feature_id!r} has an undecodable blaze value "
                f"({raw_value!r}) - falling back to {blaze_color!r}"
            )
        normalized.append({**feature, "_blaze_color": blaze_color})
    return normalized


def _points_wkt(coordinates: list) -> str:
    return ", ".join(f"{lon} {lat}" for lon, lat in coordinates)


def geometry_to_wkt(geometry: dict) -> str | None:
    """Convert a GeoJSON LineString/MultiLineString geometry to WKT. Returns
    None for anything else (including missing/null geometry) - the real raw
    data has both: real-data gotcha confirmed against the actual downloaded
    centerline.geojson/side_trails.geojson (2026-07-28) - a few genuine trail
    segments (e.g. side_trails' "Catawba Greenway Trail", both centerline
    segments named "Appalachian National Scenic Trail") are MultiLineString,
    not LineString, and one side_trails feature ("Alec Kennedy Tent Pad Spur
    Trail #s 2 & 3") has null geometry entirely. Silently dropping the
    MultiLineString ones on a naive "geometry.type != LineString" check would
    have quietly erased real trail mileage from the map - a safety-relevant
    gap, not a cosmetic one - so both geometry types are handled here; only
    a feature with no usable geometry at all is skipped (with a warning from
    the caller, never silently)."""
    gtype = geometry.get("type")
    if gtype == "LineString":
        return f"LINESTRING ({_points_wkt(geometry['coordinates'])})"
    if gtype == "MultiLineString":
        parts = ", ".join(f"({_points_wkt(line)})" for line in geometry["coordinates"])
        return f"MULTILINESTRING ({parts})"
    return None


def build_trail_records(source: dict, normalized_features: list[dict]) -> list[dict]:
    """Flatten one source's blaze-normalized features into plain dict rows
    ready for the DuckDB output table - id/source/name/blaze_color plus a
    WKT LineString/MultiLineString. A feature with no usable geometry is
    skipped with a loud warning (see geometry_to_wkt) rather than silently
    dropped or crashing the run."""
    key = source["key"]
    records = []
    for feature in normalized_features:
        geometry = feature.get("geometry") or {}
        wkt = geometry_to_wkt(geometry)
        properties = feature.get("properties") or {}
        feature_id = properties.get("GlobalID", feature.get("id"))
        if wkt is None:
            print(
                f"WARNING: {key} feature {feature_id!r} has unsupported or missing geometry ({geometry.get('type')!r}) - skipped"
            )
            continue
        records.append(
            {
                "id": f"{key}:{feature_id}",
                "source": key,
                "name": properties.get("Name"),
                "blaze_color": feature["_blaze_color"],
                "wkt": wkt,
            }
        )
    return records


def build_corridor(con: duckdb.DuckDBPyConnection) -> None:
    """Build the 'corridor' table fresh from RAW_DIR/centerline.geojson -
    mirrors spike_corridor.py's/export_poi.py's ST_Buffer(30mi) +
    ST_Union_Agg pattern exactly, including always_xy on both transform legs
    (see README.md's "Gotcha hit and fixed" note - without it ST_Transform
    silently swaps lat/lon and produces garbage geometry)."""
    centerline_path = (RAW_DIR / "centerline.geojson").as_posix()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE OR REPLACE TABLE centerline_raw AS SELECT * FROM ST_Read('{centerline_path}')")

    buffer_meters = BUFFER_MILES * METERS_PER_MILE
    con.execute(f"""
        CREATE OR REPLACE TABLE corridor AS
        SELECT ST_Transform(
            ST_Union_Agg(
                ST_Buffer(
                    ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true),
                    {buffer_meters}
                )
            ),
            '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true
        ) AS geom
        FROM centerline_raw
    """)


def clip_to_corridor(con: duckdb.DuckDBPyConnection, records: list[dict]) -> list[dict]:
    """Keep only trail-line records whose geometry intersects the already-
    built 'corridor' table - the same clip spike_corridor.py/export_poi.py
    prove on points, generalized here to line geometry (a line is kept if
    any part of it intersects the corridor, matching spike_corridor.py's own
    ST_Intersects clip - this filters features out/in, it doesn't cut a
    kept line's geometry down to the corridor boundary)."""
    if not records:
        return []

    con.execute("CREATE OR REPLACE TABLE trail_lines_raw (id VARCHAR, wkt VARCHAR)")
    con.executemany("INSERT INTO trail_lines_raw VALUES (?, ?)", [(r["id"], r["wkt"]) for r in records])

    rows = con.execute("""
        SELECT trail_lines_raw.id FROM trail_lines_raw, corridor
        WHERE ST_Intersects(ST_GeomFromText(trail_lines_raw.wkt), corridor.geom)
    """).fetchall()
    kept_ids = {row[0] for row in rows}
    return [r for r in records if r["id"] in kept_ids]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_trails(con: duckdb.DuckDBPyConnection, records: list[dict]) -> dict:
    """Write every clipped/normalized trail-line record to one combined
    GeoJSON + FlatGeobuf pair under OUT_DIR. Returns a manifest with a
    per-artifact path/sha256/feature_count entry - same shape as
    export_poi.py's write_poi_type."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    con.execute("""
        CREATE OR REPLACE TABLE trails_out (
            id VARCHAR, source VARCHAR, name VARCHAR, blaze_color VARCHAR, wkt VARCHAR
        )
    """)
    if records:
        con.executemany(
            "INSERT INTO trails_out VALUES (?, ?, ?, ?, ?)",
            [(r["id"], r["source"], r["name"], r["blaze_color"], r["wkt"]) for r in records],
        )
    con.execute("""
        CREATE OR REPLACE TABLE trails_geom AS
        SELECT id, source, name, blaze_color, ST_GeomFromText(wkt) AS geom FROM trails_out
    """)

    geojson_path = OUT_DIR / "trails.geojson"
    fgb_path = OUT_DIR / "trails.fgb"
    # COPY TO refuses to overwrite an existing file for these drivers, and
    # this needs to be safely re-runnable.
    geojson_path.unlink(missing_ok=True)
    fgb_path.unlink(missing_ok=True)

    con.execute(f"COPY trails_geom TO '{geojson_path.as_posix()}' WITH (FORMAT GDAL, DRIVER 'GeoJSON')")
    con.execute(f"COPY trails_geom TO '{fgb_path.as_posix()}' WITH (FORMAT GDAL, DRIVER 'FlatGeobuf')")

    return {
        "geojson": {"path": str(geojson_path), "sha256": sha256_file(geojson_path), "feature_count": len(records)},
        "fgb": {"path": str(fgb_path), "sha256": sha256_file(fgb_path), "feature_count": len(records)},
    }


def main() -> dict:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    print("Building 30-mile corridor from centerline...")
    build_corridor(con)

    sources = load_line_sources()
    all_records = []
    for source in sources:
        key = source["key"]
        features = load_features(RAW_DIR / f"{key}.geojson")
        normalized = normalize_source_features(source, features)
        records = build_trail_records(source, normalized)
        print(f"  {key}: {len(records)} line features normalized.")
        all_records.extend(records)

    clipped = clip_to_corridor(con, all_records)
    print(f"  {len(clipped)}/{len(all_records)} within the corridor.")

    manifest = write_trails(con, clipped)
    print(f"  trails: {len(clipped)} features -> {OUT_DIR / 'trails'}.{{geojson,fgb}}")

    manifest_path = OUT_DIR / "trails_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest -> {manifest_path}")

    return manifest


if __name__ == "__main__":
    main()
