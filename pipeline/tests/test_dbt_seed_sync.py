"""The dbt seed and the Python constants it mirrors cannot drift (#100).

dbt/seeds/poi_type_mapping.csv transcribes four things this repository
already trusts: fetch_opentrail.py's ICON_LEGEND (the documented meaning of
each icon code), export_poi.py's OPENTRAIL_ICON_MAP (which codes mint a POI,
as what, at what confidence), export_poi.py's DIRECT_SOURCES rows for the
ATC layers in the Phase A slice, and - since Phase D - sources.json's own
per-layer `poi_type` declarations for NYS DEC. DBT.md names this
hand-mirroring as the one duplication risk in the design and asks for
exactly this test: CI fails the moment the CSV and its sources disagree,
instead of the seed going quietly stale while they move on.

The DEC half mirrors THE REGISTRY rather than a Python constant, which is
the better authority for it: six DEC entries declare a layer-wide `poi_type`
in sources.json, and the seed says the same thing in the warehouse's
vocabulary. The confidence is not a fresh call either - the test asks
export_nearby_poi.public_verdict() what a kept row's confidence actually is
rather than restating the answer, so a change to that function's rule fails
here instead of leaving the seed asserting the old one.
"""

import csv
import json
from pathlib import Path

import export_nearby_poi
import export_poi
import fetch_opentrail

PIPELINE_ROOT = Path(__file__).parent.parent
SEED_PATH = PIPELINE_ROOT / "dbt" / "seeds" / "poi_type_mapping.csv"
SOURCES_PATH = PIPELINE_ROOT / "sources.json"


def _seed_rows():
    with open(SEED_PATH, newline="") as f:
        return list(csv.DictReader(f))


def _registry_sources():
    return json.loads(SOURCES_PATH.read_text())["sources"]


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
    """Mapped atc rows ARE DIRECT_SOURCES; unmapped ones must not be.

    An atc row with a poi_type claims export_poi.py publishes that layer, so
    the pair must match DIRECT_SOURCES exactly - in both directions, or a
    layer could be dropped from the export while the seed kept promising it.
    An atc row with an EMPTY poi_type (bridges) claims the opposite: the
    layer is registered and POI-shaped but deliberately unpublished (#99
    records the product call as open), so it must NOT appear in
    DIRECT_SOURCES, and like the unmapped opentrail icons it carries no
    confidence either.
    """
    rows = {r["code"]: r for r in _seed_rows() if r["source_system"] == "atc"}
    direct = {stem: (poi_type, fields.get("confidence")) for stem, poi_type, _src, fields in export_poi.DIRECT_SOURCES}

    mapped = {stem: row for stem, row in rows.items() if row["poi_type"]}
    assert set(mapped) == set(direct), "the seed's mapped atc rows and DIRECT_SOURCES must name exactly the same layers"
    for stem, row in mapped.items():
        poi_type, confidence = direct[stem]
        assert row["poi_type"] == poi_type
        assert row["confidence"] == confidence

    for stem, row in rows.items():
        if not row["poi_type"]:
            assert stem not in direct, f"seed marks atc layer {stem!r} deliberately-unmapped, but DIRECT_SOURCES exports it"
            assert not row["confidence"], f"unmapped atc layer {stem!r} must not carry a confidence"


def test_the_seed_stays_inside_the_unified_poi_vocabulary():
    from lib.poi_schema import POI_TYPES

    for row in _seed_rows():
        if row["poi_type"]:
            assert row["poi_type"] in POI_TYPES


# --- Phase D: the non-A.T. organizations (#100) ---------------------------


def test_dec_rows_are_the_registrys_own_poi_type_declarations():
    """Every DEC layer that declares a poi_type is in the seed as that type,
    and no seed row claims a declaration the registry does not make.

    Both directions matter. A DEC layer added to sources.json with a
    poi_type but not to the seed is a layer dim_pois would type without the
    seed's relationships test ever having heard of it; a seed row for a
    layer whose declaration was removed is the seed promising a type nothing
    upstream stands behind.
    """
    seed = {row["code"]: row for row in _seed_rows() if row["source_system"] == "dec"}
    declared = {
        entry["key"]: entry["poi_type"]
        for entry in _registry_sources()
        if entry.get("provider") == "NYS DEC" and entry.get("poi_type") is not None
    }

    assert set(seed) == set(declared), "the seed's dec rows and sources.json's declared poi_types must name the same layers"
    for key, poi_type in declared.items():
        assert seed[key]["poi_type"] == poi_type


def test_dec_confidence_is_what_export_nearby_poi_actually_returns():
    """Asked of the function rather than restated.

    A DEC entry declares no `public_flag_sets_confidence`, so
    public_verdict() keeps a flagged row at CONFIDENCE_HIGH. If that rule
    ever changes - or if an entry gains the flag - the seed stops being true
    and this fails, which is the whole point of a sync test.
    """
    seed = {row["code"]: row for row in _seed_rows() if row["source_system"] == "dec"}
    by_key = {entry["key"]: entry for entry in _registry_sources()}

    for key, row in seed.items():
        entry = by_key[key]
        flagged = {entry.get("public_field", "PUBLICUSE"): entry.get("public_value", "Y")}
        keep, confidence = export_nearby_poi.public_verdict(entry, flagged)
        assert keep, f"{key}: a row carrying the entry's own public_value must be kept"
        assert row["confidence"] == confidence


def test_a_layer_typed_per_row_is_deliberately_absent_from_the_seed():
    """oprhp_facilities and dec_backcountry_features publish POIs and have
    no seed row, and that is a decision rather than a gap.

    Both are typed PER ROW by export_nearby_poi.py's value maps, each with
    its own allowlist and its own NAMED_EXCLUSIONS - the water holdbacks
    among them. A seed row would have to either restate one of those maps or
    claim a layer-wide type neither layer has. This test pins the absence so
    a future session adding one has to argue with a failing test rather than
    with a comment.
    """
    codes = {row["code"] for row in _seed_rows()}

    for key in export_nearby_poi.TYPED_LAYERS:
        assert key not in codes, (
            f"{key} is typed per row by export_nearby_poi.TYPED_LAYERS; a seed row would be a second home "
            "for that map or a layer-wide type it does not have"
        )


def test_every_seed_source_system_is_one_the_dbt_schema_allows():
    """The seed's accepted_values test lives in dbt/seeds/seeds.yml and can
    only run once the warehouse is built. This is the same assertion at
    pytest speed, and it is the check that would have caught Phase A's
    two-value domain the first time a third organization arrived."""
    allowed = {"atc", "opentrail", "dec"}
    seen = {row["source_system"] for row in _seed_rows()}

    assert seen <= allowed, (
        f"seed rows carry source_system values the dbt accepted_values test would reject: {sorted(seen - allowed)}. "
        "Widen dbt/seeds/seeds.yml and this set together, or the seed passes pytest and fails the dbt build."
    )
