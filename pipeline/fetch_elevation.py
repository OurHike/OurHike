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
import rasterio
import requests

ROOT = Path(__file__).parent
CORRIDOR_PATH = ROOT / "data" / "spike" / "corridor.geojson"
OUT_DIR = ROOT / "data" / "raw" / "elevation"
MANIFEST_PATH = OUT_DIR / "manifest.json"

TNM_API_URL = "https://tnmaccess.nationalmap.gov/api/v1/products"
DATASET = "Digital Elevation Model (DEM) 1 meter"
PAGE_SIZE = 1000

CELL_DEGREES = 1.0

TILE_URL_RE = re.compile(r"/Projects/(?P<project>[^/]+)/TIFF/(?P<filename>[^/]+)$")


def parse_tile_url(url: str) -> tuple[str, str, str]:
    """Extract (state, project, filename) from a real elevation tile
    downloadURL, e.g.
    .../Projects/VA_FEMA-NRCS_SouthCentral_2017_D17/TIFF/USGS_1M_17_x54y410_VA_FEMA-NRCS_SouthCentral_2017_D17.tif
    -> ("VA", "VA_FEMA-NRCS_SouthCentral_2017_D17", "USGS_1M_17_x54y410_VA_FEMA-NRCS_SouthCentral_2017_D17.tif").

    Project folder names are consistently <STATE>_<rest> on the real bucket
    (confirmed against AL_, AR_, VA_, GA_, ... project folders) - used only
    to keep downloaded tiles organized locally under OUT_DIR/<state>/, the
    same layout fetch_topo_quads.py uses. The download URL itself always
    comes straight from the TNM Access API's own downloadURL field (see
    module docstring for why that's the real source of truth here, unlike
    the topo quads case), never reconstructed from a filename."""
    match = TILE_URL_RE.search(url)
    if not match:
        raise ValueError(f"couldn't parse project/filename from tile URL: {url}")
    project = match.group("project")
    filename = match.group("filename")
    state = project.split("_", 1)[0]
    return state, project, filename


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


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}

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

    print(f"{len(candidates)} tiles intersect the corridor (real download scope).")

    downloaded = skipped = corrupted = unparseable = 0
    total_bytes = 0
    for n, item in enumerate(candidates, 1):
        tif_url = item["downloadURL"]
        try:
            state, _project, filename = parse_tile_url(tif_url)
        except ValueError as e:
            print(f"  [{n}/{len(candidates)}] SKIPPING unparseable URL: {e}")
            unparseable += 1
            continue
        local_path = OUT_DIR / state / filename

        head = requests.head(tif_url, timeout=30)
        if head.status_code != 200:
            print(f"  [{n}/{len(candidates)}] HEAD failed unexpectedly for {tif_url}")
            continue

        remote_last_modified = head.headers.get("Last-Modified")
        prior = manifest.get(tif_url)
        if prior and prior.get("last_modified") == remote_last_modified and local_path.exists():
            skipped += 1
            continue

        local_path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(tif_url, timeout=300)
        resp.raise_for_status()
        local_path.write_bytes(resp.content)
        total_bytes += len(resp.content)

        # Validate readability, not just presence - fetch_topo_quads.py hit
        # this exact gotcha for real: 3 of its 1,654 quads downloaded with a
        # matching HTTP status and exact Content-Length yet were genuinely
        # corrupted on USGS's own S3 bucket. Without this check, that kind
        # of corruption goes undetected until something downstream (e.g. an
        # elevation-profile query) tries to actually read the file.
        try:
            with rasterio.open(local_path) as src:
                src.read(1)
        except Exception as e:
            print(f"  [{n}/{len(candidates)}] CORRUPTED after download: {state}/{filename} ({e})")
            corrupted += 1
            continue

        manifest[tif_url] = {
            "last_modified": remote_last_modified,
            "local_path": str(local_path.relative_to(ROOT)),
        }
        downloaded += 1
        print(f"  [{n}/{len(candidates)}] downloaded {state}/{filename} ({len(resp.content) / 1e6:.1f} MB)")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(
        f"\nDone. {downloaded} downloaded ({total_bytes / 1e9:.2f} GB), "
        f"{skipped} already up to date, {corrupted} corrupted, {unparseable} unparseable. "
        f"Manifest -> {MANIFEST_PATH}"
    )
    if corrupted:
        print(
            f"{corrupted} tile(s) downloaded but failed validation - investigate before trusting elevation output built from them."
        )


if __name__ == "__main__":
    main()
