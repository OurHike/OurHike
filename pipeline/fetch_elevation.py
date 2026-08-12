"""Fetch USGS 3DEP 1-meter DEM tiles (GeoTIFF) that intersect the AT corridor.

Confirmed to live on the same S3 bucket the topo quads use
(prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/), but unlike the topo
quads it is NOT one uniform nationwide grid with a lightweight per-tile bbox
CSV (fetch_topo_quads.py's ustopo_current.csv). Real-service research before
writing this:

- 1m DEM tiles are grouped into irregular per-LiDAR-acquisition "project"
  folders (.../Elevation/1m/Projects/<project>/TIFF/<tile>.tif) - project
  footprints vary in size and shape (a few counties, a whole state, etc.),
  not a fixed grid cell, so there's no simple state-prefix listing scheme
  like fetch_topo_quads.py's list_state_geotiffs() to lean on.
- Tile filenames aren't consistent either: some embed a UTM-zone digit
  before the grid-cell ID (USGS_1M_17_x54y410_VA_..._D17.tif), others don't
  (USGS_1m_x51y383_AL_25Co_B1_2017.tif) - a real echo of the dated/undated
  product_filename inconsistency fetch_topo_quads.py's bare_key() exists to
  handle, so this script never tries to derive a tile's geographic footprint
  from its filename.
- USGS does publish a nationwide spatial index
  (.../FullExtentSpatialMetadata/10_km_cell_grid.gpkg, ~51MB, 184,152 cells)
  - but it's the grid definition only (cell polygon + UTM zone), not tied to
    which project/tile actually covers a given cell, so it can't build a
    real download URL on its own.

What DOES map every real tile to both a bbox and a working download URL in
one place is the TNM Access API (tnmaccess.nationalmap.gov) - a purpose-
built discovery layer over the same S3 bucket, not a separate hosting
scheme. (fetch_topo_quads.py's docstring explains why that API was a poor
fit there - multiple cataloged "editions" per quad, flaky pagination; that's
specific to the maps catalog. This elevation dataset is one edition per
tile with a real boundingBox on every row, and its own offset/total
pagination is handled explicitly here - see list_products_for_cell().)

CORRECTION (2026-07-29, confirmed against the live catalog): the claim above
that this dataset is "one edition per tile" is WRONG. The real corridor query
returns 244 tiles covering only 110 distinct footprints - n35w084 alone has
four editions (20220504, 20220512, 20220725, 20230215), separated only by a
date in the filename. It is the same multiple-editions problem
fetch_topo_quads.py documents for the maps catalog, and it matters here
because ElevationSampler takes the first tile covering a point: without
deduplication the profile would silently mix survey vintages along the trail.
build_tile_index keeps the newest edition per footprint.

Queried per corridor grid cell (the same 1-degree cell approach
spike_raster_mosaic.py already uses) rather than one query for the
corridor's whole bounding rectangle - GA to Maine as a rectangle is mostly
empty space, so one giant query would pull in tiles nowhere near the actual
trail. Candidate tiles are deduplicated by download URL across cells, then
filtered against the real corridor polygon (not just cell membership) since
a tile can sit in a cell's corner the corridor itself never reaches. The
corridor itself is built fresh on every run, from data/raw/centerline.geojson
via lib/corridor.py's build_corridor() (the same 30-mile buffer
export_poi.py/export_trails.py use) - never read from
data/spike/corridor.geojson, which is stale proof-of-concept output (see
lib/corridor.py's docstring for why that file specifically must not be read).

No incremental fetch, no manifest, no per-tile validation - because nothing
is downloaded. Unlike fetch_topo_quads.py, this script never HEADs a tile to
compare its S3 Last-Modified against a manifest.json, and never opens a
downloaded file with rasterio to check it reads cleanly: there is no local
file for either check to apply to. 3DEP tiles are Cloud-Optimized GeoTIFFs,
so export_elevation.py streams only the blocks it needs straight from each
tile's URL at read time (see build_tile_index below) - there was never a
download step here for a manifest or a readability check to guard. The real
design is narrower: query the TNM catalog per grid cell, dedupe to the
newest edition per footprint, filter to what actually intersects the
corridor polygon, and write the resulting {url, bounds} list to
tile_index.json for export_elevation.py to read later.

The safety net this file does have is on the write itself, not on
individual tiles: main() refuses to overwrite a known-good tile_index.json
with one that shrank more than expected (see write_gate_problems), rather
than silently clobbering a good index with a bad run's output.
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

import duckdb

from lib.completeness import fail_if_incomplete
from lib.corridor import build_corridor
from lib.http_retry import request_with_retry

ROOT = Path(__file__).parent
# The source line build_corridor() buffers into the 'corridor' table fresh
# on every run (see module docstring) - deliberately never
# data/spike/corridor.geojson, which is stale proof-of-concept output.
CENTERLINE_PATH = ROOT / "data" / "raw" / "centerline.geojson"
OUT_DIR = ROOT / "data" / "raw" / "elevation"
# A small JSON list of {url, bounds} - NOT downloaded rasters. See
# build_tile_index for why nothing is downloaded.
INDEX_PATH = OUT_DIR / "tile_index.json"

# One file per corridor cell holding that cell's TNM answer, so a run that
# dies on cell 37 keeps cells 1-36 (#536).
#
# WHY CACHING THIS IS SAFE, WHICH IS THE ONLY REASON TO DO IT. What is cached
# is USGS's CATALOGUE of which 1/3 arc-second tiles cover a cell - not the
# elevation data itself, and not anything a hiker sees. 3DEP re-flies a region
# on a cycle measured in years, so a run that rediscovers all 51 cells every
# time is making 51 requests to learn what it already knew. The publish that
# prompted this died on the FIRST of those 51, having already fetched sources
# and exported trails, POIs and spurs.
#
# Freshness is bounded rather than trusted forever: past CELL_CACHE_MAX_AGE_DAYS
# a cell is asked again, and `--refresh` ignores the cache entirely. The
# existing shrink gate still runs over the assembled index either way, so a
# cache that somehow went wrong cannot quietly publish a smaller corridor.
CELL_CACHE_DIR = OUT_DIR / "tnm_cells"

# A month. Far shorter than 3DEP's actual revision cycle, so the cache cannot
# hide a real change for long, and far longer than the gap between publishes,
# so a normal run makes no catalogue requests at all.
CELL_CACHE_MAX_AGE_DAYS = 30

# Write-gate tolerances for the final tile_index.json write (see
# write_gate_problems). Expressed as a fraction of the PREVIOUS run's count,
# not a fixed tile count, so the check keeps working unmodified as the
# corridor's real tile count changes over time (new surveys, corridor scope
# changes, etc.) rather than needing retuning.
SHRINK_TOLERANCE = 0.15

# First-run-only backstop, used only when there is no previous index to
# scale against. Deliberately NOT derived from today's real corridor count
# (110 tiles) - tying it to that would turn a safety net into a maintenance
# chore that needs bumping every time the corridor legitimately grows. It
# exists only to catch a first run that comes back with next to nothing
# (e.g. a malformed query silently matching almost no tiles).
COLD_START_MIN_TILES = 10

# Explicit override for an intentional shrink (e.g. a real corridor/dataset
# change), settable via --allow-shrink or this env var - see main().
ALLOW_SHRINK_ENV_VAR = "FETCH_ELEVATION_ALLOW_SHRINK"

TNM_API_URL = "https://tnmaccess.nationalmap.gov/api/v1/products"
# 1/3 arc-second (~10 m), NOT 1 metre. Measured against the real TNM catalog
# before any download: 1 m comes to roughly 1 TB for this corridor (~190
# tiles per 1-degree cell at a median 324 MB, across 51 cells) - about three
# orders of magnitude more than an elevation profile rendered into a 100x40
# SVG needs. 1 m DEM exists to measure boulders and building footprints.
#
# 10 m gives ~1-2 m vertical accuracy, which is what the "+640 ft ahead"
# callout needs to be trustworthy - it feeds the Naismith time estimate
# directly. A move back to 1 m is a ~40x change and should be deliberate.
DATASET = "National Elevation Dataset (NED) 1/3 arc-second"
PAGE_SIZE = 1000

# How patient to be with USGS's catalogue. Longer than lib/http_retry.py's
# default ladder on purpose (#536): this call is made once per corridor cell,
# 51 times, and it runs after fetching sources, exporting trail lines, POIs
# and spurs - so the cost of giving up is the whole publish, not one request.
# A 504 from tnmaccess.nationalmap.gov threw away exactly that, on the FIRST
# cell, 35 seconds in. Roughly two minutes of waiting spread over four
# attempts is cheap against an hour of build.
TNM_BACKOFF_SECONDS = (5, 15, 45, 60)

CELL_DEGREES = 1.0


def compute_grid_cells() -> list[tuple[float, float, float, float]]:
    """Return the CELL_DEGREES x CELL_DEGREES cells (west, south, east,
    north) that intersect the corridor - the same grid-chunking pattern
    spike_raster_mosaic.py uses, needed here so each TNM Access API query
    stays small (see module docstring)."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    build_corridor(con, CENTERLINE_PATH)
    xmin, ymin, xmax, ymax = con.execute(
        "SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom) FROM corridor"
    ).fetchone()

    cells = []
    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            cx0, cy0 = x, y
            cx1, cy1 = min(x + CELL_DEGREES, xmax), min(y + CELL_DEGREES, ymax)
            hit = con.execute(f"""
                SELECT EXISTS (
                    SELECT 1 FROM corridor
                    WHERE ST_Intersects(geom, ST_MakeEnvelope({cx0}, {cy0}, {cx1}, {cy1}))
                )
            """).fetchone()[0]
            if hit:
                cells.append((cx0, cy0, cx1, cy1))
            y += CELL_DEGREES
        x += CELL_DEGREES
    return cells


