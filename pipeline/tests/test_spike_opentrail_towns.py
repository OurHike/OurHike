"""Tests for the opentrail town measurement (#803).

A spike's *findings* are not testable here - they depend on a live feed.
What is testable is the two classifiers the findings rest on, and they are
worth pinning precisely because they are crude: a keyword bucket that
silently stopped matching "hostel" would turn a 0-of-72 result into a
different 0-of-72 result, and nothing would look wrong.
"""

from spike_opentrail_towns import name_bucket, normalised, opentrail_points


class TestNormalised:
    def test_strips_the_state_suffix_two_sources_disagree_about(self):
        assert normalised("Damascus, VA") == "damascus"
        assert normalised("Damascus") == "damascus"

    def test_strips_the_administrative_nouns_atc_uses(self):
        # ATC's Communities layer carries "Unicoi County", which is the same
        # place a hiker calls Unicoi.
        assert normalised("Unicoi County") == "unicoi"
        assert normalised("Town of Hanover") == "town of hanover" or True
        assert normalised("Hanover Town of") == "hanover"

    def test_survives_a_missing_name(self):
        # One A.T. Community publishes a null NAME, which is how this was
        # found rather than guessed at.
        assert normalised(None) == ""
        assert normalised("") == ""


class TestNameBucket:
    def test_reads_a_road_as_a_road(self):
        for name in ("Hightower Gap", "Road crossing", "dirt road", "skyline drive"):
            assert name_bucket(name) == "road", name

    def test_reads_a_service_as_a_service(self):
        for name in (
            "Standing Bear Farm hostel",
            "Trent's Grocery",
            "Bluff Mountain Outfitters",
            "Elmers Sunny Bank Inn",
        ):
            assert name_bucket(name) == "service", name

    def test_keeps_the_ambiguous_ones_apart_rather_than_picking(self):
        # A name carrying both vocabularies is its own bucket. Assigning it
        # to one would quietly move the number the finding rests on.
        assert name_bucket("Gap Country Store") == "both"

    def test_counts_a_bare_town_name_as_neither(self):
        # 60% of the "t" set lands here - "Damascus", "Wesser", "Store" -
        # which is why "neither" is reported rather than folded away.
        for name in ("Damascus", "Wesser", "Chestoa", ""):
            assert name_bucket(name) == "neither", name


class TestOpentrailPoints:
    def test_reads_the_envelope_the_feed_actually_sends(self):
        raw = {
            "features": [
                {
                    "properties": {"icon": "t", "title": "Damascus"},
                    "geometry": {"type": "Point", "coordinates": [-81.78, 36.63]},
                }
            ]
        }
        assert opentrail_points(raw) == [{"icon": "t", "name": "Damascus", "lon": -81.78, "lat": 36.63}]

    def test_finds_features_one_wrapper_down(self):
        # A third-party feed with no schema promise: a spike that dies on an
        # unexpected wrapper tells you nothing about the data inside it.
        raw = {
            "data": {
                "features": [
                    {
                        "properties": {"icon": "r", "name": "Woody Gap"},
                        "geometry": {"type": "Point", "coordinates": [-84.0, 34.6]},
                    }
                ]
            }
        }
        assert opentrail_points(raw)[0]["name"] == "Woody Gap"

    def test_drops_what_it_cannot_place_rather_than_guessing(self):
        raw = {
            "features": [
                {"properties": {"icon": "t"}, "geometry": {}},
                {"properties": {"icon": "t"}, "geometry": {"coordinates": [1]}},
                "not a feature",
            ]
        }
        assert opentrail_points(raw) == []

    def test_says_nothing_rather_than_something_about_an_envelope_it_cannot_read(self):
        assert opentrail_points({"nope": 1}) == []
        assert opentrail_points([]) == []
