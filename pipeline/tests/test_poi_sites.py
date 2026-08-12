"""The site-grouping rule (#523, lib/poi_sites.py, features/POI_SITES.md).

A shelter, its privy and its campsites are one place with parts. What is worth
testing here is the RULE - which pairs it makes, which it refuses, and which it
prefers when two are available - because a wrong grouping is baked into the
artifacts and a hiker cannot undo it.

Every fixture name and distance below is a real shape from the ATC corridor
rather than an invented one, and the cases that exist because a measurement said
so carry the measurement.
"""

import pytest

from lib.poi_sites import (
    NAME_MATCH_RADIUS_M,
    PROXIMITY_RADIUS_M,
    ROLE_ANCHOR,
    ROLE_MEMBER,
    base_name,
    group_sites,
    normalise_name,
    site_properties,
)

# A degree of latitude is ~111.32 km, so this converts a metre offset into one.
# Latitude rather than longitude on purpose: no cos() correction to get wrong,
# which keeps the fixtures' distances readable as the numbers they are.
DEGREE_PER_METRE = 1 / 111_320.0


def poi(poi_id, poi_type, name, *, north_of=0.0, lat=41.0, lon=-73.95):
    """One unified POI record, `north_of` metres north of the base latitude."""
    return {
        "id": poi_id,
        "poi_type": poi_type,
        "name": name,
        "lat": lat + north_of * DEGREE_PER_METRE,
        "lon": lon,
    }


class TestNormalisation:
    """What a child's name reduces to, and why each step is there.

    The design doc named three suspected causes of the unresolved tail. Measured
    against all 828 corridor points, one was real and two were not - these pin
    which is which so the dead ones are not re-added on intuition.
    """

    def test_punctuation_becomes_space_rather_than_disappearing(self):
        # Deleting it would run words together: "Mt.Algo" matches nothing.
        assert normalise_name("Mt. Algo Shelter") == "mt algo shelter"

    def test_lean_to_needs_no_special_handling(self):
        # POI_SITES.md suspected "Lean-to" vs "Lean to" of costing matches.
        # Punctuation is already collapsed to spaces before the type-word list
        # is consulted, so both spell the same thing and the folding code that
        # was written for this measured at exactly zero.
        assert normalise_name("Hurd Brook Lean-to") == normalise_name("Hurd Brook Lean to")

    def test_the_trailing_type_word_comes_off(self):
        assert base_name("Mt. Algo Shelter Privy") == "mt algo"

    def test_a_sibling_number_comes_off_too(self):
        # 53 of the 828 corridor names end in one, and stripping them is the
        # single biggest win measured: privies matched go from 86% to 89%.
        assert base_name("Mt. Wilcox South Shelter 2") == "mt wilcox south"
        assert base_name("Bald Mtn Brook Lean-to Privy 2") == "bald mtn brook lean to"

    def test_a_plural_parent_comes_off(self):
        # ATC names a campsite after a PAIR of shelters. Worth two campsites and
        # one site over the corridor - small, and the only one of eight extra
        # type words that bought anything at all.
        assert base_name("Tumbling Run Shelters Campsite") == "tumbling run"

    def test_a_group_suffix_comes_off(self):
        # Worth four privies and seven campsites - the largest gain after the
        # digits, and one POI_SITES.md did not predict.
        assert base_name("Eckville Shelter Group Campsite") == "eckville"
        assert base_name("Osgood Tentsite Group Campsite") == "osgood tentsite"

    def test_a_name_that_is_only_type_words_reduces_to_nothing(self):
        # And must therefore match nothing rather than everything, which is what
        # the empty-key guard in the index is for.
        assert base_name("Privy") == ""
        assert base_name(None) == ""


