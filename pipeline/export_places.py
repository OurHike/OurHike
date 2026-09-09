"""Publish the places a hiker can name before anything is downloaded - parks,
towns, trailheads and the long trails - as `places.json` (#1371).

    python export_places.py

THE QUESTION THIS ANSWERS. First run asks "where do you hike?" before location
is on and before a single waypoint is on the phone (App.tsx fetches the
centerline only while entering), and keeps the answer as the map's fallback
centre for every fix GPS never gets. A park is not a POI type, so nothing the
pipeline publishes could answer "Harriman State Park"; the towns on a phone
are the 59 A.T. Communities; a trailhead is a waypoint that arrives after the
question is asked. This is the small artifact that lets the question be
answered with signal, and it is read by the same client resolver the finder
already has (client/src/lib/suggestedHikes.ts's searchPlaces): a name, a kind,
a point, and what the phone would actually hold if it downloaded there.

WHAT A ROW IS. One named place, and every field a screen prints is either the
publisher's own word or a measurement over lines this run published:

  kind        park | town | trailhead | parking | trail
  name        the publisher's name, unaltered
  state       ONLY where the source says it or the source is a state agency
              (NYS OPRHP and NYS DEC publish New York and nothing else - a
              reasoned line, not a lookup). Absent otherwise, never guessed.
  within      the park polygon a point sits inside, by name, so a trailhead
              can say "Harriman State Park" where the layer says nothing.
  poiId       for trailheads, parking and towns: the PUBLISHED waypoint's own
              id, so a pick here is also a waypoint the app holds. Resolved
              against export_poi.py's and export_nearby_poi.py's output for
              export_spurs.py's reason - an id has to be one a device already
              knows.
  lon, lat    a park's centroid, a trail's bbox centre, a waypoint's point
  bbox        parks and trails, so a map can FIT the place rather than centre
              on a point inside it
  trailMiles  MEASURED: miles of published trail line inside a park's
              boundary, or within PLACE_TRAIL_RADIUS_MILES of a point, or a
              trail's own length. Omitted on every row when no line was
              published to measure against (see below) - absent means
              unknown, never zero.

"MILES OF TRAIL HELD" IS OVER WHAT THIS RUN PUBLISHED, which is the honest
subject: `nearby_trails.geojson` (the lines other organizations maintain, past
their own licence gate) and `trails.geojson` (the A.T.). A park whose only
trails are ones no steward has licensed reads as holding no trail - true of
what a phone would download, which is what the number is for.

WHEN THERE ARE NO LINES AT ALL - the licence gate having held every steward's
lines back and the A.T. export not run - `trailMiles` is omitted from every
row and the document says `trailMilesMeasured: false`. That state is ordinary
(lib/corridor.py's own reading of an empty network) and it must not read as
"no park holds any trail". Trailheads and parking with nothing published near
them are DROPPED when measurement ran and kept when it did not: a USFS
trailhead in Arizona is not a place this app can put a trail under (#1231 is
the same concern one artifact over), while a town or a park with no trail
data is exactly the row a hiker who lives there should find - "no trail data
held" is a true sentence and a useful one.

PLACE_TRAIL_RADIUS_MILES IS @unvalidated. Five miles is a round number chosen
so a Community at the foot of a ridge counts the trail on the ridge; what would
settle it is the median distance from a published trailhead or Community to
its nearest published line, measurable from the same two tables this module
joins. The artifact carries the radius (`trailRadiusMiles`) so a screen prints
what was measured rather than a word like "nearby".

THE PARK LAYER SHIPS BEHIND ITS OWN reaches_hikers, like everything else.
`oprhp_park_polygons` was registered `false` for one reason, recorded in
pipeline/README.md: nothing exported it. This does; the licence block
(`oprhp_licence`) already reads that the terms permit it, and #1097 made the
same move for `oprhp_facilities` on the same terms. A registry that still
says false publishes no park rows and says so in the manifest.

RUNS AFTER export_trails.py, export_nearby_trails.py, export_poi.py and
export_nearby_poi.py; reads only data/processed/ and the raw layers those
already read. NO NETWORK.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from export_nearby_trails import NAMED_TRAIL_THRESHOLD_MILES
from lib.corridor import GEOGRAPHIC_CRS, METERS_PER_MILE, PROJECTED_CRS, count_features
from lib.hashing import sha256_file
from lib.manifest_paths import to_manifest_path
from lib.poi_schema import poi_output_name
from lib.source_registry import find_source, load_registry

ROOT = Path(__file__).resolve().parent
SOURCES_PATH = ROOT / "sources.json"
RAW_DIR = ROOT / "data" / "raw"
EXTERNAL_RAW_DIR = RAW_DIR / "external"
PROCESSED_DIR = ROOT / "data" / "processed"
POI_DIR = PROCESSED_DIR / "poi"
OUT_PATH = PROCESSED_DIR / "places.json"
MANIFEST_PATH = PROCESSED_DIR / "places_manifest.json"

#: The registry key of the park boundaries, and the raw file fetch_external_layers.py writes for it.
PARKS_KEY = "oprhp_park_polygons"

#: The two line artifacts a place's trail is measured over, in data/processed/.
LINE_ARTIFACTS = ("nearby_trails.geojson", "trails.geojson")

#: @unvalidated - see the module docstring for what would settle it.
PLACE_TRAIL_RADIUS_MILES = 5.0

#: Which published poi_types are places a hiker names, and the kind word each
#: becomes. `resupply` is a town only when it came from ATC's Communities layer
#: (TOWN_SOURCES) - a resupply point somebody tagged on a store is not a town.
POINT_PLACE_KINDS = {"trailhead": "trailhead", "parking": "parking", "resupply": "town"}
TOWN_SOURCES = frozenset({"atc_communities"})

#: The raw layer the Communities' STATE column is read from, joined by
#: GlobalID - export_poi.py publishes the name and never the state.
COMMUNITIES_RAW = "communities.geojson"

#: Providers whose every point is in one state by construction. A reasoned
#: line rather than a lookup: a New York state agency publishes New York.
PROVIDER_STATES = {"NYS OPRHP": "NY", "NYS DEC": "NY"}

#: export_trails.py names each centerline feature by ATC's own segment name,
#: so the one trail that file is about is named here and its rows are summed
#: under it - the trail's name, not an organization's.
AT_SOURCE = "centerline"
AT_NAME = "Appalachian Trail"


def _stamp(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _features(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("features", [])


def source_states(registry: dict) -> dict[str, str]:
    """Registry key -> the one state that source publishes, for the providers
    in PROVIDER_STATES. Every other source gets no state at all."""
    return {
        entry["key"]: PROVIDER_STATES[entry.get("provider")]
        for entry in registry.get("sources", [])
        if entry.get("provider") in PROVIDER_STATES
    }


def community_states(raw_path: Path) -> dict[str, str]:
    """GlobalID -> STATE off ATC's raw Communities layer, for the towns."""
    states: dict[str, str] = {}
    for feature in _features(raw_path):
        properties = feature.get("properties") or {}
        global_id, state = _clean(properties.get("GlobalID")), _clean(properties.get("STATE"))
        if global_id and state:
            states[global_id] = state
    return states


