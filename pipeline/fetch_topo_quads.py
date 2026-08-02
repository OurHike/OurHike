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

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import duckdb
import rasterio
import requests

from lib.completeness import fail_if_incomplete

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
    if remote_last_modified and state.get("last_modified") == remote_last_modified and csv_path.exists():
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


def corridor_intersecting_quads(con) -> list[tuple]:
    """product_filename rows for every quad whose bbox intersects the AT
    corridor - the real download scope, out of the full nationwide metadata
    inventory. `con` must already have `quads` (metadata CSV) and `corridor`
    (corridor polygon) tables loaded."""
    return con.execute("""
        SELECT q.product_filename
        FROM quads q, corridor c
        WHERE ST_Intersects(
            ST_MakeEnvelope(q.westbc, q.southbc, q.eastbc, q.northbc),
            c.geom
        )
    """).fetchall()


def resolve_state_index(states: list[str]) -> dict:
    """Every actual GeoTIFF filename available per state, keyed the same way
    as list_state_geotiffs() - lifted out of main() so a per-cell caller
    (which usually only needs 1-2 states) can call it with just the states
    its own quads span."""
    state_index = {}
    for state in states:
        state_index[state] = list_state_geotiffs(state)
        print(f"  {state}: {len(state_index[state])} quads available")
    return state_index


def fetch_one_quad(product_filename: str, state_index: dict, out_dir: Path, manifest: dict) -> dict:
    """Fetch one corridor quad if it's new/changed, skip if not - the same
    logic main()'s loop always ran, extracted so both the whole-corridor
    path and the per-cell path (fetch_and_mosaic_cell.py) can call it.
    Mutates `manifest` in place on a successful download, same as before.
    Returns a status dict instead of touching shared counters directly, so
    each caller can tally/log results its own way."""
    state = product_filename.split("_", 1)[0]
    name_no_ext = product_filename.rsplit(".", 1)[0]
    key = bare_key(name_no_ext)
    filename = state_index.get(state, {}).get(key)
    if not filename:
        return {"status": "unmatched", "reason": "no_match", "product_filename": product_filename, "key": key}

    tif_url = f"{BUCKET_URL}/{GEOTIFF_PREFIX}/{state}/{filename}"
    local_path = out_dir / state / filename

    head = requests.head(tif_url, timeout=30)
    if head.status_code != 200:
        return {"status": "unmatched", "reason": "head_failed", "tif_url": tif_url}

    remote_last_modified = head.headers.get("Last-Modified")
    prior = manifest.get(tif_url)
    if prior and remote_last_modified and prior.get("last_modified") == remote_last_modified and local_path.exists():
        return {"status": "skipped", "state": state, "filename": filename, "path": local_path}

    local_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(tif_url, timeout=180)
    resp.raise_for_status()
    local_path.write_bytes(resp.content)

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
        # bytes included even though the download is unusable: the original
        # code counted total_bytes unconditionally right after the write,
        # before this validation ran, and the final summary line should
        # keep reflecting what was actually transferred over the network.
        return {
            "status": "corrupted",
            "state": state,
            "filename": filename,
            "path": local_path,
            "error": str(e),
            "bytes": len(resp.content),
        }

    try:
        # Relative to ROOT when possible - reproduces the original manifest
        # format exactly for every caller today (out_dir is always under
        # ROOT so far). Falls back to absolute rather than raising: this
        # field is write-only bookkeeping (never read back - only
        # "last_modified" drives the skip logic above), so a future caller
        # whose out_dir isn't under ROOT shouldn't crash over it.
        stored_path = str(local_path.relative_to(ROOT))
    except ValueError:
        stored_path = str(local_path)

    manifest[tif_url] = {
        "last_modified": remote_last_modified,
        "local_path": stored_path,
    }
    return {"status": "downloaded", "state": state, "filename": filename, "path": local_path, "bytes": len(resp.content)}


def fetch_quads_for_cell(product_filenames: list[str], state_index: dict, out_dir: Path, manifest: dict) -> list[dict]:
    """Same per-quad fetch as the whole-corridor path, scoped to one cell's
    quad list - used by fetch_and_mosaic_cell.py. Returns every result
    (including unmatched/corrupted, not just successes) in the same order
    as `product_filenames`, so the caller can react per-quad rather than
    just tallying a summary."""
    return [fetch_one_quad(pf, state_index, out_dir, manifest) for pf in product_filenames]


def completeness_problems(unmatched: int, corrupted: int) -> list[str]:
    """Build main()'s fail_if_incomplete() problem list. Deliberately
    asymmetric between the two "bad" per-quad outcomes fetch_one_quad() can
    report:

    - `corrupted` (matched and downloaded, but the bytes don't decode as a
      valid raster - see fetch_one_quad()'s post-download validation) is
      always *our* data-quality problem on a file we successfully identified
      and fetched, with a known recovery path (fix_corrupted_quads.py), so
      any nonzero count always fails the run.
    - `unmatched` (USGS's own metadata CSV lists a quad this script found no
      corresponding GeoTIFF for on S3) deliberately does NOT gate the exit
      code. This module's docstring already treats that as an expected,
      surfaced-not-fatal outcome ("Any quad that genuinely doesn't match is
      reported, not silently skipped") - a mismatch can reflect a real gap
      in USGS's own inventory rather than a bug in this script's name
      matching. Hard-failing on any nonzero count would make CI cry wolf on
      pre-existing upstream gaps and eventually train people to ignore real
      failures. It still gets a loud stderr warning in main() so it's never
      silently invisible - just not exit-code-fatal by itself.
    """
    problems = []
    if corrupted:
        problems.append(f"{corrupted} quad(s) corrupted after download (failed validation) - run fix_corrupted_quads.py")
    return problems


