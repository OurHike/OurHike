"""Tests for the ATC Trail Updates parser (spike_atc_updates.py).

The strings below are REAL - copied from the nine Trail Updates live on
appalachiantrail.org on 2026-08-09, not invented to suit the pattern. That
matters more here than in most parser tests: the whole feasibility claim in
features/ATC_TRAIL_UPDATES.md is a claim about how ATC writes prose, and a
test against prose we wrote ourselves would only prove the regex matches
itself.

No network. The spike hits the live feed; these exercise the pure functions
it is built out of.
"""

import pytest

from spike_atc_updates import (
    TRAIL_MILE_MAX,
    TRAIL_MILE_MIN,
    Update,
    extract_mile_references,
    nearest_marker,
    parse_mile,
    strip_html,
)

# Real sentences, one per live update that carries a mile reference.
IRON_MTN_GAP = (
    "Members of the Tennessee Eastman Hiking & Canoeing Club and staff from the "
    "Appalachian Trail Conservancy have done significant work in clearing back the "
    "brush on the section south of Iron Mountain Gap (NOBO mile 360.6 to 364.8). "
    "Hikers should still take care in this section and follow all posted signage."
)
LIMESTONE_SPRING = (
    "Limestone Spring Shelter is closed due to a damaged tree from the recent storms "
    "(NOBO mile 1,503.6). A large maple tree snapped during the storm."
)
CREEPER_TRAIL = (
    "Additional construction-related closures include: Straight Branch Trailhead "
    "(NOBO mile 476.6) Creek Junction Trailhead (NOBO mile 484.6) The Creeper Trail "
    "is closed. Grassy Ridge Road is the northern boundary of the construction "
    "closure at NOBO mile 485.8. NOBO hikers can pick-up the A.T. from here."
)
HELENE = (
    "The A.T. from Davenport Gap to Pearisburg, VA was severely damaged by Hurricane "
    "Helene in the fall of 2024 (NOBO miles 239.4 to 637.8)."
)
VERNIE_SWAMP = (
    "The A.T. north of Unionville, NY, regularly floods thanks to the hard work of "
    "some nearby beavers (approx. NOBO mile 1,346.3)."
)
# Both live updates that carry no mile reference at all. Neither is a defect:
# one is a region-wide weather advisory, the other a law-enforcement request
# with no location. See the design doc's "what is not a map feature".
SEVERE_WEATHER = (
    "Severe weather is expected across the region. Hikers should be prepared for "
    "high winds and heavy rain and should avoid exposed ridgelines."
)
HELP_IDENTIFYING = "The ATC is seeking the public's help identifying an individual."


def test_extracts_a_range_written_with_singular_mile():
    """ATC writes "mile 360.6 to 364.8" as often as "miles" - the plural is
    not a reliable signal of a range, so the pattern must not depend on it."""
    (reference,) = extract_mile_references(IRON_MTN_GAP)
    assert (reference.start, reference.end) == (360.6, 364.8)
    assert reference.is_range


def test_extracts_a_range_written_with_plural_miles():
    (reference,) = extract_mile_references(HELENE)
    assert (reference.start, reference.end) == (239.4, 637.8)


def test_a_thousands_comma_is_not_a_truncated_mile():
    """The failure this guards is the one that would have been shipped rather
    than caught: a number pattern without the comma reads "NOBO mile 1,503.6"
    as mile 1, turning a shelter in Connecticut into a point in Georgia. It
    parses, it looks plausible, and it is 1,502 miles wrong."""
    (reference,) = extract_mile_references(LIMESTONE_SPRING)
    assert reference.start == 1503.6
    assert reference.end is None


def test_a_point_is_not_silently_widened_into_a_range():
    """`end is None` has to survive, because a point and a range are drawn
    differently and a zero-length range is a lie about what ATC said."""
    (reference,) = extract_mile_references(VERNIE_SWAMP)
    assert reference.start == 1346.3
    assert reference.end is None
    assert not reference.is_range


def test_a_sentence_final_mile_does_not_swallow_the_period():
    """ "...closure at NOBO mile 485.8. NOBO hikers can pick-up..." - the
    period ends the sentence, and the next word is another NOBO reference.
    Getting this wrong yields either 485.8-as-4858 or one merged range
    spanning the two sentences."""
    references = extract_mile_references(CREEPER_TRAIL)
    assert [r.start for r in references] == [476.6, 484.6, 485.8]
    assert all(r.end is None for r in references)