def load_parks(raw_path: Path, registry: dict) -> tuple[list[dict], str | None]:
    """The park rows, or none and the reason.

    Each row keeps the polygon's own GeoJSON geometry for the measurement
    step; `id` is the registry key plus OPRHP's GlobalID, the id every other
    published row of theirs already carries."""
    entry = find_source(registry, PARKS_KEY)
    if entry is None:
        return [], f"{PARKS_KEY} is not registered"
    if not entry.get("reaches_hikers"):
        return [], f"{PARKS_KEY} is registered with reaches_hikers false"
    if not raw_path.exists():
        return [], f"{raw_path.name} has not been fetched"

    parks = []
    for feature in _features(raw_path):
        properties = feature.get("properties") or {}
        name = _clean(properties.get("Name"))
        global_id = _clean(properties.get("GlobalID")) or _clean(properties.get("OBJECTID"))
        geometry = feature.get("geometry")
        if not name or not global_id or not geometry:
            continue
        parks.append(
            {
                "id": f"{PARKS_KEY}:{global_id}",
                "name": name,
                "kind": "park",
                "state": PROVIDER_STATES.get(entry.get("provider")),
                "category": _clean(properties.get("Category")),
                "source": PARKS_KEY,
                "geometry": geometry,
            }
        )
    return parks, None


