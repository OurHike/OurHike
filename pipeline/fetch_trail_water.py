"""Derive data/raw/trail_water.json - where the A.T. meets water, and which
shelters and campsites have water they can actually walk to.

This replaces an earlier attempt that published, on every shelter card, the
nearest USGS-mapped stream within a kilometre. That was the wrong claim: a
stream 700 m away is a true fact about the map and says nothing about the
shelter, and a card that prints it is answering a question nobody asked. What
a hiker asks is "can I get water here" and "where does the trail cross
water" - so this file answers those two, and nothing else.

## What it produces

**Crossings** - exact geometric intersections of ATC's centerline with the
stream lines of both hydrographies. Not a proximity guess: the two lines
cross, so a hiker walking the trail walks through the water. **1,125 of them
over the corridor, 571 seen by both databases**, filling the `crossing`
poi_type that lib/poi_schema.py declared and nothing has ever populated
(#97's investigation measured the same thing against NHD alone first: 841).

**Site water** - for each shelter and campsite, the nearest point on a
stream, published as a water POI only when a hiker could actually reach it:

  - **within MATCH_RADIUS_FT of the site**, because a water source is
    somewhere you walk with a bottle, not somewhere on the same hillside; and
  - **not down a cliff** - the ground between the site and the water must not
    exceed MAX_GRADE, measured from real elevations at both ends (USGS EPQS,
    the 3DEP data the elevation profile already reads).

Both gates have to hold. A stream 90 ft away and 120 ft below is not this
shelter's water source however close the map says it is, and publishing it as
one would send somebody over an edge in the dark looking for it.

## Both hydrographies, merged - and why USGS arrives in bulk

USGS and OSM know different things about the same streams. **USGS classifies
flow** - perennial, intermittent, ephemeral - which is the one structured
answer anywhere to "will this be dry in August", and OSM has almost nothing
like it. **OSM more often has the local name**, and its geometry is edited by
people who walk there. Taking one and dropping the other throws away half of
what a hiker could be told, so both are read and the duplicates are merged
rather than resolved to a winner (merge_stream_facts, and
features/POI_DEDUPLICATION.md's rule, written after this branch's first merge
did exactly the wrong thing).

USGS is taken as **bulk staged GeoPackages, one per subregion**, not through
its query service, and that is not a preference: asking NHDPlus HR for the
reaches along 2,197 miles of trail means hundreds of polyline queries, and
that service 504s under exactly that load - the same failure that killed two
publish runs through the TNM Access API (pipeline/ELEVATION_SOURCES.md,
#549). Each subregion is downloaded, read and deleted in turn, so the peak
cost on disk is one ~270 MB archive rather than 3.1 GB of them, and the whole
derivation re-runs without a single interactive request.

OSM costs no network at all: `fetch_osm_water.py` and the basemap build both
download the fourteen Geofabrik state extracts already, and this reads the
same files off disk.

## Why the terrain gate applies to these and not to the mapped springs

The points here are DERIVED - nobody stood at them; geometry put them where a
stream passes nearest a shelter. That derivation is exactly what can be wrong
in the way a contour hides, so it is gated on the contour. A `natural=spring`
node or a water point in opentrail.org is the opposite: somebody was there
and recorded it, and the fact that a mapper bothered is itself evidence the
source gets used. Those ride in ungated, and the two kinds are told apart by
`source` on the published feature.

## The join is the site fold, not a second matching rule

A water point within lib/poi_sites.py's PROXIMITY_RADIUS_M (60 m / 197 ft)
already folds into a shelter's site and rides its pin, so a match under
MATCH_RADIUS_FT needs no new association logic: it is published at its real
coordinates and the existing grouping does the rest. That is also why the
radius here stays inside that gate - a "match" this file cannot make the map
show would be a match in name only.

## Why this is a fetch step and not a reviewed file

It nearly shipped as `reference/trail_water.json`, checked in beside
shelter_capacity.json and water_distance.json, and that was the wrong shelf.
Those two are JOINS THAT ENCODE JUDGEMENT - a row in shelter_capacity.json is
somebody's decision that this hiker-list entry is that ATC shelter, and a
diff of it is a review of those decisions. This file's rows are derived
geometry: 1,125 crossing coordinates and 512 site verdicts, none of which a
human reads one by one.

The judgement here lives in the CONSTANTS - MATCH_RADIUS_FT, MAX_GRADE,
CROSSING_DEDUPE_M, which streams count - and those are code, reviewed as
code. So the output goes where every other derived input goes: `data/raw/`,
gitignored, cached between CI runs, and standing behind a receipt like every
other fetcher (#542). What reaches hikers reaches them the way every layer
does - through export_poi.py into `crossing.geojson` and `water.geojson`, and
through publish.py into R2.

Re-running it costs the extracts already on disk plus ~3.1 GB of USGS
subregions downloaded and deleted in turn, which is why the publish workflow
makes it an opt-in step and why its output rides the fetch cache: a run that
does not ask for it exports whatever the last run derived, exactly as the
photo fetches behave.

Licence: NHD and 3DEP are U.S. federal work in the public domain (USGS asks
for a courtesy citation, which the source block carries). OSM is ODbL -
attribution and share-alike, the terms the basemap and `fetch_osm_water.py`
already comply with. Every published description names whichever of the two
it came from, and a merged one names both, so the attribution travels with
the record rather than sitting in a registry line somebody has to find.

Usage:
    python fetch_trail_water.py

A derivation this expensive must not be able to quietly replace good output
with less of it, so the write is guarded the way fetch_opentrail.py's is: a
result under MIN_CROSSINGS, or one that has lost more than
MAX_CROSSING_DROP_RATIO of what is already on disk, refuses rather than
overwrites. Ordinary edits to either hydrography never halve a corridor's
crossings; a broken read does.
"""

