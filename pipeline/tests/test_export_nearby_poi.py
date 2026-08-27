"""Tests for export_nearby_poi.py - DEC's and OPRHP's waypoints (#1097).

Why this exists
---------------
Every failure guarded here is SILENT. This module reads two agencies'
free-text asset columns and decides which rows become pins on a hiker's map;
nothing about a wrong answer crashes, and most wrong answers look like a
slightly different feature count in a log nobody reads.

The four that would actually hurt somebody, in the order they would happen:

1. **A refused value comes back.** DEC's water is a measured refusal - 23
   features, zero flagged public, and the 350 that merely sound like water are
   fire ponds and natural gas wells (sources.json's `dec_water_holdback`). The
   allowlists here are the mechanism that keeps it out, and an allowlist is one
   careless line away from a prefix match that sweeps 'WATERHOLE' back in.
2. **A `PROPOSED` asset ships.** DEC publishes 98 of them. A hiker who walks to
   a proposed lean-to finds trees.
3. **The two public flags get read the same way.** They are opposite by
   measurement, not by taste: DEC's `PUBLICUSE` filters because its N side is
   4,290 culverts and other internal assets, OPRHP's `ParksApp` sets confidence
   because its N side includes every one of their 37 lean-tos. Reading OPRHP's
   as a filter loses real shelters; reading DEC's as a confidence signal
   publishes culverts at low confidence, which is still publishing culverts.
4. **A hazard is drawn as an amenity.** DEC's 36 `FORD` rows are unbridged
   crossings. The same pin as a footbridge would say the opposite of what they
   mean.

These run against synthetic features rather than the fetched layers, for
test_export_sources.py's reason: what is on disk in `data/raw/external/` depends
on when somebody last ran the fetcher, and a suite that reads it would pass or
fail on that. The live counts belong in POI_COVERAGE_SURVEY.md, dated, and in
spike_org_poi_coverage.py, re-runnable.
"""

from __future__ import annotations

import json

import pytest

import export_nearby_poi
from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES

DEC_BIG = {
    "key": "dec_backcountry_features",
    "provider": "NYS DEC",
    "public_field": "PUBLICUSE",
    "public_value": "Y",
    "id_field": "OBJECTID",
    "name_field": "NAME",
    "facility_field": "FACILITY",
    "asset_field": "ASSET",
}

DEC_LEAN_TOS = {
    "key": "dec_lean_tos",
    "provider": "NYS DEC",
    "poi_type": "shelter",
    "public_field": "PUBLICUSE",
    "public_value": "Y",
    "id_field": "OBJECTID",
    "name_field": "NAME",
    "facility_field": "FACILITY",
    "asset_field": "ASSET",
}

OPRHP = {
    "key": "oprhp_facilities",
    "provider": "NYS OPRHP",
    "public_field": "ParksApp",
    "public_value": "Y",
    "public_flag_sets_confidence": True,
    "id_field": "OBJECTID",
    "name_field": "Name",
    "facility_field": "Facility",
    "asset_field": "Sub_Asset",
}


def feature(lon: float = -74.0, lat: float = 44.0, **properties) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }


def kept_types(source: dict, features: list[dict]) -> list[str]:
    records, _ = export_nearby_poi.build_records(source, features)
    return [record["poi_type"] for record in records]


# ---------------------------------------------------------------------------
# 1. The refusals hold.


@pytest.mark.parametrize(
    "asset",
    [
        "WATER SUPPLY SYSTEM",  # the 23 real ones, zero of them public
        "WATERHOLE",  # 207 fire-and-wildlife impoundments
        "WELL",  # 97, dominated by natural gas wells
        "SPRING",  # 19, incl. one DEC's own notes call untested
        "CISTERN",  # 4 CCC-era fire cisterns
        "WATERFALL",
    ],
)
def test_no_dec_value_that_sounds_like_water_ever_ships(asset: str):
    """The refusal is the point, and a PUBLICUSE Y on the row must not rescue it.

    Parameterised over the values rather than asserted once, so a future edit
    that adds one back has to delete a named case saying why it is water.
    """
    assert kept_types(DEC_BIG, [feature(ASSET=asset, PUBLICUSE="Y", OBJECTID=1)]) == []


