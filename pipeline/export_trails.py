"""Export trail-line data (centerline + side_trails) with a normalized
`blaze_color` property on every feature, per features/TRAIL_BLAZE_COLORS.md
and lib/blaze.py: decode each blaze_field source's raw value against its
real ArcGIS coded domain (lib/arcgis.py's get_field_coded_domain - derived
from the FeatureServer's own field metadata, not hand-copied), or apply a
flat blaze_default for a source with no per-feature field at all. Clip to
the 30-mile corridor and write one combined GeoJSON + FlatGeobuf artifact,
with a SHA256 content hash per artifact in a manifest - same
"content hash per artifact" pattern export_poi.py already uses.

Corridor: built via lib/corridor.py's build_corridor() (shared with
export_poi.py - both used to carry an identical, verbatim-duplicated copy of
this function before that extraction) from data/raw/centerline.geojson,
mirroring spike_corridor.py's/export_poi.py's ST_Buffer(30mi) + ST_Union_Agg
pattern exactly, including the always_xy gotcha (see README.md).

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

import json
from pathlib import Path

import duckdb
from pyproj import Transformer
from shapely import wkt as shapely_wkt
from shapely.geometry import MultiLineString
from shapely.ops import linemerge
from shapely.ops import transform as shapely_transform

from lib.arcgis import get_field_coded_domain
from lib.blaze import load_blaze_mapping, map_source_blaze, normalize_blaze_color
from lib.completeness import count_problems, fail_if_incomplete
from lib.corridor import build_corridor
from lib.feature_id import resolve_feature_id
from lib.hashing import sha256_file

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"
SOURCES_PATH = ROOT / "sources.json"

# Same CRS choice as spike_corridor.py/export_poi.py, for the same reason:
# EPSG:5070 (NAD83 / Conus Albers) is equal-area, meters, and appropriate for
# a CONUS-spanning buffer operation.
PROJECTED_CRS = "EPSG:5070"
GEOGRAPHIC_CRS = "EPSG:4326"

# Built once: pyproj Transformers are relatively expensive to construct and
# are reused across every feature in the export.
_TO_METRIC = Transformer.from_crs(GEOGRAPHIC_CRS, PROJECTED_CRS, always_xy=True).transform
_TO_GEOGRAPHIC = Transformer.from_crs(PROJECTED_CRS, GEOGRAPHIC_CRS, always_xy=True).transform


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
    # The reviewed table for THIS source, or None. A source with no table -
    # every A.T. source today - takes the decode-only path below exactly as it
    # did before #782, which is what makes the palette extension A.T.-safe:
    # nothing about the seven colours already shipping goes through the new
    # code at all.
    mapping = load_blaze_mapping().get(key)

    normalized = []
    for index, feature in enumerate(features):
        properties = feature.get("properties") or {}
        raw_value = properties.get(blaze_field) if blaze_field else None
        blaze_color, decoded = normalize_blaze_color(raw_value, coded_domain, source.get("blaze_default"))

        # A reviewed mapping applies to what the DECODE produced, not to the
        # raw value: OPRHP's layer is coded, so "Teal" is what comes out the
        # far side of the domain lookup, and mapping the code would tie the
        # reviewed file to an ArcGIS numbering that can change under us.
        disposition = None
        if mapping is not None and decoded:
            mapped, disposition = map_source_blaze(blaze_color, mapping)
            blaze_color = mapped

        if not decoded:
            feature_id = resolve_feature_id(key, feature, properties, index)
            print(
                f"WARNING: {key} feature {feature_id!r} has an undecodable blaze value "
                f"({raw_value!r}) - falling back to {blaze_color!r}"
            )
        elif disposition == "unmapped":
            # The loud one WIREFRAMES.md section 3 requires: a colour the map
            # has never heard of must never invent a paint, and must never
            # pass quietly either. Distinct from "deferred", which is a
            # decision already recorded in reference/blaze_mapping.json and
            # would be noise repeated per feature.
            feature_id = resolve_feature_id(key, feature, properties, index)
            print(
                f"WARNING: {key} feature {feature_id!r} has blaze {raw_value!r}, which no "
                f"reviewed mapping covers - rendering neutral. Add it to "
                f"reference/blaze_mapping.json, mapped or deferred."
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
    for index, feature in enumerate(normalized_features):
        geometry = feature.get("geometry") or {}
        wkt = geometry_to_wkt(geometry)
        properties = feature.get("properties") or {}
        feature_id = resolve_feature_id(key, feature, properties, index)
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


"""Trail-geometry simplification.

