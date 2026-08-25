"""Index the USGS 3DEP 1/3 arc-second DEM tiles covering the ground this app
publishes trails for - the A.T. corridor, and since #1011 the other
organizations' lines the junction graph routes over too (see network_extent()).

Nothing is downloaded and nothing is discovered. The tile list is COMPUTED
from the corridor's own geometry, because 3DEP's 1/3 arc-second product is a
uniform 1-degree grid with a deterministic URL per cell:

    https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/{cell}/USGS_13_{cell}.tif
    cell = f"n{ceil(lat):02d}w{ceil(-lon):03d}"     # the cell's north-west corner

Verified 2026-08-12 against the real ANST centerline buffered 30 miles:
**56/56 corridor cells resolve, zero discovery requests.** That measurement is
of the corridor alone and predates the network extent below.

WHAT THE NETWORK ADDS IS NO LONGER BOUNDED BY NINE CELLS. This docstring used
to say it was - the network was clipped to a bounding box around New York City
that spans nine cells, most of which the corridor already crosses in NY and NJ.
#1019 removed that clip and registered NYS DEC, so the network is now every
line NYS Parks, DEC, NYNJTC and Mohonk Preserve publish: measured 2026-08-25
against the exported artifact either side of that change, **the lines touch 31
cells where they used to touch 7** - from n41w073 in the Hudson Highlands to
n46w074 on the Canadian border and n43w080 at Lake Erie. How many of those 31 the corridor already crosses is still unmeasured
here, because this sandbox has no centerline fetch to compare against - and
main() prints the before/after counts, so the real figure lands in the log
rather than in this docstring.

WHY THIS FILE USED TO ASK TNM ACCESS, AND WHY IT NO LONGER DOES

It used to query the TNM Access API (tnmaccess.nationalmap.gov) once per
corridor cell to find out which tiles existed. Its docstring argued at length
that 3DEP had no grid-and-listing scheme to lean on - irregular
per-acquisition project folders, inconsistent tile filenames, a nationwide
spatial index that could not build a download URL on its own.

Every word of that was true **of the 1-metre product**, which is what those
sentences described. `DATASET` was `NED 1/3 arc-second`, and the 1/3
arc-second product is laid out completely differently. The reasoning that
justified reaching for a discovery API was written about a dataset this
script does not use. pipeline/ELEVATION_SOURCES.md section 3 is the survey
that established that, with the probe behind it (#548, #549).

What it cost meanwhile: that API is what failed. Both publish runs on
2026-08-12 died there before anything was exported, with every cell 504-ing
at least twice - after fetching sources and exporting trails, POIs and spurs,
all of which was thrown away.

THE EDITIONS HAZARD WAS REAL AND IS NOW UPSTREAM'S PROBLEM

This file used to carry a correction about multiple catalogued editions per
footprint - n35w084 alone had four, separated only by a date in the filename -
and a build_tile_index that kept the newest per footprint. That hazard was
genuine: ElevationSampler takes the first tile covering a point, so mixing
survey vintages along the trail was a live risk.

It is gone rather than solved here, because USGS already split the bucket:
`current/` holds exactly one tif per cell and `historical/` holds the dated
ones. The TNM catalogue returned both mixed together, which is *why* the
dedup existed. Asking `current/` asks a question that cannot have a wrong
answer, so the edition parsing and the footprint dedup are not ported.

WHAT IS STILL DONE HERE

The coverage filter, which is not the same question as the cell grid:
a 1-degree cell is large, and one can clip the corridor's bounding rectangle
in a corner the trail itself never reaches. The corridor is built fresh on
every run from data/raw/centerline.geojson via lib/corridor.py's
build_corridor() - the same 30-mile buffer export_poi.py and export_trails.py
use - and never read from data/spike/corridor.geojson, which is stale
proof-of-concept output (see lib/corridor.py's docstring for why that file
specifically must not be read).

And the write gate, which now guards a different failure than the one it was
built for - see write_gate_problems().

Still no manifest, no per-tile validation and no download. 3DEP tiles are
Cloud-Optimized GeoTIFFs, so export_elevation.py streams only the blocks the
trail crosses straight from each tile's URL at read time. There is no local
file for a checksum or a readability check to apply to, and there never was.
"""

import argparse
import json
import math
import os
from pathlib import Path

import duckdb
import requests

from lib import fetch_receipts
from lib.completeness import fail_if_incomplete
from lib.corridor import build_corridor

# One cheap metadata request per corridor cell, and the only requests this
# script makes. See stamp_last_modified().
HEAD_TIMEOUT = 30

