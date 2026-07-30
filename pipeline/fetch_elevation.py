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
a tile can sit in a cell's corner the corridor itself never reaches.

Incremental: compares each tile's real S3 Last-Modified (one HEAD request
per tile, same as fetch_topo_quads.py) against
data/raw/elevation/manifest.json from the previous run, and only
re-downloads tiles that are new or changed. Every downloaded tile is
validated for actual readability via rasterio before being recorded in the
manifest - not just trusted because the HTTP layer reported 200 - matching
fetch_topo_quads.py's discipline there (3 of its 1,654 quads downloaded
successfully by every HTTP measure yet were genuinely corrupted on USGS's
own bucket).
"""

import json
import re
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).parent
CORRIDOR_PATH = ROOT / "data" / "spike" / "corridor.geojson"
OUT_DIR = ROOT / "data" / "raw" / "elevation"
# A small JSON list of {url, bounds} - NOT downloaded rasters. See
# build_tile_index for why nothing is downloaded.
INDEX_PATH = OUT_DIR / "tile_index.json"

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

CELL_DEGREES = 1.0


def compute_grid_cells() -> list[tuple[float, float, float, float]]:
    """Return the CELL_DEGREES x CELL_DEGREES cells (west, south, east,
    north) that intersect the corridor - the same grid-chunking pattern
    spike_raster_mosaic.py uses, needed here so each TNM Access API query
    stays small (see module docstring)."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE TABLE corridor AS SELECT * FROM ST_Read('{CORRIDOR_PATH.as_posix()}')")
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
        resp = requests.get(
            TNM_API_URL,
            params={
                "bbox": f"{xmin},{ymin},{xmax},{ymax}",
                "datasets": DATASET,
                "outputFormat": "JSON",
                "max": PAGE_SIZE,
                "offset": offset,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("items", [])
        items.extend(batch)
        offset += len(batch)
        if not batch or offset >= data.get("total", 0):
            break
    return items


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


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE TABLE corridor AS SELECT * FROM ST_Read('{CORRIDOR_PATH.as_posix()}')")

    cells = compute_grid_cells()
    print(f"{len(cells)} cell(s) intersect the 30-mile AT corridor.")

    seen_urls = set()
    candidates = []
    for i, cell in enumerate(cells, 1):
        items = list_products_for_cell(cell)
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
        print(f"  cell {i}/{len(cells)}: {len(items)} candidate(s) from TNM, {new_here} new corridor-intersecting tile(s)")

    index = build_tile_index(candidates, corridor_hit=lambda _bbox: True)
    print(f"{len(index)} DEM tile(s) intersect the corridor.")

    INDEX_PATH.write_text(json.dumps(index, indent=2))
    print(f"Tile index -> {INDEX_PATH}")
    print(
        "No rasters downloaded: these are Cloud-Optimized GeoTIFFs, and "
        "export_elevation.py reads only the blocks the trail crosses."
    )

    return index


if __name__ == "__main__":
    main()
