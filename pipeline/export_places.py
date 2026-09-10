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
  state       a postal code, ONLY where the source says it or its organization
              declares one in sources.json (`state` on the organization: NYS
              OPRHP and NYS DEC publish New York and nothing else - a reasoned
              line, recorded beside the organization). ATC's Communities layer
              writes the state as a word ("Virginia", and once "Virgnia", and
              blank fourteen times - live read 2026-09-10), so its words are
              read into the same codes and anything that is not a state's name
              is absent. Never guessed at.
  within      the park a point sits inside, by name, so a trailhead can say
              "Harriman State Park" where the layer says nothing.
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

ONE ROW PER PARK, NOT PER POLYGON. OPRHP's layer holds one polygon per
parcel: measured against the live service on 2026-09-10, 858 polygons carry
257 distinct `Name` and 258 distinct `MasterAreaID` (one null) - "Genesee
Valley Greenway" alone is 47 rows, "Hudson Highlands" 39. The rows here are
the UNITS: polygons are grouped by `MasterAreaID` and unioned before anything
is measured, so a hiker typing a park's name sees one row whose centroid,
bbox and miles are the whole park's. `Name` alone would not do - "Robert
Moses" is two parks (units 127 and 270) and "Long Point" three - and a unit
can carry more than one name ("Captree/Robert Moses" beside "Robert Moses"),
so a unit takes the name most of its polygons wear. The layer's fields are
declared on its registry entry (PARK_FIELDS has the defaults).

"MILES OF TRAIL HELD" IS OVER WHAT THIS RUN PUBLISHES, which is the honest
subject - and the gate is applied HERE, one file before publish.py applies
it to the line artifact itself. `nearby_trails.geojson` holds every exported
steward's lines, held back or not, because a reviewer has to see the map
before a licence answer arrives; publish.py then holds the whole artifact
back while any source in it carries `reaches_hikers: false`. Measured over
that file unfiltered, a park would print miles of trail no phone receives
and a trailhead would be kept for a line that is not published. So the lines
are filtered to `shipped_line_source_keys` (export_nearby_trails.py's own
answer to the same question, written for the water build) plus the A.T.,
which is its own export behind its own gate. A park whose only trails are
ones no steward has licensed reads as holding no trail - true of what a
phone would download, which is what the number is for. The manifest counts
what was held back, per source.

WHEN THERE ARE NO LINES AT ALL - the licence gate having held every steward's
lines back and the A.T. export not run - `trailMiles` is omitted from every
row and the document says `trailMilesMeasured: false`. That state is ordinary
(lib/corridor.py's own reading of an empty network) and it must not read as
"no park holds any trail". Trailheads and parking with nothing published near
them are DROPPED when measurement ran and kept when it did not: a USFS
trailhead in Arizona is not a place this app can put a trail under (#1231 is
the same concern one artifact over), while a town or a park with no trail
data is exactly the row a hiker who lives there should find - "no trail data
held" is a true sentence and a useful one. "Nothing near" is decided on the
measured metres, not on the rounded figure: a lot with eighty metres of trail
beside it prints 0.0 and is kept.

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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np

from export_nearby_trails import NAMED_TRAIL_THRESHOLD_MILES, owned_route_names, shipped_line_source_keys
from export_spurs import load_destination_pois, load_features
from lib.corridor import GEOGRAPHIC_CRS, METERS_PER_MILE, PROJECTED_CRS
from lib.hashing import sha256_file
from lib.manifest_paths import to_manifest_path
from lib.source_registry import find_source, load_registry, poi_source_entry
from lib.stamps import utc_stamp

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

#: The park layer's fields are DECLARED ON ITS REGISTRY ENTRY (`name_field`,
#: `id_field`, `unit_field`), the way every other external layer's are, so
#: the registry records the join and a column rename at OPRHP is a registry
#: edit. These are the defaults the entry declares today (live read
#: 2026-09-10: all present, `displayField` is `Name`); `Category` is the
#: publisher's own word for what the unit is, carried as `category`.
PARK_FIELDS = {"name_field": "Name", "id_field": "GlobalID", "unit_field": "MasterAreaID"}
PARK_CATEGORY_FIELD = "Category"

#: The two line artifacts a place's trail is measured over, in data/processed/.
LINE_ARTIFACTS = ("nearby_trails.geojson", "trails.geojson")

#: @unvalidated - see the module docstring for what would settle it.
PLACE_TRAIL_RADIUS_MILES = 5.0

#: Which published poi_types are places a hiker names, and the kind word each
#: becomes. `resupply` is a town only when its source's registry entry says so
#: (`place_kind: "town"` on ATC's Communities layer) - a resupply point
#: somebody tagged on a store is not a town, and which layer IS a town layer
#: is a fact about the layer, recorded beside it rather than named here.
POINT_PLACE_KINDS = {"trailhead": "trailhead", "parking": "parking", "resupply": "town"}
TOWN_KIND = "town"

#: The kinds whose rows are dropped when nothing published lies within the radius.
DROPPED_WHEN_FAR = frozenset({"trailhead", "parking"})

#: The raw layer the Communities' STATE column is read from, joined by
#: GlobalID - export_poi.py publishes the name and never the state.
COMMUNITIES_RAW = "communities.geojson"

#: The fifty states and the District, name to postal code, so one field in
#: the artifact speaks one vocabulary whatever the source wrote.
US_STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}  # fmt: skip