def load_point_places(poi_dir: Path, nearby_path: Path, states: dict[str, str], town_states: dict[str, str]) -> list[dict]:
    """Trailheads, parking and towns, from the PUBLISHED waypoint artifacts.

    Named rows only - a place with no name cannot be searched for, and most
    of OPRHP's pull-offs and DEC's lots have none. The published id rides as
    `poiId` so the client can open the waypoint a pick refers to."""
    features: list[dict] = []
    for poi_type in POINT_PLACE_KINDS:
        features.extend(_features(poi_dir / poi_output_name(poi_type)))
    features.extend(_features(nearby_path))

    places = []
    seen: set[str] = set()
    for feature in features:
        properties = feature.get("properties") or {}
        poi_type = properties.get("poi_type")
        kind = POINT_PLACE_KINDS.get(poi_type)
        source = properties.get("source")
        if kind is None or (kind == "town" and source not in TOWN_SOURCES):
            continue
        poi_id, name = _clean(properties.get("id")), _clean(properties.get("name"))
        lon, lat = properties.get("lon"), properties.get("lat")
        if not poi_id or not name or lon is None or lat is None or poi_id in seen:
            continue
        seen.add(poi_id)
        state = states.get(source)
        if kind == "town":
            state = town_states.get(_clean(properties.get("source_feature_id")) or "") or state
        places.append(
            {
                "id": poi_id,
                "poiId": poi_id,
                "name": name,
                "kind": kind,
                "state": state,
                "source": source,
                "lon": float(lon),
                "lat": float(lat),
            }
        )
    return places


def _bbox(bounds: list[tuple[float, float, float, float]]) -> list[float]:
    return [
        round(min(b[0] for b in bounds), 5),
        round(min(b[1] for b in bounds), 5),
        round(max(b[2] for b in bounds), 5),
        round(max(b[3] for b in bounds), 5),
    ]


def load_lines(con: duckdb.DuckDBPyConnection, paths: list[Path]) -> int:
    """Load every line artifact that exists into `lines(source, name, g, geom)`,
    projected to metres and R-tree indexed, and return how many. An empty or
    absent file contributes nothing (lib/corridor.py's own reading), and the
    table is always left in place so the joins below can run unconditionally."""
    con.execute("CREATE OR REPLACE TABLE lines (source VARCHAR, name VARCHAR, g GEOMETRY, geom GEOMETRY)")
    loaded = 0
    for path in paths:
        if not count_features(con, path):
            continue
        columns = {row[0] for row in con.execute(f"DESCRIBE SELECT * FROM ST_Read('{path.as_posix()}')").fetchall()}
        name_column = "name" if "name" in columns else "NULL"
        source_column = "source" if "source" in columns else "NULL"
        con.execute(f"""
            INSERT INTO lines
            SELECT {source_column}, {name_column},
                   ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true),
                   geom
            FROM ST_Read('{path.as_posix()}')
        """)
        loaded += 1
    con.execute("DROP INDEX IF EXISTS lines_rtree")
    con.execute("CREATE INDEX lines_rtree ON lines USING RTREE (g)")
    return con.execute("SELECT count(*) FROM lines").fetchone()[0]


