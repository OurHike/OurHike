"""Archive the footprint of every NYNJTC paper map sheet, once, into the
bucket's own `archive/` folder (#1574 - A hiker on NYNJTC ground has nowhere
to buy the paper map for where they are).

    python archive_nynjtc_sheet_extents.py             read Avenza, write data/archive/nynjtc_map_sheets.json
    python archive_nynjtc_sheet_extents.py --upload    ...and put it at archive/nynjtc_map_sheets.json in R2
    python archive_nynjtc_sheet_extents.py --print     print the sheets already written, no network

WHAT A FOOTPRINT IS AND WHERE IT COMES FROM. NYNJTC publishes no index of
which paper sheet covers what ground: probed whole on 2026-09-17, none of the
27 public feature services under services7.arcgis.com/G1WTEJ6UVRUTvh9C carries
a sheet or map-number field, the org has no tile services, and none of its 76
public portal items is a map index. What does exist is the Avenza Map Store,
which sells each sheet singly as a georeferenced PDF and prints that
georeference on the product page as `data-bounds` - four lat/lng corners.
That is the publisher's own georeferencing of their own sheet, and it is the
only published footprint there is. Measured against the Kittatinny set's
locator picture the same day, the boxes agree with the sheet layout drawn
there; where a sheet is printed diagonal (the four Kittatinny sheets), the
footprint is the upright box AROUND the diagonal paper, so its corners claim
ground the paper does not show. lib/... does not correct for that, and the
reference file's note on that product says so.

WHY THIS IS AN ARCHIVE AND NOT A FETCH STEP, in the maintainer's words
(2026-09-17): "If you use avenza, that will eventually go away. It shouldn't
be a real pipeline that runs regularly. Just an archive that sits in its own
folder in r2." So:

  - NOTHING IN THE REGULAR PUBLISH RUNS THIS. `export_sources.py` reads the
    reviewed table in reference/ and never the network; the publish workflows
    do not invoke this file, and scripts/pipeline_scopes.py will report it
    `unclaimed`, which is correct.
  - IT WRITES TO ITS OWN PREFIX, `archive/`, declared in lib/r2_keys.py and
    R2_LAYOUT.md, at the bucket root beside `conditions/` - not inside a
    release folder, because a release is rebuilt from the code and this is a
    snapshot of somebody else's site that the code cannot rebuild once the
    site is gone.
  - IT RUNS WHEN A PERSON DISPATCHES IT (.github/workflows/archive-nynjtc-
    sheets.yml), and the object stays until a person replaces it.

THE JOIN IT DEPENDS ON IS REVIEWED, NOT DERIVED. Which Avenza product stands
for which print sheet is recorded per sheet in
reference/nynjtc_paper_maps.json (`avenza`), by a person, from the product
titles - "Harriman-Bear Mountain (South - Map 118) : 2023 : Trail Conference"
names its sheet, and the title is what the row was read from. A sheet with no
Avenza product (145 and 146 of the Catskill set, on 2026-09-17) is written to
the archive with no footprint rather than guessed at, and the phone matches no
ground to it - a miss, never a wrong answer.

WHAT THE PHONE DOES WITH IT. client/src/lib/mapSheets.ts fetches
`archive/nynjtc_map_sheets.json` when it has signal and keeps it beside the
conditions baseline; the tapped-line sheet asks which footprints hold the
tapped point and names the product those sheets belong to, from the
`paper_maps` the stewards artifact carries. No footprint on the phone means
no line on the sheet.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import html
import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path

from lib.data_env import resolve as resolve_environment
from lib.data_env import scope_key
from lib.http_retry import request_with_retry
from lib.r2_keys import validate_key
from lib.user_agent import USER_AGENT

ROOT = Path(__file__).parent
REFERENCE_PATH = ROOT / "reference" / "nynjtc_paper_maps.json"
OUT_PATH = ROOT / "data" / "archive" / "nynjtc_map_sheets.json"

#: The one object this writes. Spelled here and read by the client's
#: lib/mapSheets.ts; tests/test_published_key_contract.py holds the two
#: spellings together the way it holds every other key.
ARCHIVE_KEY = "archive/nynjtc_map_sheets.json"

#: The store is Shopify, so a product's page is its handle.
AVENZA_PRODUCT_URL = "https://store.avenza.com/products/{handle}"

#: The footprint, as the product page prints it:
#:   data-bounds="[{'lat': 41.11, 'lng': -74.23}, {'lat': 41.25, ...}, ...]"
#: Single-quoted Python-looking literals inside an HTML attribute, so the
#: value is unescaped and then read with ast.literal_eval rather than json.
BOUNDS_ATTRIBUTE = re.compile(r'data-bounds="([^"]*)"')

#: The year in an Avenza title - "... : 2023 : Trail Conference" - which is
#: the edition the footprint was read from, and worth carrying because the
#: print store may be a newer edition (the Kittatinny set is).
TITLE_YEAR = re.compile(r": (\d{4}) :")

#: Well-off-trail sanity bounds for a footprint: NYNJTC's whole region, with
#: a margin. A corner outside this is a parse that read something else.
LON_RANGE = (-76.5, -72.5)
LAT_RANGE = (40.0, 43.0)

#: Between requests, out of courtesy to a store this reads once.
THROTTLE_SECONDS = 1.0

WRITE_ENABLED_ENV_VAR = "R2_WRITE_ENABLED"


def parse_bounds(page: str) -> list[tuple[float, float]] | None:
    """The footprint on one product page as `[(lon, lat), ...]`, or None.

    None for a page with no `data-bounds` at all (a product that is not a
    map, or a page shape Avenza has since changed) and for a footprint that
    does not read as four corners inside NYNJTC's region - both are "no
    footprint", never a guess, because the phone treats an absent footprint
    as ground it cannot place and a wrong one as ground it can.
    """
    match = BOUNDS_ATTRIBUTE.search(page)
    if match is None:
        return None
    try:
        corners = ast.literal_eval(html.unescape(match.group(1)))
    except (ValueError, SyntaxError):
        return None
    if not isinstance(corners, list) or len(corners) < 3:
        return None
    ring: list[tuple[float, float]] = []
    for corner in corners:
        if not isinstance(corner, dict):
            return None
        try:
            lat = float(corner["lat"])
            lon = float(corner["lng"])
        except (KeyError, TypeError, ValueError):
            return None
        if not (LON_RANGE[0] <= lon <= LON_RANGE[1] and LAT_RANGE[0] <= lat <= LAT_RANGE[1]):
            return None
        ring.append((lon, lat))
    return ring


def sheets_to_archive(reference: dict) -> dict[str, dict]:
    """sheet -> {product handle, avenza handle or None}, from the reviewed table.

    Every sheet every product lists, including the ones with no Avenza
    product: they are written to the archive with `bounds: null` so a reader
    can tell "never looked" from "looked and found nothing".
    """
    rows: dict[str, dict] = {}
    for product in reference.get("maps", []):
        avenza = product.get("avenza") or {}
        for sheet in product.get("sheets", []):
            if sheet in rows:
                raise SystemExit(f"sheet {sheet} is listed by two products in {REFERENCE_PATH.name}; a sheet belongs to one")
            rows[sheet] = {"product": product["handle"], "avenza_handle": avenza.get(sheet)}
    return rows


def fetch_page(handle: str) -> str:
    response = request_with_retry(
        AVENZA_PRODUCT_URL.format(handle=handle),
        headers={"User-Agent": USER_AGENT},
        throttle_seconds=THROTTLE_SECONDS,
        label=f"avenza {handle}",
    )
    return response.text


def build_archive(
    reference: dict,
    fetch: Callable[[str], str] = fetch_page,
    now: dt.datetime | None = None,
) -> dict:
    """The archive document. `fetch` is injected so the tests never reach Avenza."""
    read_at = (now or dt.datetime.now(dt.UTC)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sheets: dict[str, dict] = {}
    for sheet, row in sheets_to_archive(reference).items():
        record: dict = {"product": row["product"], "avenza_handle": row["avenza_handle"], "bounds": None, "edition_year": None}
        if row["avenza_handle"] is not None:
            page = fetch(row["avenza_handle"])
            record["bounds"] = parse_bounds(page)
            title = re.search(r"<title>([^<]*)</title>", page)
            year = TITLE_YEAR.search(title.group(1)) if title else None
            record["edition_year"] = int(year.group(1)) if year else None
            if record["bounds"] is None:
                print(f"  {sheet}: no footprint on {row['avenza_handle']}", file=sys.stderr)
        sheets[sheet] = record
    return {
        "generated_at": read_at,
        "source": {
            "name": "Avenza Map Store",
            "url_pattern": AVENZA_PRODUCT_URL,
            "field": "data-bounds on each product page - the publisher's georeference of the sheet's PDF",
            "read_at": read_at,
        },
        "reference": f"pipeline/reference/{REFERENCE_PATH.name}",
        "bounds_are": "an upright lon/lat box around the sheet, as Avenza prints it; a sheet printed diagonal is wider than its paper",
        "sheets": sheets,
    }


def render(document: dict) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def upload(path: Path, key: str = ARCHIVE_KEY) -> str:
    """Put the archive in the bucket, under the data environment's prefix.

    The same guards publish.py keeps, in the same order: the key has to be
    legal in this layout, the environment has to be one of the three, and
    R2_WRITE_ENABLED has to be set - so a script run by hand on a laptop with
    credentials in the environment still writes nothing by accident.
    """
    reason = validate_key(key)
    if reason is not None:
        raise SystemExit(reason)
    if os.environ.get(WRITE_ENABLED_ENV_VAR) != "true":
        raise SystemExit(f"{WRITE_ENABLED_ENV_VAR} is not 'true', so nothing is uploaded. Set it to write to R2 on purpose.")
    environment = resolve_environment()
    scoped = scope_key(environment, key)

    import boto3  # here rather than at the top: reading Avenza needs no bucket credentials

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    client.put_object(
        Bucket=os.environ["R2_BUCKET"],
        Key=scoped,
        Body=path.read_bytes(),
        ContentType="application/json",
        CacheControl="public, max-age=3600",
    )
    return scoped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--upload", action="store_true", help=f"after writing, put the file at {ARCHIVE_KEY} in R2")
    parser.add_argument("--print", action="store_true", help="print the archive already on disk and read nothing")
    args = parser.parse_args(argv)

    if args.print:
        if not OUT_PATH.exists():
            print(f"{OUT_PATH} does not exist - run without --print first.")
            return 1
        document = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    else:
        reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
        document = build_archive(reference)
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(render(document), encoding="utf-8")
        print(f"Wrote {OUT_PATH}")

    with_bounds = {sheet: row for sheet, row in document["sheets"].items() if row["bounds"]}
    print(f"{len(with_bounds)} of {len(document['sheets'])} sheets carry a footprint (read {document['source']['read_at']})")
    for sheet, row in sorted(document["sheets"].items()):
        if row["bounds"] is None:
            print(f"  {sheet:5s} no footprint")
            continue
        lons = [lon for lon, _ in row["bounds"]]
        lats = [lat for _, lat in row["bounds"]]
        print(f"  {sheet:5s} lon {min(lons):.4f}..{max(lons):.4f}  lat {min(lats):.4f}..{max(lats):.4f}  ({row['edition_year']})")

    if args.upload:
        scoped = upload(OUT_PATH)
        print(f"Uploaded to {scoped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
