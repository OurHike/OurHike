"""Tests for lib/club_sections.py - who maintains which stretch (#594).

Two of these guard mistakes that were actually made while writing it and that
no type checker or lint would have caught, because both produce a plausible
artifact:

  - `test_a_run_spans_the_trail_its_mileposts_stand_for` is the half-mile
    bug. Reporting a run as first-milepost-to-last silently lost 44.0 of the
    trail's 2,197.5 miles across 87 runs and published two zero-length
    stretches. Nothing about the output looked wrong until the totals were
    added up.
  - `test_the_published_stretches_tile_the_whole_trail` is the same failure
    caught from the other end, and it is the one worth keeping: it fails for
    a seam, an overlap, a short total, or an end past Katahdin, whatever the
    cause.
"""

import pytest

from lib.club_sections import (
    MILEPOST_HALF_WIDTH,
    SPRINGER_MILE,
    STRETCH_GAP_MILES,
    assemble,
    build_stretches,
    canonical_clubs,
    is_attributable,
)

# Mileposts every half mile, as half_mile_points_from_springer publishes them.
STEP = 0.5


def mileposts(start: float, count: int, acronym: str | None) -> list[tuple[float, str | None]]:
    return [(start + i * STEP, acronym) for i in range(count)]


def polygon(acronym: str, name: str, region: str = "SORO") -> dict:
    return {"properties": {"ACROYNM": acronym, "TRAIL_CLUB": name, "REGION": region}}


# --- which values name a club ---------------------------------------------


@pytest.mark.parametrize("acronym", ["MATC", "AMC-DV", " PATC "])
def test_a_real_acronym_is_attributable(acronym):
    assert is_attributable(acronym)


@pytest.mark.parametrize("value", ["23", "0", " 11 ", "", "   ", None, 23, 4.5])
def test_the_broken_upstream_values_are_not(value):
    """47 centerline features carry a digit string in both Trail_Club and
    Acronym - an unjoined FID upstream. Tested as a total rule rather than as
    a blocklist of the twelve seen on one day, so a thirteenth needs no code
    change."""
    assert not is_attributable(value)


# --- the spelling authority -----------------------------------------------


def test_canonical_names_come_from_the_polygon_layer():
    canonical = canonical_clubs([polygon("PATC", "Potomac Appalachian Trail Club", "MARO")])
    assert canonical["PATC"] == {"name": "Potomac Appalachian Trail Club", "region": "MARO"}


def test_a_junk_polygon_row_is_skipped_rather_than_indexed():
    assert canonical_clubs([polygon("", "nameless"), polygon("23", "junk")]) == {}


def test_the_canonical_spelling_beats_the_centerlines_misspelling():
    """The centerline spells it "Potomac Appalachain Trail Club" and the
    polygon layer spells it correctly; both agree on the acronym. The acronym
    is the key precisely because it is the field the two never disagree on -
    so the misspelling never reaches a hiker, while the fresh source still
    decides which stretch is whose."""
    clubs, _ = assemble(
        mileposts(0.5, 4, "PATC"),
        canonical_clubs([polygon("PATC", "Potomac Appalachian Trail Club", "MARO")]),
    )
    assert [(c.acronym, c.name, c.region) for c in clubs] == [("PATC", "Potomac Appalachian Trail Club", "MARO")]


def test_a_club_the_polygon_layer_has_never_heard_of_keeps_its_acronym():
    """Cannot happen against today's data - the thirty agree. Dropping a real
    stretch of trail because a two-year-old lookup table lacks a row is the
    wrong failure to pick in advance."""
    clubs, _ = assemble(mileposts(0.5, 4, "NEWCLUB"), {})
    assert [(c.acronym, c.name, c.region) for c in clubs] == [("NEWCLUB", "NEWCLUB", None)]


# --- runs, and the half-mile bug ------------------------------------------


def flanked(middle: list[tuple[float, str | None]]) -> list[tuple[float, str | None]]:
    """`middle`, with a club either side of it.

    Every test about a run's WIDTH needs this. The southernmost and
    northernmost runs are pinned to the termini, so a fixture consisting of one
    run is measuring the pinning rather than the half-width, and would pass
    against the very bug these tests exist to catch.
    """
    return mileposts(0.5, 2, "SOUTH") + middle + mileposts(900.0, 2, "NORTH")


def test_a_run_spans_the_trail_its_mileposts_stand_for():
    """THE regression this file exists for. Four mileposts at 0.5-mile spacing
    stand for 2.0 miles of trail, not the 1.5 miles between the outer two."""
    runs = build_stretches(flanked(mileposts(10.5, 4, "GMC")))
    ((start, end),) = runs["GMC"]
    assert end - start == pytest.approx(4 * STEP)


