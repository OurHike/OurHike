"""Fetch current USGS US Topo raster quads (GeoTIFF) that intersect the AT corridor.

Uses USGS's own metadata inventory (ustopo_current.zip -> ustopo_current.csv,
from https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/Metadata/) instead
of the TNM Access API. This is a much better source for our purposes:
- One row per quad, `edition` column is always "Current" - no need to fight
  the multiple-cataloged-editions-per-quad problem the API query had.
- Real bbox columns (westbc/eastbc/northbc/southbc) for every quad, so
  filtering to "intersects the corridor" is one local DuckDB query - no
  per-cell API round-trips at all.

The CSV's product_filename column is NOT reliable for constructing the
GeoTIFF download URL directly: some rows have the dated form
("AL_Abbeville_East_20240208_TM_geo.pdf") and others the plain simplified
form ("CT_Ansonia.pdf", no date) - inconsistent within the same file. Instead
of guessing, this lists each relevant state's actual GeoTIFF folder from the
same public S3 bucket (verified to exist at
.../USTopo/GeoTIFF/<state>/<name>_<date>_TM_geo.tif, even though that path
isn't documented in USGS's own metadata readme) and matches by name with the
date suffix stripped from both sides. Any quad that genuinely doesn't match
is reported, not silently skipped.

Scope: only quads whose bbox intersects the 30-mile AT corridor (see
spike_corridor.py) - not every quad in every state the trail crosses. A
full-state pull is 1000+ quads per state (~300-500GB across all 14 states);
the corridor cuts that to ~1,650 quads (~16-17GB), which is what the app
actually needs (value #8 - keep downloads/hosting small).

Incremental: compares each quad's S3 Last-Modified against
data/raw/topo_quads/manifest.json from the previous run, and only
re-downloads quads that are new or have actually changed.
"""

import io
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import duckdb
import rasterio
import requests

ROOT = Path(__file__).parent
CORRIDOR_PATH = ROOT / "data" / "spike" / "corridor.geojson"
METADATA_URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/Metadata/ustopo_current.zip"
METADATA_DIR = ROOT / "data" / "raw" / "topo_metadata"
METADATA_STATE_PATH = METADATA_DIR / "fetch_state.json"
OUT_DIR = ROOT / "data" / "raw" / "topo_quads"
MANIFEST_PATH = OUT_DIR / "manifest.json"

BUCKET_URL = "https://prd-tnm.s3.amazonaws.com"
GEOTIFF_PREFIX = "StagedProducts/Maps/USTopo/GeoTIFF"
S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

DATED_SUFFIX_RE = re.compile(r"_\d{8}_TM_geo$")