import argparse
import json
import math
import sys
import time
import zipfile
from pathlib import Path

import duckdb
import requests

from build_water_distance import fetch_atc_features
from export_basemap import AT_STATES, OSM_RAW_DIR
from lib import fetch_receipts

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = RAW_DIR / "trail_water.json"
NHD_TMP_DIR = RAW_DIR / "nhd_tmp"

# Ground elevations already asked for, under data/ because it is a fetch
# artifact rather than reviewed source - the answers are USGS's and the file
# is disposable.
ELEVATION_CACHE_PATH = RAW_DIR / "epqs_elevations.json"
CENTERLINE_PATH = RAW_DIR / "centerline.geojson"

# What counts as a stream a hiker could fill a bottle from. `waterway=ditch`,
# `drain` and `canal` are deliberately absent - all three are water and none
# of them is drinking water anybody should be pointed at - and so are the
# lake and pond polygons `natural=water` draws, whose honesty question
# fetch_osm_water.py's docstring leaves open.
STREAM_WATERWAYS = ("stream", "river")

# USGS's own hydrography, taken in bulk rather than by query. The service
# 504s under corridor-scale polyline queries; the staged GeoPackages are one
# ~270 MB download per subregion, read offline and thrown away again.
#
# NHD is a frozen snapshot - USGS retired it 2023-10-01 and its 3DHP
# successor drops the flow classification entirely (WATER_SOURCES.md §5) -
# which is the second reason the answer is checked in rather than re-fetched.
NHD_GPKG_URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/HU4/GPKG/NHD_H_{huc4}_HU4_GPKG.zip"

# The 21 subregions the trail actually crosses, from the WBD's own polygons
# queried against the centerline (not its bounding box, which is a slab of
# the eastern seaboard). 0430 "Middle Saint Lawrence" is the one that looks
# wrong and is not: the Vermont trail drains to Lake Champlain.
NHD_HU4S = (
    "0102",
    "0103",
    "0104",
    "0106",
    "0107",
    "0108",
    "0110",
    "0202",
    "0203",
    "0204",
    "0205",
    "0207",
    "0208",
    "0301",
    "0306",
    "0313",
    "0315",
    "0430",
    "0505",
    "0601",
    "0602",
)

# StreamRiver FCodes. 46000 is a stream USGS never classified, so it enters
# with no flow claim at all rather than a hedged one; artificial paths
# (55800 - the threads drawn through lakes to keep the network connected) and
# canals are excluded by asking for what is wanted.
NHD_FLOW_BY_FCODE = {46006: "perennial", 46003: "intermittent", 46007: "ephemeral", 46000: None}

# USGS's point elevation service, feet. Same 3DEP data export_elevation.py
# samples the profile from; ELEVATION_SOURCES.md measured it at ~1.9 s/point,
# which is why only the candidates that pass the distance gate are queried.
EPQS_URL = "https://epqs.nationalmap.gov/v1/json"

# How far a hiker may walk for a stream to count as this site's water.
#
# The maintainer's number, kept tight on their reasoning rather than mine:
# **most A.T. shelters have had their own spring built out over decades**, so
# the water a shelter actually uses is usually a piped source somebody dug,
# not the nearest blue line on a map. Where those two disagree ATC's own
# measured distance is the better answer for a shelter (build_water_distance.py,
# #668), and this derivation is not trying to beat it - it fills in a real
# COORDINATE where geometry can honestly supply one, and stays quiet where it
# cannot.
#
# It also sits inside lib/poi_sites.py's 60 m proximity fold on purpose (see
# the module docstring): a match the map cannot draw as part of the site
# would be a match in name only. Every candidate out to REPORT_RADIUS_FT is
# recorded with its numbers regardless, so widening this is a decision
# somebody can make from the file.
MATCH_RADIUS_FT = 100.0
REPORT_RADIUS_FT = 400.0

# "Not down a cliff", as a number: rise over run between the site and the
# water.
#
# This started at 0.35 and the maintainer's answer was that a 30% grade is
# ridiculous, which it is: a 35 ft drop over 100 ft of ground is a scramble
# somebody does once with an empty bottle and not again at dusk with a full
# one. 0.15 is the top of the range they named (10-15%) - a 15 ft drop over
# 100 ft, which is a path down a bank rather than a descent.
#
# The looser number was never doing much work anyway: at 0.35 it refused 4
# candidates out of 47. The gate that binds is MATCH_RADIUS_FT, and that one
# is deliberately tight (see there).
MAX_GRADE = 0.15