def list_products_for_cell(cell: tuple[float, float, float, float]) -> list[dict]:
    """Query the TNM Access API for every real 1m DEM tile whose bbox
    intersects this cell. Pages via offset/total explicitly rather than
    trusting a single response - a cell dense enough to exceed PAGE_SIZE
    would otherwise silently return a truncated result."""
    xmin, ymin, xmax, ymax = cell
    items = []
    offset = 0
    while True:
        resp = request_with_retry(
            TNM_API_URL,
            params={
                "bbox": f"{xmin},{ymin},{xmax},{ymax}",
                "datasets": DATASET,
                "outputFormat": "JSON",
                "max": PAGE_SIZE,
                "offset": offset,
            },
            timeout=60,
            backoff=TNM_BACKOFF_SECONDS,
            label=f"TNM cell {xmin:.2f},{ymin:.2f}",
        )
        data = resp.json()
        batch = data.get("items", [])
        items.extend(batch)
        offset += len(batch)
        if not batch or offset >= data.get("total", 0):
            break
    return items


def cell_cache_path(cell: tuple[float, float, float, float]) -> Path:
    """Where this cell's TNM answer is kept.

    Named from the bbox to three decimals, which is finer than CELL_DEGREES
    ever moves and so cannot collide, and stable across runs so a cache
    written by one run is found by the next.
    """
    xmin, ymin, xmax, ymax = cell
    return CELL_CACHE_DIR / f"{xmin:.3f}_{ymin:.3f}_{xmax:.3f}_{ymax:.3f}.json"