def test_oprhp_water_is_held_back_too_even_though_it_is_real():
    """OPRHP's spigots ARE drinking water - the holdback is seasonality, not doubt.

    A different reason from DEC's and the same outcome, which is exactly why it
    needs its own case: somebody reading only the DEC refusal might conclude
    OPRHP's should ship.
    """
    features = [
        feature(Sub_Asset="Water Spigot", ParksApp="Y", OBJECTID=1),
        feature(Sub_Asset="Drinking Fountain", ParksApp="Y", OBJECTID=2),
    ]
    assert kept_types(OPRHP, features) == []


def test_a_proposed_asset_is_not_a_feature():
    """A hiker who walks to a proposed lean-to finds trees."""
    features = [
        feature(ASSET="PROPOSED LEAN-TO", PUBLICUSE="Y", OBJECTID=1),
        feature(ASSET="PROPOSED PIT PRIVY", PUBLICUSE="Y", OBJECTID=2),
        feature(ASSET="PIT PRIVY", PUBLICUSE="Y", OBJECTID=3),
    ]
    assert kept_types(DEC_BIG, features) == ["privy"]


def test_a_ford_is_a_hazard_and_does_not_draw_as_a_crossing():
    """DEC's 36 unbridged crossings, kept off the map until HIKER_SAFETY.md has them."""
    features = [
        feature(ASSET="FORD", PUBLICUSE="Y", OBJECTID=1),
        feature(ASSET="FORD ", PUBLICUSE="Y", OBJECTID=2),  # the trailing-space twin
        feature(ASSET="BRIDGE", PUBLICUSE="Y", OBJECTID=3),
    ]
    assert kept_types(DEC_BIG, features) == ["crossing"]


def test_culverts_are_not_crossings():
    """4,290 of them, and a pipe under the tread is not a thing anyone walks over."""
    assert kept_types(DEC_BIG, [feature(ASSET="CULVERT", PUBLICUSE="Y", OBJECTID=1)]) == []


def test_oprhp_stairs_and_road_bridges_are_not_crossings():
    """Tightened from the survey's counting buckets on the way to shipping.

    POI_COVERAGE_SURVEY.md §0 counts Stairs under `crossing` and says a reviewer
    may want them separated; this is where that matters, because counting a
    staircase and drawing one are different acts.
    """
    features = [
        feature(Sub_Asset="Stairs", ParksApp="Y", OBJECTID=1),
        feature(Sub_Asset="Vehicle Bridge", ParksApp="Y", OBJECTID=2),
        feature(Sub_Asset="Trail Bridge", ParksApp="Y", OBJECTID=3),
    ]
    assert kept_types(OPRHP, features) == ["crossing"]


def test_the_allowlist_matches_whole_values_not_prefixes():
    """The mechanism behind every refusal above.

    DEC's column has 223 trimmed values and carries 'PROPOSED PIT PRIVY' beside
    'PIT PRIVY'. A prefix or substring rule would ship both, and would put
    'WATERHOLE' back within a word of 'WATER SUPPLY SYSTEM'.
    """
    assert kept_types(DEC_BIG, [feature(ASSET="PIT PRIVY SIGN", PUBLICUSE="Y", OBJECTID=1)]) == []
    assert kept_types(DEC_BIG, [feature(ASSET="PIT PRIVY", PUBLICUSE="Y", OBJECTID=2)]) == ["privy"]


# ---------------------------------------------------------------------------
# 2. The two public flags, read the two different ways.


def test_dec_public_use_filters_a_row_out_entirely():
    features = [
        feature(ASSET="PIT PRIVY", PUBLICUSE="N", OBJECTID=1),
        feature(ASSET="PIT PRIVY", PUBLICUSE="Y", OBJECTID=2),
    ]
    records, stats = export_nearby_poi.build_records(DEC_BIG, features)
    assert [record["source_feature_id"] for record in records] == [2]
    assert stats["low_confidence"] == 0


def test_oprhp_parks_app_keeps_the_row_and_lowers_its_confidence():
    """The 37 lean-tos this rule exists for: real, and in nobody's app."""
    features = [
        feature(Sub_Asset="Lean-to", ParksApp="N", OBJECTID=1),
        feature(Sub_Asset="Scenic View", ParksApp="Y", OBJECTID=2),
    ]
    records, stats = export_nearby_poi.build_records(OPRHP, features)
    assert [(r["poi_type"], r["confidence"]) for r in records] == [
        ("shelter", CONFIDENCE_LOW),
        ("viewpoint", CONFIDENCE_HIGH),
    ]
    assert stats["low_confidence"] == 1


