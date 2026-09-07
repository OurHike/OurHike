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
from lib import corridor
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


USFS = {
    "key": "usfs_rec_sites",
    "provider": "USFS",
    "id_field": "objectid",
    "name_field": "site_name",
    "facility_field": "recarea_name",
    "asset_field": "site_type",
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


def test_the_allowlist_matches_whatever_case_the_agency_writes():
    """Whole values, stripped AND case-folded - what sources.json has claimed
    all along and what only became true with `_folded`.

    The failure this closes is silent in the worst way: DEC writes uppercase
    today, so a reshaping of their column to 'Pit Privy' would drop all 356
    privies while the run's own log called them "not a published POI type" -
    a sentence about the allowlist rather than about the case, so nobody
    reading it would look here.

    Both directions, because the two agencies write opposite cases and a fold
    that only handled DEC's would be half a fix.
    """
    assert kept_types(DEC_BIG, [feature(ASSET="Pit Privy", PUBLICUSE="Y", OBJECTID=1)]) == ["privy"]
    assert kept_types(OPRHP, [feature(Sub_Asset="LEAN-TO", ParksApp="Y", OBJECTID=2)]) == ["shelter"]


def test_a_refusal_survives_a_casing_change_too():
    """The direction that matters more, and it is not symmetric with the one
    above: an allowlist miss loses a pin, and an EXCLUSION miss ships a hazard.

    'Ford' would fall through to the allowlist rather than to its named
    exclusion, and the allowlist has no 'ford' - so the row still drops. This
    asserts the whole of that: no crossing pin, and the run still says WHY,
    because a drop labelled "not a published POI type" is how a deliberate
    refusal quietly becomes an oversight nobody can find later.
    """
    features = [
        feature(ASSET="Ford", PUBLICUSE="Y", OBJECTID=1),
        feature(ASSET="Water Supply System", PUBLICUSE="Y", OBJECTID=2),
    ]
    records, stats = export_nearby_poi.build_records(DEC_BIG, features)
    assert records == []
    dropped = stats["dropped"]
    assert any(label.startswith("excluded: Ford - unbridged crossing") for label in dropped), dropped
    assert any(label.startswith("excluded: Water Supply System - DEC water refused") for label in dropped), dropped


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


# --- USFS, and the one type that must never come out (#1207) ----------------


def test_usfs_dispersed_camping_never_ships():
    """The largest site_type in the layer, held back on purpose.

    'CAMPING AREA' is 10,783 of usfs_rec_sites' 31,405 nationwide rows - more
    than every developed campground in the national forest system combined -
    and it is dispersed camping: development_scale 0 on 8,135 of them, names
    that are forest-road references ('RD 614 SITE 13', 'FS1302-03') rather than
    places.

    This project already decided not to publish that class of location.
    SOURCE_SURVEY.md section 3b holds back ATC's 2,333 user-created campsites
    because "publishing locations may be actively harmful" - they are the ones
    land managers are often trying to close - and the screenshot rules name a
    dispersed campsite at a readable zoom as one of four things that must never
    appear even in a picture, because a map is a publication of coordinates.
    Shipping these would be that publication at 4.6x the scale, arriving as a
    side effect of a change about the White Mountains.

    So it is a test rather than a comment: USFS_SITE_TYPES is one careless line
    away from including it, and nothing else would notice.
    """
    features = [
        feature(site_type="CAMPING AREA", development_scale="0", site_name="RD 614 SITE 13", objectid=1),
        feature(site_type="CAMPING AREA", development_scale="0", site_name="FS1302-03", objectid=2),
    ]
    assert kept_types(USFS, features) == []


def test_usfs_developed_campgrounds_do_ship():
    """The other half of the holdback: developed sites are not the concern.

    Without this case the test above is satisfied by USFS shipping no campsites
    at all, which would be a different bug wearing the same green tick.
    """
    features = [
        feature(site_type="CAMPGROUND", site_name="Fixture Brook Campground", objectid=1),
        feature(site_type="GROUP CAMPGROUND", site_name="Fixture Group Camp", objectid=2),
    ]
    assert kept_types(USFS, features) == ["campsite", "campsite"]


def test_a_usfs_lookout_is_not_a_shelter():
    """815 LOOKOUT/CABIN rows, and a hiker walking into weather must not be
    told there is a roof ahead they cannot use. sources.json's poi_coverage
    calls this `unsuitable` - real data, misleading reading - and the allowlist
    is what enforces it."""
    assert kept_types(USFS, [feature(site_type="LOOKOUT/CABIN", site_name="Fixture Summit Lookout", objectid=1)]) == []


def test_usfs_trailheads_and_observation_sites_are_the_two_clean_mappings():
    features = [
        feature(site_type="TRAILHEAD", site_name="Fixture Notch Trailhead", objectid=1),
        feature(site_type="OBSERVATION SITE", site_name="Fixture Ledge Overlook", objectid=2),
    ]
    assert kept_types(USFS, features) == ["parking", "viewpoint"]


def test_the_two_typed_layer_maps_cannot_drift_apart():
    """TYPED_LAYERS selects the sources; TYPED_LAYERS_FOLDED types their rows.

    They are two hand-maintained dicts that must hold the same keys, and
    nothing checked that until this test. IT IS NOT HYPOTHETICAL: adding USFS
    under #1207 updated the first and not the second, and the result was a
    KeyError raised only when a usfs_rec_sites row reached the typing step -
    so the export selected a source it could not then type. A third org is what
    made a two-entry duplication start costing something.

    Keys and field names both, because a field spelled one way in the selector
    and another in the lookup fails the same way one step later.
    """
    assert set(export_nearby_poi.TYPED_LAYERS) == set(export_nearby_poi.TYPED_LAYERS_FOLDED)
    for key, (field, _) in export_nearby_poi.TYPED_LAYERS.items():
        assert field == export_nearby_poi.TYPED_LAYERS_FOLDED[key][0], (
            f"{key} reads {field!r} when selecting and {export_nearby_poi.TYPED_LAYERS_FOLDED[key][0]!r} when typing"
        )


def test_folding_usfs_site_types_loses_nothing():
    """The folded map is the one that decides, so it has to carry every row.

    A collision would silently drop a mapping - _folded raises on a true
    collision, but a quiet size mismatch would mean a type nobody notices is
    missing.
    """
    assert len(export_nearby_poi.USFS_SITE_TYPES_FOLDED) == len(export_nearby_poi.USFS_SITE_TYPES)
    assert "CAMPING AREA".casefold() not in export_nearby_poi.USFS_SITE_TYPES_FOLDED, (
        "the dispersed-camping holdback has to survive case folding too - it is the whole point of #1207's "
        "USFS_SITE_TYPES allowlist"
    )


class TestTheRingAroundThePublishedTrails:
    """#1113: the decisions table says amenity POIs are chosen-trail-only, and
    #1097 shipped 8,480 of them clipped to nothing. The maintainer took that
    knowingly and asked for the collision to be recorded; this is the clip that
    closes it, buffering by the same NETWORK_BUFFER_FEET water already uses."""

    @staticmethod
    def _network(tmp_path, lines):
        path = tmp_path / "nearby_trails.geojson"
        path.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": line},
                            "properties": {"source": "oprhp_trails"},
                        }
                        for line in lines
                    ],
                }
            )
        )
        return path

    @staticmethod
    def _poi(poi_type, lon, lat, source="oprhp_facilities"):
        return {"id": f"{source}:{poi_type}:{lon}:{lat}", "source": source, "poi_type": poi_type, "lon": lon, "lat": lat}

    def test_a_waypoint_beside_a_trail_survives_and_one_far_off_does_not(self, tmp_path):
        # A degree of latitude is ~364,000 ft, so 0.01 deg is ~3,650 ft - well
        # outside the 500 ft ring - and 0.0005 deg is ~180 ft, well inside.
        network = self._network(tmp_path, [[[-74.0, 44.0], [-74.0, 44.02]]])
        near = self._poi("campsite", -74.0, 44.0005)
        far = self._poi("campsite", -74.01, 44.0005)

        kept, ring = export_nearby_poi.clip_to_network([near, far], network)

        assert [record["id"] for record in kept] == [near["id"]]
        assert ring["ran"] is True
        assert ring["dropped"] == 1

    def test_parking_and_trailheads_are_exempt_because_that_is_where_you_leave_the_car(self, tmp_path):
        """MEASURED: a uniform 500 ft ring drops 49% of DEC's parking areas,
        and exempting them changes no densest-screen figure at all because both
        types start hidden under #865. #981 is the argument - a lot is an
        annotation on a start, never a precondition."""
        network = self._network(tmp_path, [[[-74.0, 44.0], [-74.0, 44.02]]])
        far = [
            self._poi("parking", -74.01, 44.0005),
            self._poi("trailhead", -74.01, 44.001),
            self._poi("privy", -74.01, 44.0015),
        ]

        kept, ring = export_nearby_poi.clip_to_network(far, network)

        assert sorted(record["poi_type"] for record in kept) == ["parking", "trailhead"]
        assert ring["exempt_types"] == ["parking", "trailhead"]
        assert ring["dropped_by_source_type"] == {"oprhp_facilities/privy": 1}

    def test_it_buffers_by_the_same_number_water_does_rather_than_one_of_its_own(self):
        """One number, one home. A second radius here is the drift this
        repository keeps finding - and NEARBY_TRAILS.md section 11's argument
        for 500 ft is about this same ring."""
        assert export_nearby_poi.NETWORK_BUFFER_FEET == corridor.NETWORK_BUFFER_FEET

    def test_an_empty_network_keeps_everything_rather_than_emptying_the_map(self, tmp_path):
        """An empty artifact is an ordinary state - the licence gate having held
        every steward's lines back - and reading "no lines to measure against"
        as "nothing is near a line" would drop every amenity waypoint on a day
        nothing is wrong."""
        network = tmp_path / "nearby_trails.geojson"
        network.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
        records = [self._poi("campsite", -74.01, 44.0005)]

        kept, ring = export_nearby_poi.clip_to_network(records, network)

        assert kept == records
        assert ring["ran"] is False
        assert ring["dropped"] == 0
        assert "no ring" in ring["reason"]

    def test_a_missing_network_keeps_everything_too(self, tmp_path):
        records = [self._poi("campsite", -74.01, 44.0005)]

        kept, ring = export_nearby_poi.clip_to_network(records, tmp_path / "absent.geojson")

        assert kept == records
        assert ring["ran"] is False

    def test_the_manifest_says_what_the_ring_did(self, tmp_path, monkeypatch):
        """Each `sources` entry counts what its layer contributed BEFORE the
        clip, so without this block the manifest's per-source figures and its
        feature_count disagree with nothing to explain the gap."""
        monkeypatch.setattr(export_nearby_poi, "OUT_DIR", tmp_path)
        ring = {
            "ran": True,
            "ring_feet": 500,
            "exempt_types": ["parking"],
            "kept": 1,
            "dropped": 2,
            "dropped_by_source_type": {"a/b": 2},
        }

        manifest = export_nearby_poi.write_artifact([self._poi("campsite", -74.0, 44.0)], {}, ring)

        assert manifest["network_ring"] == ring