# Two crossings closer than this are one crossing.
#
# The frame is A HIKER'S STOP rather than a database's identity: two places
# the trail meets water 50 m apart are one stop with one bottle, whether they
# are one stream drawn twice or a stream and the tributary joining it.
#
# A CORRECTION IS RECORDED HERE ON PURPOSE. This constant was first argued up
# from 20 m on a measurement that said not one OSM crossing landed within
# 20 m of a USGS one, median nearest neighbour 363 m - which would have meant
# the two databases could never be reconciled. That measurement was taken on
# output whose merge was silently broken (see dedupe_crossings), so it
# measured the leftovers of a collapse rather than the relationship, and it
# was wrong. With the merge working, **571 of the corridor's 1,125 crossings
# are seen by both databases** at this radius: they agree about the water far
# more than that artifact suggested.
#
# 50 m stands anyway, on the hiker's-stop reasoning it should have rested on
# in the first place. Whether 20 m would serve as well is a real question and
# an honest re-measurement away - one this file's own counts would answer.
CROSSING_DEDUPE_M = 50.0

# The same question for a site's water is a different question, and keeps the
# tighter number. Both databases' nearest points are anchored to the same
# shelter, so they converge on it rather than drifting apart - 25 of the 39
# published points already merged at 20 m. Widening it here would start
# folding a shelter's spring into the creek below it, which are two things a
# hiker chooses between.
SITE_WATER_MERGE_M = 20.0

M_PER_FT = 0.3048
M_PER_DEG_LAT = 111_132.0

USER_AGENT = "OurHike-pipeline/1.0 (+https://github.com/OurHike/OurHike)"
TIMEOUT = 90
TRIES = 5

NO_STREAM_NEARBY = f"no stream within {REPORT_RADIUS_FT:.0f} ft"

# The write guards, in fetch_opentrail.py's shape and for its reason. The
# floor is far under the 1,125 the corridor measured (2026-08-13), because it
# is there to catch a read that returned nothing, not to police the tide.
MIN_CROSSINGS = 200
MAX_CROSSING_DROP_RATIO = 0.5
TOO_FAR = "the nearest stream is {distance_ft:.0f} ft away, past the {radius:.0f} ft a hiker walks for water"
TOO_STEEP = (
    "the ground drops {drop_ft:.0f} ft over {distance_ft:.0f} ft - a {grade:.0%} grade, which is a scramble rather than a walk"
)


def osm_stream_table(con: duckdb.DuckDBPyConnection, pbf: Path) -> int:
    """Assemble one state's OSM stream geometry into the `streams` table.

    Three passes over the extract, in the only order that fits in memory: the
    stream WAYS first (a way is an id and a list of node references, no
    coordinates); then only the NODES those ways reference, which is what
    keeps a state's twenty million other nodes out of this; then the two
    joined back into linestrings, ordered by each way's own reference order -
    unordered, a stream's vertices would zigzag and every distance computed
    from it would be wrong.

    `flow` is NULL unless a mapper tagged `intermittent`, and NULL means
    nobody said - never "year-round". USGS is where a positive flow claim
    comes from, which is the whole reason both sources are read.
    """
    waterways = ", ".join(f"'{kind}'" for kind in STREAM_WATERWAYS)
    con.execute(f"""
        CREATE OR REPLACE TABLE ways AS
        SELECT id, refs, tags['name'] AS name, tags['intermittent'] AS intermittent, tags['seasonal'] AS seasonal
        FROM st_readosm('{pbf.as_posix()}')
        WHERE kind = 'way' AND tags IS NOT NULL AND tags['waterway'] IN ({waterways})
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE way_nodes AS
        SELECT id, lat, lon FROM st_readosm('{pbf.as_posix()}')
        WHERE kind = 'node' AND id IN (SELECT UNNEST(refs) FROM ways)
    """)
    con.execute("""
        CREATE OR REPLACE TABLE streams AS
        WITH pairs AS (
            SELECT id, name, intermittent, seasonal,
                   UNNEST(refs) AS ref,
                   UNNEST(range(1, len(refs) + 1)) AS position
            FROM ways
        )
        SELECT 'osm' AS source,
               CAST(pairs.id AS VARCHAR) AS id,
               any_value(pairs.name) AS name,
               CASE
                   WHEN lower(any_value(pairs.intermittent)) = 'yes' THEN 'intermittent'
                   WHEN lower(coalesce(any_value(pairs.seasonal), 'no')) NOT IN ('no', '') THEN 'intermittent'
                   ELSE NULL
               END AS flow,
               ST_MakeLine(list(ST_Point(way_nodes.lon, way_nodes.lat) ORDER BY pairs.position)) AS geom
        FROM pairs JOIN way_nodes ON way_nodes.id = pairs.ref
        GROUP BY pairs.id
        HAVING count(*) >= 2
    """)
    return con.execute("SELECT count(*) FROM streams").fetchone()[0]