def cached_cell_items(path: Path, max_age_days: int, now: float) -> list[dict] | None:
    """This cell's remembered TNM items, or None if absent, stale or unreadable.

    Unreadable counts as absent rather than fatal: a truncated file from a run
    killed mid-write is a reason to ask TNM again, not a reason to stop. The
    cost of being wrong here is one request.
    """
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
        queried_at = float(payload["queried_at"])
        items = payload["items"]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError):
        return None
    if now - queried_at > max_age_days * 86400:
        return None
    return items


def cell_products(
    cell: tuple[float, float, float, float],
    *,
    refresh: bool = False,
    max_age_days: int = CELL_CACHE_MAX_AGE_DAYS,
    now: float | None = None,
) -> tuple[list[dict], bool]:
    """(items, came_from_cache) for one cell.

    Writes the answer to disk IMMEDIATELY on a fetch, before the next cell is
    asked. That is what makes a run resumable: the failure this exists for hit
    cell 1 of 51, but had it hit cell 37, the previous 36 would have been
    thrown away too.
    """
    path = cell_cache_path(cell)
    stamp = time.time() if now is None else now

    if not refresh:
        cached = cached_cell_items(path, max_age_days, stamp)
        if cached is not None:
            return cached, True

    items = list_products_for_cell(cell)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"queried_at": stamp, "items": items}))
    return items, False


