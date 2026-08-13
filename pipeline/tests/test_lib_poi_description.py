"""Tests for lib/poi_description.py - assembling a POI's one-line
description from ATC's inventory columns.

The attribute dicts here mirror real ATC features (read 2026-08-09), with the
columns the composer reads and nothing else, so a test says which facts drive
which clause.
"""

import pytest

from lib.poi_description import (
    NEARBY_ORDER,
    describe_campsite,
    describe_parking,
    describe_privy,
    describe_shelter,
    describe_viewpoint,
    describe_water,
    nearby_clause,
    stream_sentence,
)

# Upper Goose Pond Cabin: two storeys, clapboard, fireplace, fire ring, porch.
CABIN = {
    "Stories": 2,
    "Exterior_M": "2",
    "Chimneys": 1,
    "Metal_Fir": 1,
    "Mortared": 0,
    "Food_Boxe": 0,
    "Food_Cabl": 0,
    "Food_Pole": 0,
    "Deck_Lengt": 24,
    "Year_Built": 1915,
}

# Chairback Gap Lean-to: the common case - one storey, log, nothing else.
LEAN_TO = {
    "Stories": 1,
    "Exterior_M": "5",
    "Chimneys": 0,
    "Metal_Fir": 0,
    "Mortared": 0,
    "Food_Boxe": 0,
    "Food_Cabl": 0,
    "Food_Pole": 0,
    "Deck_Lengt": 0,
    "Year_Built": 1954,
}

CAMPSITE = {"Type": "0", "Site_Num": 3, "Tent_Pads": 0, "Tent_Plat": 0, "Metal_Fir": 0, "Food_Boxe": 1}


def test_the_sentence_reads_as_a_sentence():
    assert describe_shelter(CABIN, capacity=14) == (
        "Two-storey clapboard shelter, sleeps 14, with a fireplace, a fire ring and a porch. Built 1915."
    )


def test_the_plain_case_says_only_what_atc_states():
    assert describe_shelter(LEAN_TO, capacity=6) == "Log shelter, sleeps 6. Built 1954."


def test_capacity_is_omitted_rather_than_guessed():
    """18 of ATC's 280 shelters have no published capacity
    (build_shelter_capacity.py refuses to split them). Those get the same
    sentence minus one clause, never "sleeps 0" and never a estimate."""
    assert describe_shelter(LEAN_TO) == "Log shelter. Built 1954."
    assert "sleeps" not in describe_shelter(LEAN_TO)


def test_an_unmapped_material_drops_to_a_plain_shelter():
    """Exterior_M codes 9 and 10 describe siding rather than structure and
    have no adjective. The sentence loses a word; it does not lose meaning
    or gain a wrong one."""
    assert describe_shelter({**LEAN_TO, "Exterior_M": "10"}, capacity=6) == "Shelter, sleeps 6. Built 1954."


def test_bear_proof_food_storage_is_named_whichever_form_atc_recorded():
    """Boxes, cables and poles are three columns and one fact to a hiker,
    who wants to know whether food can be hung safely - not the hardware."""
    for column in ("Food_Boxe", "Food_Cabl", "Food_Pole"):
        described = describe_shelter({**LEAN_TO, column: 1}, capacity=6)
        assert described == "Log shelter, sleeps 6, with bear-proof food storage. Built 1954."


@pytest.mark.parametrize("year", [0, None, 1799, 2101])
def test_an_implausible_year_is_left_off(year):
    """A placeholder year is a data-entry artifact, and "Built 0." would read
    as a bug rather than as the absence of a fact."""
    assert describe_shelter({**LEAN_TO, "Year_Built": year}, capacity=6) == "Log shelter, sleeps 6."


def test_a_shelter_atc_states_nothing_about_gets_no_description():
    """None, not "Shelter." - a sentence that repeats the card's own type
    line is worse than no sentence, because it looks like content."""
    assert describe_shelter({}) is None