def nhd_stream_table(con: duckdb.DuckDBPyConnection, gpkg: Path) -> int:
    """Assemble one subregion's NHD flowlines into the same `streams` table.

    One statement rather than three: a GeoPackage already holds assembled
    geometry, which is the whole advantage of taking USGS in bulk. ST_Force2D
    because NHD carries Z values the intersection has no use for and DuckDB's
    predicates would otherwise have to carry around.

    The geometry column is `SHAPE`, not `geom`: these GeoPackages are written
    out of Esri tooling and keep its name for it. Spelled here rather than
    discovered at runtime, so a layout change fails loudly on the next
    re-run instead of quietly matching nothing.

    And NHD is NAD83 (EPSG:4269) where the centerline is WGS84, so it is
    transformed on the way in rather than assumed compatible - DuckDB
    refuses to intersect across coordinate systems, which is the right
    refusal even though the two differ by about a metre here. `always_xy`
    for the reason README.md gives at length: without it EPSG:4326's
    authority-defined lat/lon axis order silently swaps every coordinate.
    """
    fcodes = ", ".join(str(code) for code in NHD_FLOW_BY_FCODE)
    cases = " ".join(
        f"WHEN fcode = {code} THEN {'NULL' if flow is None else repr(flow)}" for code, flow in NHD_FLOW_BY_FCODE.items()
    )
    con.execute(f"""
        CREATE OR REPLACE TABLE streams AS
        SELECT 'nhd' AS source,
               permanent_identifier AS id,
               gnis_name AS name,
               CASE {cases} ELSE NULL END AS flow,
               ST_Transform(ST_Force2D(SHAPE), 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
        FROM ST_Read('{gpkg.as_posix()}', layer='NHDFlowline')
        WHERE fcode IN ({fcodes})
    """)
    return con.execute("SELECT count(*) FROM streams").fetchone()[0]


