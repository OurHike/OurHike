"""build_water_distance.py - the CSI join, its gates, and its refusals.

The judgement calls live in three places and each gets its tests: the name
normalisation (CSI's names are mile prefixes, pad numbers and abbreviations
around the words that matter), the match order (name agreement from further
away beats a nearer stranger; bare proximity only within the tight gate), and
the refusals (a 0 ft distance and a missing row both publish nothing, with the
reason written down). The network functions are exercised nowhere here -
TESTING.md, never the real data - and the fetch itself is pinned only for the
one property that is a policy rather than plumbing: the WHERE clause that
keeps user-created sites from ever being requested.
"""

from __future__ import annotations

import build_water_distance as bwd


def csi_row(location, lat, lon, distance=100.0, provenance="NHDP_HR_Stream", rims="R1", site_type="Shelter"):
    return {
        "RIMS_ID": rims,
        "Location": location,
        "Site_Type": site_type,
        "Proximity_Water_ft": distance,
        "Nearest_Water_Source": provenance,
        "Latitude": lat,
        "Longitude": lon,
    }


def atc_feature(name, lat=40.0, lon=-76.0, global_id="g1"):
    return {"global_id": global_id, "name": name, "lat": lat, "lon": lon}


# At 40°N one degree of longitude is ~85.2 km, so this is ~44 m - inside
# the proximity gate. Distances below are built from this unit.
DEGREES_44_M = 0.00052


# --- normalise / names_agree ------------------------------------------------


def test_normalise_drops_type_words_digits_and_expands_abbreviations():
    """The three habits CSI and ATC do not share: ATC writes "Mtn" and pad-
    less names; CSI writes mile prefixes, pad numbers, and its own "Sh"."""
    assert bwd.normalise("Springer Mtn Shelter Campsite 1") == "springer mountain"
    assert bwd.normalise("Springer mountain shelter site 9") == "springer mountain"
    assert bwd.normalise("1088.1 Quarry Gap Shelters Campsite 2") == "quarry gap"
    assert bwd.normalise("West Mountain Sh tent site 1") == "west mountain"


def test_normalise_keeps_a_name_that_is_only_a_number():
    """PA's 501 Shelter is a digit string once "shelter" goes. Dropping the
    digit too would leave nothing, and nothing must never match everything -
    so the digits stay exactly when they are all the identity there is."""
    assert bwd.normalise("501 Shelter") == "501"


def test_names_agree_on_containment_but_never_on_emptiness():
    assert bwd.names_agree("Springer Mtn Shelter Campsite 1", "Springer mountain shelter site 9")
    assert bwd.names_agree("Wise Shelter", "Wise Shelter spring side")
    # "Campsite @ mile 1924.3" normalises to nothing and must not thereby
    # agree with every campsite on the trail.
    assert not bwd.names_agree("Leroy A. Smith Shelter", "Campsite @ mile 1924.3")
    assert not bwd.names_agree("Campbell Shelter", "Catawba Shelter")


# --- match_csi_row -----------------------------------------------------------


def test_a_name_match_beats_a_nearer_stranger():
    """The privy lesson from lib/poi_sites.py, applied to this join: the name
    is the better evidence, so the row ATC's feature is actually named for
    wins over an anonymous pad ten metres closer."""
    feature = atc_feature("Quarry Gap Shelters Campsite")
    stranger = csi_row("Campsite @ mile 1088.4", 40.0001, -76.0, rims="stranger")
    named = csi_row("1088.1 Quarry Gap Shelters Campsite 2", 40.0008, -76.0, rims="named")

    row, how, _ = bwd.match_csi_row(feature, [stranger, named])

    assert row["RIMS_ID"] == "named"
    assert how == "name"