#: export_trails.py names each centerline feature by ATC's own segment name,
#: so the one trail that file is about is summed under one name - the route
#: its source OWNS in the registry (`owns_route_names`, the same fact
#: export_nearby_trails.py suppresses other stewards' copies by), never a
#: name written here.
AT_SOURCE = "centerline"


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def state_code(value) -> str | None:
    """A postal code from what a source wrote - the code itself, or a state's
    name - and None for anything else: a typo is not a state, and absent
    means unknown rather than guessed."""
    text = _clean(value)
    if text is None:
        return None
    if len(text) == 2 and text.upper() in US_STATE_CODES.values():
        return text.upper()
    return US_STATE_CODES.get(text.lower())


def _columns(con: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()}


def _read_file(con: duckdb.DuckDBPyConnection, table: str, path: Path) -> set[str]:
    """Materialise `path` into `table` with ONE parse - lib/corridor.py's
    `centerline_raw` pattern - and return its columns. `ST_Read` infers the
    columns from the features it finds, so an empty FeatureCollection has no
    `source`, `name` or `geom` at all (count_features's own note), and an
    absent file is an empty table with none; either way the caller sees the
    columns it can name and names nothing else."""
    if path.exists():
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM ST_Read('{path.as_posix()}')")
    else:
        con.execute(f"CREATE OR REPLACE TABLE {table} (geom GEOMETRY)")
        return set()
    return _columns(con, table)


def organization_states(registry: dict) -> dict[str, str]:
    """Provider -> the one state every point of that organization's is in,
    read off the registry's `organizations` block (`state` on the
    organization, where the fact belongs: a New York state agency publishes
    New York). An organization that declares none gives its rows none."""
    orgs = registry.get("organizations", {}).get("orgs", {})
    return {org["provider"]: org["state"] for org in orgs.values() if org.get("state")}


def source_entry(registry: dict, source: str) -> dict | None:
    """The registry entry behind a published row's `source`: through
    POI_SOURCE_KEYS where the published namespace differs from the key
    (`atc_communities` -> `communities`), else the key itself, which is how
    every external layer is published."""
    return poi_source_entry(registry, source) or find_source(registry, source)


def community_states(raw_path: Path) -> dict[str, str]:
    """GlobalID -> state code off ATC's raw Communities layer, for the towns.
    Only the rows whose STATE reads as a state: the layer writes full names,
    and a blank or a misspelling is left absent."""
    states: dict[str, str] = {}
    for feature in load_features(raw_path):
        properties = feature.get("properties") or {}
        global_id, state = _clean(properties.get("GlobalID")), state_code(properties.get("STATE"))
        if global_id and state:
            states[global_id] = state
    return states