def state_crossings(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Where the loaded state's streams cross the trail.

    A true geometric intersection, computed by DuckDB's spatial extension
    rather than inferred from a radius: #97 records that buffer-and-count
    overshoots into thousands of near-misses, while the lines crossing is a
    fact neither dataset can be talked out of.

    The CTE is not cosmetic - written as a subquery in the FROM list beside
    the two tables it reads, the join is uncorrelated and each intersection
    point is paired with the wrong stream's name.
    """
    rows = con.execute("""
        WITH hits AS (
            SELECT streams.source AS source,
                   streams.id AS stream_id,
                   streams.name AS name,
                   streams.flow AS flow,
                   UNNEST(ST_Dump(ST_Intersection(centerline.geom, streams.geom))).geom AS point
            FROM streams JOIN centerline ON ST_Intersects(centerline.geom, streams.geom)
        )
        SELECT source, stream_id, name, flow, ST_X(point) AS lon, ST_Y(point) AS lat
        FROM hits WHERE ST_GeometryType(point) = 'POINT'
    """).fetchall()
    return [
        {"sources": [source], "stream_id": str(stream_id), "name": name or None, "flow": flow, "lat": lat, "lon": lon}
        for source, stream_id, name, flow, lon, lat in rows
        if lat is not None and lon is not None
    ]


def state_site_candidates(con: duckdb.DuckDBPyConnection) -> dict[str, list[dict]]:
    """Every stream reach running near a site, keyed by the site's GlobalID.

    ST_DWithin in degrees, generously: it only has to over-select, because
    the distance that decides anything is computed exactly afterwards in
    metres. A degree of longitude is shorter than a degree of latitude
    everywhere on this trail, so a single degree threshold errs wide in the
    direction that matters.
    """
    degrees = (REPORT_RADIUS_FT * M_PER_FT) / (M_PER_DEG_LAT * math.cos(math.radians(45.0)))
    rows = con.execute(f"""
        SELECT sites.global_id, streams.source, streams.id, streams.name, streams.flow, ST_AsGeoJSON(streams.geom)
        FROM streams JOIN sites ON ST_DWithin(streams.geom, sites.geom, {degrees})
    """).fetchall()
    candidates: dict[str, list[dict]] = {}
    for global_id, source, stream_id, name, flow, geojson in rows:
        geometry = json.loads(geojson)
        paths = [geometry["coordinates"]] if geometry["type"] == "LineString" else geometry["coordinates"]
        candidates.setdefault(global_id, []).append(
            {"source": source, "stream_id": str(stream_id), "name": name or None, "flow": flow, "paths": paths}
        )
    return candidates


def collect_streams(sites: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    """Walk both hydrographies once, collecting crossings and site candidates.

    One dataset at a time, each dropped before the next is read: fourteen
    state extracts and twenty-one subregions at once is tens of gigabytes,
    and nothing here needs two in memory together. The USGS subregions are
    downloaded, read and deleted in the same loop, so the peak cost on disk
    is one 270 MB archive rather than 3.1 GB of them.
    """
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE OR REPLACE TABLE centerline AS SELECT * FROM ST_Read('{CENTERLINE_PATH.as_posix()}')")
    con.execute("CREATE OR REPLACE TABLE sites (global_id VARCHAR, geom GEOMETRY)")
    con.executemany(
        "INSERT INTO sites VALUES (?, ST_Point(?, ?))",
        [(site["global_id"], site["lon"], site["lat"]) for site in sites],
    )

    crossings: list[dict] = []
    candidates: dict[str, list[dict]] = {}

    def collect(label: str, reaches: int) -> None:
        found = state_crossings(con)
        crossings.extend(found)
        for global_id, near in state_site_candidates(con).items():
            candidates.setdefault(global_id, []).extend(near)
        print(f"  {label}: {reaches} stream reaches, {len(found)} crossings", flush=True)

    for state in AT_STATES:
        pbf = OSM_RAW_DIR / f"{state}-latest.osm.pbf"
        if not pbf.exists():
            raise FileNotFoundError(f"{pbf} is missing - run fetch_osm_water.py (or export_basemap.py) first")
        collect(f"osm/{state}", osm_stream_table(con, pbf))

    for huc4 in NHD_HU4S:
        gpkg = fetch_nhd_subregion(huc4)
        try:
            collect(f"nhd/{huc4}", nhd_stream_table(con, gpkg))
        finally:
            # Deleted whichever way the read went: 270 MB apiece, and a
            # failure part-way through must not leave twenty of them behind.
            gpkg.unlink(missing_ok=True)
    return crossings, candidates


def fetch_nhd_subregion(huc4: str) -> Path:
    """Download and unpack one NHD subregion's GeoPackage, returning its path.

    Straight to a temporary directory rather than data/raw/: unlike the OSM
    extracts, nothing else in this pipeline reads these, and keeping 3.1 GB
    of them to re-run a derivation whose answer is checked in would be
    storing the working out.
    """
    NHD_TMP_DIR.mkdir(parents=True, exist_ok=True)
    archive = NHD_TMP_DIR / f"NHD_H_{huc4}_HU4_GPKG.zip"
    url = NHD_GPKG_URL.format(huc4=huc4)
    with requests.get(url, stream=True, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as response:
        response.raise_for_status()
        with open(archive, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
    with zipfile.ZipFile(archive) as bundle:
        names = [name for name in bundle.namelist() if name.endswith(".gpkg")]
        if not names:
            raise ValueError(f"{url} holds no .gpkg - the staged product's layout has changed")
        bundle.extract(names[0], NHD_TMP_DIR)
    archive.unlink(missing_ok=True)
    return NHD_TMP_DIR / names[0]


def merge_stream_facts(kept: dict, other: dict) -> dict:
    """Fold a duplicate's facts into the one being kept.

    COMBINE, NEVER DROP-THE-LOSER, which is the rule
    features/POI_DEDUPLICATION.md wrote down after watching this branch's
    first merge throw the losing record's tags away. The two hydrographies
    know different things about the same stream - USGS classifies flow and
    OSM often has the local name - so a merged crossing keeps whichever half
    each supplied, and says so: `sources` carries both, and `flow_source`
    records who made the flow claim, because "mapped as year-round" is a
    statement somebody is answerable for.
    """
    merged = dict(kept)
    merged["sources"] = sorted(set(kept.get("sources", [])) | set(other.get("sources", [])))
    merged["name"] = kept.get("name") or other.get("name")
    if not kept.get("flow") and other.get("flow"):
        merged["flow"] = other["flow"]
        merged["flow_source"] = other.get("flow_source") or (other.get("sources") or [None])[0]
    return merged


def dedupe_crossings(crossings: list[dict]) -> list[dict]:
    """One pin per place the trail meets water.

    By PROXIMITY rather than by identity, and across both databases at once:
    OSM splits a stream wherever a tag changes, USGS splits a reach at every
    confluence, and the two disagree about where the same water is by tens of
    metres anyway (see CROSSING_DEDUPE_M for the measurement). A hiker
    walking through gets wet once.
    """
    kept: list[dict] = []
    # USGS first, so a merged crossing keeps the surveyed position and OSM's
    # name folds onto it rather than the other way round. Within
    # CROSSING_DEDUPE_M the two are the same stop either way; this only
    # decides which one the published id is built from, and that id has to be
    # stable across re-runs.
    for crossing in sorted(crossings, key=lambda c: ("nhd" not in c["sources"], c["lat"], c["lon"])):
        twin = next(
            (
                index
                for index, other in enumerate(kept)
                if distance_between(crossing["lat"], crossing["lon"], other["lat"], other["lon"]) <= CROSSING_DEDUPE_M
            ),
            None,
        )
        if twin is None:
            kept.append(
                {
                    **crossing,
                    "flow_source": crossing["sources"][0] if crossing.get("flow") else None,
                    "lat": round(crossing["lat"], 6),
                    "lon": round(crossing["lon"], 6),
                }
            )
            continue
        # COMBINED, not discarded: the loser usually knows something the
        # winner does not - a name, or the flow class - and dropping it is
        # the mistake features/POI_DEDUPLICATION.md was written about.
        kept[twin] = merge_stream_facts(kept[twin], crossing)
    return sorted(kept, key=lambda crossing: (crossing["lat"], crossing["lon"]))


def distance_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Metres between two points, equirectangular - exact well past any
    distance this module cares about."""
    mx = M_PER_DEG_LAT * math.cos(math.radians(lat1))
    return math.hypot((lon2 - lon1) * mx, (lat2 - lat1) * M_PER_DEG_LAT)


def closest_point_on_paths(lat: float, lon: float, paths: list[list[list[float]]]) -> tuple[float, float, float]:
    """(distance in metres, lat, lon) of the nearest point on a flowline.

    Point-to-SEGMENT, and the point is returned rather than only the
    distance: a shelter beside the middle of a long reach is beside the
    stream there, and there is where a hiker walks - reporting a vertex
    would put the published water point somewhere nobody goes.
    """
    mx = M_PER_DEG_LAT * math.cos(math.radians(lat))
    best = (math.inf, lat, lon)
    for path in paths:
        points = [((x - lon) * mx, (y - lat) * M_PER_DEG_LAT) for x, y in path]
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            dx, dy = bx - ax, by - ay
            length_sq = dx * dx + dy * dy
            if length_sq == 0:
                t = 0.0
            else:
                t = max(0.0, min(1.0, -(ax * dx + ay * dy) / length_sq))
            px, py = ax + t * dx, ay + t * dy
            distance = math.hypot(px, py)
            if distance < best[0]:
                best = (distance, lat + py / M_PER_DEG_LAT, lon + px / mx)
    return best


def nearest_stream(lat: float, lon: float, candidates: list[dict]) -> dict | None:
    """The nearest reachable stream point, with both hydrographies' facts.

    Nearest is computed PER SOURCE and then merged, rather than taken once
    across the pile, because the two databases draw the same stream a few
    metres apart and the winner would otherwise decide which facts survive.
    Where their nearest points agree to within CROSSING_DEDUPE_M it is one
    stream: the closer point is published and the other's name or flow class
    folds onto it (merge_stream_facts). Where they disagree by more than
    that they are different water, and the closer one is simply the answer.

    The candidates arrive pre-filtered by the spatial join, so this is the
    exact half: point-to-SEGMENT against every reach that came back, keeping
    the point itself rather than only the distance.
    """
    limit_m = REPORT_RADIUS_FT * M_PER_FT
    best_by_source: dict[str, dict] = {}
    for candidate in candidates:
        distance, point_lat, point_lon = closest_point_on_paths(lat, lon, candidate["paths"])
        if distance > limit_m:
            continue
        current = best_by_source.get(candidate["source"])
        if current is None or distance < current["distance_m"]:
            best_by_source[candidate["source"]] = {
                "sources": [candidate["source"]],
                "stream_id": candidate["stream_id"],
                "name": candidate["name"],
                "flow": candidate["flow"],
                "flow_source": candidate["source"] if candidate["flow"] else None,
                "distance_m": distance,
                "lat": point_lat,
                "lon": point_lon,
            }
    if not best_by_source:
        return None

    ranked = sorted(best_by_source.values(), key=lambda found: found["distance_m"])
    best = ranked[0]
    for other in ranked[1:]:
        if distance_between(best["lat"], best["lon"], other["lat"], other["lon"]) <= SITE_WATER_MERGE_M:
            best = merge_stream_facts(best, other)
    return best


def elevation_ft(lat: float, lon: float) -> float | None:
    """Ground elevation in feet from USGS EPQS, or None if it will not say.

    None rather than a raise: an elevation this service cannot answer is a
    candidate this file declines to publish, which is the same safe direction
    every other gate here rounds in.

    Cached on disk, because the gates above are meant to be argued with. The
    ground does not move between runs, and re-deriving with a tighter
    MAX_GRADE should cost the reading of the hydrography and not several
    hundred more round trips to a service that answers in seconds apiece.
    """
    cache = _elevation_cache()
    key = f"{lat:.6f},{lon:.6f}"
    if key in cache:
        return cache[key]
    for attempt in range(TRIES):
        try:
            response = requests.get(
                EPQS_URL,
                params={"x": lon, "y": lat, "units": "Feet", "wkid": 4326, "includeDate": "false"},
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            value = response.json().get("value")
            elevation = None if value is None else float(value)
            if elevation is not None:
                cache[key] = elevation
                _write_elevation_cache(cache)
            return elevation
        except Exception:  # noqa: BLE001 - retried, then declined
            time.sleep(2**attempt)
    return None


_ELEVATION_CACHE: dict[str, float] | None = None


def _elevation_cache() -> dict[str, float]:
    global _ELEVATION_CACHE
    if _ELEVATION_CACHE is None:
        _ELEVATION_CACHE = json.loads(ELEVATION_CACHE_PATH.read_text()) if ELEVATION_CACHE_PATH.exists() else {}
    return _ELEVATION_CACHE


def _write_elevation_cache(cache: dict[str, float]) -> None:
    ELEVATION_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = ELEVATION_CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache))
    tmp.replace(ELEVATION_CACHE_PATH)