def test_the_nearest_of_several_name_matches_wins():
    """CSI records individual pads, so several rows can honestly agree with
    one campsite - the nearest is the one surveyed closest to where ATC put
    the feature."""
    feature = atc_feature("Lance Creek Campsite")
    far_pad = csi_row("Lance creek 2", 40.0009, -76.0, rims="far", distance=200.0)
    near_pad = csi_row("Lance creek 1", 40.0003, -76.0, rims="near", distance=120.0)

    row, how, _ = bwd.match_csi_row(feature, [far_pad, near_pad])

    assert row["RIMS_ID"] == "near"
    assert how == "name"


def test_proximity_alone_matches_only_inside_the_tight_gate():
    """CSI misspells freely ("Governer Clement", "Limstone Spring"), so a row
    at the feature's own location matches without name agreement - but only
    within PROXIMITY_RADIUS_M. Past that, geometry alone is not evidence."""
    feature = atc_feature("Governor Clement Shelter")
    typo_at_site = csi_row("Governer Clement Shelter", 40.0 + DEGREES_44_M, -76.0)

    row, how, _ = bwd.match_csi_row(feature, [typo_at_site])
    assert row is not None
    assert how == "proximity"

    # The same stranger at ~110 m: inside the name radius, outside the
    # proximity one, and carrying no name evidence - no match.
    typo_further = csi_row("Governer Clement Shelter Annex Xyz", 40.0 + 2.5 * DEGREES_44_M, -76.0)
    row, how, _ = bwd.match_csi_row(atc_feature("Campbell Shelter"), [typo_further])
    assert row is None


def test_no_row_inside_the_name_radius_is_no_match():
    feature = atc_feature("West Carry Pond Lean-to Shelter")
    maine_gap = csi_row("Speck Pond Shelter tent 5", 41.0, -76.0)  # ~111 km away

    assert bwd.match_csi_row(feature, [maine_gap]) == (None, None, None)


# --- resolve_layer: the complete-statement shape ------------------------------


def test_every_feature_is_listed_and_blanks_carry_reasons():
    """The shelter_capacity.json shape: a feature that resolves nothing still
    appears, so a match lost on a later run is a changed line in a diff
    rather than a disappearance."""
    matched = atc_feature("Wise Shelter", global_id="g-matched")
    unmatched = atc_feature("Pierce Pond Lean-to Shelter", lat=45.0, global_id="g-unmatched")
    rows = [csi_row("Wise Shelter spring side", 40.0001, -76.0, distance=385.7)]

    records = bwd.resolve_layer("shelters", [matched, unmatched], rows)

    assert [record["atc_global_id"] for record in records] == ["g-matched", "g-unmatched"]
    resolved, missing = records
    assert resolved["distance_ft"] == 386
    assert resolved["listed_distance_ft"] == 385.7
    assert resolved["provenance"] == "NHDP_HR_Stream"
    assert resolved["csi_location"] == "Wise Shelter spring side"
    assert "unresolved" not in resolved
    assert missing["distance_ft"] is None
    assert missing["unresolved"] == bwd.NO_ROW_NEARBY


def test_a_zero_distance_publishes_nothing_with_the_reason_stated():
    """35 of the 1,013 official rows say 0 ft. Zero reads as at-the-source or
    as unmeasured, and the row does not say which - so the record refuses,
    out loud, instead of publishing a number nobody stands behind."""
    feature = atc_feature("Zeroed Shelter")
    rows = [csi_row("Zeroed Shelter", 40.0001, -76.0, distance=0)]

    [record] = bwd.resolve_layer("shelters", [feature], rows)

    assert record["distance_ft"] is None
    assert record["csi_location"] == "Zeroed Shelter"  # the row WAS read
    assert "0 ft" in record["unresolved"]