def test_the_filter_applies_to_dec_per_type_services_too():
    """They are already DEC's public slice - the filter is there for the day one isn't.

    Not hypothetical at the margin: dec_firetowers publishes 35 rows against 34
    the big layer flags public, so one row of that service already fails this.
    """
    features = [
        feature(ASSET="LEAN-TO", PUBLICUSE="N", OBJECTID=1),
        feature(ASSET="LEAN-TO", PUBLICUSE="Y", OBJECTID=2),
    ]
    assert kept_types(DEC_LEAN_TOS, features) == ["shelter"]


# ---------------------------------------------------------------------------
# 3. What reaches the artifact.


def test_no_record_carries_a_mile():
    """A lean-to in the Adirondacks has no position on ATC's centerline.

    export_poi.attach_miles projects onto that axis; publishing a mile here
    would print a trail position for a place 1,200 km from the trail. The key is
    absent rather than null, and the client already reads absent as "no mile".
    """
    records, _ = export_nearby_poi.build_records(DEC_LEAN_TOS, [feature(ASSET="LEAN-TO", PUBLICUSE="Y", OBJECTID=1)])
    assert "mile" not in records[0]


def test_dec_null_sentinels_never_reach_a_name():
    """'-99' is DEC's own null. Rendered under a shelter it is worse than nothing."""
    features = [
        feature(ASSET="LEAN-TO", PUBLICUSE="Y", OBJECTID=1, NAME="-99"),
        feature(ASSET="LEAN-TO", PUBLICUSE="Y", OBJECTID=2, NAME="   "),
        feature(ASSET="LEAN-TO", PUBLICUSE="Y", OBJECTID=3, NAME=" Saginaw Bay Lean-To "),
    ]
    records, stats = export_nearby_poi.build_records(DEC_LEAN_TOS, features)
    assert [record["name"] for record in records] == [None, None, "Saginaw Bay Lean-To"]
    assert stats["unnamed"] == 2


def test_a_description_is_composed_from_the_orgs_own_two_columns():
    """OPRHP names 18% of its rows; without this the other 82% carry nothing at all."""
    records, _ = export_nearby_poi.build_records(
        OPRHP, [feature(Sub_Asset="Trail Bridge", Facility="Beaver Island State Park", ParksApp="Y", OBJECTID=1)]
    )
    assert records[0]["description"] == "Trail Bridge in Beaver Island State Park."
    assert records[0]["name"] is None


def test_dec_all_caps_is_title_cased_and_oprhps_own_casing_is_left_alone():
    """.title() is formatting, and it is applied to DEC's vocabulary only.

    Running OPRHP's through it would turn their 'Lean-to' into 'Lean-To', which
    is somebody else's spelling of the steward's own word.
    """
    dec, _ = export_nearby_poi.build_records(
        DEC_BIG, [feature(ASSET="PIT PRIVY", FACILITY="Delaware Wild Forest", PUBLICUSE="Y", OBJECTID=1)]
    )
    oprhp, _ = export_nearby_poi.build_records(
        OPRHP, [feature(Sub_Asset="Lean-to", Facility="Allegany State Park", ParksApp="Y", OBJECTID=1)]
    )
    assert dec[0]["description"] == "Pit Privy in Delaware Wild Forest."
    assert oprhp[0]["description"] == "Lean-to in Allegany State Park."


def test_a_surveyors_note_never_reaches_the_description():
    """DESCRIP is 27% under twelve characters of maintenance shorthand.

    The first version of compose_description appended it and produced
    "Observation Platform in Mcdonough State Forest. 12'."
    """
    records, _ = export_nearby_poi.build_records(
        DEC_BIG,
        [feature(ASSET="BRIDGE", FACILITY="Hunts Pond State Forest", DESCRIP='18" X 24 Metal', PUBLICUSE="Y", OBJECTID=1)],
    )
    assert records[0]["description"] == "Bridge in Hunts Pond State Forest."


