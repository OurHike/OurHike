"""The curated highlight list, resolved against published data (#595).

What is worth asserting here is almost entirely about REFUSAL. The editorial
judgement lives in reference/highlights.json and is reviewed by reading it;
what this module can get wrong is publishing a stretch whose ends nobody
placed, or quietly dropping one nobody notices is gone.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.highlights import (
    AT_TRAIL_ID,
    NAMED_BASIS,
    Highlight,
    Leg,
    as_published,
    club_for_mile,
    clubs_without_a_highlight,
    poi_miles,
    resolve,
)

REFERENCE = Path(__file__).resolve().parent.parent / "reference" / "highlights.json"


def poi(poi_id: str, mile: float | None) -> dict:
    return {"id": poi_id, "mile": mile}


def entry(**overrides) -> dict:
    base = {
        "id": "mcafee-knob",
        "name": "McAfee Knob",
        "note": "The most photographed spot on the A.T.",
        "reviewed": "2026-08-20",
        "legs": [{"trail": AT_TRAIL_ID, "from_poi": "park:1", "to_poi": "summit:1"}],
    }
    base.update(overrides)
    return base


PUBLISHED = [poi("park:1", 705.6), poi("summit:1", 709.1)]


class TestResolvingALeg:
    def test_takes_the_mile_range_from_the_published_pois(self):
        # The whole reason a leg names POIs and no numbers: the range is ATC's
        # own measurement, not a guidebook figure typed into a JSON file.
        resolved = resolve([entry()], PUBLISHED)
        assert resolved.dropped == []
        assert resolved.highlights[0].legs == (Leg(AT_TRAIL_ID, 705.6, 709.1),)

    def test_orders_the_ends_so_a_leg_never_runs_backwards(self):
        # Which anchor is `from` is editorial - a hiker walks it either way -
        # and a negative-length leg would break every consumer downstream.
        backwards = entry(legs=[{"trail": AT_TRAIL_ID, "from_poi": "summit:1", "to_poi": "park:1"}])
        assert resolve([backwards], PUBLISHED).highlights[0].legs[0].start_mile == 705.6

    def test_carries_the_trail_each_leg_belongs_to(self):
        # A mile only means something relative to one trail, which is why the
        # range moved down a level in the first place.
        assert resolve([entry()], PUBLISHED).highlights[0].legs[0].trail == AT_TRAIL_ID

    def test_the_at_trail_id_is_the_one_published_pois_carry(self):
        # Restated in lib/highlights.py rather than imported, so this is what
        # keeps the two from drifting apart.
        from export_poi import TRAIL_ID

        assert AT_TRAIL_ID == TRAIL_ID


class TestRefusal:
    """Every one of these publishes nothing rather than publishing a guess."""

    @pytest.mark.parametrize(
        ("broken", "because"),
        [
            (entry(legs=[{"trail": AT_TRAIL_ID, "from_poi": "gone:9", "to_poi": "summit:1"}]), "no published mile"),
            (entry(legs=[{"trail": AT_TRAIL_ID, "from_poi": "park:1", "to_poi": "gone:9"}]), "no published mile"),
            (entry(legs=[{"trail": AT_TRAIL_ID, "to_poi": "summit:1"}]), "no from_poi"),
            (entry(legs=[{"from_poi": "park:1", "to_poi": "summit:1"}]), "names no trail"),
            (entry(legs=[]), "no legs"),
            (entry(name=""), "no name"),
            (entry(id=""), "no id"),
        ],
    )
    def test_drops_what_it_cannot_place(self, broken, because):
        resolved = resolve([broken], PUBLISHED)
        assert resolved.highlights == []
        assert len(resolved.dropped) == 1
        assert because in resolved.dropped[0][1]

    def test_drops_a_poi_that_published_without_a_mile(self):
        # attach_miles leaves the field None where a point could not be
        # projected onto the ordered centerline. That is a gap, not a zero.
        resolved = resolve([entry()], [poi("park:1", None), poi("summit:1", 709.1)])
        assert resolved.highlights == []

    def test_keeps_mile_zero_which_is_springer_mountain(self):
        # The one number a truthiness check would eat. Springer is a real
        # place a highlight could legitimately start from.
        resolved = resolve(
            [entry(legs=[{"trail": AT_TRAIL_ID, "from_poi": "park:1", "to_poi": "summit:1"}])],
            [poi("park:1", 0.0), poi("summit:1", 8.8)],
        )
        assert resolved.highlights[0].legs[0].start_mile == 0.0

    def test_drops_a_walk_between_two_ends_at_the_same_mile(self):
        resolved = resolve([entry()], [poi("park:1", 705.6), poi("summit:1", 705.6)])
        assert resolved.highlights == []

    def test_drops_the_second_of_two_rows_claiming_one_id(self):
        # An editing accident, and the second would silently win a dict-keyed
        # consumer downstream.
        resolved = resolve([entry(), entry(name="A different walk")], PUBLISHED)
        assert len(resolved.highlights) == 1
        assert resolved.dropped == [("mcafee-knob", "duplicate id")]

    def test_publishes_nothing_of_a_highlight_whose_second_leg_fails(self):
        # All or nothing: half a walk drawn is a walk that ends where nothing
        # ends.
        two_legs = entry(
            legs=[
                {"trail": AT_TRAIL_ID, "from_poi": "park:1", "to_poi": "summit:1"},
                {"trail": "Falling Waters", "from_poi": "summit:1", "to_poi": "gone:9"},
            ]
        )
        assert resolve([two_legs], PUBLISHED).highlights == []

    def test_one_bad_row_does_not_cost_the_rows_beside_it(self):
        good = entry(id="wayah-bald", name="Wayah Bald")
        resolved = resolve([entry(id=""), good], PUBLISHED)
        assert [h.id for h in resolved.highlights] == ["wayah-bald"]


class TestClubs:
    CLUB_RUNS = [
        {"acronym": "RATC", "stretches": [{"start_mile": 700.0, "end_mile": 720.0}]},
        {"acronym": "GATC", "stretches": [{"start_mile": 0.0, "end_mile": 77.0}]},
    ]

    def test_derives_the_club_rather_than_taking_the_file_s_word(self):
        # Derived, so "one per club" is a fact the exporter can check instead
        # of a claim the reference file makes about itself.
        resolved = resolve([entry()], PUBLISHED, self.CLUB_RUNS)
        assert resolved.highlights[0].club == "RATC"

    def test_a_mile_two_clubs_share_resolves_northbound(self):
        # Half-open, matching client/src/lib/clubSections.ts exactly, so the
        # two halves of the app cannot disagree about who maintains mile 77.
        runs = [
            {"acronym": "GATC", "stretches": [{"start_mile": 0.0, "end_mile": 77.0}]},
            {"acronym": "NHC", "stretches": [{"start_mile": 77.0, "end_mile": 100.0}]},
        ]
        assert club_for_mile(runs, 76.9) == "GATC"
        assert club_for_mile(runs, 77.0) == "NHC"

    def test_an_unattributed_mile_has_no_club_and_that_is_not_an_error(self):
        # 38.5 miles of the trail are like this.
        assert club_for_mile(self.CLUB_RUNS, 500.0) is None

    def test_reports_the_clubs_the_list_still_says_nothing_about(self):
        # The gap is visible on every run rather than only when somebody
        # counts - and it is a report, not a failure. A club with no
        # well-known stretch is a fact about the trail.
        resolved = resolve([entry()], PUBLISHED, self.CLUB_RUNS)
        assert clubs_without_a_highlight(resolved.highlights, self.CLUB_RUNS) == ["GATC"]


class TestPublishedShape:
    def test_names_its_basis_and_never_says_popular(self):
        # "Popular" is three questions with different evidence behind them.
        # The record says which one it is answering.
        record = as_published(resolve([entry()], PUBLISHED).highlights[0])
        assert record["bases"] == [NAMED_BASIS]
        assert record["citations"][NAMED_BASIS]["by"] == "OurHike"
        assert record["citations"][NAMED_BASIS]["reviewed"] == "2026-08-20"

    def test_stores_no_length_ascent_or_time(self):
        # Derived on the phone from the elevation profile it already holds, so
        # a better profile improves every highlight without a republish.
        record = as_published(resolve([entry()], PUBLISHED).highlights[0])
        assert not {"miles", "length", "ascent", "ascent_ft", "naismith", "minutes"} & set(record)

    def test_never_carries_a_visited_count(self):
        # #596's, and now also needing an explicit decision about
        # features/EVENTING.md rule 2, which has not been taken.
        record = as_published(resolve([entry()], PUBLISHED).highlights[0])
        assert "visited" not in record["bases"]
        assert "visited_count" not in record


class TestTheCuratedFileItself:
    """The reference file is editorial, so what is checked is its shape."""

    @staticmethod
    def curated() -> list[dict]:
        return json.loads(REFERENCE.read_text())["highlights"]

    def test_every_row_carries_what_a_reviewer_needs_to_judge_it(self):
        for row in self.curated():
            assert row["id"] and row["name"] and row["note"] and row["reviewed"], row
            # The anchors block repeats the POI names in words, so a diff can
            # be read without resolving an id.
            assert row["anchors"]["from"] and row["anchors"]["to"], row

    def test_every_row_is_editorial_and_says_so(self):
        # An entry ATC publishes as a day hike is `published` and cites ATC.
        # Nothing here may claim that without the source being registered.
        assert {row["basis"] for row in self.curated()} == {NAMED_BASIS}

    def test_ids_are_unique(self):
        ids = [row["id"] for row in self.curated()]
        assert len(ids) == len(set(ids))

    def test_no_row_writes_a_mile_down(self):
        # The point of the whole design: miles come from the published POIs,
        # so nobody types a guidebook figure into this file.
        raw = REFERENCE.read_text()
        assert "start_mile" not in raw and "end_mile" not in raw

    def test_every_leg_is_on_a_named_trail(self):
        for row in self.curated():
            for leg in row["legs"]:
                assert leg["trail"] == AT_TRAIL_ID, row["id"]

    def test_it_resolves_against_the_pois_it_names(self):
        # Not that the miles are right - there are no published POIs here -
        # but that every row is well formed enough to resolve when they exist.
        curated = self.curated()
        anchors = {poi_id for row in curated for leg in row["legs"] for poi_id in (leg["from_poi"], leg["to_poi"])}
        published = [poi(poi_id, float(i * 10)) for i, poi_id in enumerate(sorted(anchors))]
        resolved = resolve(curated, published)
        assert resolved.dropped == []
        assert len(resolved.highlights) == len(curated)


def test_poi_miles_skips_what_has_none():
    assert poi_miles([poi("a", 1.0), poi("b", None), {"id": "c"}]) == {"a": 1.0}


def test_highlight_miles_sums_its_legs():
    # naismith.ts sums legs before rounding for the same reason; this is the
    # pipeline side of one walk being one number.
    highlight = Highlight(
        id="loop",
        name="A loop",
        legs=(Leg("AT", 10.0, 11.7), Leg("Falling Waters", 0.0, 3.2)),
        note="",
        reviewed="",
    )
    assert highlight.miles == pytest.approx(4.9)