def main():
    csv_path = fetch_metadata_csv()

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE TABLE corridor AS SELECT * FROM ST_Read('{CORRIDOR_PATH.as_posix()}')")
    con.execute(f"CREATE TABLE quads AS SELECT * FROM read_csv_auto('{csv_path.as_posix()}')")

    total_quads = con.execute("SELECT COUNT(*) FROM quads").fetchone()[0]
    print(f"{total_quads} current quads nationwide in the metadata inventory.")

    kept = corridor_intersecting_quads(con)
    print(f"{len(kept)} quads intersect the 30-mile AT corridor (this is the real download scope).")

    states = sorted({pf.split("_", 1)[0] for (pf,) in kept})
    print(f"Listing actual GeoTIFF files for {len(states)} states from S3: {states}")
    state_index = resolve_state_index(states)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}

    downloaded = skipped = unmatched = corrupted = 0
    total_bytes = 0
    for n, (product_filename,) in enumerate(kept, 1):
        result = fetch_one_quad(product_filename, state_index, OUT_DIR, manifest)
        status = result["status"]
        if status == "unmatched":
            if result["reason"] == "no_match":
                print(f"  [{n}/{len(kept)}] UNMATCHED: no GeoTIFF found for {product_filename} (key={result['key']})")
            else:
                print(f"  [{n}/{len(kept)}] HEAD failed unexpectedly for {result['tif_url']}")
            unmatched += 1
        elif status == "skipped":
            skipped += 1
        elif status == "corrupted":
            print(
                f"  [{n}/{len(kept)}] CORRUPTED after download: {result['state']}/{result['filename']} "
                f"({result['error']}) - run fix_corrupted_quads.py"
            )
            corrupted += 1
            total_bytes += result["bytes"]
        else:  # downloaded
            downloaded += 1
            total_bytes += result["bytes"]
            print(f"  [{n}/{len(kept)}] downloaded {result['state']}/{result['filename']} ({result['bytes'] / 1e6:.1f} MB)")

    # Written BEFORE the completeness gate below, deliberately, and unlike every
    # sibling script in this pipeline - which all gate first. The difference is
    # what the manifest IS. Elsewhere (trails_manifest.json, poi/manifest.json)
    # it describes publishable output, so writing one for an incomplete run
    # would hand the publish step something it must not ship. Here it is a
    # resumption record: "last_modified" is the only field read back, and it is
    # what lets the next run skip a quad it already has.
    #
    # Gating first would therefore mean one corrupted quad discards the record
    # of the ~1,650 that downloaded fine, and the next run re-fetches all 14 GB.
    # Corrupted quads are already absent from the manifest (fetch_one_quad only
    # records the "downloaded" branch), so they retry on their own without this
    # file being withheld.
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(
        f"\nDone. {downloaded} downloaded ({total_bytes / 1e9:.2f} GB), "
        f"{skipped} already up to date, {unmatched} unmatched, {corrupted} corrupted. "
        f"Manifest -> {MANIFEST_PATH}"
    )
    if corrupted:
        print(f"{corrupted} quad(s) downloaded but failed validation - run fix_corrupted_quads.py to work around them.")
    if unmatched:
        # Loud, but deliberately not fatal on its own - see completeness_problems().
        print(
            f"WARNING: {unmatched} quad(s) unmatched - see the UNMATCHED line(s) above for which ones. "
            "Not gating the exit code on this alone: USGS's own metadata inventory can genuinely list "
            "a quad with no corresponding GeoTIFF on S3, which is an upstream inventory gap rather than "
            "a defect in this script's matching logic.",
            file=sys.stderr,
        )

    fail_if_incomplete(completeness_problems(unmatched, corrupted), label="Incomplete topo quad fetch")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    # --metadata-only exists because build_cells_manifest.py needs
    # ustopo_current.csv and nothing else could produce it. fetch_metadata_csv()
    # is the only producer, and it was reachable only through main() - which
    # dies four lines later on data/spike/corridor.geojson, a stale
    # proof-of-concept artifact lib/corridor.py:15-20 explicitly forbids
    # trusting and that no fresh checkout has at all.
    #
    # So the whole-corridor path here cannot run in CI, and the per-cell path
    # (build_cells_manifest.py then fetch_and_mosaic_cell.py) is not merely
    # preferred but the only route. This flag returns before any of that,
    # exposing the one CI-safe thing this script owns.
    parser = argparse.ArgumentParser(description="Fetch USGS topo quads for the AT corridor.")
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Fetch just the quad metadata inventory (ustopo_current.csv) and stop. What build_cells_manifest.py needs.",
    )
    return parser.parse_args([] if argv is None else argv)


def run(argv: list[str] | None = None) -> None:
    """Entry point, split out of the __main__ block so it can be tested.

    build-raster.yml's compute-cells and mosaic jobs both invoke
    `--metadata-only`, and while it sat inline under `if __name__` nothing
    could import it - so the one flag CI actually depends on was the one
    thing here with no test at all."""
    if parse_args(argv).metadata_only:
        fetch_metadata_csv()
    else:
        main()


if __name__ == "__main__":
    run(sys.argv[1:])