ROOT = Path(__file__).parent
# The source line build_corridor() buffers into the 'corridor' table fresh
# on every run (see module docstring) - deliberately never
# data/spike/corridor.geojson, which is stale proof-of-concept output.
CENTERLINE_PATH = ROOT / "data" / "raw" / "centerline.geojson"
# The published network lines (export_nearby_trails.py), which this script
# runs AFTER in publish-vector-data.yml. Optional: a run without it indexes
# exactly the corridor cells it always did. See network_extent().
NEARBY_TRAILS_PATH = ROOT / "data" / "processed" / "nearby_trails.geojson"
OUT_DIR = ROOT / "data" / "raw" / "elevation"
# A small JSON list of {url, bounds} - NOT downloaded rasters.
INDEX_PATH = OUT_DIR / "tile_index.json"

# Write-gate tolerances for the final tile_index.json write (see
# write_gate_problems). Expressed as a fraction of the PREVIOUS run's count,
# not a fixed tile count, so the check keeps working unmodified as the
# corridor's real tile count changes over time (corridor scope changes,
# relocations) rather than needing retuning.
SHRINK_TOLERANCE = 0.15

# First-run-only backstop, used only when there is no previous index to
# scale against. Deliberately NOT derived from today's real corridor count
# (56 cells) - tying it to that would turn a safety net into a maintenance
# chore that needs bumping every time the corridor legitimately grows.
COLD_START_MIN_TILES = 10

# Explicit override for an intentional shrink (e.g. a real corridor change),
# settable via --allow-shrink or this env var - see main().
ALLOW_SHRINK_ENV_VAR = "FETCH_ELEVATION_ALLOW_SHRINK"

# 1/3 arc-second (~10 m), NOT 1 metre - that is the `13` in the path. Measured
# before any download: 1 m comes to roughly 1 TB for this corridor, about
# three orders of magnitude more than an elevation profile rendered into a
# 100x40 SVG needs. 1 m DEM exists to measure boulders and building
# footprints.
#
# 10 m gives ~1-2 m vertical accuracy, which is what the "+640 ft ahead"
# callout needs to be trustworthy - it feeds the Naismith time estimate
# directly. A move back to 1 m is a ~40x change and should be deliberate.
#
# `current/` rather than `historical/` is the whole editions story - see the
# module docstring.
TILE_URL_TEMPLATE = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/{cell}/USGS_13_{cell}.tif"

CELL_DEGREES = 1.0


def cell_name(north: int, west: int) -> str:
    """USGS's name for the 1-degree cell with this north-west corner.

    `north` is degrees north and `west` is degrees WEST as a positive number,
    which is how USGS writes it: n35w084 is the cell whose north-west corner
    is 35 degrees north, 84 degrees west.

    Northern and western hemispheres only, which is not a shortcut worth
    generalising away: the Appalachian Trail is entirely inside both, and a
    hemisphere this code has never seen is better refused than guessed at.
    """
    if north <= 0 or west <= 0:
        raise ValueError(f"3DEP cells here are north/west only, got n={north} w={west}")
    return f"n{north:02d}w{west:03d}"


def cell_bounds(cell: str) -> tuple[float, float, float, float]:
    """(west, south, east, north) for a cell, from its name alone.

    This is what replaced TNM's `boundingBox` field. A 1-degree cell named
    from its north-west corner extends one degree south and one degree east
    of it, so the arithmetic is total - there is no lookup that could be
    missing and no field that could be absent from a row.
    """
    north = int(cell[1:3])
    west = int(cell[4:7])
    return (
        -float(west),
        float(north) - CELL_DEGREES,
        -float(west) + CELL_DEGREES,
        float(north),
    )


def cell_url(cell: str) -> str:
    """The deterministic download URL for a cell's current edition."""
    return TILE_URL_TEMPLATE.format(cell=cell)


def candidate_cells(bbox: tuple[float, float, float, float]) -> list[str]:
    """Every 1-degree cell whose square overlaps this (west, south, east,
    north) rectangle.

    A SUPERSET on purpose. This is rectangle-against-rectangle, and the
    corridor is not a rectangle - Georgia to Maine as a box is mostly empty
    space. The real filter is the corridor polygon in build_tile_index();
    this only has to be cheap and to miss nothing.

    Pure arithmetic, so it is testable without DuckDB, a network or a
    centerline file - which is most of the point of the change it is part of.
    The function this replaced opened a spatial database to answer the same
    question.
    """
    west, south, east, north = bbox

    # A cell named nA covers latitudes [A-1, A], so it overlaps [south, north]
    # when A-1 <= north and A >= south. Inclusive at the edges: a cell that
    # merely touches costs one polygon test and no requests at all.
    lat_names = range(math.ceil(south), math.floor(north) + 2)
    # A cell named wB covers longitudes [-B, -B+1], so it overlaps
    # [west, east] when -B <= east and -B+1 >= west.
    lon_names = range(math.ceil(-east), math.floor(1 - west) + 1)

    return [cell_name(lat, lon) for lat in lat_names for lon in lon_names if lat > 0 and lon > 0]