def resolve_site(feature: dict, layer: str, candidates: list[dict]) -> dict:
    """One site's record: the water it can reach, or why it cannot.

    Every candidate out to REPORT_RADIUS_FT is written down with its
    distance, its drop and its grade, whether or not it passed - the numbers
    are what make MATCH_RADIUS_FT and MAX_GRADE reviewable rather than
    magic.
    """
    record = {
        "layer": layer,
        "atc_global_id": feature["global_id"],
        "atc_name": feature["name"],
        "water": None,
    }
    candidate = nearest_stream(feature["lat"], feature["lon"], candidates)
    if candidate is None:
        record["unresolved"] = NO_STREAM_NEARBY
        return record

    distance_ft = candidate["distance_m"] / M_PER_FT
    record["candidate"] = {
        "sources": candidate["sources"],
        "name": candidate["name"],
        "flow": candidate["flow"],
        "flow_source": candidate["flow_source"],
        "distance_ft": round(distance_ft, 1),
        "lat": round(candidate["lat"], 6),
        "lon": round(candidate["lon"], 6),
    }
    if distance_ft > MATCH_RADIUS_FT:
        record["unresolved"] = TOO_FAR.format(distance_ft=distance_ft, radius=MATCH_RADIUS_FT)
        return record

    site_elevation = elevation_ft(feature["lat"], feature["lon"])
    water_elevation = elevation_ft(candidate["lat"], candidate["lon"])
    if site_elevation is None or water_elevation is None:
        record["unresolved"] = "USGS would not give an elevation for one end of the walk, so the ground between is unknown"
        return record

    drop_ft = abs(site_elevation - water_elevation)
    # Guard the division: two points a foot apart are the same place, and a
    # grade computed from that is noise rather than terrain.
    grade = drop_ft / max(distance_ft, 1.0)
    record["candidate"].update(
        {
            "site_elevation_ft": round(site_elevation, 1),
            "water_elevation_ft": round(water_elevation, 1),
            "drop_ft": round(drop_ft, 1),
            "grade": round(grade, 3),
        }
    )
    if grade > MAX_GRADE:
        record["unresolved"] = TOO_STEEP.format(drop_ft=drop_ft, distance_ft=distance_ft, grade=grade)
        return record

    record["water"] = {
        "sources": candidate["sources"],
        "stream_id": candidate["stream_id"],
        "name": candidate["name"],
        "flow": candidate["flow"],
        "flow_source": candidate["flow_source"],
        "distance_ft": round(distance_ft, 1),
        "drop_ft": round(drop_ft, 1),
        "grade": round(grade, 3),
        "lat": round(candidate["lat"], 6),
        "lon": round(candidate["lon"], 6),
    }
    return record