class TestTheTwoGates:
    """Name agreement within 150 m, or distance alone within 60 m. Neither
    gate on its own - the pair is the whole rule."""

    def test_a_named_child_joins_its_parent_beyond_the_distance_gate(self):
        # 100 m apart: too far for proximity alone, well inside the name gate.
        # This is the ordinary case - a privy sits a median 42 m from its
        # shelter and 98% are within 100 m.
        shelter = poi("s1", "shelter", "Mt. Algo Shelter")
        privy = poi("p1", "privy", "Mt. Algo Shelter Privy", north_of=100)

        [site] = group_sites([shelter, privy])

        assert site.anchor["id"] == "s1"
        assert [m["id"] for m in site.members] == ["p1"]

    def test_an_unnamed_neighbour_joins_on_distance_alone(self):
        # No naming evidence at all, so only the tight gate applies.
        shelter = poi("s1", "shelter", "Mt. Algo Shelter")
        privy = poi("p1", "privy", "Unnamed Privy", north_of=30)

        [site] = group_sites([shelter, privy])

        assert [m["id"] for m in site.members] == ["p1"]

    def test_a_far_neighbour_with_no_name_agreement_stays_its_own_pin(self):
        shelter = poi("s1", "shelter", "Mt. Algo Shelter")
        privy = poi("p1", "privy", "Somewhere Else Privy", north_of=PROXIMITY_RADIUS_M + 10)

        assert group_sites([shelter, privy]) == []

    def test_a_matching_name_too_far_away_is_refused(self):
        # THE CASE A NAME-ONLY RULE SHIPS. Measured with the naive matcher, the
        # worst same-name pair on the corridor is 903 km apart - a generic
        # campsite name colliding with a same-named place at the other end of
        # the trail. The name gate is loose, not absent.
        shelter = poi("s1", "shelter", "Sawmill Shelter")
        privy = poi("p1", "privy", "Sawmill Shelter Privy", north_of=NAME_MATCH_RADIUS_M + 10)

        assert group_sites([shelter, privy]) == []

    def test_name_evidence_wins_over_a_closer_stranger(self):
        # Both gates open, pointing at different anchors. The name is the
        # better signal and has to win, or a privy ends up on whichever
        # shelter happens to be nearer.
        named = poi("s1", "shelter", "Mt. Algo Shelter", north_of=100)
        nearer = poi("s2", "shelter", "Other Shelter", north_of=-20)
        privy = poi("p1", "privy", "Mt. Algo Shelter Privy")

        sites = {s.anchor["id"]: s for s in group_sites([named, nearer, privy])}

        assert [m["id"] for m in sites["s1"].members] == ["p1"]
        assert "s2" not in sites

    def test_the_anchor_a_child_is_named_after_beats_one_that_merely_reduces_alike(self):
        # THE TIE-BREAK THE CORRIDOR ASKED FOR. Stripping `group` makes "Laurel
        # Ridge Campsite" and "Laurel Ridge Group Campsite" reduce to the same
        # base, so "Laurel Ridge Campsite Privy" matches both - and nearest-wins
        # picked the group site, 10 m closer and not what the privy is called.
        named = poi("c1", "campsite", "Laurel Ridge Campsite", north_of=49)
        nearer = poi("c2", "campsite", "Laurel Ridge Group Campsite", north_of=39)
        privy = poi("p1", "privy", "Laurel Ridge Campsite Privy")

        sites = {s.anchor["id"]: s for s in group_sites([named, nearer, privy])}

        assert [m["id"] for m in sites["c1"].members] == ["p1"]


class TestMembership:
    """Which types may anchor, which may ride, and which are neither."""

    @pytest.mark.parametrize("poi_type", ["viewpoint", "parking", "resupply"])
    def test_the_excluded_types_never_join_a_site(self, poi_type):
        # THE CONSTRAINT THAT RULES OUT GROUPING BY DISTANCE ALONE. At 60 m the
        # corridor holds 64 viewpoint+viewpoint clusters: two overlooks that
        # close are two overlooks, not one place with parts. `parking +
        # resupply` (26 clusters) is a trailhead - a different feature with a
        # different card, and out of v1 (POI_SITES.md open question 2).
        shelter = poi("s1", "shelter", "Mt. Algo Shelter")
        other = poi("x1", poi_type, "Mt. Algo Shelter Overlook", north_of=20)

        assert group_sites([shelter, other]) == []

    def test_two_viewpoints_at_one_spot_stay_two_pins(self):
        assert group_sites([poi("v1", "viewpoint", "The Lookout"), poi("v2", "viewpoint", "The Lookout", north_of=10)]) == []

    def test_water_rides_a_shelter(self):
        # Rare in the data - only 9 water points fold over the whole corridor,
        # because ATC's shelter layer has no water field and every water point
        # the app has comes from opentrail.org (174 for 2,197 miles). The
        # sourcing gap is #529; the rule still has to carry the type.
        shelter = poi("s1", "shelter", "Mt. Algo Shelter")
        water = poi("w1", "water", "Spring", north_of=40)

        [site] = group_sites([shelter, water])

        assert [m["id"] for m in site.members] == ["w1"]

    def test_a_shelter_never_becomes_a_member_of_another_shelter(self):
        # Horns Pond has two lean-tos ~40 m apart and is genuinely one place.
        # v1 keeps one anchor per site and lets the second shelter keep its own
        # pin - safe, and slightly wrong there (POI_SITES.md open question 1).
        first = poi("s1", "shelter", "Horns Pond Lean-to Shelter 1")
        second = poi("s2", "shelter", "Horns Pond Lean-to Shelter 2", north_of=40)

        assert group_sites([first, second]) == []

    def test_a_lone_anchor_is_not_a_site(self):
        # Writing site properties onto it would tell the client to render a
        # composition of one.
        assert group_sites([poi("s1", "shelter", "Mt. Algo Shelter")]) == []