def load_parks(con: duckdb.DuckDBPyConnection, raw_path: Path, registry: dict) -> tuple[list[dict], str | None]:
    """The park rows - one per unit, with the polygons that make it left in
    DuckDB as `park_part(part, geom)` for the measurement step - or none and
    the reason.

    The polygons never become Python objects: DuckDB reads the layer once,
    makes each boundary valid once, and hands back only the attributes the
    grouping needs. `id` is the registry key plus the unit's own id; a
    polygon with no unit id joins the unit sharing its name, or stands alone
    under the entry's declared `id_field` (GlobalID, the id every other
    published row of OPRHP's already carries). A polygon with neither, or no
    name, is not a place - deliberately not lib/feature_id.py's
    `generated-N` fallback, which would mint an id that changes with row
    order for a place a hiker keeps as their home."""
    con.execute("CREATE OR REPLACE TABLE park_part (part INTEGER, geom GEOMETRY)")
    entry = find_source(registry, PARKS_KEY)
    if entry is None:
        return [], f"{PARKS_KEY} is not registered"
    if not entry.get("reaches_hikers"):
        return [], f"{PARKS_KEY} is registered with reaches_hikers false"
    if not raw_path.exists():
        return [], f"{raw_path.name} has not been fetched"

    fields = {role: entry.get(role, default) for role, default in PARK_FIELDS.items()}
    columns = _read_file(con, "park_file", raw_path)
    if not {"geom", fields["name_field"]} <= columns:
        return [], None
    optional = {
        name: (name if name in columns else "NULL") for name in (fields["id_field"], fields["unit_field"], PARK_CATEGORY_FIELD)
    }
    # Made valid before anything is cut against a boundary: ST_Intersection
    # refuses an invalid polygon, and a refused park would be a park the
    # index silently lacks. @unvalidated how often a hand-digitised unit
    # boundary in this layer is invalid - nobody has counted; what would
    # settle it is `SELECT count(*) FROM park_file WHERE NOT ST_IsValid(geom)`
    # over the fetched layer, which takes a minute and has not been run.
    con.execute(f"""
        CREATE OR REPLACE TABLE park_part AS
        SELECT CAST(row_number() OVER () - 1 AS INTEGER) AS part,
               CAST({fields["name_field"]} AS VARCHAR) AS name,
               CAST({optional[fields["id_field"]]} AS VARCHAR) AS feature_id,
               CAST({optional[fields["unit_field"]]} AS VARCHAR) AS unit,
               CAST({optional[PARK_CATEGORY_FIELD]} AS VARCHAR) AS category,
               ST_MakeValid(geom) AS geom
        FROM park_file WHERE geom IS NOT NULL
    """)
    rows = con.execute("SELECT part, name, feature_id, unit, category FROM park_part ORDER BY part").fetchall()

    state = organization_states(registry).get(entry.get("provider"))
    units: dict[str, dict] = {}
    orphans: list[tuple[int, str, str, str | None]] = []
    for part, name, feature_id, unit, category in rows:
        name, feature_id, unit = _clean(name), _clean(feature_id), _clean(unit)
        if not name or not feature_id:
            continue
        if unit is None:
            orphans.append((part, name, feature_id, _clean(category)))
            continue
        row = units.setdefault(f"{PARKS_KEY}:{unit}", _park_row(state))
        _add_part(row, part, name, _clean(category))
    units_by_name: dict[str, set[str]] = {}
    for key, row in units.items():
        for name in row["names"]:
            units_by_name.setdefault(name, set()).add(key)
    for part, name, feature_id, category in orphans:
        keys = units_by_name.get(name, set())
        key = next(iter(keys)) if len(keys) == 1 else f"{PARKS_KEY}:{feature_id}"
        _add_part(units.setdefault(key, _park_row(state)), part, name, category)
    parks = []
    for key, row in units.items():
        names, categories = row.pop("names"), row.pop("categories")
        # The name most of the unit's polygons wear, the shortest on a tie,
        # so "Robert Moses" wins over "Captree/Robert Moses" where both are
        # written on one unit and the count is even.
        row["name"] = min(names, key=lambda name: (-names[name], len(name), name))
        row["category"] = min(categories, key=lambda c: (-categories[c], c)) if categories else None
        parks.append({"id": key, **row})
    return parks, None


