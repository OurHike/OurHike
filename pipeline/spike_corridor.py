"""DuckDB spatial spike (ROADMAP.md Phase 1, first coding task).

Proves the core pipeline operation before building the rest on top of it:
buffer the full AT centerline by 30 miles, union it into one corridor
polygon, and clip real ATC POI data (campsites, shelters) against it.

Uses only already-fetched ATC data (see fetch_all.py) - no OSM/USGS involved
here; those are separate, purpose-built ingestion tasks per FEATURES.md, not
part of proving this method works.
"""
import duckdb

RAW_DIR = "data/raw"
OUT_DIR = "data/spike"
BUFFER_MILES = 30
METERS_PER_MILE = 1609.344

# EPSG:5070 = NAD83 / Conus Albers - equal-area, meters, good for a
# CONUS-spanning buffer operation like this one.
PROJECTED_CRS = "EPSG:5070"
GEOGRAPHIC_CRS = "EPSG:4326"


def main():
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE OR REPLACE TABLE centerline AS SELECT * FROM ST_Read('{RAW_DIR}/centerline.geojson')")

    n_segments = con.execute("SELECT COUNT(*) FROM centerline").fetchone()[0]
    print(f"Loaded {n_segments} centerline segments.")

    buffer_meters = BUFFER_MILES * METERS_PER_MILE
    print(f"Buffering each segment by {BUFFER_MILES} miles ({buffer_meters:.0f}m) in {PROJECTED_CRS}, then unioning...")

    # always_xy: EPSG:4326's authority-defined axis order is (lat, lon), but
    # every geometry we read (GeoJSON, GeoPandas, etc.) is (lon, lat). Without
    # this, ST_Transform silently swaps axes and produces garbage coordinates.
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
        FROM centerline
    """)

    area_sq_mi = con.execute(f"""
        SELECT ST_Area(ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true)) / (1609.344 * 1609.344)
        FROM corridor
    """).fetchone()[0]
    print(f"Corridor computed. Area: {area_sq_mi:,.0f} sq mi.")

    con.execute(f"COPY corridor TO '{OUT_DIR}/corridor.geojson' WITH (FORMAT GDAL, DRIVER 'GeoJSON')")
    print(f"Exported corridor -> {OUT_DIR}/corridor.geojson")

    # Clip real POI data against the corridor - proves the clip step, and
    # doubles as a data sanity check (anything outside 30mi of centerline
    # is either bad centerline data or a POI on a distant side/spur trail).
    for layer in ("campsites", "shelters"):
        con.execute(f"CREATE OR REPLACE TABLE {layer} AS SELECT * FROM ST_Read('{RAW_DIR}/{layer}.geojson')")
        total = con.execute(f"SELECT COUNT(*) FROM {layer}").fetchone()[0]

        con.execute(f"""
            CREATE OR REPLACE TABLE {layer}_clipped AS
            SELECT {layer}.* FROM {layer}, corridor
            WHERE ST_Intersects({layer}.geom, corridor.geom)
        """)
        within = con.execute(f"SELECT COUNT(*) FROM {layer}_clipped").fetchone()[0]

        con.execute(f"COPY {layer}_clipped TO '{OUT_DIR}/{layer}_clipped.geojson' WITH (FORMAT GDAL, DRIVER 'GeoJSON')")
        print(f"{layer}: {within}/{total} within 30mi corridor -> {OUT_DIR}/{layer}_clipped.geojson")
        if within < total:
            print(f"  NOTE: {total - within} {layer} fell outside the corridor - worth a look (bad centerline data or a distant spur-trail site)")


if __name__ == "__main__":
    main()