def test_atcs_own_note_is_attributed_rather_than_blended_in():
    """The composed half is assembled from columns; the note is a person's
    prose. Running them together would present a maintainer's judgement as
    this pipeline's assertion."""
    described = describe_shelter(LEAN_TO, capacity=6, note="Not an accessible shelter")

    assert described == "Log shelter, sleeps 6. Built 1954. ATC notes: Not an accessible shelter."


def test_a_note_that_already_ends_in_a_stop_is_not_given_a_second():
    described = describe_shelter(LEAN_TO, capacity=6, note="Has a loft.")

    assert described.endswith("ATC notes: Has a loft.")


def test_campsites_lean_on_the_columns_they_actually_have():
    assert describe_campsite(CAMPSITE) == "Designated campsite, 3 sites, with bear-proof food storage."


def test_a_group_site_says_so():
    assert describe_campsite({**CAMPSITE, "Type": "1"}).startswith("Designated group campsite")


def test_pads_and_platforms_are_counted_separately_and_pluralised():
    described = describe_campsite({**CAMPSITE, "Tent_Pads": 1, "Tent_Plat": 6, "Food_Boxe": 0})

    assert described == "Designated campsite, 3 sites, 1 tent pad and 6 tent platforms."


def test_a_campsite_atc_states_nothing_about_gets_no_description():
    assert describe_campsite({"Type": "0"}) is None


@pytest.mark.parametrize("value", [None, "", "not a number", []])
def test_a_missing_or_junk_count_reads_as_none_of_them(value):
    """These are inventory counts. A column nobody filled in means nobody
    recorded any, which for the purpose of a sentence is zero - and must not
    raise partway through a data build."""
    described = describe_shelter({**LEAN_TO, "Chimneys": value, "Deck_Lengt": value}, capacity=6)

    assert described == "Log shelter, sleeps 6. Built 1954."


# --- vistas, parking and privies -------------------------------------------
#
# The same shape as above: real column values (read 2026-08-09), the ones the
# composer reads and nothing else.

# Bake Oven Knob (East) Vista: a 180° arc opening east, on a ridge.
VISTA = {"Left_Beari": 40, "Right_Bear": 220, "Location": "Mtn/Ridge/Outcrop"}

# Fox Gap (PA Rte 191): gravel, seven cars, no accessible spaces.
PARKING = {"Type": "0", "Surface": "3", "Parking_S": 7, "ADA_Space": 0}

# Bromley Summit Privy: moldering, single enclosure, rebuilt 2003.
PRIVY = {"Type": "1", "Enclosure": "1", "Year_Built": 2003}


def test_a_vista_says_how_wide_the_view_is_which_way_it_faces_and_what_from():
    """The three things a hiker has a question about before walking to one."""
    assert describe_viewpoint(VISTA) == "A 180° view south-east from a ridge or rock outcrop."


def test_the_arc_is_swept_clockwise_from_left_to_right():
    """Not the smaller of the two angles between the bearings. Wolf Rocks (PA)
    runs 280 -> 10, which is a 90° view over the north-west, and reading it
    the other way round would publish 270° facing south-east - the opposite
    direction and three times the view."""
    assert describe_viewpoint({"Left_Beari": 280, "Right_Bear": 10}) == "A 90° view north-west."


def test_a_view_of_almost_everything_is_called_panoramic_rather_than_aimed():
    """98 vistas sweep 300° or more. "A 340° view north-east" names one edge
    of a place you can turn round in."""
    assert describe_viewpoint({"Left_Beari": 10, "Right_Bear": 350, "Location": "Summit"}) == ("A panoramic view from a summit.")


def test_two_bearings_that_coincide_are_the_whole_horizon_not_nothing():
    assert describe_viewpoint({"Left_Beari": 90, "Right_Bear": 90}) == "A panoramic view."


