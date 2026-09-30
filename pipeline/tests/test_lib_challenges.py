"""A club's challenge, resolved against published data.

#1780 - Let a club publish a challenge - places on its own trails that
hikers opt into and tag at camp - starting with the ATC's A.T. Summer
Bucket List.

What is worth asserting here is almost entirely about REFUSAL, as in
test_lib_highlights.py. The judgement - which line of a club's list is which
place - lives in reference/challenges/ and is reviewed by reading it. What
lib/challenges.py can get wrong is publishing a place nobody placed, a
place on somebody else's trail, a finish line nobody can reach, or a sealed
title in the clear.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from lib.challenges import (
    DEFAULT_RADIUS_M,
    MAX_RADIUS_M,
    MIN_RADIUS_M,
    haversine_m,
    resolve,
    resolve_challenge,
    trail_distance_index,
    unseal,
)

TODAY = date(2026, 9, 30)

#: The scope publishers.json would give: the ATC on the A.T., and a second
#: organization on a second trail, so "a trail that is not yours" has
#: somewhere real to point.
ORG_TRAILS = {"atc": {"AT"}, "nynjtc": {"LP"}}

#: The types export_challenges.build_output would pass: the ones a published
#: POI actually carries. `trailhead` is declared in POI_TYPES and absent here.
PUBLISHED_TYPES = ("shelter", "resupply", "viewpoint")


def poi(poi_id: str, **overrides) -> dict:
    base = {
        "id": poi_id,
        "trail_id": "AT",
        "poi_type": "viewpoint",
        "name": "McAfee Knob Summit",
        "mile": 714.92,
        "lat": 37.39,
        "lon": -80.03,
    }
    base.update(overrides)
    return base


POIS = {
    p["id"]: p
    for p in (
        poi("atc_viewpoints:knob"),
        poi("atc_viewpoints:tooth", name="Dragons Tooth Peak", mile=700.1, lat=37.38, lon=-80.16),
        poi("atc_viewpoints:tinker", name="Tinker Cliffs 2", mile=725.0, lat=37.45, lon=-79.99),
        poi("atc_shelters:priest", poi_type="shelter", name="The Priest Shelter", mile=830.0, lat=37.82, lon=-79.07),
        poi("atc_communities:monson", poi_type="resupply", name="Monson", mile=2078.0, lat=45.29, lon=-69.50),
        poi("lp_viewpoints:elsewhere", trail_id="LP", name="Somewhere on the Long Path"),
        poi("atc_viewpoints:unmiled", mile=None),
        poi("atc_viewpoints:unplaced", lat=None),
        poi("atc_parking:knob", poi_type="parking", name="McAfee Knob Parking"),
    )
}


def on_the_trail(lon: float, lat: float) -> float:
    """A distance function that puts every point 5 m off the centerline."""
    return 5.0


def at(metres: float):
    return lambda lon, lat: metres


def item(**overrides) -> dict:
    base = {
        "id": "mcafee-knob",
        "section": "experience",
        "title": "Hike to McAfee Knob.",
        "match": {"kind": "place", "poi": "atc_viewpoints:knob"},
    }
    base.update(overrides)
    return base


def challenge(**overrides) -> dict:
    base = {
        "id": "summer-list",
        "org": "atc",
        "trail": "AT",
        "name": "Summer List",
        "status": "draft",
        "window": {"opens": "2027-05-15", "closes": "2027-09-01"},
        "finish": None,
        "reward": None,
        "sections": [
            {"id": "experience", "title": "Experience the A.T.", "short": "Anywhere"},
            {"id": "mystery", "title": "Mystery Items", "short": "Mystery"},
        ],
        "items": [item()],
        "reviewed": "2026-09-30",
    }
    base.update(overrides)
    return base


def run(raw, *, distance=on_the_trail, today=TODAY, org_trails=ORG_TRAILS):
    return resolve_challenge(
        raw,
        org_trails=org_trails,
        poi_types=PUBLISHED_TYPES,
        pois=POIS,
        trail_distance_m=distance,
        today=today,
    )


def one_item(match_or_item: dict, **kwargs) -> tuple[dict | None, str]:
    """(the published item, "") or (None, why it dropped), for a challenge
    holding that one item and nothing else."""
    raw_item = match_or_item if "id" in match_or_item else item(match=match_or_item)
    record, dropped, why = run(challenge(items=[raw_item]), **kwargs)
    assert why == "", f"the challenge itself dropped: {why}"
    if dropped:
        return None, dropped[0][1]
    return record["items"][0], ""


class TestScopedToThePublisher:
    """Design principle 5: a challenge can only use places on trails its
    organization publishes."""

    def test_an_organization_publishers_json_does_not_list_is_refused(self):
        record, _, why = run(challenge(org="gatc"))
        assert record is None
        assert "'gatc' is not a known organization" in why

    def test_a_trail_the_organization_does_not_publish_is_refused(self):
        # The ATC putting a challenge on the Long Path: a real trail, a real
        # organization, and not the ATC's to put a list on.
        record, _, why = run(challenge(trail="LP"))
        assert record is None
        assert "'LP' is not one 'atc' publishes" in why

    def test_a_poi_on_another_trail_is_refused_even_when_it_is_published(self):
        _, why = one_item({"kind": "place", "poi": "lp_viewpoints:elsewhere"})
        assert "on trail 'LP', not 'AT'" in why

    def test_a_malformed_org_drops_the_file_rather_than_crashing_the_job(self):
        # A list where a string belongs is unhashable; before the isinstance
        # guard this raised TypeError out of a dict lookup and would have
        # failed the whole trail publish over one reviewed file.
        record, _, why = run(challenge(org=["atc"]))
        assert record is None
        assert "not a known organization" in why


class TestAPlace:
    def test_carries_the_published_records_own_mile_name_and_coordinate(self):
        # Items name ids, never numbers: what the phone matches against is
        # the figure every other screen already shows.
        published, why = one_item({"kind": "place", "poi": "atc_viewpoints:knob"})
        assert why == ""
        assert published["match"] == {
            "kind": "place",
            "radius_m": DEFAULT_RADIUS_M["place"],
            "off_trail": False,
            "places": [
                {
                    "poi": "atc_viewpoints:knob",
                    "name": "McAfee Knob Summit",
                    "poi_type": "viewpoint",
                    "mile": 714.92,
                    "lat": 37.39,
                    "lon": -80.03,
                }
            ],
        }

    def test_a_poi_that_is_not_published_is_refused(self):
        # Gone upstream or mistyped - either way guessing where it was is what
        # this module exists not to do.
        _, why = one_item({"kind": "place", "poi": "atc_viewpoints:gone"})
        assert "not in the published POIs" in why

    def test_a_poi_with_no_published_mile_is_refused(self):
        _, why = one_item({"kind": "place", "poi": "atc_viewpoints:unmiled"})
        assert "no published mile" in why

    def test_a_poi_with_no_coordinate_is_refused(self):
        _, why = one_item({"kind": "place", "poi": "atc_viewpoints:unplaced"})
        assert "no coordinate" in why

    def test_a_place_farther_from_the_trail_than_its_radius_is_refused(self):
        # attach_miles gives any point an A.T. mile, so the mile proves
        # nothing about distance; this check is the one that does.
        _, why = one_item({"kind": "place", "poi": "atc_viewpoints:knob", "radius_m": 150}, distance=at(236.0))
        assert "236 m from the trail, past its 150 m radius" in why
        assert "off_trail" in why

    def test_the_same_place_publishes_when_the_file_says_it_is_off_the_trail(self):
        # The Harpers Ferry community point is 236 m out and Monson's
        # 2,867 m (measured 2026-09-30, release 2026-09-24-2). Towns are
        # real places to tag; the file has to say reaching one means leaving
        # the trail.
        published, why = one_item(
            {"kind": "place", "poi": "atc_communities:monson", "radius_m": 800, "off_trail": True},
            distance=at(2867.0),
        )
        assert why == ""
        assert published["match"]["off_trail"] is True
        assert published["match"]["radius_m"] == 800

    def test_a_place_inside_its_radius_publishes(self):
        published, _ = one_item({"kind": "place", "poi": "atc_viewpoints:knob", "radius_m": 150}, distance=at(149.0))
        assert published is not None

    def test_with_no_centerline_the_distance_check_is_not_made(self):
        # The exporter's absent-trails.geojson path, which it announces; the
        # resolver's half is only that None means "not measured", never
        # "infinitely far".
        published, _ = one_item({"kind": "place", "poi": "atc_viewpoints:knob"}, distance=None)
        assert published is not None

    @pytest.mark.parametrize("radius", [MIN_RADIUS_M - 1, MAX_RADIUS_M + 1, 0, -150])
    def test_a_radius_outside_the_bounds_is_refused(self, radius):
        _, why = one_item({"kind": "place", "poi": "atc_viewpoints:knob", "radius_m": radius})
        assert "outside" in why

    @pytest.mark.parametrize("radius", [MIN_RADIUS_M, MAX_RADIUS_M])
    def test_the_bounds_themselves_are_allowed(self, radius):
        published, why = one_item({"kind": "place", "poi": "atc_viewpoints:knob", "radius_m": radius}, distance=at(1.0))
        assert why == ""
        assert published["match"]["radius_m"] == radius

    @pytest.mark.parametrize("radius", ["150", True, None])
    def test_a_radius_that_is_not_a_number_is_refused(self, radius):
        _, why = one_item({"kind": "place", "poi": "atc_viewpoints:knob", "radius_m": radius})
        assert "not a number" in why


class TestPlacesAll:
    def test_publishes_every_place_when_every_one_resolves(self):
        published, why = one_item(
            {"kind": "places_all", "pois": ["atc_viewpoints:tooth", "atc_viewpoints:knob", "atc_viewpoints:tinker"]}
        )
        assert why == ""
        assert [p["name"] for p in published["match"]["places"]] == [
            "Dragons Tooth Peak",
            "McAfee Knob Summit",
            "Tinker Cliffs 2",
        ]

    def test_is_all_or_nothing(self):
        # Virginia's Triple Crown with one of three peaks missing is a
        # different item, and publishing it as the same one would let a
        # hiker finish something the club never set.
        _, why = one_item({"kind": "places_all", "pois": ["atc_viewpoints:tooth", "atc_viewpoints:knob", "atc_viewpoints:gone"]})
        assert "atc_viewpoints:gone" in why

    def test_one_place_off_the_trail_refuses_the_whole_item(self):
        def far_from_tinker(lon, lat):
            return 400.0 if (lon, lat) == (-79.99, 37.45) else 5.0

        _, why = one_item(
            {"kind": "places_all", "pois": ["atc_viewpoints:tooth", "atc_viewpoints:tinker"]},
            distance=far_from_tinker,
        )
        assert "atc_viewpoints:tinker is 400 m from the trail" in why

    @pytest.mark.parametrize("pois", [["atc_viewpoints:knob"], [], "atc_viewpoints:knob"])
    def test_needs_at_least_two_places(self, pois):
        _, why = one_item({"kind": "places_all", "pois": pois})
        assert "fewer than two" in why

    def test_the_same_place_twice_is_refused(self):
        _, why = one_item({"kind": "places_all", "pois": ["atc_viewpoints:knob", "atc_viewpoints:knob"]})
        assert "same poi twice" in why


class TestTheOtherMatchKinds:
    def test_poi_type_takes_the_default_any_shelter_radius(self):
        published, why = one_item({"kind": "poi_type", "type": "shelter"})
        assert why == ""
        assert published["match"] == {"kind": "poi_type", "type": "shelter", "radius_m": 60}

    @pytest.mark.parametrize("poi_type", ["trailhead", "crossing", "fire_tower", None])
    def test_poi_type_must_be_a_type_that_is_published(self, poi_type):
        # `trailhead` is declared and empty; `crossing` was withdrawn (lib/poi_schema.py's WITHDRAWN_POI_TYPES);
        # "tag any fire tower" names a layer nobody publishes. None of them
        # could ever be tagged.
        _, why = one_item({"kind": "poi_type", "type": poi_type})
        assert "not a published type" in why

    def test_elevation_publishes_its_value(self):
        published, _ = one_item({"kind": "elevation_min_ft", "value": 4000})
        assert published["match"] == {"kind": "elevation_min_ft", "value": 4000.0}

    @pytest.mark.parametrize("value", [0, -10, True, "4000", None])
    def test_elevation_needs_a_positive_number(self, value):
        _, why = one_item({"kind": "elevation_min_ft", "value": value})
        assert "positive value" in why

    def test_a_walked_section_takes_its_ends_from_published_pois_and_orders_them(self):
        # Written from the northern end first; the published range still runs
        # low to high, with each end's name beside its own mile.
        published, why = one_item(
            {"kind": "section_walked", "from_poi": "atc_viewpoints:tinker", "to_poi": "atc_viewpoints:tooth"}
        )
        assert why == ""
        assert published["match"] == {
            "kind": "section_walked",
            "trail": "AT",
            "from_mile": 700.1,
            "to_mile": 725.0,
            "from_name": "Dragons Tooth Peak",
            "to_name": "Tinker Cliffs 2",
            "min_fraction": 0.9,
        }

    def test_a_walked_section_with_a_typed_mile_instead_of_a_poi_is_refused(self):
        # A guidebook figure presented as a measurement - the thing
        # lib/highlights.py refuses for the same reason.
        _, why = one_item({"kind": "section_walked", "from_mile": 700.1, "to_poi": "atc_viewpoints:tinker"})
        assert why.startswith("from_poi")

    def test_a_walked_section_whose_ends_share_a_mile_is_refused(self):
        # A zero-length section is finished by standing still.
        _, why = one_item({"kind": "section_walked", "from_poi": "atc_viewpoints:knob", "to_poi": "atc_parking:knob"})
        assert why == "both ends resolve to the same mile"

    @pytest.mark.parametrize("fraction", [0, 1.5, True, "0.9"])
    def test_a_walked_section_fraction_must_be_in_range(self, fraction):
        _, why = one_item(
            {
                "kind": "section_walked",
                "from_poi": "atc_viewpoints:tooth",
                "to_poi": "atc_viewpoints:tinker",
                "min_fraction": fraction,
            }
        )
        assert "min_fraction" in why

    def test_a_workday_with_no_org_is_any_workday_on_the_trail(self):
        published, _ = one_item({"kind": "workday"})
        assert published["match"] == {"kind": "workday", "org": None, "trail": "AT"}

    def test_a_workday_may_name_a_known_organization(self):
        published, _ = one_item({"kind": "workday", "org": "atc"})
        assert published["match"]["org"] == "atc"

    @pytest.mark.parametrize("org", ["nobody", ["atc"], 7])
    def test_a_workday_org_must_be_a_known_organization(self, org):
        _, why = one_item({"kind": "workday", "org": org})
        assert "not a known organization" in why

    def test_self_report_passes_with_nothing_but_its_kind(self):
        # The PDF's at-home lines - the one named exception to "days, not
        # clicks" - carry no place and nothing to check.
        published, why = one_item({"kind": "self_report", "poi": "ignored"})
        assert why == ""
        assert published["match"] == {"kind": "self_report"}

    @pytest.mark.parametrize("match", [{"kind": "tap_a_button"}, {}, "place", None])
    def test_an_unknown_kind_is_refused(self, match):
        _, why = one_item(item(match=match))
        assert "match" in why


class TestItems:
    def test_a_duplicate_item_id_keeps_the_first_and_refuses_the_second(self):
        # Tags are keyed by item id; a second row with the same id would
        # silently take the first one's tags.
        record, dropped, _ = run(challenge(items=[item(title="First."), item(title="Second.", match={"kind": "self_report"})]))
        assert [i["title"] for i in record["items"]] == ["First."]
        assert dropped == [("mcafee-knob", "duplicate item id")]

    def test_an_item_in_a_section_the_challenge_does_not_declare_is_refused(self):
        _, why = one_item(item(section="protect"))
        assert "'protect' is not declared" in why

    @pytest.mark.parametrize("section", [["experience"], None, 3])
    def test_a_malformed_section_is_refused_rather_than_raised(self, section):
        _, why = one_item(item(section=section))
        assert "is not declared" in why

    def test_an_item_with_no_title_is_refused_unless_it_is_a_mystery(self):
        _, why = one_item(item(title="  "))
        assert "no title" in why

    @pytest.mark.parametrize("item_id", ["McAfee Knob", "", None, "mcafee_knob"])
    def test_an_item_id_must_be_lowercase_words_joined_by_hyphens(self, item_id):
        _, dropped, _ = run(challenge(items=[item(id=item_id), item(id="kept")]))
        assert dropped[0][1] == "item id must be lowercase words joined by hyphens"


class TestSealedMysteryItems:
    TITLE = "Find the spring the ATC hid on its map."

    def mystery(self, reveal_on, title=TITLE) -> dict:
        return item(
            id="mystery-2",
            section="mystery",
            title=title,
            mystery={"number": 2, "reveal_on": reveal_on},
            match={"kind": "self_report"},
        )

    def test_before_its_date_the_title_is_nowhere_in_the_record(self):
        # Base64 is a spoiler guard, not a secret (features/CHALLENGES.md) -
        # but the guard is only worth anything if the clear text is not also
        # sitting in some other field of the same record.
        record, dropped, why = run(challenge(items=[self.mystery("2027-07-20")]))
        assert why == "" and dropped == []

        serialized = json.dumps(record, ensure_ascii=False)
        assert self.TITLE not in serialized
        assert "hid on its map" not in serialized

        published = record["items"][0]
        assert published["title"] is None
        assert unseal(published["sealed_title"]) == self.TITLE
        assert published["mystery"] == {"number": 2, "reveal_on": "2027-07-20"}

    def test_on_its_date_the_title_ships_in_the_clear(self):
        # "On or after reveal_on", the phone's rule too - so an export run on
        # the day and a phone decoding on the day agree.
        record, _, _ = run(challenge(items=[self.mystery("2026-09-30")]))
        published = record["items"][0]
        assert published["title"] == self.TITLE
        assert "sealed_title" not in published

    def test_after_its_date_the_title_ships_in_the_clear(self):
        record, _, _ = run(challenge(items=[self.mystery("2026-07-20")]))
        published = record["items"][0]
        assert published["title"] == self.TITLE
        assert "sealed_title" not in published

    def test_with_no_title_it_ships_with_none_and_nothing_to_unseal(self):
        # The ATC's 2025 three: announced only on social media, so the
        # transcription has no title and no date, and the club reveals one by
        # republishing.
        record, dropped, _ = run(challenge(items=[self.mystery(None, title=None)]))
        assert dropped == []
        published = record["items"][0]
        assert published["title"] is None
        assert "sealed_title" not in published
        assert published["mystery"] == {"number": 2, "reveal_on": None}

    @pytest.mark.parametrize(
        ("mystery", "because"),
        [
            ({"number": 0, "reveal_on": None}, "number from 1"),
            ({"number": True, "reveal_on": None}, "number from 1"),
            ({"number": 2, "reveal_on": "20 July"}, "not a YYYY-MM-DD"),
            ("soon", "not an object"),
        ],
    )
    def test_a_malformed_mystery_is_refused(self, mystery, because):
        _, why = one_item(item(section="mystery", mystery=mystery, match={"kind": "self_report"}))
        assert because in why


class TestTheWholeChallenge:
    def test_a_finish_line_more_items_than_resolved_drops_the_whole_challenge(self):
        # "25 for the drawing" that can only ever be 24 is a promise nobody
        # can keep. The item drops are still reported, so the reason is
        # findable from the run's output.
        items = [item(), item(id="gone", match={"kind": "place", "poi": "atc_viewpoints:gone"})]
        record, dropped, why = run(challenge(items=items, finish={"count": 2, "label": "for the patch"}))
        assert record is None
        assert why == "finish needs 2 items and only 1 resolved"
        assert dropped[0][0] == "gone"

    def test_a_finish_line_the_resolved_items_reach_publishes(self):
        record, _, _ = run(challenge(finish={"count": 1, "label": " for the patch "}))
        assert record["finish"] == {"count": 1, "label": "for the patch"}

    @pytest.mark.parametrize("count", [0, -1, 1.5, True, "25"])
    def test_a_finish_count_must_be_a_whole_number_from_one(self, count):
        _, _, why = run(challenge(finish={"count": count}))
        assert "whole number" in why

    def test_a_reward_needs_a_finish_line(self):
        # A reward with no finish has no moment at which to claim it.
        _, _, why = run(challenge(reward={"kind": "patch"}))
        assert why == "a reward needs a finish line to be claimed at"

    def test_a_reward_rules_url_must_be_https(self):
        _, _, why = run(
            challenge(finish={"count": 1}, reward={"kind": "drawing", "rules_url": "http://appalachiantrail.org/sweepstakes"})
        )
        assert why == "reward rules_url must be https"

    def test_a_reward_with_its_finish_line_publishes(self):
        record, _, why = run(
            challenge(finish={"count": 1}, reward={"kind": "drawing", "rules_url": "https://appalachiantrail.org/sweepstakes"})
        )
        assert why == ""
        assert record["reward"] == {"kind": "drawing", "rules_url": "https://appalachiantrail.org/sweepstakes", "art": None}

    def test_a_reward_kind_must_be_one_the_app_knows(self):
        _, _, why = run(challenge(finish={"count": 1}, reward={"kind": "cash"}))
        assert "reward kind" in why

    @pytest.mark.parametrize(
        "window",
        [{"opens": "2027-09-01", "closes": "2027-05-15"}, {"opens": "2027-09-01", "closes": "2027-09-01"}],
    )
    def test_a_window_that_closes_on_or_before_it_opens_is_refused(self, window):
        _, _, why = run(challenge(window=window))
        assert why == "window closes on or before it opens"

    @pytest.mark.parametrize("window", [{"opens": None, "closes": None}, {"opens": None, "closes": "2027-09-01"}])
    def test_either_end_of_the_window_may_be_open(self, window):
        record, _, _ = run(challenge(window=window))
        assert record["window"] == window

    @pytest.mark.parametrize("window", [{"opens": "May 15", "closes": None}, {"opens": None, "closes": "2027-02-30"}, None])
    def test_a_malformed_window_is_refused(self, window):
        record, _, _ = run(challenge(window=window))
        assert record is None

    def test_a_status_must_be_draft_or_published(self):
        _, _, why = run(challenge(status="confirmed"))
        assert "status must be one of" in why

    def test_reviewed_must_be_a_date(self):
        _, _, why = run(challenge(reviewed="last week"))
        assert "reviewed" in why

    def test_two_sections_may_not_share_an_id(self):
        sections = [{"id": "experience", "title": "One"}, {"id": "experience", "title": "Two"}]
        _, _, why = run(challenge(sections=sections))
        assert why == "two sections share an id"

    def test_a_section_id_must_be_a_string(self):
        # `5` stringifies to a legal id; published as the integer it is, it
        # would match no item's "5" and every item in it would drop.
        _, _, why = run(challenge(sections=[{"id": 5, "title": "Five"}]))
        assert why == "a section has no usable id"

    def test_a_section_short_name_falls_back_to_its_title(self):
        record, _, _ = run(challenge(sections=[{"id": "experience", "title": "Experience the A.T."}]))
        assert record["sections"] == [{"id": "experience", "title": "Experience the A.T.", "short": "Experience the A.T."}]


class TestResolvingFiles:
    def test_the_file_stem_must_equal_the_challenge_id(self):
        # A rename without an id change (or the reverse) would publish a
        # hiker's tags under a new name.
        resolution = resolve(
            [("summer-list-2027", challenge())],
            org_trails=ORG_TRAILS,
            poi_types=PUBLISHED_TYPES,
            pois=POIS,
            trail_distance_m=on_the_trail,
            today=TODAY,
        )
        assert resolution.challenges == []
        assert resolution.dropped == [("summer-list", "file is named summer-list-2027.json but its id is summer-list")]

    def test_a_duplicate_challenge_id_keeps_the_first(self):
        resolution = resolve(
            [("summer-list", challenge(name="First")), ("summer-list", challenge(name="Second"))],
            org_trails=ORG_TRAILS,
            poi_types=PUBLISHED_TYPES,
            pois=POIS,
            trail_distance_m=on_the_trail,
            today=TODAY,
        )
        assert [c["name"] for c in resolution.challenges] == ["First"]
        assert resolution.dropped == [("summer-list", "duplicate challenge id")]

    def test_a_file_that_did_not_parse_is_dropped_under_its_stem(self):
        # export_challenges.load_challenge_files hands the resolver None for
        # a file that is not JSON.
        resolution = resolve(
            [("broken", None)],
            org_trails=ORG_TRAILS,
            poi_types=PUBLISHED_TYPES,
            pois=POIS,
            trail_distance_m=on_the_trail,
            today=TODAY,
        )
        assert resolution.dropped == [("broken", "file is not an object")]

    def test_dropped_items_are_labelled_with_their_challenge(self):
        items = [item(), item(id="gone", match={"kind": "place", "poi": "atc_viewpoints:gone"})]
        resolution = resolve(
            [("summer-list", challenge(items=items))],
            org_trails=ORG_TRAILS,
            poi_types=PUBLISHED_TYPES,
            pois=POIS,
            trail_distance_m=on_the_trail,
            today=TODAY,
        )
        assert len(resolution.challenges) == 1
        assert resolution.dropped_items == [("summer-list", "gone", "poi atc_viewpoints:gone is not in the published POIs")]


class TestTrailDistanceIndex:
    # A north-south line at 80 W with a vertex every 0.0001 degree of latitude
    # (~11 m) - about the published centerline's mean spacing of ~16 m.
    LINE = [(-80.0, 37.0 + i * 0.0001) for i in range(200)]

    def test_a_vertex_is_zero_metres_from_the_trail(self):
        distance = trail_distance_index([self.LINE])
        assert distance(-80.0, 37.005) == pytest.approx(0.0, abs=0.01)

    def test_a_point_about_a_hundred_metres_off_reads_as_about_a_hundred_metres(self):
        # 100 m of longitude at 37 N, from the same haversine the index uses,
        # so the assertion is about the index finding the right vertex rather
        # than about the formula.
        east = 100 / haversine_m(-80.0, 37.005, -79.0, 37.005)
        distance = trail_distance_index([self.LINE])
        assert distance(-80.0 + east, 37.005) == pytest.approx(100.0, abs=1.0)

    def test_the_nearest_vertex_is_found_across_a_grid_cell_edge(self):
        # 37.0 sits exactly on a 0.05-degree boundary; a point just south of
        # it lives in the next cell down and must still find the line.
        distance = trail_distance_index([self.LINE])
        assert distance(-80.0, 36.9999) == pytest.approx(11.1, abs=0.5)

    def test_a_point_more_than_a_cell_from_every_vertex_is_infinitely_far(self):
        distance = trail_distance_index([self.LINE])
        assert distance(-79.0, 37.005) == float("inf")

    def test_more_than_one_line_is_searched(self):
        distance = trail_distance_index([[(-75.0, 41.0)], self.LINE])
        assert distance(-75.0, 41.0) == pytest.approx(0.0, abs=0.01)
        assert distance(-80.0, 37.0) == pytest.approx(0.0, abs=0.01)

    def test_one_cell_is_wider_than_the_largest_radius_at_the_northern_end(self):
        # The docstring's reasoned claim, made checkable: at Katahdin's
        # latitude a 0.05-degree cell of longitude still exceeds MAX_RADIUS_M,
        # so no place inside its radius can read as infinitely far.
        assert haversine_m(-68.92, 45.90, -68.87, 45.90) > MAX_RADIUS_M