class TestAnchorPriority:
    """`shelter` first, then `campsite` - and exactly one anchor per site."""

    def test_a_shelter_outranks_a_campsite_for_the_same_privy(self):
        shelter = poi("s1", "shelter", "Imp Shelter", north_of=50)
        campsite = poi("c1", "campsite", "Imp Shelter Campsite", north_of=20)
        privy = poi("p1", "privy", "Imp Shelter Privy")

        sites = {s.anchor["id"]: s for s in group_sites([shelter, campsite, privy])}

        # One site, anchored on the shelter, with both the campsite and the
        # privy riding it - which is the corridor's second most common shape
        # (113 sites are shelter + campsite + privy).
        assert list(sites) == ["s1"]
        assert sorted(m["id"] for m in sites["s1"].members) == ["c1", "p1"]

    def test_a_campsite_no_shelter_claimed_anchors_its_own_site(self):
        # 41 of the corridor's 291 sites are campsite-anchored.
        campsite = poi("c1", "campsite", "Crystal Mtn Campsite")
        privy = poi("p1", "privy", "Crystal Mtn Campsite Privy", north_of=42)

        [site] = group_sites([campsite, privy])

        assert site.anchor["id"] == "c1"
        assert [m["id"] for m in site.members] == ["p1"]

    def test_a_campsite_that_is_already_a_member_cannot_anchor(self):
        # A part of a place cannot hold parts of its own, or the same privy
        # ends up claimed twice and `site_id` stops being one answer.
        shelter = poi("s1", "shelter", "Imp Shelter")
        campsite = poi("c1", "campsite", "Imp Shelter Campsite", north_of=30)
        privy = poi("p1", "privy", "Imp Shelter Campsite Privy", north_of=45)

        sites = group_sites([shelter, campsite, privy])

        assert [s.anchor["id"] for s in sites] == ["s1"]
        assert sorted(m["id"] for m in sites[0].members) == ["c1", "p1"]


class TestPublishedProperties:
    def test_every_anchor_and_member_carries_the_three_properties(self):
        shelter = poi("s1", "shelter", "Mt. Algo Shelter")
        privy = poi("p1", "privy", "Mt. Algo Shelter Privy", north_of=42)

        properties = site_properties(group_sites([shelter, privy]))

        assert properties["s1"] == {
            "site_id": "s1",
            "site_role": ROLE_ANCHOR,
            "site_name": "Mt. Algo Shelter",
        }
        assert properties["p1"] == {
            "site_id": "s1",
            "site_role": ROLE_MEMBER,
            "site_name": "Mt. Algo Shelter",
        }

    def test_a_poi_in_no_site_appears_nowhere(self):
        # export_poi.py writes NULL for it, which is most POIs - and is what
        # keeps these properties additive.
        alone = poi("v1", "viewpoint", "The Lookout")

        assert site_properties(group_sites([alone])) == {}

    def test_the_site_id_is_the_anchors_own_poi_id(self):
        # Never a minted one: a site is what a report or a closure references,
        # and unify_poi already made this id stable across runs.
        shelter = poi("atc_shelters:abc", "shelter", "Mt. Algo Shelter")
        privy = poi("atc_privies:def", "privy", "Mt. Algo Shelter Privy", north_of=42)

        [site] = group_sites([shelter, privy])

        assert site.site_id == "atc_shelters:abc"


class TestStability:
    def test_the_result_does_not_depend_on_input_order(self):
        # verify_release.py compares hashes, so an order-dependent grouping
        # would rewrite every POI artifact on a run that changed nothing.
        records = [
            poi("s1", "shelter", "Imp Shelter"),
            poi("c1", "campsite", "Imp Shelter Campsite", north_of=30),
            poi("p1", "privy", "Imp Shelter Privy", north_of=45),
            poi("s2", "shelter", "Crystal Mtn Shelter", lat=42.0),
            poi("p2", "privy", "Crystal Mtn Shelter Privy", north_of=40, lat=42.0),
        ]

        forwards = site_properties(group_sites(records))
        backwards = site_properties(group_sites(list(reversed(records))))

        assert forwards == backwards

    def test_members_of_a_site_are_in_a_fixed_order(self):
        records = [
            poi("s1", "shelter", "Imp Shelter"),
            poi("p2", "privy", "Imp Shelter Privy 2", north_of=45),
            poi("p1", "privy", "Imp Shelter Privy 1", north_of=40),
        ]

        [site] = group_sites(records)
        [reversed_site] = group_sites(list(reversed(records)))

        assert [m["id"] for m in site.members] == [m["id"] for m in reversed_site.members]