def test_both_bearings_reading_zero_is_an_unsurveyed_vista_not_one_facing_north():
    """217 of 1,223 carry 0/0, which is the blank this layer writes. Read as a
    bearing it would publish a zero-degree view due north on every one of
    them."""
    assert describe_viewpoint({"Left_Beari": 0, "Right_Bear": 0, "Location": "Summit"}) == "A view from a summit."


def test_the_arc_is_rounded_because_atc_says_its_own_bearings_wander():
    """ATC's own comment on one vista: "measured bearings 3 times, each time
    getting different results". 62° published as 62° claims a precision the
    instrument did not have."""
    assert describe_viewpoint({"Left_Beari": 90, "Right_Bear": 152}) == "A 60° view south-east."


def test_a_narrow_view_survives_the_rounding_rather_than_becoming_zero():
    assert describe_viewpoint({"Left_Beari": 90, "Right_Bear": 92}) == "A 5° view east."


def test_the_number_gets_the_article_it_would_be_read_with():
    assert describe_viewpoint({"Left_Beari": 40, "Right_Bear": 120}).startswith("An 80°")
    assert describe_viewpoint({"Left_Beari": 40, "Right_Bear": 220}).startswith("A 180°")


def test_a_landform_atc_did_not_recognise_drops_the_clause_rather_than_guessing():
    """`Location` is free text: `TBD` on 90 features, and values like `Side
    Trail` that say where the surveyor stood rather than what the view is
    from."""
    assert describe_viewpoint({**VISTA, "Location": "TBD"}) == "A 180° view south-east."
    assert describe_viewpoint({**VISTA, "Location": "Side Trail"}) == "A 180° view south-east."


def test_a_multi_value_location_is_read_from_its_first_entry():
    """ "Summit; Lookout Tower" on 13 features. Matching the whole string would
    drop every one of them."""
    assert describe_viewpoint({**VISTA, "Location": "Summit; Lookout Tower"}).endswith("from a summit.")


def test_a_vista_with_no_arc_and_no_landform_gets_no_description():
    """The card's own type line already says "Viewpoint"."""
    assert describe_viewpoint({"Location": "TBD"}) is None


def test_a_vista_with_only_a_note_still_publishes_the_note():
    """ "No view beyond foreground; bald rock" is the most useful thing ATC
    says about that feature, and it would be silence if a note needed a
    sentence to hang off."""
    assert describe_viewpoint({}, note="No view beyond foreground") == "ATC notes: No view beyond foreground."


def test_parking_says_what_you_park_on_and_whether_there_is_room():
    assert describe_parking(PARKING) == "Gravel parking area, room for 7 cars."


def test_a_single_space_is_not_pluralised():
    assert describe_parking({**PARKING, "Parking_S": 1}) == "Gravel parking area, room for 1 car."


def test_accessible_spaces_are_named_separately_when_atc_counted_any():
    assert describe_parking({**PARKING, "ADA_Space": 2}) == "Gravel parking area, room for 7 cars and 2 accessible spaces."


def test_a_wide_spot_on_the_shoulder_is_not_called_a_parking_area():
    """`Roadside/Shoulder` is on 53 features and is not in ATC's own coded
    domain for the field - it is still the one `Type` value worth saying,
    because arriving at a shoulder in the dark is a different thing from
    arriving at a lot."""
    assert describe_parking({**PARKING, "Type": "Roadside/Shoulder"}) == "Roadside parking, room for 7 cars."


def test_an_unrecognised_surface_shortens_the_sentence_rather_than_guessing():
    assert describe_parking({**PARKING, "Surface": "Unknown"}) == "Parking area, room for 7 cars."


def test_a_parking_area_atc_states_nothing_about_gets_no_description():
    assert describe_parking({"Type": "Unknown", "Surface": "Unknown"}) is None


def test_a_privy_names_the_type_because_it_changes_how_it_is_used():
    assert describe_privy(PRIVY) == "Moldering privy. Built 2003."


def test_a_multi_seat_privy_says_so():
    assert describe_privy({**PRIVY, "Enclosure": "2"}) == "Multi-seat moldering privy. Built 2003."