def test_repeated_references_are_kept_in_document_order():
    """iron-mtn-gap-detour states its range three times across months of
    edits. Deduplicating before a human sees it discards the edit history
    that makes the update readable."""
    text = IRON_MTN_GAP + " " + HELENE + " " + IRON_MTN_GAP
    references = extract_mile_references(text)
    assert [r.start for r in references] == [360.6, 239.4, 360.6]


@pytest.mark.parametrize("text", [SEVERE_WEATHER, HELP_IDENTIFYING])
def test_updates_with_no_location_yield_nothing_rather_than_a_guess(text):
    """Two of nine live updates name no mile at all. The right answer is an
    empty list - an update the pipeline declines to place, not one it places
    approximately."""
    assert extract_mile_references(text) == []


def test_prose_without_the_nobo_marker_is_not_treated_as_a_location():
    """ "Mile 12 of the Creeper Trail" is a different trail's mileage, and
    "mile 5" in a sentence about a road walk is not A.T. mileage either.
    Requiring the NOBO/SOBO prefix is what keeps those out."""
    assert extract_mile_references("The detour adds mile 12 of road walking, then miles 3 to 4 of gravel.") == []


def test_mappability_is_a_property_of_the_update_not_the_parser():
    placed = Update(title="t", link="l", published="p", text=IRON_MTN_GAP, references=extract_mile_references(IRON_MTN_GAP))
    unplaced = Update(title="t", link="l", published="p", text=SEVERE_WEATHER, references=[])
    assert placed.mappable
    assert not unplaced.mappable


@pytest.mark.parametrize(
    "raw,expected",
    [("360.6", 360.6), ("1,503.6", 1503.6), ("364", 364.0), ("2,197.5", 2197.5)],
)
def test_parse_mile(raw, expected):
    assert parse_mile(raw) == expected


def test_a_mile_beyond_the_trail_is_reported_rather_than_placed():
    """The layer runs 0.5 to 2197.5. A parsed 3,400 is not a spot in Maine -
    it is a parse that went wrong, and nearest-marker would happily snap it to
    Katahdin and say nothing."""
    (reference,) = extract_mile_references("Closed at NOBO mile 3,400.0 for the season.")
    assert reference.start == 3400.0
    assert not reference.in_trail_extent


@pytest.mark.parametrize("mile", [TRAIL_MILE_MIN, 1000.0, TRAIL_MILE_MAX])
def test_miles_inside_the_extent_are_placeable(mile):
    (reference,) = extract_mile_references(f"Closed at NOBO mile {mile}.")
    assert reference.in_trail_extent


def test_strip_html_does_not_run_words_together_across_tags():
    """A closing/opening tag pair is a word boundary in rendered text. Losing
    it turns "<p>mile</p><p>360.6</p>" into "mile360.6", which the pattern
    then fails to see at all."""
    assert strip_html("<p>NOBO mile</p><p>360.6 to 364.8</p>") == "NOBO mile 360.6 to 364.8"


def test_strip_html_unescapes_entities():
    """ATC's feed carries `&#38;` and `&#8230;` in real bodies."""
    assert strip_html("<p>Tennessee Eastman Hiking &#38; Canoeing Club</p>") == "Tennessee Eastman Hiking & Canoeing Club"


def test_extraction_survives_the_html_it_actually_arrives_in():
    """End to end on the shape the feed really delivers: markup in, miles
    out."""
    markup = "<p>Updated 08/04/2026</p><p>clearing back the brush (NOBO mile 360.6 to 364.8). Hikers should take care.</p>"
    (reference,) = extract_mile_references(strip_html(markup))
    assert (reference.start, reference.end) == (360.6, 364.8)


def test_nearest_marker_picks_the_closest_half_mile_point():
    """Markers are every half mile, ATC quotes tenths, so the common case is
    a near miss rather than a hit - 360.6 belongs to the 360.5 marker."""
    index = {360.0: (-82.28, 36.13), 360.5: (-82.27, 36.12), 361.0: (-82.27, 36.12)}
    marker, _ = nearest_marker(index, 360.6)
    assert marker == 360.5


def test_nearest_marker_on_an_empty_index_returns_nothing():
    """A failed layer fetch must not read as "this update is at mile 0"."""
    assert nearest_marker({}, 360.6) is None