README = [
    "Where the A.T. meets water, and which shelters and campsites have water",
    "they can actually walk to (#529).",
    "",
    "GENERATED by fetch_trail_water.py - re-run that script rather than",
    "editing rows here, and review the diff it produces.",
    "",
    "`crossings` are exact geometric intersections of ATC's centerline with",
    "USGS and OSM stream lines: the two lines cross, so a hiker walking the trail",
    "walks through the water. export_poi.py publishes them as the `crossing`",
    "poi_type, which has been declared and empty since it was declared.",
    "",
    "`sites` carries one record per shelter and campsite. A record publishes",
    # Interpolated rather than written out, because this said "35%" for as
    # long as MAX_GRADE was 0.15 - a file describing a gate twice as loose as
    # the one it was actually written under, in the one place a reader would
    # look to check.
    f"water only when a hiker could reach it - within {MATCH_RADIUS_FT:.0f} ft AND under a {MAX_GRADE:.0%}",
    "grade, measured from real USGS elevations at both ends, because a stream",
    "90 ft away and 120 ft below is not a water source however close the map",
    "says it is. Everything rejected keeps its numbers and its reason, so",
    "widening either gate is a decision somebody can make from this file.",
    "",
    "A published water point is a real coordinate on the stream (the nearest",
    "point on the reach, not a vertex), so lib/poi_sites.py's 60 m proximity",
    "fold attaches it to the site with no second matching rule.",
    "",
    "Streams come from BOTH hydrographies, merged: USGS classifies flow",
    "(perennial / intermittent), OSM more often has the local name, and a",
    "record deduped across the two keeps whichever half each supplied -",
    "`sources` says who, and `flow_source` says who made the flow claim.",
]