def build_tile_index(bbox: tuple[float, float, float, float], corridor_hit) -> list[dict]:
    """The {url, bounds} list for every 3DEP cell the corridor actually
    crosses, computed from the corridor's bounding box.

    Nothing is downloaded, and that is the point. 3DEP tiles are
    Cloud-Optimized GeoTIFFs - tiled 512x512, with overviews, served with
    `Accept-Ranges: bytes` - so rasterio reads them in place over HTTP and
    pulls only the blocks the trail crosses. Measured on real centerline
    points: 400 samples in 4.0 s (10 ms/point), which extrapolates to about
    12 minutes for the whole corridor with no bulk transfer and no local DEM
    storage. The corridor's tiles come to ~25.5 GB and none of it moves.

    `corridor_hit(bounds)` is injected rather than called directly so this
    stays testable without a DuckDB spatial connection - the real caller
    passes the ST_Intersects check against the true corridor polygon.
    Filtering on the polygon rather than on the bounding box matters: a
    1-degree cell is large, and one can clip the corridor's rectangle in a
    corner the trail never reaches.

    Sorted by cell name, which is not cosmetic: it makes tile_index.json a
    file whose diff between two runs shows what actually changed, rather than
    whatever order a catalogue happened to answer in.
    """
    index = []
    for cell in sorted(set(candidate_cells(bbox))):
        bounds = cell_bounds(cell)
        if not corridor_hit(bounds):
            continue
        index.append({"url": cell_url(cell), "bounds": list(bounds)})
    return index


def stamp_last_modified(index: list[dict], *, head=None) -> list[dict]:
    """Add each tile's S3 `Last-Modified` to the index, in place.

    WHY THIS IS NOT A CONTRADICTION OF "ZERO DISCOVERY REQUESTS". Discovery -
    asking which tiles exist - is gone, and that is the failure this change
    was about. This asks a different question of a different service: **when
    was this one cell last revised**, of the same S3 bucket export_elevation.py
    already streams from. One HEAD per cell, no pagination, no gateway that
    gives up at 30 seconds.

    It is here rather than in check_freshness.py because capture is offline by
    design: `capture_state()` reads data/raw/ and makes no requests, so a
    freshness marker it can build has to already be on disk.

    WHAT IT REPLACES, AND WHY SOMETHING HAD TO. lib/freshness_state.py's
    `edition_key` read the 8-digit date out of a filename, because a
    republished cell arrived as a NEW dated filename and there was "no
    per-file timestamp to HEAD". Under `current/` there is: the name never
    changes, and `Last-Modified` is what moves - the survey checked it against
    `historical/` on three cells and it matched the newest dated edition every
    time (n35w084 -> 2023-02-15, n46w069 -> 2026-05-21, n41w074 -> 2024-09-26).

    Left alone, the marker would have gone constant, every comparison would
    have read FRESH, and 3DEP could re-fly the whole corridor without the
    monitor saying a word. An alarm that is always off is worse than one that
    is always on, because nobody notices it stopped.

    Non-fatal on purpose. A tile whose HEAD fails records `None`, which
    freshness_state already keeps rather than filters - "we did not find out"
    is a state it models. The index itself is unaffected, so a network
    problem costs freshness detail and never the elevation profile.
    """
    send = head if head is not None else _head
    for tile in index:
        tile["last_modified"] = send(tile["url"])
    return index


def _head(url: str) -> str | None:
    try:
        response = requests.head(url, timeout=HEAD_TIMEOUT)
        if response.status_code >= 400:
            return None
        return response.headers.get("Last-Modified")
    except requests.RequestException:
        return None


