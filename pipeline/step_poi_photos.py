"""step_poi_photos: the photo manifests export_poi.py attaches to POIs, written to derived.poi_photos for dbt to read back.

    python step_poi_photos.py [--warehouse data/warehouse.duckdb]
        [--commons <poi_images.json>] [--atc <poi_images_atc.json>] [--decisions <photo_screen_decisions.json>]

pipeline/ELT.md's ledger rows PO24 and PO38, and "Python steps, outside dbt".

MANIFEST ROWS, NEVER PIXELS. A photo reaches a card through two outcome files
the photo fetchers write: fetch_poi_images.py's poi_images.json (Commons, one
`photo` per POI) and fetch_atc_photos.py's poi_images_atc.json (ATC's own
inventory photos, a `photos` list). Each photo record carries its bucket key
(`digest`, the sha256 of the bytes the fetcher stored), its credit (page_url,
author, license, taken) and, for Commons, the face screen's result
(lib/photo_screen.py's `screen`). Those records are what land here; the bytes
stay where the fetchers put them and the bucket gate in publish.py reads
(decision 4: bytes never enter DuckDB).

A STAND-IN FOR AN EXTRACT KIND. The Commons manifest belongs to the extract
(`_shared/wikimedia/`), which waits: fetch_poi_images.py geosearches around
each POI the export publishes, so its input is a dbt output, and the digest
and the screen both come from the bytes, which no extract resource may read.
Until the kind is built, this lands the two files export_poi.py reads today,
from the paths it reads them at, so a dbt build attaches exactly the photos a
publish does. An absent file is a build with none of its photos, as it is for
export_poi.py's load_photo_records().

WHAT IS DECIDED HERE, AND WHAT IN SQL. Two facts come from Python's own
homes: which records are found photos (export_poi.load_photo_records(), one
home for the two files' shapes) and whether a Commons photo is flagged
(lib/photo_screen.flagged()); and each digest's human decision, read through
lib/photo_screen.load_decisions(), which refuses a decision it does not know
rather than read a typo like "clear" as not cleared. The gate itself, refused
never ships and flagged ships only once cleared (PO38), and the attachment
(PO24) are int_points_of_interest__photos.

One row per photo, in each POI's list order.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

import export_poi
from lib import photo_screen

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
SCHEMA = "derived"
TABLE = "poi_photos"


def manifest_rows(commons: Path, atc: Path, decisions: dict[str, dict]) -> list[tuple]:
    """(source, poi_id, photo_index, digest, page_url, author, license, taken, screened, flagged, decision, photo) per found photo."""
    rows = []
    for source, path in (("commons", commons), ("atc", atc)):
        for poi_id, photos in export_poi.load_photo_records(path).items():
            for index, photo in enumerate(photos):
                digest = photo.get("digest")
                rows.append(
                    (
                        source,
                        poi_id,
                        index,
                        digest,
                        *(photo.get(field) for field in export_poi.PHOTO_FIELDS),
                        "screen" in photo,
                        photo_screen.flagged(photo),
                        decisions.get(digest or "", {}).get("decision"),
                        json.dumps(photo),
                    )
                )
    return rows


def write_poi_photos(con: duckdb.DuckDBPyConnection, rows: list[tuple], loaded_at: datetime) -> int:
    """Replace derived.poi_photos with these rows. Returns the row count."""
    con.execute(f"create schema if not exists {SCHEMA}")
    con.execute(f"""
        create or replace table {SCHEMA}.{TABLE} (
            source varchar,
            poi_id varchar,
            photo_index integer,
            digest varchar,
            page_url varchar,
            author varchar,
            license varchar,
            taken varchar,
            screened boolean,
            flagged boolean,
            decision varchar,
            photo json,
            _loaded_at timestamptz
        )
    """)
    if rows:
        con.executemany(
            f"insert into {SCHEMA}.{TABLE} values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(*row, loaded_at) for row in rows],
        )
    return con.execute(f"select count(*) from {SCHEMA}.{TABLE}").fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--commons", type=Path, default=export_poi.RAW_DIR / export_poi.IMAGES_FILENAME)
    parser.add_argument("--atc", type=Path, default=export_poi.RAW_DIR / export_poi.ATC_IMAGES_FILENAME)
    parser.add_argument("--decisions", type=Path, default=photo_screen.DECISIONS_PATH)
    args = parser.parse_args(argv)

    rows = manifest_rows(args.commons, args.atc, photo_screen.load_decisions(args.decisions))
    with duckdb.connect(str(args.warehouse)) as con:
        written = write_poi_photos(con, rows, datetime.now(UTC))
    counts = {source: sum(1 for row in rows if row[0] == source) for source in ("commons", "atc")}
    flagged = sum(1 for row in rows if row[0] == "commons" and row[9])
    print(
        f"{SCHEMA}.{TABLE}: {written:,} photos, {counts['commons']:,} from {args.commons} "
        f"({flagged:,} flagged by the face screen), {counts['atc']:,} from {args.atc}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