def fetch_metadata_csv() -> Path:
    csv_path = METADATA_DIR / "ustopo_current.csv"
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    state = json.loads(METADATA_STATE_PATH.read_text()) if METADATA_STATE_PATH.exists() else {}
    head = requests.head(METADATA_URL, timeout=30)
    head.raise_for_status()
    remote_last_modified = head.headers.get("Last-Modified")
    if state.get("last_modified") == remote_last_modified and csv_path.exists():
        print(f"Quad metadata inventory unchanged since last fetch, skipping -> {csv_path}")
        return csv_path

    print(f"Fetching quad metadata inventory from {METADATA_URL} ...")
    resp = requests.get(METADATA_URL, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        z.extract("ustopo_current.csv", METADATA_DIR)
    METADATA_STATE_PATH.write_text(json.dumps({"last_modified": remote_last_modified}))
    print(f"  -> {csv_path}")
    return csv_path


def bare_key(filename_no_ext: str) -> str:
    """Strip a trailing _YYYYMMDD_TM_geo date suffix, if present, so dated and
    undated forms of the same quad name compare equal."""
    return DATED_SUFFIX_RE.sub("", filename_no_ext)


def list_state_geotiffs(state: str) -> dict:
    """List every GeoTIFF filename for a state, keyed by its bare (date-stripped)
    name - so we can match a CSV row to the real file without guessing."""
    keys = {}
    marker = ""
    while True:
        params = {"prefix": f"{GEOTIFF_PREFIX}/{state}/", "max-keys": 1000}
        if marker:
            params["marker"] = marker
        resp = requests.get(BUCKET_URL, params=params, timeout=60)
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
        contents = root.findall(f"{S3_NS}Contents")
        if not contents:
            break
        last_key = None
        for c in contents:
            key = c.find(f"{S3_NS}Key").text
            last_key = key
            filename = key.rsplit("/", 1)[-1]
            if not filename.endswith(".tif"):
                continue
            name_no_ext = filename[: -len(".tif")]
            bare = bare_key(name_no_ext)
            date_match = re.search(r"_(\d{8})_TM_geo$", name_no_ext)
            date = date_match.group(1) if date_match else ""
            prior = keys.get(bare)
            if prior is None or date > prior[1]:
                keys[bare] = (filename, date)
        is_truncated = root.find(f"{S3_NS}IsTruncated").text == "true"
        if not is_truncated:
            break
        marker = last_key
    return {k: v[0] for k, v in keys.items()}


def main():
    csv_path = fetch_metadata_csv()

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE TABLE corridor AS SELECT * FROM ST_Read('{CORRIDOR_PATH.as_posix()}')")
    con.execute(f"CREATE TABLE quads AS SELECT * FROM read_csv_auto('{csv_path.as_posix()}')")

    total_quads = con.execute("SELECT COUNT(*) FROM quads").fetchone()[0]
    print(f"{total_quads} current quads nationwide in the metadata inventory.")

    kept = con.execute("""
        SELECT q.product_filename
        FROM quads q, corridor c
        WHERE ST_Intersects(
            ST_MakeEnvelope(q.westbc, q.southbc, q.eastbc, q.northbc),
            c.geom
        )
    """).fetchall()
    print(f"{len(kept)} quads intersect the 30-mile AT corridor (this is the real download scope).")

    states = sorted({pf.split("_", 1)[0] for (pf,) in kept})
    print(f"Listing actual GeoTIFF files for {len(states)} states from S3: {states}")
    state_index = {}
    for state in states:
        state_index[state] = list_state_geotiffs(state)
        print(f"  {state}: {len(state_index[state])} quads available")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}

    downloaded = skipped = unmatched = corrupted = 0
    total_bytes = 0
    for n, (product_filename,) in enumerate(kept, 1):
        state = product_filename.split("_", 1)[0]
        name_no_ext = product_filename.rsplit(".", 1)[0]
        key = bare_key(name_no_ext)
        filename = state_index.get(state, {}).get(key)
        if not filename:
            print(f"  [{n}/{len(kept)}] UNMATCHED: no GeoTIFF found for {product_filename} (key={key})")
            unmatched += 1
            continue

        tif_url = f"{BUCKET_URL}/{GEOTIFF_PREFIX}/{state}/{filename}"
        local_path = OUT_DIR / state / filename

        head = requests.head(tif_url, timeout=30)
        if head.status_code != 200:
            print(f"  [{n}/{len(kept)}] HEAD failed unexpectedly for {tif_url}")
            unmatched += 1
            continue

        remote_last_modified = head.headers.get("Last-Modified")
        prior = manifest.get(tif_url)
        if prior and prior.get("last_modified") == remote_last_modified and local_path.exists():
            skipped += 1
            continue

        local_path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(tif_url, timeout=180)
        resp.raise_for_status()
        local_path.write_bytes(resp.content)
        total_bytes += len(resp.content)

        # Validate readability, not just presence - 3 quads out of 1,654 were
        # confirmed genuinely corrupted on USGS's own S3 bucket (LZW decode
        # failures in a later strip; verified independently via tifffile too,
        # not a rasterio quirk) despite downloading with a matching HTTP
        # status and exact Content-Length. Without this check, that kind of
        # corruption goes undetected until something downstream tries to
        # actually read the file - see fix_corrupted_quads.py for the
        # re-download-then-fallback recovery path for anything flagged here.
        try:
            with rasterio.open(local_path) as src:
                src.read(1)
        except Exception as e:
            print(f"  [{n}/{len(kept)}] CORRUPTED after download: {state}/{filename} ({e}) - run fix_corrupted_quads.py")
            corrupted += 1
            continue

        manifest[tif_url] = {
            "last_modified": remote_last_modified,
            "local_path": str(local_path.relative_to(ROOT)),
        }
        downloaded += 1
        print(f"  [{n}/{len(kept)}] downloaded {state}/{filename} ({len(resp.content) / 1e6:.1f} MB)")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(
        f"\nDone. {downloaded} downloaded ({total_bytes / 1e9:.2f} GB), "
        f"{skipped} already up to date, {unmatched} unmatched, {corrupted} corrupted. "
        f"Manifest -> {MANIFEST_PATH}"
    )
    if corrupted:
        print(f"{corrupted} quad(s) downloaded but failed validation - run fix_corrupted_quads.py to work around them.")


if __name__ == "__main__":
    main()