WHY THIS STEP EXISTS
--------------------
The corridor-clipped centerline export is real GPS-surveyed geometry, and
there is a great deal of it: 4,224 features carrying 772,603 coordinates,
which serialises to ~31 MB of GeoJSON. Every one of those bytes is parsed by
the phone on each map load, and MapLibre keeps the parsed result in memory
for as long as the layer is mounted.

TECHNICAL_ARCHITECTURE.md deliberately chose GeoJSON over vector tiles for
these layers, on the grounds that they are "small vector GeoJSON" that hikers
search and filter. That reasoning still holds - but 31 MB is not small, and
the gap between the decision and the data is what this function closes. It
closes it by removing vertices rather than by changing format, so the
architecture decision stands.

WHY 1 METRE
-----------
Measured against the real export, not guessed:

    tolerance   coordinates    GeoJSON     features lost
    none            772,603     31.0 MB    -
    1 ft (0.3 m)    510,075     20.8 MB    0
    1 m             273,262     11.6 MB    0
    5.5 m            79,666      4.1 MB    0

1 metre was chosen over the alternatives at both ends for two reasons.

*It is below one screen pixel at every zoom OurHike ships.* The background
archive tops out at z13, where one 512px tile pixel covers roughly 9.5 m of
ground at AT latitudes; at the default z12 it is ~19 m. A 1 m displacement
cannot move a line by even a fraction of a pixel, so the simplified geometry
is not merely close to the original - it is indistinguishable from it on
screen, at any zoom a hiker can reach.

*It is also below the source data's own accuracy.* This is GPS-surveyed
centerline data whose real positional error is metres. Keeping sub-metre
vertices preserves survey noise rather than trail shape - a finer tolerance
(1 ft would cost ~9 MB more) buys precision the source never actually had.

Against the other direction: 5.5 m would save a further 7.5 MB and would
still be invisible at z12/z13. It was not taken because 1 m keeps ~3.4x more
vertices for a file that is already small enough, leaving headroom for things
that read the geometry rather than draw it - a future zoom past z13, or the
route-tracing that SEGMENTS.md's completion tracking implies. Download size
is no longer the binding constraint at 11.6 MB; fidelity for later consumers
is the better thing to spend the difference on.

None of this is one-way. Simplification happens at export and the
full-precision source stays in data/raw, so changing the tolerance later is a
re-run of this script, not a re-fetch from ATC.

HOW IT IS APPLIED
-----------------
In EPSG:5070 (NAD83 / Conus Albers), where the unit genuinely is the metre -
the same projected CRS build_corridor() already uses for the 30-mile buffer,
reused here rather than introducing a second way of measuring distance.