def build(features_by_layer: dict[str, list[dict]], candidates: dict[str, list[dict]], crossings: list[dict]) -> dict:
    sites = []
    for layer, features in features_by_layer.items():
        for feature in features:
            sites.append(resolve_site(feature, layer, candidates.get(feature["global_id"], [])))

    matched = [site for site in sites if site["water"] is not None]
    counts = {
        "crossings": len(crossings),
        "sites": len(sites),
        "sites_with_water": len(matched),
        "named_crossings": sum(1 for crossing in crossings if crossing["name"]),
        "crossings_from_both": sum(1 for crossing in crossings if len(crossing["sources"]) > 1),
        "crossings_usgs_only": sum(1 for crossing in crossings if crossing["sources"] == ["nhd"]),
        "crossings_osm_only": sum(1 for crossing in crossings if crossing["sources"] == ["osm"]),
    }
    for flow in ("perennial", "intermittent", "ephemeral"):
        counts[f"crossings_{flow}"] = sum(1 for crossing in crossings if crossing["flow"] == flow)

    return {
        "_README": README,
        "source": {
            "title": "USGS NHD flowlines + OpenStreetMap stream ways, merged; USGS 3DEP point elevations",
            "url": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/HU4/GPKG/",
            "provider": "U.S. Geological Survey; OpenStreetMap contributors",
            "licence": (
                "NHD and 3DEP are U.S. federal work, public domain (courtesy citation: National "
                "Hydrography Dataset, U.S. Geological Survey). OSM is ODbL - attribution and "
                "share-alike, the terms the basemap and fetch_osm_water.py already comply with. "
                "Every published description names whichever of the two it came from, and a "
                "merged record names both."
            ),
            "gates": {
                "match_radius_ft": MATCH_RADIUS_FT,
                "max_grade": MAX_GRADE,
                "report_radius_ft": REPORT_RADIUS_FT,
                "waterways": list(STREAM_WATERWAYS),
            },
        },
        "counts": counts,
        "crossings": crossings,
        "sites": sites,
    }


def render(document: dict) -> str:
    """The document as text, ONE RECORD PER LINE inside the two big arrays.

    Rendered rather than `json.dumps(indent=2)`d because the point of
    checking this file in is that a change to it is reviewable, and at this
    volume indentation defeats that: 1,125 crossings and 512 sites spread
    over nine lines apiece is 20,000 lines, three times the largest reference
    file this pipeline has, and nobody reads it. One line per record is the
    same data in about a tenth of the space, and a moved crossing or a lost
    match is exactly one changed line in the diff - which is more reviewable
    than the pretty-printed form, not less.

    The header keeps its indentation: `_README`, `source` and `counts` are
    the parts a human actually reads.
    """
    header = {key: document[key] for key in ("_README", "source", "counts")}
    lines = [json.dumps(header, indent=2)[:-2] + ","]  # drop the closing brace, keep the comma
    for name in ("crossings", "sites"):
        lines.append(f'  "{name}": [')
        records = [f"    {json.dumps(record, separators=(', ', ': '))}" for record in document[name]]
        lines.append(",\n".join(records))
        lines.append("  ]," if name == "crossings" else "  ]")
    lines.append("}")
    return "\n".join(line for line in lines if line) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)

    features_by_layer = {}
    for layer in ("shelters", "campsites"):
        print(f"Fetching the ATC {layer} layer ...")
        features_by_layer[layer] = fetch_atc_features(layer)
    sites = [feature for features in features_by_layer.values() for feature in features]
    print(f"  {len(sites)} shelters and campsites.")

    print(f"Reading streams: {len(AT_STATES)} OSM state extracts, then {len(NHD_HU4S)} USGS subregions ...")
    crossings, candidates = collect_streams(sites)
    crossings = dedupe_crossings(crossings)
    print(f"  {len(crossings)} distinct trail crossings.")

    print(f"Matching water to sites (<= {MATCH_RADIUS_FT:.0f} ft, <= {MAX_GRADE:.0%} grade) ...")
    document = build(features_by_layer, candidates, crossings)
    counts = document["counts"]
    print(f"  {counts['sites_with_water']}/{counts['sites']} sites have water they can walk to.")

    if len(crossings) < MIN_CROSSINGS:
        print(f"Refusing to write: {len(crossings)} crossings is below the floor of {MIN_CROSSINGS} - see MIN_CROSSINGS.")
        return 1
    previous = existing_crossing_count(OUT_PATH)
    if previous and len(crossings) < previous * MAX_CROSSING_DROP_RATIO:
        print(
            f"Refusing to overwrite {OUT_PATH.name}: {len(crossings)} crossings against {previous} "
            f"on disk is past the {MAX_CROSSING_DROP_RATIO:.0%} drop guard."
        )
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".tmp")
    tmp.write_text(render(document), encoding="utf-8")
    tmp.replace(OUT_PATH)
    print(f"Wrote {OUT_PATH}")

    fetch_receipts.record("fetch_trail_water", [OUT_PATH])
    return 0


def existing_crossing_count(path: Path) -> int | None:
    if not path.exists():
        return None
    return len(json.loads(path.read_text(encoding="utf-8")).get("crossings", []))


if __name__ == "__main__":
    sys.exit(main())