def test_a_privy_with_no_building_round_it_says_so_in_plain_words():
    """ATC's own term for this is "chum", which is trail vocabulary rather
    than English, and 8 of the 316 are one."""
    assert describe_privy({**PRIVY, "Enclosure": "0"}) == ("Moldering privy, open to the air with no enclosure. Built 2003.")


def test_an_unrecognised_privy_type_still_describes_the_privy():
    """One feature reads `Cool Composting`, which is not in ATC's domain.
    Mapping it onto a code would be this pipeline guessing at somebody's data
    entry."""
    assert describe_privy({**PRIVY, "Type": "Cool Composting"}) == "Privy. Built 2003."


def test_a_privy_atc_states_nothing_about_gets_no_description():
    assert describe_privy({"Type": "5", "Enclosure": "3"}) is None


# --- what an anchor says about its parts (#614) -----------------------------
#
# (poi_type, metres, ATC attributes) per member, which is the shape
# export_poi.attach_descriptions builds from the site properties.

MULTI_SEAT_PRIVY = ("privy", 41.7, {"Type": "1", "Enclosure": "2"})
GROUP_CAMPSITE = ("campsite", 25.4, {"Type": "1", "Site_Num": 6, "Tent_Pads": 8})
WATER = ("water", 89.6, {})


def test_an_anchor_names_its_parts_and_how_far_each_one_is():
    assert nearby_clause([GROUP_CAMPSITE, WATER, MULTI_SEAT_PRIVY]) == (
        " Nearby: a multi-seat moldering privy 42 m away, water 90 m and a group campsite 25 m."
    )


def test_the_parts_are_a_sentence_of_their_own_and_not_something_the_shelter_has():
    """The whole point of the clause. "with a fireplace, a fire ring and a
    porch" lists what the shelter HAS; a privy and a water source are separate
    points a short walk away, and putting them in that list would have this
    pipeline assert something ATC's data does not say."""
    sentence = describe_shelter(CABIN, capacity=14, nearby=nearby_clause([MULTI_SEAT_PRIVY, WATER]))

    assert sentence == (
        "Two-storey clapboard shelter, sleeps 14, with a fireplace, a fire ring and a porch. Built 1915."
        " Nearby: a multi-seat moldering privy 42 m away and water 90 m."
    )
    # Said as an assertion rather than left to the string above, because it is
    # the one property of this clause that is not a formatting choice.
    with_clause, _, parts = sentence.partition(". Built")
    assert "privy" not in with_clause and "water" not in with_clause


def test_a_poi_in_no_site_composes_exactly_the_sentence_it_did_before():
    """Every POI that is not an anchor takes this path, which is most of them -
    719 of the corridor's points carry site properties and the rest do not. A
    byte of drift here would rewrite artifacts for nothing, and
    verify_release.py compares hashes."""
    assert describe_shelter(CABIN, capacity=14, nearby=nearby_clause([])) == describe_shelter(CABIN, capacity=14)
    assert describe_campsite(CAMPSITE, nearby=nearby_clause([])) == describe_campsite(CAMPSITE)


def test_away_is_said_once_and_carried_across_the_list():
    """Three of them in a row reads as a sentence explaining its own grammar,
    and "Nearby" has already said it."""
    assert nearby_clause([MULTI_SEAT_PRIVY, WATER, GROUP_CAMPSITE]).count(" away") == 1


def test_one_part_still_says_away():
    assert nearby_clause([MULTI_SEAT_PRIVY]) == " Nearby: a multi-seat moldering privy 42 m away."


def test_the_parts_are_ordered_the_way_the_pin_and_the_chips_order_them():
    """NEARBY_ORDER, not nearest-first: features/POI_SITES.md's framing of the
    question is "is there a privy, and is there water", and the client's
    SITE_MEMBER_TYPES fixes the same order for the pin's footer glyphs. The
    campsite here is the NEAREST of the three and is named last."""
    assert NEARBY_ORDER == ("privy", "water", "campsite")

    named = nearby_clause([GROUP_CAMPSITE, WATER, MULTI_SEAT_PRIVY])
    assert named.index("privy") < named.index("water") < named.index("campsite")


