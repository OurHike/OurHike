"""The dbt seed and the Python constants it mirrors cannot drift (#100).

dbt/seeds/poi_type_mapping.csv transcribes three things this repository
already trusts: fetch_opentrail.py's ICON_LEGEND (the documented meaning of
each icon code), export_poi.py's OPENTRAIL_ICON_MAP (which codes mint a POI,
as what, at what confidence), and export_poi.py's DIRECT_SOURCES rows for
the ATC layers in the Phase A slice. DBT.md names this hand-mirroring as the
one duplication risk in the design and asks for exactly this test: CI fails
the moment the CSV and the constants disagree, instead of the seed going
quietly stale while the Python moves on.
"""

import csv
from pathlib import Path

import export_poi
import fetch_opentrail

SEED_PATH = Path(__file__).parent.parent / "dbt" / "seeds" / "poi_type_mapping.csv"


def _seed_rows():
    with open(SEED_PATH, newline="") as f:
        return list(csv.DictReader(f))


def test_opentrail_rows_carry_the_icon_legend_verbatim():
    rows = {r["code"]: r for r in _seed_rows() if r["source_system"] == "opentrail"}

    assert set(rows) == set(fetch_opentrail.ICON_LEGEND), (
        "the seed must document every icon ICON_LEGEND documents, and no invented ones"
    )
    for code, legend in fetch_opentrail.ICON_LEGEND.items():
        assert rows[code]["label"] == legend


def test_opentrail_poi_type_mapping_is_export_pois_own():
    rows = {r["code"]: r for r in _seed_rows() if r["source_system"] == "opentrail"}

    mapped = {code: (row["poi_type"], row["confidence"]) for code, row in rows.items() if row["poi_type"]}
    assert mapped == export_poi.OPENTRAIL_ICON_MAP, (
        "the seed's mint-a-POI decisions must be export_poi.OPENTRAIL_ICON_MAP, not a second opinion"
    )
    for code, row in rows.items():
        if not row["poi_type"]:
            assert not row["confidence"], f"unmapped icon {code!r} must not carry a confidence"


def test_atc_rows_mirror_direct_sources():
    rows = {r["code"]: r for r in _seed_rows() if r["source_system"] == "atc"}
    direct = {stem: (poi_type, fields.get("confidence")) for stem, poi_type, _src, fields in export_poi.DIRECT_SOURCES}

    for stem, row in rows.items():
        assert stem in direct, f"seed's atc row {stem!r} names a layer DIRECT_SOURCES does not export"
        poi_type, confidence = direct[stem]
        assert row["poi_type"] == poi_type
        assert row["confidence"] == confidence


def test_the_seed_stays_inside_the_unified_poi_vocabulary():
    from lib.poi_schema import POI_TYPES

    for row in _seed_rows():
        if row["poi_type"]:
            assert row["poi_type"] in POI_TYPES