def _park_row(state: str | None) -> dict:
    return {"kind": "park", "state": state, "source": PARKS_KEY, "parts": [], "names": Counter(), "categories": Counter()}


def _add_part(row: dict, part: int, name: str, category: str | None) -> None:
    row["parts"].append(part)
    row["names"][name] += 1
    if category:
        row["categories"][category] += 1


def load_point_places(registry: dict, poi_dir: Path, nearby_path: Path, town_states: dict[str, str]) -> list[dict]:
    """Trailheads, parking and towns, from the PUBLISHED waypoint artifacts.

    Named rows only - a place with no name cannot be searched for, and most
    of OPRHP's pull-offs and DEC's lots have none. The published id rides as
    `poiId` so the client can open the waypoint a pick refers to. A row's
    state and whether its resupply rows are towns come from its source's
    registry entry, through the same join every other reader of a published
    `source` makes (lib/source_registry.py)."""
    org_states = organization_states(registry)
    entries: dict[str, dict | None] = {}
    places = []
    seen: set[str] = set()
    published = load_destination_pois(poi_dir, POINT_PLACE_KINDS)
    nearby = (feature.get("properties") or {} for feature in load_features(nearby_path))
    for properties in (*published, *nearby):
        kind = POINT_PLACE_KINDS.get(properties.get("poi_type"))
        source = properties.get("source")
        if kind is None or not source:
            continue
        if source not in entries:
            entries[source] = source_entry(registry, source)
        entry = entries[source] or {}
        if kind == TOWN_KIND and entry.get("place_kind") != TOWN_KIND:
            continue
        poi_id, name = _clean(properties.get("id")), _clean(properties.get("name"))
        lon, lat = properties.get("lon"), properties.get("lat")
        if not poi_id or not name or lon is None or lat is None or poi_id in seen:
            continue
        seen.add(poi_id)
        state = org_states.get(entry.get("provider"))
        if kind == TOWN_KIND:
            state = town_states.get(_clean(properties.get("source_feature_id"))) or state
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


def _bbox(west: float, south: float, east: float, north: float) -> list[float]:
    return [round(west, 5), round(south, 5), round(east, 5), round(north, 5)]


def load_lines(con: duckdb.DuckDBPyConnection, paths: list[Path], shipped: set[str]) -> tuple[int, dict[str, int]]:
    """Load the line artifacts' rows whose source reaches hikers into
    `lines(source, name, geom, g)` - the geographic geometry beside the
    projected, R-tree indexed one - and return how many lines that is and,
    per source, how many were held back.

    Not lib/corridor.load_network_lines, deliberately: that loader keeps one
    projected column of one artifact, and this needs `source` for the gate,
    `name` for the long trails, the geographic geometry for their bboxes,
    and two artifacts in one table. What it shares with the loader it
    imports - the CRS pair and the reading of an empty artifact as an
    ordinary state. The gate is the module docstring's: a line whose steward
    is held back measures nothing here, because it reaches no phone."""
    con.execute("CREATE OR REPLACE TABLE line_rows (source VARCHAR, name VARCHAR, geom GEOMETRY)")
    for path in paths:
        if {"source", "name", "geom"} <= _read_file(con, "line_file", path):
            con.execute("INSERT INTO line_rows SELECT source, name, geom FROM line_file")
    allowed = ", ".join(f"'{key}'" for key in sorted(shipped | {AT_SOURCE}))
    con.execute("DROP INDEX IF EXISTS lines_rtree")
    con.execute(f"""
        CREATE OR REPLACE TABLE lines AS
        SELECT source, name, geom, ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS g
        FROM line_rows WHERE source IN ({allowed})
    """)
    con.execute("CREATE INDEX lines_rtree ON lines USING RTREE (g)")
    held = con.execute(f"""
        SELECT coalesce(source, ''), count(*) FROM line_rows
        WHERE source IS NULL OR source NOT IN ({allowed}) GROUP BY 1 ORDER BY 1
    """).fetchall()
    return con.execute("SELECT count(*) FROM lines").fetchone()[0], dict(held)