def test_two_parts_of_one_type_come_out_nearest_first():
    """ "Backpacker Campsite Upper Privy" and "...Lower Privy" are two real
    privies at one campsite (features/POI_SITES.md open question 4). Which is
    nearer is the only thing telling them apart that a hiker standing at the
    anchor can act on."""
    far = ("privy", 80.0, {"Type": "3"})
    near = ("privy", 20.0, {"Type": "1"})

    assert nearby_clause([far, near]) == " Nearby: a moldering privy 20 m away and a pit privy 80 m."


def test_a_part_carries_the_adjectives_that_tell_one_from_another():
    """The same facts describe_privy argues for: the type, because a moldering
    privy is used differently from a pit one, and the missing enclosure,
    because 8 of the 316 have none."""
    assert "a multi-seat moldering privy" in nearby_clause([MULTI_SEAT_PRIVY])
    assert "a pit privy" in nearby_clause([("privy", 30.0, {"Type": "3"})])
    assert "a moldering privy with no enclosure" in nearby_clause([("privy", 30.0, {"Type": "1", "Enclosure": "0"})])


def test_a_part_does_not_carry_its_own_whole_card():
    """The counts are on the campsite, whose sentence has room for them. Here
    they would land a number directly against the distance - "a campsite with 8
    tent pads 25 m" - which is two figures with nothing between them. Group or
    not is the fact a party of six acts on."""
    assert nearby_clause([GROUP_CAMPSITE]) == " Nearby: a group campsite 25 m away."
    assert nearby_clause([("campsite", 25.4, {"Type": "0", "Site_Num": 3})]) == " Nearby: a campsite 25 m away."
    # And no build year, which is a fact about the privy, read on the privy.
    assert "2003" not in nearby_clause([("privy", 30.0, {**PRIVY})])


def test_water_composes_from_nothing_because_there_is_nothing_to_compose_from():
    """It is opentrail.org's, not ATC's, so it arrives with no inventory
    columns at all - and its own free-text title stays off the sentence for the
    reason every unrecognised value does."""
    assert nearby_clause([WATER]) == " Nearby: water 90 m away."


def test_a_member_type_this_release_has_no_phrase_for_is_still_named():
    """A fallback rather than a skip: a type a later release publishes would
    otherwise vanish from the only sentence that mentions it, which is the bug
    this clause exists to fix, reintroduced by the code that fixed it."""
    assert nearby_clause([("crossing", 30.0, {})]) == " Nearby: a crossing 30 m away."


def test_a_distance_is_whole_metres_and_never_zero():
    """Whole metres for the reason the view arc is rounded to 5°, and rounded
    the way #526's chip rounds it so one pair cannot print two numbers. "0 m
    away" would read as a bug rather than as two survey points sharing a
    coordinate, which is what it would be."""
    assert "42 m" in nearby_clause([("privy", 41.7, {})])
    assert "1 m away" in nearby_clause([("privy", 0.3, {})])


def test_the_parts_come_before_atcs_own_words():
    """The note is a person's prose and stays last, where the attribution reads
    as covering it and nothing else. A composed clause trailing "ATC notes:
    ..." would read as part of what ATC wrote."""
    sentence = describe_shelter(CABIN, capacity=14, note="Bear cables installed 2021", nearby=nearby_clause([WATER]))

    assert sentence.index("Nearby:") < sentence.index("ATC notes:")
    assert sentence.endswith("Nearby: water 90 m away. ATC notes: Bear cables installed 2021.")