def test_a_point_with_no_coordinates_is_dropped_rather_than_published_at_null_island():
    """Not hypothetical: 14 rows across three of these layers arrive this way."""
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": []},
            "properties": {"ASSET": "LEAN-TO", "PUBLICUSE": "Y", "OBJECTID": 1},
        },
        feature(ASSET="LEAN-TO", PUBLICUSE="Y", OBJECTID=2),
    ]
    records, stats = export_nearby_poi.build_records(DEC_LEAN_TOS, features)
    assert [record["source_feature_id"] for record in records] == [2]
    assert stats["dropped"]["no usable point geometry"] == 1


def test_every_published_type_is_one_the_schema_knows():
    """The two value maps are hand-written, and a typo in one would publish a
    poi_type no client build has an icon for."""
    published = set(export_nearby_poi.DEC_ASSET_TYPES.values()) | set(export_nearby_poi.OPRHP_SUB_ASSET_TYPES.values())
    assert published <= set(POI_TYPES), f"{sorted(published - set(POI_TYPES))} are not POI_TYPES"


def test_neither_value_map_publishes_water():
    """The refusal, asserted against the maps themselves rather than through a
    feature - so it holds even if build_records is rewritten."""
    assert "water" not in export_nearby_poi.DEC_ASSET_TYPES.values()
    assert "water" not in export_nearby_poi.OPRHP_SUB_ASSET_TYPES.values()


def test_the_artifact_carries_lat_and_lon_as_properties():
    """lib/trailData.ts's readPois drops a POI whose properties have no lat/lon.

    The geometry alone is not enough, and the two ends would disagree silently:
    a feature drawn on the map and absent from the store is a waypoint that
    cannot be searched, tapped or reported against.
    """
    records, _ = export_nearby_poi.build_records(
        DEC_LEAN_TOS, [feature(lon=-74.4, lat=44.3, ASSET="LEAN-TO", PUBLICUSE="Y", OBJECTID=1)]
    )
    collection = export_nearby_poi.records_to_geojson(records)
    properties = collection["features"][0]["properties"]
    assert (properties["lat"], properties["lon"]) == (44.3, -74.4)
    assert collection["features"][0]["geometry"]["coordinates"] == [-74.4, 44.3]


def test_the_artifact_omits_empty_values_rather_than_publishing_nulls():
    """An unnamed waypoint publishes no `name` key at all.

    3,133 of the 8,480 features have no name, so a null per row would be
    published emptiness on more than a third of the artifact - and the client
    reads an absent name exactly as it reads a null one.
    """
    records, _ = export_nearby_poi.build_records(DEC_LEAN_TOS, [feature(ASSET="LEAN-TO", PUBLICUSE="Y", OBJECTID=1, NAME="-99")])
    properties = export_nearby_poi.records_to_geojson(records)["features"][0]["properties"]
    assert "name" not in properties
    assert json.dumps(properties)  # serialisable, which is what the writer needs


# ---------------------------------------------------------------------------
# 4. The registry agrees with this module.


def test_every_registered_poi_source_has_a_home_in_this_module():
    """A layer registered with a `poi_type` this module cannot place would be
    fetched on every run and read by nothing - the exact state DEC's POI layers
    were in for nine days before #1097."""
    registry = json.loads((export_nearby_poi.ROOT / "sources.json").read_text())
    for source in export_nearby_poi.poi_sources(registry):
        assert source["provider"] in export_nearby_poi.TRAIL_IDS, (
            f"{source['key']} has no trail_id for provider {source['provider']!r}"
        )
        declared = source.get("poi_type")
        assert declared is None or declared in POI_TYPES, f"{source['key']} declares poi_type {declared!r}"
        if declared is None:
            assert source["key"] in export_nearby_poi.TYPED_LAYERS


def test_the_registered_water_holdbacks_say_why_in_the_registry_itself():
    """Both holdbacks are recorded beside the sources, not only in a survey.

    The next person to read dec_backcountry_features' ASSET column will see
    'SPRING' and 'WELL' and reasonably wonder; the answer has to be where they
    are looking.
    """
    registry = json.loads((export_nearby_poi.ROOT / "sources.json").read_text())
    assert "PUBLICUSE" in registry["dec_water_holdback"]
    assert "seasonal" in registry["oprhp_water_holdback"].lower()