Simplifying in raw lon/lat degrees would have been easier and wrong in an
awkward way: a degree of longitude at AT latitudes is ~15% shorter than a
degree of latitude, so a single degree-valued tolerance means two different
distances depending on direction. Projecting first makes "1 metre" mean one
metre on both axes.
"""

DEFAULT_SIMPLIFY_TOLERANCE_M = 1.0


def simplify_records(records: list[dict], tolerance_m: float = DEFAULT_SIMPLIFY_TOLERANCE_M) -> list[dict]:
    """Return `records` with each geometry simplified to `tolerance_m` metres.

    Douglas-Peucker, which guarantees no point on the simplified line is
    further than the tolerance from the original - the property that makes
    this safe to do to safety-relevant geometry at all. Endpoints are always
    preserved, so a line still meets whatever it met before.

    A tolerance of 0 returns the source geometry untouched, which is the
    supported way for a consumer that needs full precision to ask for it.

    Never drops a feature. This pipeline has already produced one silent
    geometry-loss bug (3 MultiLineString centerline features vanishing from an
    export, which would have erased real trail mileage with no error raised),
    so a degenerate simplification result falls back to the original geometry
    rather than being written out or skipped.
    """
    if tolerance_m < 0:
        raise ValueError(f"tolerance_m must be >= 0, got {tolerance_m}")
    if not records or tolerance_m == 0:
        return [dict(record) for record in records]

    simplified: list[dict] = []
    for record in records:
        geom = shapely_wkt.loads(record["wkt"])
        projected = shapely_transform(_TO_METRIC, geom)
        reduced = shapely_transform(
            _TO_GEOGRAPHIC,
            # preserve_topology=False is correct for lines: the flag guards
            # against self-intersection when simplifying polygons, and the
            # faster algorithm still keeps both endpoints.
            projected.simplify(tolerance_m, preserve_topology=False),
        )

        # A line reduced below two points renders as nothing at all - the
        # worst kind of failure, because the output still looks clean. Keep
        # the original instead.
        if reduced.is_empty or not _has_drawable_geometry(reduced):
            reduced = geom

        simplified.append({**record, "wkt": reduced.wkt})

    return simplified


def _has_drawable_geometry(geom) -> bool:
    if geom.geom_type == "LineString":
        return len(geom.coords) >= 2
    return bool(geom.geoms) and all(len(part.coords) >= 2 for part in geom.geoms)


"""Centerline chain merging (#161).

WHY THIS STEP EXISTS
--------------------
MapLibre tiles this GeoJSON through geojson-vt, whose per-zoom simplification
DROPS WHOLE FEATURES whose projected length falls under its bar - ~1.4 km at
z4 with the default tolerance. ATC surveys the centerline as ~3,000 segments
averaging ~1.2 km, so at corridor zooms much of the trail was under the bar,
consecutive short segments vanished together, and the AT rendered with
miles-long gaps (#160) - a false statement about where the trail is, on the
one map that cannot afford one.

The client's fix was `tolerance: 0` on the trails source (map/style.ts),
which makes the drop rule structurally impossible and also disables the GOOD
half of geojson-vt's work, vertex thinning - so every low-zoom tile carries
every exported coordinate (#161 measured ~512k line points across the z4-z6
corridor tiles, against ~5.5k with simplification on).

The durable fix is in the data shape: merge contiguous centerline segments
into maximal chains, so every published feature is far above the drop bar at
any zoom, after which the client can return `tolerance` to its default and
get correct per-zoom generalization free. The client detects the merged
shape by the `chain:` ids below (lib/trailShape.ts sniffs for
`"centerline:chain:`), so a phone still holding a pre-merge download keeps
`tolerance: 0` - which is why the id spelling here is a published contract,
pinned by tests on both sides, not a naming preference.

WHAT IS AND IS NOT MERGED
-------------------------
Only the sources named in CHAIN_MERGED_SOURCES - today the centerline.
Spurs stay unmerged: each side trail is its own destination and its own
line-detail sheet (#134), spurs.json keys off their individual ids, and
their absence at the zooms the drop rule bites is sub-pixel.

Within a merged source, chains never cross a blaze_color boundary - one
feature carries one blaze, and merging two would repaint one of them. The
centerline is uniformly White today (a flat blaze_default), so this is a
guard rather than a live branch.

WHAT THE MERGE COSTS, SAID PLAINLY
----------------------------------
Per-segment identity. A chain's id is synthetic (`centerline:chain:<n>`,
stable only for identical input) and its name survives only where every
constituent agreed on one. Audited before this landed (#161's first bullet):
nothing consumes centerline segment ids or names - the client reads
trails.geojson only through MapLibre expressions on `blaze_color` and
`source`, spurs.json keys off side_trails ids only, and the line-detail
sheet names the through-route from `source` rather than from a per-segment
name. The .fgb variant is published and fetched by nothing.

The merge runs AFTER simplification, which is safe in both directions:
Douglas-Peucker preserves endpoints, so segments that touched still touch,
and simplifying the merged chain instead would produce the same vertices.
"""

CHAIN_MERGED_SOURCES = ("centerline",)

# geojson-vt's approximate whole-feature drop bar at z4 under MapLibre's
# default tolerance - the coarsest zoom the corridor is read at, so the bar
# every published feature has to clear. Reasoned in #160/#161 from the 0.375px
# default (~1.4 km at z4, halving per zoom), not newly measured here. Used
# only for the honesty stat main() prints: chains still under it are the
# fragments that will drop at low zoom, and their total length is the size of
# that approximation.
LOW_ZOOM_DROP_BAR_M = 1_400.0


def _component_lines(geom) -> list:
    if geom.geom_type == "LineString":
        return [geom]
    return list(geom.geoms)


def merge_chain_records(records: list[dict]) -> tuple[list[dict], dict]:
    """Merge each CHAIN_MERGED_SOURCES source's records into maximal chains.

    Returns (records, stats): the merged sources' chain records followed by
    every other record untouched and in its original order, and per-source
    {"constituents", "chains"} counts for the manifest and the run log.

    Ordering note: chains are emitted first, but paint order does not ride on
    it - WIREFRAMES.md §3's "a through-route is drawn last" is enforced by
    `line-sort-key` in the client, not by feature order.

    Chain ids are `{source}:chain:{n}` with n assigned in sorted-bounds order,
    so the same input yields the same ids. They are NOT stable across data
    releases - an upstream edit can renumber every chain - which is fine for
    the same audited reason collapsing segment ids was: nothing anchors to a
    centerline feature id. Anything that ever needs to must anchor to miles,
    the way closures already do.
    """
    merged: list[dict] = []
    passed_through: list[dict] = []
    stats: dict[str, dict] = {}

    groups: dict[tuple[str, str], list[dict]] = {}
    for record in records:
        if record["source"] in CHAIN_MERGED_SOURCES:
            groups.setdefault((record["source"], record["blaze_color"]), []).append(record)
        else:
            passed_through.append(record)

    counters: dict[str, int] = {}
    for (source, blaze_color), group in groups.items():
        lines = [line for record in group for line in _component_lines(shapely_wkt.loads(record["wkt"]))]
        chains = _component_lines(linemerge(MultiLineString(lines)))
        # Sorted by geometry rather than left in library order, so a re-run
        # over identical input cannot renumber the chains.
        chains.sort(key=lambda chain: chain.bounds)

        # One name only if every constituent that had one agreed - a chain
        # spanning two named stretches has no honest single name, and null
        # says so. Nothing reads this field today (see the audit above); it
        # is carried for whoever inspects the artifact by hand.
        names = {record["name"] for record in group if record["name"]}
        name = names.pop() if len(names) == 1 else None

        source_stats = stats.setdefault(source, {"constituents": 0, "chains": 0})
        source_stats["constituents"] += len(group)
        source_stats["chains"] += len(chains)
        for chain in chains:
            index = counters.get(source, 0)
            counters[source] = index + 1
            merged.append(
                {
                    "id": f"{source}:chain:{index}",
                    "source": source,
                    "name": name,
                    "blaze_color": blaze_color,
                    "wkt": chain.wkt,
                }
            )

    return merged + passed_through, stats


def _chain_drop_bar_report(records: list[dict]) -> str:
    """How much merged geometry still sits under the low-zoom drop bar.

    The merge's honesty stat: linemerge only joins segments whose endpoints
    touch exactly, so genuinely disconnected fragments stay short and still
    drop at low zoom once the client's tolerance reverts. What makes that
    acceptable is their size, so the size is printed every run rather than
    asserted once and trusted forever.
    """
    short_m = 0.0
    short_count = 0
    for record in records:
        if record["source"] not in CHAIN_MERGED_SOURCES:
            continue
        length = shapely_transform(_TO_METRIC, shapely_wkt.loads(record["wkt"])).length
        if length < LOW_ZOOM_DROP_BAR_M:
            short_count += 1
            short_m += length
    return f"{short_count} chain(s) under the ~{LOW_ZOOM_DROP_BAR_M / 1000:.1f} km z4 drop bar, {short_m / 1000:.1f} km in total"


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


"""The corridor-view centerline (#869).

WHY A SECOND, COARSER COPY OF THE SAME LINE
-------------------------------------------
`trails.geojson` is 12,304,418 bytes, 4,143,296 of them gzipped (measured
against the live bucket 2026-08-20). At 12 Mbps that is ~2.8 s of transfer
before a phone can draw the trail at all, and a first run's three entry steps
take about eight seconds to click through - so the newcomer reads three
sentences about a map over an empty background. #863 took the first line from
~12 s to ~5 s by committing the centerline the moment it arrives; the
remaining five seconds are mostly those megabytes, and no amount of client
work makes them smaller.

This is the artifact that makes them smaller. Centerline only, simplified
hard, and merged into ONE feature, because at the zoom first run opens at the
whole trail is a few hundred pixels of line.

Measured the same day, against the same published centerline (219,341
vertices across 3,025 features):

    tolerance     vertices      bytes    gzipped   worst departure
    1 m (shipped)  219,341   12.3 MB     4.14 MB   -
    100 m            9,989    0.19 MB   51,068 B   100 m
    250 m            7,173    0.14 MB   35,049 B   250 m
    500 m            6,375    0.13 MB   30,217 B   500 m

**81x smaller at 100 m**, which at 12 Mbps is ~34 ms of transfer - less than
the round trip that fetches it.

WHY 100 m AND NOT COARSER
-------------------------
The 16 KB between 100 m and 250 m is about ten milliseconds on the wire, and
buys back 150 m of fidelity. Douglas-Peucker's guarantee is that no point
moves further than the tolerance, so 100 m is exactly the worst this line is
ever wrong by - which is 0.013 px at the corridor view (z4, ~7.5 km per pixel
at A.T. latitudes) and 0.43 px at the pin seam (z9, ~234 m per pixel).

Above that seam it stops being a sketch and starts being a claim: 3.4 px out
at z12, 14 px at z14. The client does not draw it above the seam and drops it
the moment the real centerline lands - map/style.ts holds that end of the
bargain, and this file's tolerance is why the seam is where it is.

WHY ONE FEATURE
---------------
Per-feature JSON overhead, not vertices, is most of what is left after
simplifying: at 250 m the 3,025 feature wrappers were 466 KB of a 525 KB
file. One MultiLineString with one property set drops all of it. Nothing
reads this artifact per-feature - it is a shape to draw, never a trail to
identify - so the identity the merge costs is identity nobody wants here.

The chain merge upstream (#161) exists for a different reason and is not a
substitute: it keeps whole features above geojson-vt's drop bar. A single
MultiLineString of the entire trail is far above that bar by construction.

WHY IT IS WRITTEN HERE RATHER THAN THROUGH DUCKDB
-------------------------------------------------
Coordinate precision. GDAL's GeoJSON driver writes seven decimals, and at
this tolerance four (about 11 m, still finer than the 100 m the geometry is
good to) is 51,068 gzipped bytes against 61,480 - a fifth of the file, for
digits that describe survey noise the simplification has already discarded.
The driver takes a precision option; DuckDB's COPY does not pass one
through, and one feature is a JSON document this file can simply write.
"""

# Ten times the pin seam's pixel, and the number the client's `maxzoom` on
# this layer is reasoned from - see the block above before changing either.
OVERVIEW_SIMPLIFY_TOLERANCE_M = 100.0

# Enough to place the trail, not enough to survey it. Four decimals is ~11 m
# of longitude at A.T. latitudes, an order finer than the tolerance above.
OVERVIEW_COORDINATE_DECIMALS = 4


def _overview_coordinates(geom, decimals: int) -> list[list[list[float]]]:
    """Every line in `geom` as rounded [lon, lat] pairs."""
    return [[[round(x, decimals), round(y, decimals)] for x, y in line.coords] for line in _component_lines(geom)]


def write_overview(records: list[dict]) -> dict:
    """Write the corridor-view centerline to OUT_DIR, and return its manifest
    entry.

    Takes the SAME records the full export publishes, after clipping and the
    1 m simplification, so the two artifacts can never describe different
    trails - this is that line with vertices removed, not a second derivation
    of it.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    centerline = [r for r in records if r["source"] in CHAIN_MERGED_SOURCES]
    coarse = simplify_records(centerline, OVERVIEW_SIMPLIFY_TOLERANCE_M)

    lines: list[list[list[float]]] = []
    for record in coarse:
        lines.extend(_overview_coordinates(shapely_wkt.loads(record["wkt"]), OVERVIEW_COORDINATE_DECIMALS))

    # One feature, and the two properties the client's line styling reads
    # (map/style.ts keys width and sort order off `source`, colour off
    # `blaze_color`) - so the sketch is drawn by the same expressions as the
    # real line rather than by a second set that could drift from it.
    body = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"source": "centerline", "blaze_color": "White"},
                "geometry": {"type": "MultiLineString", "coordinates": lines},
            }
        ],
    }
    path = OUT_DIR / "trails_overview.geojson"
    path.write_text(json.dumps(body, separators=(",", ":")))

    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "feature_count": 1,
        "line_count": len(lines),
        "coordinate_count": sum(len(line) for line in lines),
        "tolerance_m": OVERVIEW_SIMPLIFY_TOLERANCE_M,
    }


