"""Tests for lib/poi_schema.py - the unified POI schema (ROADMAP.md's
"Unified POI schema" line) that export_poi.py maps every source (ATC
shelters/campsites/communities, opentrail.org water tags) into.

Pure-function tests only, per TESTING.md - no I/O, no DuckDB, no network.
export_poi.py's own tests cover the corridor-clip/export/manifest wiring
this schema plugs into.
"""

import copy

import pytest

from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_RANK, unify_poi

SHELTER_FEATURE = {
    "type": "Feature",
    "id": 1,
    "geometry": {"type": "Point", "coordinates": [-69.2624152728137, 45.4531807456927]},
    "properties": {
        "GlobalID": "11111111-1111-1111-1111-111111111111",
        "OBJECTID": 1,
        "Name": "Chairback Gap Lean-to Shelter",
    },
}

SHELTER_FIELD_MAP = {"id_field": "GlobalID", "name_field": "Name", "confidence": CONFIDENCE_HIGH}


def _community_feature():
    return {
        "type": "Feature",
        "id": 1,
        "geometry": {"type": "Point", "coordinates": [-82.4168092597345, 36.1451152009164]},
        "properties": {
            "GlobalID": "1dd87b3c-56b4-46a9-994f-5634049e509e",
            "FID": 1,
            "NAME": "Unicoi County",
        },
    }


def _opentrail_water_feature():
    return {
        "type": "Feature",
        "id": 0,
        "geometry": {"type": "Point", "coordinates": [-84.0, 34.5]},
        "properties": {"title": "Piped spring", "icon": "w", "dbid": 1237},
    }


def test_unify_poi_id_is_stable_across_repeated_runs_on_identical_input():
    """A future Report/Closure references a POI by id - it must never drift
    on a re-run of the pipeline against unchanged source data, so it can't
    be a randomly regenerated UUID."""
    feature = copy.deepcopy(SHELTER_FEATURE)

    first = unify_poi(feature, "shelter", "atc_shelters", "AT", SHELTER_FIELD_MAP)
    second = unify_poi(copy.deepcopy(feature), "shelter", "atc_shelters", "AT", SHELTER_FIELD_MAP)

    assert first["id"] == second["id"]
    assert first["id"] == "atc_shelters:11111111-1111-1111-1111-111111111111"


def test_unify_poi_does_not_hardcode_a_trail_id():
    """trail_id must come from the caller/field_map, never baked into the
    function as "AT" - this project starts AT-only but the schema itself
    has to be inheritable to a future trail/club (value #7)."""
    feature = copy.deepcopy(SHELTER_FEATURE)

    at_result = unify_poi(feature, "shelter", "atc_shelters", "AT", SHELTER_FIELD_MAP)
    lt_result = unify_poi(feature, "shelter", "atc_shelters", "LT", SHELTER_FIELD_MAP)

    assert at_result["trail_id"] == "AT"
    assert lt_result["trail_id"] == "LT"
    # Only trail_id should differ between the two calls - everything else is
    # derived from the feature/source, not the trail.
    assert at_result["id"] == lt_result["id"]
    assert at_result["poi_type"] == lt_result["poi_type"]


def test_unify_poi_takes_confidence_from_the_source_not_from_the_poi_type():
    """Two sources can feed one poi_type at different confidences, and the
    schema has to keep them apart.

    This used to be written as communities-versus-opentrail-resupply, and
    #806 retired that pairing: opentrail's "r" tag is roads and gaps rather
    than shops, so nothing feeds `resupply` above the ATC Community proxy any
    more. The property under test never depended on that pair - it is that
    `confidence` comes from the field_map - so it is stated here on a pairing
    that is still true rather than deleted with the example that expired."""
    community_result = unify_poi(
        _community_feature(),
        "resupply",
        "atc_communities",
        "AT",
        {"id_field": "GlobalID", "name_field": "NAME", "confidence": CONFIDENCE_LOW},
    )
    water_result = unify_poi(
        _opentrail_water_feature(),
        "water",
        "opentrail_at",
        "AT",
        {"id_field": "dbid", "name_field": "title", "confidence": CONFIDENCE_HIGH},
    )

    assert community_result["confidence"] == CONFIDENCE_LOW
    assert water_result["confidence"] == CONFIDENCE_HIGH
    assert CONFIDENCE_RANK[community_result["confidence"]] < CONFIDENCE_RANK[water_result["confidence"]]


def test_unify_poi_raises_on_missing_source_feature_id():
    """A misconfigured field_map (id_field pointing at a property the source
    doesn't actually have) must fail loudly, not silently produce ids like
    "source:None" that collide across every feature from that source. No
    top-level "id" fallback either, unlike the other tests here - this
    proves the failure isn't masked by that fallback."""
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-69.0, 45.0]},
        "properties": {"Name": "No id field here"},
    }
    bad_field_map = {"id_field": "NotARealField", "confidence": CONFIDENCE_HIGH}

    with pytest.raises(ValueError):
        unify_poi(feature, "shelter", "atc_shelters", "AT", bad_field_map)


def test_unify_poi_rejects_an_unknown_poi_type():
    feature = copy.deepcopy(SHELTER_FEATURE)
    with pytest.raises(ValueError):
        unify_poi(feature, "not_a_real_poi_type", "atc_shelters", "AT", SHELTER_FIELD_MAP)