def build_tile_index(items: list[dict], corridor_hit) -> list[dict]:
    """Turn TNM catalog rows into a deduplicated list of {url, bounds} for
    every 10 m DEM tile the corridor actually crosses.

    Nothing is downloaded, and that is the point. 3DEP tiles are
    Cloud-Optimized GeoTIFFs - tiled 512x512, served with
    `Accept-Ranges: bytes` - so rasterio reads them in place over HTTP and
    pulls only the blocks the trail crosses. Measured on real centerline
    points: 400 samples in 4.0 s (10 ms/point), which extrapolates to about
    12 minutes for the whole corridor with no bulk transfer and no local DEM
    storage. Downloading whole 1-degree tiles to sample a line through them
    would move ~24 GB to read a small fraction of it.

    `corridor_hit(bbox)` is injected rather than called directly so this
    stays testable without a DuckDB spatial connection - the real caller
    passes the ST_Intersects check against the true corridor polygon.
    Filtering on the polygon rather than cell membership matters: a tile can
    sit in a cell's corner the actual corridor never reaches.
    """
    best: dict[tuple, dict] = {}
    seen: set[str] = set()

    for item in items:
        url = item.get("downloadURL")
        bbox = item.get("boundingBox")
        if not url or not bbox or url in seen:
            continue
        if not corridor_hit(bbox):
            continue

        seen.add(url)
        bounds = (bbox["minX"], bbox["minY"], bbox["maxX"], bbox["maxY"])
        candidate = {"url": url, "bounds": list(bounds), "edition": _edition_of(url)}

        # Keep the newest edition per footprint. An undated filename sorts
        # lowest, so it is used only when nothing dated covers that cell -
        # losing coverage would be worse than an unknown vintage.
        incumbent = best.get(bounds)
        if incumbent is None or candidate["edition"] > incumbent["edition"]:
            best[bounds] = candidate

    return [{"url": t["url"], "bounds": t["bounds"]} for t in best.values()]


def _edition_of(url: str) -> str:
    """The 8-digit date USGS embeds in a 3DEP filename
    (USGS_13_n35w084_20230215.tif), or "" when the name does not carry one."""
    match = re.search(r"_(\d{8})\.tif$", url)
    return match.group(1) if match else ""


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

    Two independent checks:
    (a) Relative shrink: once a previous index exists (`old_count` is not
        None), `new_count` must not fall more than `tolerance` below it -
        self-scaling against whatever the corridor legitimately produced
        last run, rather than a fixed tile count that would need retuning
        as corridor scope grows.
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


def main(allow_shrink: bool = False, refresh: bool = False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    build_corridor(con, CENTERLINE_PATH)

    cells = compute_grid_cells()
    print(f"{len(cells)} cell(s) intersect the 30-mile AT corridor.")

    seen_urls = set()
    candidates = []
    from_cache = 0
    for i, cell in enumerate(cells, 1):
        items, cached = cell_products(cell, refresh=refresh)
        from_cache += 1 if cached else 0
        new_here = 0
        for item in items:
            url = item.get("downloadURL")
            bbox = item.get("boundingBox")
            if not url or not bbox or url in seen_urls:
                continue
            # Precise filter, not just cell membership - a tile can sit in a
            # cell's corner the actual (non-rectangular) corridor polygon
            # never reaches.
            hit = con.execute(f"""
                SELECT EXISTS (
                    SELECT 1 FROM corridor
                    WHERE ST_Intersects(geom, ST_MakeEnvelope({bbox["minX"]}, {bbox["minY"]}, {bbox["maxX"]}, {bbox["maxY"]}))
                )
            """).fetchone()[0]
            if not hit:
                continue
            seen_urls.add(url)
            candidates.append(item)
            new_here += 1
        where = "cache" if cached else "TNM"
        print(f"  cell {i}/{len(cells)}: {len(items)} candidate(s) from {where}, {new_here} new corridor-intersecting tile(s)")

    print(f"{from_cache}/{len(cells)} cell(s) answered from cache; {len(cells) - from_cache} asked of TNM.")

    index = build_tile_index(candidates, corridor_hit=lambda _bbox: True)
    new_count = len(index)
    print(f"{new_count} DEM tile(s) intersect the corridor.")

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
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Ask TNM for every cell again, ignoring the per-cell cache. The cache exists because "
            f"3DEP revises on a multi-year cycle and a warm run needs no catalogue requests at all; "
            f"entries older than {CELL_CACHE_MAX_AGE_DAYS} days are refreshed anyway."
        ),
    )
    args = parser.parse_args()
    main(allow_shrink=args.allow_shrink, refresh=args.refresh)