def _total_coordinates(records: list[dict]) -> int:
    """Vertex count across an export, for the reduction line main() prints."""
    total = 0
    for record in records:
        geom = shapely_wkt.loads(record["wkt"])
        if geom.geom_type == "LineString":
            total += len(geom.coords)
        else:
            total += sum(len(part.coords) for part in geom.geoms)
    return total


def main() -> dict:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    print("Building 30-mile corridor from centerline...")
    build_corridor(con, RAW_DIR / "centerline.geojson")

    sources = load_line_sources()
    all_records = []
    counts = {}
    for source in sources:
        key = source["key"]
        features = load_features(RAW_DIR / f"{key}.geojson")
        normalized = normalize_source_features(source, features)
        records = build_trail_records(source, normalized)
        print(f"  {key}: {len(records)} line features normalized.")
        counts[key] = len(records)
        all_records.extend(records)

    # Completeness check: every line source this export processes (today:
    # centerline, side_trails - see load_line_sources) must produce at least
    # one feature. Unlike export_poi.py's `crossing` poi_type, none of this
    # file's sources are intentionally allowed to come back empty, so a
    # source silently returning 0 features (e.g. an ArcGIS schema change)
    # must fail the run loudly instead of just logging a count of 0 and
    # exiting 0. Runs before any output (manifest included) is written.
    fail_if_incomplete(count_problems(counts), label="Incomplete trail export")

    clipped = clip_to_corridor(con, all_records)
    print(f"  {len(clipped)}/{len(all_records)} within the corridor.")

    # Simplify AFTER clipping, so the corridor test runs against full-precision
    # geometry and a feature can never be excluded because simplification moved
    # it. See simplify_records' rationale block for why 1 m.
    before = _total_coordinates(clipped)
    simplified = simplify_records(clipped)
    after = _total_coordinates(simplified)
    print(
        f"  simplified to {DEFAULT_SIMPLIFY_TOLERANCE_M} m: "
        f"{before:,} -> {after:,} coordinates ({100 - after * 100 // max(before, 1)}% smaller)"
    )

    # Merge LAST, once the corridor clip and the simplification have both run
    # on per-segment geometry - see the chain-merging rationale block (#161).
    merged, chain_stats = merge_chain_records(simplified)
    for source, source_stats in chain_stats.items():
        print(f"  {source}: {source_stats['constituents']} segments merged into {source_stats['chains']} chains")
    if chain_stats:
        print(f"  {_chain_drop_bar_report(merged)}")

    manifest = write_trails(con, merged)
    # From `simplified` rather than from `merged`: the overview simplifies the
    # same geometry a second time, and Douglas-Peucker on the merged chains
    # would give the same vertices for more work.
    manifest["overview"] = write_overview(simplified)
    # The published feature count changed meaning with the merge, so the
    # counts a drop-detector should compare across it are recorded too:
    # `constituent_count` is what feature_count used to be (per-segment,
    # pre-merge), and check_output_quality.trails_verdict reads it so ~3,000
    # segments becoming ~500 chains does not read as a broken export.
    manifest["constituent_count"] = len(simplified)
    manifest["chain_counts"] = {source: s["chains"] for source, s in chain_stats.items()}
    print(f"  trails: {len(merged)} features -> {OUT_DIR / 'trails'}.{{geojson,fgb}}")
    overview = manifest["overview"]
    print(
        f"  overview: {overview['coordinate_count']:,} coordinates in {overview['line_count']} lines "
        f"at {overview['tolerance_m']:g} m -> {overview['path']}"
    )

    manifest_path = OUT_DIR / "trails_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest -> {manifest_path}")

    return manifest


if __name__ == "__main__":
    main()