def load_named_trails(con: duckdb.DuckDBPyConnection, registry: dict) -> list[dict]:
    """The long trails, from the lines already loaded: every (source, name)
    totalling at least NAMED_TRAIL_THRESHOLD_MILES, plus the A.T. under the
    route name its source owns. export_nearby_trails.py's own threshold and
    its own route-owner map, imported rather than copied, so what the legend
    calls a named trail and what this calls one cannot drift. The rule that
    consumes the threshold is restated here over the PUBLISHED lines rather
    than the overview's simplified records, which is the input this artifact
    is about; the two can differ by a simplified metre, never by a name."""
    # The centerline is grouped by source alone: export_trails.py names each
    # of its features by ATC's own segment name, and a trail summed segment by
    # segment would be forty rows under the threshold rather than one over it.
    owned = next((name for name, owner in owned_route_names(registry).items() if owner == AT_SOURCE), None)
    trail = f"CASE WHEN source = '{AT_SOURCE}' THEN '{owned}' ELSE name END" if owned else "name"
    rows = con.execute(f"""
        SELECT source, trail, metres, ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e)
        FROM (SELECT source, {trail} AS trail, sum(ST_Length(g)) AS metres, ST_Extent_Agg(geom) AS e
              FROM lines GROUP BY source, trail)
    """).fetchall()
    trails = []
    for source, name, metres, west, south, east, north in rows:
        if not _clean(name):
            continue
        miles = metres / METERS_PER_MILE
        if miles < NAMED_TRAIL_THRESHOLD_MILES:
            continue
        bbox = _bbox(west, south, east, north)
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


def measure(con: duckdb.DuckDBPyConnection, parks: list[dict], points: list[dict], radius_miles: float, measured: bool) -> None:
    """Fill in each park's centroid, bbox and the metres of line inside it;
    each point's metres of line within `radius_miles` and the park it sits
    in. The metres stay on the row as `_metres` for the drop rule and print
    as `trailMiles` to a tenth; with nothing to measure against
    (`measured` false) neither join runs and no disc is built - the rows
    keep their centroid, bbox and `within`, which need no line.

    One query per table, the aggregates as LEFT JOINs, so a park no line
    crosses reads zero from the SQL rather than from a priming loop."""
    parts = [(part, idx) for idx, park in enumerate(parks) for part in park["parts"]]
    con.register(
        "_park_unit",
        {"part": np.array([p for p, _ in parts], dtype=np.int64), "idx": np.array([i for _, i in parts], dtype=np.int64)},
    )
    con.execute(f"""
        CREATE OR REPLACE TABLE park AS
        SELECT idx, geom, ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS g
        FROM (SELECT u.idx, ST_Union_Agg(p.geom) AS geom FROM park_part p JOIN _park_unit u USING (part) GROUP BY u.idx)
    """)
    con.unregister("_park_unit")
    park_metres = """
        LEFT JOIN (SELECT p.idx, sum(ST_Length(ST_Intersection(l.g, p.g))) AS metres
                   FROM park p JOIN lines l ON ST_Intersects(l.g, p.g) GROUP BY p.idx) m USING (idx)"""
    for idx, lon, lat, west, south, east, north, metres in con.execute(f"""
        SELECT idx, ST_X(c), ST_Y(c), ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e), coalesce(m.metres, 0)
        FROM (SELECT idx, ST_Centroid(geom) AS c, ST_Extent(geom) AS e FROM park) p
        {park_metres if measured else "LEFT JOIN (SELECT NULL AS idx, NULL AS metres) m USING (idx)"}
    """).fetchall():
        parks[idx]["lon"], parks[idx]["lat"] = round(lon, 5), round(lat, 5)
        parks[idx]["bbox"] = _bbox(west, south, east, north)
        parks[idx]["_metres"] = metres
        parks[idx]["trailMiles"] = round(metres / METERS_PER_MILE, 1)

    # The register-a-dict pattern rather than executemany, for the measured
    # >1000x reason export_elevation.reproject_points_to_wgs84 documents.
    con.register(
        "_pt_src",
        {
            "idx": np.arange(len(points), dtype=np.int64),
            "x": np.array([p["lon"] for p in points], dtype=np.float64),
            "y": np.array([p["lat"] for p in points], dtype=np.float64),
        },
    )
    disc = f"ST_Buffer(ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true), {radius_miles * METERS_PER_MILE})"
    con.execute(f"""
        CREATE OR REPLACE TABLE pt AS
        SELECT idx, geom, {disc if measured else "NULL::GEOMETRY"} AS disc
        FROM (SELECT idx, ST_Point(x, y) AS geom FROM _pt_src)
    """)
    con.unregister("_pt_src")
    point_metres = """
        LEFT JOIN (SELECT t.idx, sum(ST_Length(ST_Intersection(l.g, t.disc))) AS metres
                   FROM pt t JOIN lines l ON ST_Intersects(l.g, t.disc) GROUP BY t.idx) m USING (idx)"""
    for idx, metres, park_idx in con.execute(f"""
        SELECT t.idx, coalesce(m.metres, 0), w.park
        FROM pt t
        {point_metres if measured else "LEFT JOIN (SELECT NULL AS idx, NULL AS metres) m USING (idx)"}
        LEFT JOIN (SELECT t.idx, min(p.idx) AS park FROM pt t JOIN park p ON ST_Contains(p.geom, t.geom) GROUP BY t.idx) w USING (idx)
    """).fetchall():
        points[idx]["_metres"] = metres
        points[idx]["trailMiles"] = round(metres / METERS_PER_MILE, 1)
        if park_idx is not None:
            points[idx]["within"] = parks[park_idx]["name"]