def test_a_farout_derived_row_is_held_back_with_its_evidence_kept():
    """WATER_SOURCES.md §4/§7: CSI's FarOut-measured distances derive from a
    commercial dataset this project has no rights to, so they publish nothing
    until ATC blesses them. The join evidence and the listed value stay - a
    reviewer of the holdback has to see what is held, and the value is one
    public query away on ATC's own service regardless."""
    feature = atc_feature("Hurd Brook Lean-to Shelter")
    rows = [csi_row("Hurd Brook Lean-to", 40.0001, -76.0, distance=120.0, provenance="FarOut")]

    [record] = bwd.resolve_layer("shelters", [feature], rows)

    assert record["distance_ft"] is None
    assert record["unresolved"] == bwd.HELD_BACK
    assert record["listed_distance_ft"] == 120.0
    assert record["provenance"] == "FarOut"
    assert record["csi_location"] == "Hurd Brook Lean-to"


def test_farout_is_not_among_the_publishable_provenances():
    """Pinned as data because it is the licence decision itself: adding
    "FarOut" here after ATC's blessing is the whole change that releases the
    held rows, and nothing else in this file should move when that happens."""
    assert bwd.PUBLISHABLE_PROVENANCES == frozenset({"NHDP_HR_Stream", "NHDP_HR_Pond", "OSA_Field_Estimate"})


def test_a_sub_metre_distance_rounds_up_to_a_foot_rather_than_to_zero():
    """round() alone would turn 0.4 ft into the 0 this file just refused to
    publish - a rounding artifact wearing the refusal's clothes."""
    feature = atc_feature("Waterside Shelter")
    rows = [csi_row("Waterside Shelter", 40.0001, -76.0, distance=0.4)]

    [record] = bwd.resolve_layer("shelters", [feature], rows)

    assert record["distance_ft"] == 1


# --- build: the document ------------------------------------------------------


def test_build_counts_per_layer_and_records_the_licence_position():
    """The counts are what a reviewer of the next diff reads first, and the
    source block is CONTRIBUTING.md's licence note made a field: the terms
    question is recorded in the artifact itself, not left to be rediscovered."""
    shelters = [atc_feature("Wise Shelter", global_id="s1")]
    campsites = [atc_feature("Lance Creek Campsite", lat=41.0, global_id="c1")]
    rows = [csi_row("Wise Shelter", 40.0001, -76.0)]

    document = bwd.build(rows, {"shelters": shelters, "campsites": campsites})

    assert document["counts"] == {
        "features": 2,
        "with_distance": 1,
        "shelters": 1,
        "shelters_with_distance": 1,
        "campsites": 1,
        "campsites_with_distance": 0,
    }
    assert "unstated" in document["source"]["licence"]
    assert "maintainer direction" in document["source"]["licence"]
    assert "User Created" not in str(document["sites"])


def test_the_fetch_asks_only_for_official_site_types():
    """The one property of the fetch that is policy rather than plumbing
    (SOURCE_SURVEY.md §3b): the 2,333 user-created campsites are excluded by
    the WHERE clause itself, so their locations never reach this machine.
    Pinned as data - the tuple this module builds its query from."""
    assert bwd.OFFICIAL_SITE_TYPES == ("Shelter", "A.T. Club or Agency Created Campsite")
    assert "User Created Campsite" not in bwd.OFFICIAL_SITE_TYPES


# --- the checked-in file ------------------------------------------------------


def test_the_checked_in_reference_file_is_complete_and_internally_consistent():
    """Not a re-derivation (that is `--check`, and it needs the network) -
    structural honesty of what is committed: every record either states a
    distance or states why not, layers and counts agree with the rows, and
    only the two registered layers appear."""
    document = __import__("json").loads(bwd.OUT_PATH.read_text(encoding="utf-8"))

    records = document["sites"]
    assert document["counts"]["features"] == len(records)
    assert {record["layer"] for record in records} == set(bwd.ATC_LAYERS)
    for record in records:
        stated = record["distance_ft"] is not None
        refused = bool(record.get("unresolved"))
        assert stated != refused, f"{record['atc_name']}: a record states a distance or a reason, never both or neither"
        if stated:
            assert record["distance_ft"] >= 1
            assert record["provenance"], f"{record['atc_name']}: a distance with no provenance"
    assert document["counts"]["with_distance"] == sum(1 for record in records if record["distance_ft"] is not None)