def test_a_lone_milepost_is_half_a_mile_not_nothing():
    """The naive version published two zero-length stretches, where a single
    milepost sat between two broken features."""
    runs = build_stretches(flanked([(500.0, "RMC")]))
    ((start, end),) = runs["RMC"]
    assert end - start == pytest.approx(STEP)


def test_a_change_of_club_starts_a_new_stretch():
    runs = build_stretches(mileposts(0.5, 4, "GATC") + mileposts(2.5, 4, "NHC"))
    assert len(runs["GATC"]) == 1 and len(runs["NHC"]) == 1


def test_consecutive_clubs_abut_exactly_rather_than_overlapping_or_leaving_a_seam():
    runs = build_stretches(mileposts(0.5, 4, "GATC") + mileposts(2.5, 4, "NHC"))
    assert runs["GATC"][0][1] == pytest.approx(runs["NHC"][0][0])


def test_a_gap_in_the_mileposts_splits_one_club_into_two_stretches():
    """Four clubs on the A.T. maintain discontiguous trail. Publishing them as
    one stretch would claim the miles in between, which belong to somebody
    else."""
    far = mileposts(10.5, 3, "MATC") + mileposts(80.0, 3, "MATC")
    assert len(build_stretches(far)["MATC"]) == 2


def test_a_gap_inside_the_tolerance_does_not_split():
    assert STRETCH_GAP_MILES > STEP
    assert len(build_stretches(mileposts(10.5, 6, "MATC"))["MATC"]) == 1


def test_unattributed_mileposts_are_published_not_dropped():
    """25 miles of trail the fresh source cannot name. Omitting them reads as
    "no trail here"; publishing them reads as "not recorded", which is what is
    true."""
    runs = build_stretches(mileposts(0.5, 2, "GATC") + mileposts(1.5, 2, None) + mileposts(2.5, 2, "GATC"))
    assert len(runs[None]) == 1
    assert len(runs["GATC"]) == 2


def test_no_input_is_no_runs_rather_than_a_crash():
    assert build_stretches([]) == {}


# --- the termini ----------------------------------------------------------


def test_the_southernmost_stretch_starts_at_springer():
    """Mileposts begin at 0.5, so the half-width would otherwise leave the
    first quarter mile of the trail belonging to nobody."""
    runs = build_stretches(mileposts(0.5, 4, "GATC"))
    assert runs["GATC"][0][0] == SPRINGER_MILE


def test_the_northernmost_stretch_stops_at_the_last_milepost():
    """A quarter mile past Katahdin is not trail anybody can walk, and a client
    drawing the published range would draw it."""
    runs = build_stretches(mileposts(0.5, 4, "MATC"))
    assert runs["MATC"][0][1] == pytest.approx(2.0)


def test_the_published_stretches_tile_the_whole_trail():
    """The property that catches the half-mile bug, a seam, an overlap and an
    overshoot at once, whatever introduced them."""
    points = mileposts(0.5, 20, "GATC") + mileposts(10.5, 10, None) + mileposts(15.5, 20, "NHC")
    runs = build_stretches(points)

    spans = sorted(span for values in runs.values() for span in values)
    assert spans[0][0] == SPRINGER_MILE
    assert spans[-1][1] == pytest.approx(max(mile for mile, _ in points))
    for (_, end), (next_start, _) in zip(spans, spans[1:]):
        assert end == pytest.approx(next_start), "stretches must abut"
    assert sum(end - start for start, end in spans) == pytest.approx(len(points) * STEP)


# --- assembly -------------------------------------------------------------


def test_clubs_come_out_south_to_north():
    clubs, _ = assemble(
        mileposts(100.5, 4, "NHC") + mileposts(0.5, 4, "GATC"),
        canonical_clubs([polygon("GATC", "Georgia"), polygon("NHC", "Nantahala")]),
    )
    assert [c.acronym for c in clubs] == ["GATC", "NHC"]


def test_the_unattributed_runs_come_back_separately_not_as_a_club():
    clubs, unattributed = assemble(mileposts(0.5, 2, "GATC") + mileposts(1.5, 2, None), {})
    assert [c.acronym for c in clubs] == ["GATC"]
    assert len(unattributed) == 1


def test_a_clubs_mileage_is_the_sum_of_its_stretches():
    clubs, _ = assemble(flanked(mileposts(10.5, 4, "MATC") + mileposts(80.0, 6, "MATC")), {})
    club = next(c for c in clubs if c.acronym == "MATC")
    assert club.miles == pytest.approx(sum(end - start for start, end in club.stretches))
    assert club.miles == pytest.approx(10 * STEP)


def test_the_half_width_constant_is_half_the_milepost_spacing():
    """If half_mile_points_from_springer ever ships at a different interval,
    this is the constant that has to move with it."""
    assert MILEPOST_HALF_WIDTH == pytest.approx(STEP / 2)