def _record(place: dict) -> dict:
    """The published row: every field with a value, in one fixed order, and
    never the working state (the polygon parts, the raw metres)."""
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
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    parks, parks_held = load_parks(con, parks_path, registry)
    points = load_point_places(registry, poi_dir, nearby_path, community_states(communities_raw))
    line_count, lines_held = load_lines(con, line_paths, shipped_line_source_keys(registry))
    measured = line_count > 0
    trails = load_named_trails(con, registry)
    measure(con, parks, points, radius_miles, measured)

    dropped: Counter[str] = Counter()
    kept_points = []
    for point in points:
        if measured and point["kind"] in DROPPED_WHEN_FAR and point["_metres"] == 0:
            dropped[f"{point['source']}/{point['kind']}"] += 1
        else:
            kept_points.append(point)

    places = sorted(parks + kept_points + trails, key=lambda place: (place["kind"], place["name"], place["id"]))
    if not measured:
        for place in places:
            place.pop("trailMiles", None)
    output = {
        "generated_at": utc_stamp(generated_at),
        "trailRadiusMiles": radius_miles,
        "trailMilesMeasured": measured,
        "places": [_record(place) for place in places],
    }
    parks_entry = find_source(registry, PARKS_KEY) or {}
    report = {
        "counts": dict(Counter(place["kind"] for place in places)),
        "lines_measured": line_count,
        "lines_held_back": lines_held,
        "dropped_far_from_any_line": dict(dropped.most_common()),
        "parks_held_back": parks_held,
        # The same `sources` shape the line and POI manifests carry, so the
        # publish log's held-back report and check_output_quality read this
        # artifact the way they read its siblings.
        "sources": {
            PARKS_KEY: {
                "steward": parks_entry.get("steward"),
                "attribution": parks_entry.get("attribution"),
                "reaches_hikers": bool(parks_entry.get("reaches_hikers")),
                "rows": sum(1 for place in places if place["kind"] == "park"),
            }
        },
    }
    return output, report


def write_artifact(output: dict, report: dict) -> dict:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, separators=(",", ":")) + "\n", encoding="utf-8")
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
    for source, count in report["lines_held_back"].items():
        print(f"{count} line(s) from {source or 'no source'} measure nothing: reaches_hikers is false.", file=sys.stderr)
    counted = ", ".join(f"{count} {kind}" for kind, count in sorted(report["counts"].items()))
    dropped = sum(report["dropped_far_from_any_line"].values())
    print(f"{len(output['places'])} places ({counted}; {dropped} dropped far from any line) -> {OUT_PATH}")
    print(f"Manifest -> {MANIFEST_PATH}")
    return manifest


if __name__ == "__main__":
    main()