def _env_flag_set(name: str) -> bool:
    """True when env var `name` holds a truthy value ("1", "true", "yes",
    case-insensitive) - unset, empty, "0", and "false" all count as not set,
    same forgiving parsing most boolean env-var flags use."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def write_gate_problems(
    old_count: int | None,
    new_count: int,
    *,
    tolerance: float = SHRINK_TOLERANCE,
    cold_start_min: int = COLD_START_MIN_TILES,
) -> list[str]:
    """Problem strings for an index write that should be refused (suitable
    for lib.completeness.fail_if_incomplete), or [] when it's safe to
    proceed. Pure count comparison - no filesystem/network/DuckDB - so
    main() can gate its tile_index.json write with it and tests can exercise
    it directly.

    WHAT THIS NOW GUARDS, WHICH IS NOT WHAT IT WAS BUILT FOR. It used to
    catch a catalogue query that came back thin because a server was slow.
    Computed URLs cannot fail that way - the cell list is arithmetic over the
    corridor's bounding box and makes no requests at all - so that failure
    mode left with the API.

    It is kept because the OTHER input did not go anywhere. The corridor is
    rebuilt from centerline.geojson on every run, so a centerline that
    fetched short, a buffer that changed, or a geometry regression in
    lib/corridor.py still shrinks this count, and this is the only thing
    watching for it. A check costing one integer comparison is not worth
    trading away for a class of silent failure that survived the change.

    Two independent checks:
    (a) Relative shrink: once a previous index exists (`old_count` is not
        None), `new_count` must not fall more than `tolerance` below it -
        self-scaling against whatever the corridor legitimately produced
        last run, rather than a fixed count that would need retuning as
        corridor scope grows.
    (b) Cold-start floor: when there is no previous index at all (first run
        ever, `old_count` is None), there is nothing to scale against, so
        `new_count` is checked against a small absolute floor instead.
    """
    if old_count is None:
        if new_count < cold_start_min:
            return [f"cold-start floor: {new_count} tile(s) with no previous index to compare against (minimum {cold_start_min})"]
        return []

    floor = old_count * (1 - tolerance)
    if new_count < floor:
        return [
            f"relative shrink check: {new_count} tile(s) vs {old_count} previously - "
            f"more than {tolerance:.0%} smaller (floor {floor:.1f})"
        ]
    return []


def network_extent(con, path: Path) -> bool:
    """Load the published network trail lines into a `network` table, so the
    tile index covers the ground a day hike can be built on and not only the
    A.T. corridor.

    WHY THE INDEX WAS SHORT, AND WHY IT IS NOT A BUG SOMEBODY INTRODUCED. This
    script has always computed its cells from `build_corridor()` - the A.T.
    centerline buffered 30 miles - because until #950 the A.T. was the only
    trail this app drew. The junction graph now holds NYS OPRHP's, NYNJTC's and
    Mohonk Preserve's lines too, and build_trail_graph.py does NOT clip them to
    the A.T. corridor. So there was ground a hiker can route over that no DEM
    tile covered, and #1011 needs it covered.

    NO BUFFER, DELIBERATELY, unlike the corridor. A 3DEP cell is a whole degree
    square; a line anywhere inside one pulls the entire cell, so buffering
    before the intersection test would only add cells the trails never enter.
    The corridor's 30 miles exist because POIs and the basemap need context
    AROUND the trail - elevation needs the trail itself.

    NOT A CODE CHANGE PER SOURCE, which is the recurring half of #1011. This
    reads the published artifact, and `export_nearby_trails.network_line_sources`
    puts every registry entry carrying `blaze_field` or `blaze_default` into it.
    So registering a Catskills or NJ layer in sources.json pulls the DEM cells
    it needs on the next run, with nobody editing a list of cells or of trails.

    False when the artifact is absent - a publish that skipped the network
    export, or one whose licence gate held those lines back. main() says so out
    loud rather than silently indexing a smaller world.
    """
    if not path.exists():
        return False
    con.execute(f"CREATE OR REPLACE TABLE network AS SELECT * FROM ST_Read('{path.as_posix()}')")
    return bool(con.execute("SELECT COUNT(*) FROM network").fetchone()[0])


def _union_bbox(*boxes: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """The smallest (west, south, east, north) containing all of them."""
    wests, souths, easts, norths = zip(*boxes)
    return (min(wests), min(souths), max(easts), max(norths))


def network_bbox(con) -> tuple[float, float, float, float]:
    """(west, south, east, north) of the `network` table already on `con`."""
    xmin, ymin, xmax, ymax = con.execute(
        "SELECT MIN(ST_XMin(geom)), MIN(ST_YMin(geom)), MAX(ST_XMax(geom)), MAX(ST_YMax(geom)) FROM network"
    ).fetchone()
    return (xmin, ymin, xmax, ymax)


def corridor_bbox(con) -> tuple[float, float, float, float]:
    """(west, south, east, north) of the corridor already built on `con`."""
    xmin, ymin, xmax, ymax = con.execute(
        "SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom) FROM corridor"
    ).fetchone()
    return (xmin, ymin, xmax, ymax)


def main(allow_shrink: bool = False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    build_corridor(con, CENTERLINE_PATH)

    bbox = corridor_bbox(con)
    has_network = network_extent(con, NEARBY_TRAILS_PATH)
    if has_network:
        bbox = _union_bbox(bbox, network_bbox(con))
    else:
        # Visible rather than inferred. An index built without the network is
        # correct for the A.T. and short for everything else, and
        # export_network_elevation.py would report those edges as unmeasured
        # without anybody knowing why.
        print(f"No network lines at {NEARBY_TRAILS_PATH} - indexing the A.T. corridor only.")

    candidates = candidate_cells(bbox)
    print(f"Corridor{' + network' if has_network else ''} bbox {bbox} -> {len(candidates)} candidate 1-degree cell(s).")

    def covered_hit(bounds: tuple[float, float, float, float]) -> bool:
        """A cell is indexed if the A.T. corridor OR any network trail line
        touches it. Two tables rather than one union: the corridor is a single
        buffered polygon and the network is thousands of lines, so the cheap
        test is asked first and the expensive one only when it misses."""
        west, south, east, north = bounds
        envelope = f"ST_MakeEnvelope({west}, {south}, {east}, {north})"
        hit = con.execute(f"SELECT EXISTS (SELECT 1 FROM corridor WHERE ST_Intersects(geom, {envelope}))").fetchone()[0]
        if hit or not has_network:
            return bool(hit)
        return bool(con.execute(f"SELECT EXISTS (SELECT 1 FROM network WHERE ST_Intersects(geom, {envelope}))").fetchone()[0])

    index = build_tile_index(bbox, corridor_hit=covered_hit)
    new_count = len(index)
    print(
        f"{new_count} DEM tile(s) intersect the corridor{' or the network' if has_network else ''}, with zero discovery requests."
    )

    stamp_last_modified(index)
    stamped = sum(1 for tile in index if tile.get("last_modified"))
    print(f"{stamped}/{new_count} cell(s) answered a HEAD with a Last-Modified.")
    if stamped == 0 and new_count > 0:
        # Not fatal - the index is still correct and the profile still builds.
        # Said out loud because a silent zero here is the freshness monitor
        # going dark, which is the failure stamp_last_modified() exists to
        # prevent.
        print("  WARNING: no cell answered. Freshness detection will report nothing for elevation.")

    old_count = len(json.loads(INDEX_PATH.read_text())) if INDEX_PATH.exists() else None
    print(f"Previous index: {old_count if old_count is not None else 'none (first run)'} tile(s) -> new: {new_count} tile(s).")

    problems = write_gate_problems(old_count, new_count)
    if problems:
        if allow_shrink:
            print(f"--allow-shrink ({ALLOW_SHRINK_ENV_VAR}) set: overriding the write gate:")
            for problem in problems:
                print(f"  {problem}")
        else:
            # Exits non-zero without writing INDEX_PATH - the last-good
            # index stays in place. See write_gate_problems for why this
            # triggers.
            fail_if_incomplete(problems, label="Refusing to overwrite tile index")

    INDEX_PATH.write_text(json.dumps(index, indent=2))
    print(f"Tile index -> {INDEX_PATH}")
    # After the write gate above, so an index this run refused to overwrite
    # never gets a receipt saying it did.
    fetch_receipts.record("fetch_elevation", [INDEX_PATH])
    print(
        "No rasters downloaded: these are Cloud-Optimized GeoTIFFs, and "
        "export_elevation.py reads only the blocks the trail crosses."
    )

    return index


if __name__ == "__main__":
    # argparse kept outside main() deliberately - main() is called directly
    # (with allow_shrink passed as a plain kwarg) by the test suite, and
    # argparse.parse_args() with no explicit argv reads sys.argv, which would
    # try to parse pytest's own command-line arguments if this lived inside
    # main() instead (see export_basemap.py for the same pattern).
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--allow-shrink",
        action="store_true",
        default=_env_flag_set(ALLOW_SHRINK_ENV_VAR),
        help=(
            "Accept a tile_index.json write that shrank beyond the normal tolerance "
            f"instead of refusing it (also settable via {ALLOW_SHRINK_ENV_VAR}=1)."
        ),
    )
    args = parser.parse_args()
    main(allow_shrink=args.allow_shrink)