def test_a_campsite_anchors_a_site_of_its_own_and_names_its_parts():
    """A campsite is in both of lib/poi_sites.py's tuples - a member of a
    shelter's site, and the anchor of its own where there is no shelter. 41 of
    the corridor's 291 sites are campsite-anchored."""
    assert describe_campsite(CAMPSITE, nearby=nearby_clause([MULTI_SEAT_PRIVY])) == (
        "Designated campsite, 3 sites, with bear-proof food storage. Nearby: a multi-seat moldering privy 42 m away."
    )


# --- water points (#529, fetch_osm_water.py) --------------------------------


def test_describe_water_names_what_was_mapped():
    assert describe_water({"kind": "spring"}) == "Spring. Mapped by OpenStreetMap contributors."
    assert describe_water({"kind": "water_tap"}) == "Water tap. Mapped by OpenStreetMap contributors."


def test_describe_water_carries_the_reliability_tags_only_where_they_exist():
    """The census measured `seasonal` on zero features trail-wide - absence
    is the normal state and composes NOTHING. 'Flows year-round' from a tag
    nobody set would be the pipeline strengthening silence into a promise."""
    assert (
        describe_water({"kind": "spring", "intermittent": "yes"})
        == "Spring, mapped as intermittent. Mapped by OpenStreetMap contributors."
    )
    assert (
        describe_water({"kind": "spring", "seasonal": "spring;summer"})
        == "Spring, mapped as seasonal. Mapped by OpenStreetMap contributors."
    )
    assert describe_water({"kind": "spring", "seasonal": "no"}) == "Spring. Mapped by OpenStreetMap contributors."


def test_describe_water_gives_not_drinking_water_its_own_sentence():
    assert (
        describe_water({"kind": "drinking_water", "drinking_water": "no"})
        == "Drinking water point. Marked not drinking water. Mapped by OpenStreetMap contributors."
    )


def test_describe_water_composes_nothing_for_a_point_with_no_facts():
    """opentrail's water points carry an icon and a title - no `kind`, no
    tags - and compose None, exactly the sentence they had before the water
    describer existed. An unrecognised kind rounds the same direction every
    unrecognised ATC code does: shorter, never guessed."""
    assert describe_water({"icon": "w", "title": "Piped spring"}) is None
    assert describe_water({"kind": "holy_well"}) is None


# --- the stream sentence (#529, build_nhd_streams.py) -----------------------


def test_stream_sentence_names_the_stream_and_qualifies_the_flow_claim():
    assert (
        stream_sentence(72, "perennial", "Stony Brook")
        == "Nearest mapped stream: Stony Brook, about 70 m (USGS; mapped as year-round, not recently verified)."
    )


def test_stream_sentence_calls_intermittent_and_ephemeral_seasonal():
    assert (
        stream_sentence(307, "intermittent", None)
        == "Nearest mapped stream about 300 m (USGS; mapped as seasonal, not recently verified)."
    )
    assert (
        stream_sentence(307, "ephemeral", None)
        == "Nearest mapped stream about 300 m (USGS; mapped as seasonal, not recently verified)."
    )


def test_stream_sentence_makes_no_flow_claim_for_an_unclassified_reach():
    """46000 is a stream USGS never classified - the sentence says where it
    is and stops, rather than hedging a claim nobody made."""
    assert stream_sentence(140, "unclassified", "Matts Creek") == "Nearest mapped stream: Matts Creek, about 150 m (USGS)."


def test_stream_sentence_rounds_coarsely_and_floors_at_ten():
    """'About 707 m' would dress an envelope query against survey-era
    geometry as a measurement; 'about 0 m' would read as a bug."""
    assert "about 10 m" in stream_sentence(2, "perennial", None)
    assert "about 70 m" in stream_sentence(72, "perennial", None)
    assert "about 700 m" in stream_sentence(707, "perennial", None)


def test_stream_sentence_prints_the_no_stream_fact():
    """Blood Mountain's sentence: a dry ridge is a fact a hiker plans an
    evening around, and silence would read as the app not knowing."""
    assert stream_sentence(None, None, None) == "No mapped stream within 1 km (USGS)."
