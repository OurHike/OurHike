"""The reviewed park-terms table, dbt/seeds/notice_park_terms.csv, held to its own shape and the registry.

A club's `park:` term maps to the park areas places.json publishes for it, each as that place's bounding box, and a
notice whose every park term is mapped shows only to a planned route that meets one of them
(client/src/lib/plannedNotices.ts). A wrong row hides a club's notice from the hike it is about, so every row must
name a notice source that exists, a place of a registered source, and a box a phone can read.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
SEED = PIPELINE / "dbt" / "seeds" / "notice_park_terms.csv"
READERS = PIPELINE / "dbt" / "seeds" / "notice_readers.csv"
REGISTRY = {row["key"] for row in json.loads((PIPELINE / "sources.json").read_text())["sources"]}


def seed_rows() -> list[dict]:
    with SEED.open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_every_row_names_a_notice_source_and_a_park_term():
    with READERS.open(newline="") as handle:
        sources = {row["source_key"] for row in csv.DictReader(handle)}
    for row in seed_rows():
        assert row["source_key"] in sources, row
        assert re.fullmatch(r"park:[a-z0-9-]+", row["term"]), row


def test_every_place_id_belongs_to_a_registered_source():
    """places.json's ids are `<source>:<id>`, or `trail:<source>:<name>` for a trail (pub_places)."""
    for row in seed_rows():
        parts = row["place_id"].split(":")
        source = parts[1] if parts[0] == "trail" else parts[0]
        assert source in REGISTRY, row


def test_every_box_is_west_south_east_north_in_degrees():
    for row in seed_rows():
        west, south, east, north = (float(row[k]) for k in ("west", "south", "east", "north"))
        assert -180 <= west < east <= 180, row
        assert -90 <= south < north <= 90, row


def test_no_term_maps_to_one_place_twice():
    keys = [(row["source_key"], row["term"], row["place_id"]) for row in seed_rows()]
    assert len(keys) == len(set(keys))


def test_the_three_parks_with_no_published_area_stay_unmapped():
    """Measured 2026-10-15: places.json (UA release 2026-10-10-2) carries no area for these three of NYNJTC's ten
    park terms, so a row for any of them would name a place that is not there; and OPRHP's 0.004-degree
    'Palisades' parcel in New York is not the Palisades Interstate Park whose New Jersey cliffs Giant Stairs is on."""
    terms = {row["term"] for row in seed_rows()}
    assert terms.isdisjoint({"park:pequannock-watershed", "park:mahlon-dickerson-reservation", "park:palisades-interstate-park"})