def load_named_trails(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """The long trails, from the lines already loaded: every (source, name)
    totalling at least NAMED_TRAIL_THRESHOLD_MILES, plus the A.T. named here.
    export_nearby_trails.py's own threshold, imported rather than copied, so
    what the legend calls a named trail and what this calls one cannot drift."""
    # The centerline is grouped by source alone: export_trails.py names each
    # of its features by ATC's own segment name, and a trail summed segment by
    # segment would be forty rows under the threshold rather than one over it.
    rows = con.execute(f"""
        SELECT source, CASE WHEN source = '{AT_SOURCE}' THEN '{AT_NAME}' ELSE name END AS trail,
               sum(ST_Length(g)), min(ST_XMin(geom)), min(ST_YMin(geom)), max(ST_XMax(geom)), max(ST_YMax(geom))
        FROM lines
        GROUP BY source, trail
    """).fetchall()
    trails = []
    for source, name, metres, west, south, east, north in rows:
        if not _clean(name):
            continue
        miles = metres / METERS_PER_MILE
        if miles < NAMED_TRAIL_THRESHOLD_MILES:
            continue
        bbox = _bbox([(west, south, east, north)])
        trails.append(
            {
                "id": f"trail:{source}:{name}",
                "name": name,
                "kind": "trail",
                "source": source,
                "lon": round((bbox[0] + bbox[2]) / 2, 5),
                "lat": round((bbox[1] + bbox[3]) / 2, 5),
                "bbox": bbox,
                "trailMiles": round(miles, 1),
            }
        )
    return trails


def measure(con: duckdb.DuckDBPyConnection, parks: list[dict], points: list[dict], radius_miles: float) -> None:
    """Fill in each park's centroid, bbox and the miles of line inside it;
    each point's miles of line within `radius_miles` and the park it sits in.

    Parks are made valid before anything is cut against them, because a unit
    boundary digitised by hand self-touches often enough that ST_Intersection
    would refuse the row otherwise, and a refused park would be a park the
    index silently lacks."""
    # DuckDB refuses an empty executemany, and an empty list is an ordinary
    # state for both tables - a registry holding the parks back, a run with
    # no named waypoint - so each insert is guarded rather than the join.
    con.execute("CREATE OR REPLACE TABLE park (idx INTEGER, g GEOMETRY, geom GEOMETRY)")
    if parks:
        con.executemany(
            f"""INSERT INTO park
                SELECT ?, ST_Transform(ST_MakeValid(ST_GeomFromGeoJSON(?)), '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true),
                       ST_MakeValid(ST_GeomFromGeoJSON(?))""",
            [(at, json.dumps(park["geometry"]), json.dumps(park["geometry"])) for at, park in enumerate(parks)],
        )
    for idx, lon, lat, west, south, east, north in con.execute("""
        SELECT idx, ST_X(ST_Centroid(geom)), ST_Y(ST_Centroid(geom)),
               ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)
        FROM park
    """).fetchall():
        parks[idx]["lon"], parks[idx]["lat"] = round(lon, 5), round(lat, 5)
        parks[idx]["bbox"] = _bbox([(west, south, east, north)])
        parks[idx]["trailMiles"] = 0.0
    for idx, metres in con.execute("""
        SELECT p.idx, sum(ST_Length(ST_Intersection(l.g, p.g)))
        FROM park p JOIN lines l ON ST_Intersects(l.g, p.g)
        GROUP BY p.idx
    """).fetchall():
        parks[idx]["trailMiles"] = round((metres or 0.0) / METERS_PER_MILE, 1)

    radius_m = radius_miles * METERS_PER_MILE
    con.execute("CREATE OR REPLACE TABLE pt (idx INTEGER, g GEOMETRY, disc GEOMETRY, geom GEOMETRY)")
    if points:
        con.executemany(
            f"""INSERT INTO pt
                SELECT ?, ST_Transform(ST_Point(?, ?), '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true),
                       ST_Buffer(ST_Transform(ST_Point(?, ?), '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true), {radius_m}),
                       ST_Point(?, ?)""",
            [(at, p["lon"], p["lat"], p["lon"], p["lat"], p["lon"], p["lat"]) for at, p in enumerate(points)],
        )
    for point in points:
        point["trailMiles"] = 0.0
    for idx, metres in con.execute("""
        SELECT t.idx, sum(ST_Length(ST_Intersection(l.g, t.disc)))
        FROM pt t JOIN lines l ON ST_Intersects(l.g, t.disc)
        GROUP BY t.idx
    """).fetchall():
        points[idx]["trailMiles"] = round((metres or 0.0) / METERS_PER_MILE, 1)
    for idx, park_idx in con.execute("""
        SELECT t.idx, min(p.idx)
        FROM pt t JOIN park p ON ST_Contains(p.geom, t.geom)
        GROUP BY t.idx
    """).fetchall():
        points[idx]["within"] = parks[park_idx]["name"]


def _record(place: dict) -> dict:
    """The published row: every field with a value, in one fixed order, and
    never the working geometry."""
    ordered = ("id", "poiId", "name", "kind", "category", "state", "within", "lon", "lat", "bbox", "trailMiles", "source")
    return {key: place[key] for key in ordered if place.get(key) is not None}


def build_output(
    registry: dict,
    parks_path: Path,
    poi_dir: Path,
    nearby_path: Path,
    communities_raw: Path,
    line_paths: list[Path],
    generated_at: datetime,
    radius_miles: float = PLACE_TRAIL_RADIUS_MILES,
) -> tuple[dict, dict]:
    parks, parks_held = load_parks(parks_path, registry)
    points = load_point_places(poi_dir, nearby_path, source_states(registry), community_states(communities_raw))

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    line_count = load_lines(con, line_paths)
    measured = line_count > 0
    trails = load_named_trails(con) if measured else []
    measure(con, parks, points, radius_miles)

    dropped: dict[str, int] = {}
    kept_points = []
    for point in points:
        far = measured and point["kind"] in ("trailhead", "parking") and point["trailMiles"] == 0.0
        if far:
            key = f"{point['source']}/{point['kind']}"
            dropped[key] = dropped.get(key, 0) + 1
            continue
        if not measured:
            point.pop("trailMiles", None)
        kept_points.append(point)
    if not measured:
        for park in parks:
            park.pop("trailMiles", None)

    places = sorted(parks + kept_points + trails, key=lambda place: (place["kind"], place["name"], place["id"]))
    output = {
        "generated_at": _stamp(generated_at),
        "trailRadiusMiles": radius_miles,
        "trailMilesMeasured": measured,
        "places": [_record(place) for place in places],
    }
    counts: dict[str, int] = {}
    for place in places:
        counts[place["kind"]] = counts.get(place["kind"], 0) + 1
    report = {
        "counts": counts,
        "lines_measured": line_count,
        "dropped_far_from_any_line": dict(sorted(dropped.items(), key=lambda kv: -kv[1])),
        "parks_held_back": parks_held,
    }
    return output, report


def write_artifact(output: dict, report: dict) -> dict:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, separators=(",", ":"), sort_keys=False) + "\n", encoding="utf-8")
    manifest = {"path": to_manifest_path(OUT_PATH), "sha256": sha256_file(OUT_PATH), **report}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> dict:
    registry = load_registry(SOURCES_PATH)
    output, report = build_output(
        registry,
        EXTERNAL_RAW_DIR / f"{PARKS_KEY}.geojson",
        POI_DIR,
        PROCESSED_DIR / "nearby_poi.geojson",
        RAW_DIR / COMMUNITIES_RAW,
        [PROCESSED_DIR / name for name in LINE_ARTIFACTS],
        datetime.now(timezone.utc),
    )
    manifest = write_artifact(output, report)
    if report["parks_held_back"]:
        print(f"No parks: {report['parks_held_back']}.", file=sys.stderr)
    if not output["trailMilesMeasured"]:
        print("No published lines to measure against - trailMiles omitted on every row.", file=sys.stderr)
    counted = ", ".join(f"{count} {kind}" for kind, count in sorted(report["counts"].items()))
    dropped = sum(report["dropped_far_from_any_line"].values())
    print(f"{len(output['places'])} places ({counted}; {dropped} dropped far from any line) -> {OUT_PATH}")
    print(f"Manifest -> {MANIFEST_PATH}")
    return manifest


if __name__ == "__main__":
    main()
