"""Tests for lib/atc_notes.py - filtering ATC's `Comments` down to what a
hiker can use.

The strings here are real values from the live layers (read 2026-08-09), kept
verbatim including their typos, because the whole risk this module carries is
mishandling text somebody else wrote in a hurry.
"""

import pytest

from lib.atc_notes import clean_note


@pytest.mark.parametrize(
    "raw",
    [
        "Has a loft",
        "Not an accessible shelter",
        "One group campsite",
        "Shiplap siding",
        "2 Tent Platforms, was 3 but one destroyed by fire leaving only 2 now",
        "Roof replaced in 2021 - from Shingles to Metal",
    ],
)
def test_a_note_about_the_place_survives_untouched(raw):
    """Anything that is not survey bookkeeping comes back exactly as written.
    This module never rewords ATC - it either publishes their sentence or
    drops it."""
    assert clean_note(raw) == raw


@pytest.mark.parametrize(
    "raw",
    [
        # The single most common comment on the campsite layer: 24 features.
        "Not sure about spatial info",
        "GIS CS629-CS635",
        "GIS IDs CS623-CS628",
        "Added based on existing GIS data",
        "Adusted based on Aerial Imagery",
        "Need to Confirm to status",
        "Not on list, but in area",
        "None",
        "None.",
        "No name",
        "816/15",
        "   ",
        "",
        None,
    ],
)
def test_a_note_the_survey_wrote_to_itself_is_dropped(raw):
    """None, not "" - "ATC wrote nothing" and "ATC wrote only bookkeeping"
    have to reach the client identically, because both are a card with no
    description."""
    assert clean_note(raw) is None


def test_the_useful_half_of_a_mixed_note_is_kept():
    """Cable Gap Shelter, verbatim. Dropping the whole comment to lose its
    last sentence would throw away the only description ATC wrote for it -
    which is why the unit is the sentence."""
    raw = "Log and mortar exterior. Majority of structure is log. Please see photos."

    assert clean_note(raw) == "Log and mortar exterior. Majority of structure is log."


def test_a_surveyors_aside_is_dropped_from_the_middle_of_a_note():
    raw = (
        "Two Food Boxes Shared with Shelter; I took one general point for the "
        "tenting area, unaware there were points taken for each platform."
    )

    assert clean_note(raw) == "Two Food Boxes Shared with Shelter"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # ATC's own spacing quirks, which re-joining the split sentences used
        # to "fix" into something they never wrote.
        ("Exterior - shiplap ;skylight clear corrugated lexan", "Exterior - shiplap;skylight clear corrugated lexan"),
        ("trail south of cold Spring Shelter .1 north", "trail south of cold Spring Shelter.1 north"),
        ("clapboard eaves 156sq ft,", "clapboard eaves 156sq ft"),
    ],
)
def test_atcs_own_punctuation_survives_the_filter(raw, expected):
    """Only whitespace left behind by a removed sentence is collapsed, and
    trailing punctuation that now separates nothing is trimmed. Nothing else
    about the text moves - a filter that quietly tidies is a filter that
    quietly edits."""
    assert clean_note(raw) == expected


def test_a_note_that_is_all_bookkeeping_across_several_sentences_is_dropped():
    raw = "Katahdin Stream Cg Shelter C; Added based on existing GIS data; Not sure if we should include in FMSS or not"

    assert clean_note(raw) == "Katahdin Stream Cg Shelter C"


def test_the_longest_real_note_survives_whole():
    """Father Tom Campsite - the best thing in the whole column, and the
    reason publishing this field is worth the filtering it needs."""
    raw = (
        "Campsite is on town land in developed area. Site also features: seasonal potable town water, "
        "electricity, porta potty, trash can. Includes picnic table, 4 hammock poles, 4ft x 8ft shed "
        "for bike storage.Ground surface is grass."
    )

    assert clean_note(raw) == raw


@pytest.mark.parametrize(
    "raw",
    [
        # The vista layer's own dialect, all verbatim from the live layer.
        # `Improvements = ...` alone is 133 of its 640 populated comments.
        "Improvements = none identified",
        "Improvements = Trees cut",
        "Location adjused based on 2021 VRI",
        "Preliminary Review with VARO",
        "Need To Determine Central Bearing And Scope Of View",
        "measured bearings 3 times, each time getting different results",
        "Will be brining a compass next time",
        "Completely Socked When I Was There",
        "Mountaineer Falls: Not on Scenic Vista List",
        "Extent adjusted around cars",
    ],
)
def test_the_vista_surveys_own_bookkeeping_is_dropped_too(raw):
    """The three layers added in 2026-08 brought a second bookkeeping
    vocabulary with them - an inventory form pasted into free text, a review
    process, and the surveyor's own trouble with a compass. Same rule as the
    shelter layer's: what reaches a hiker is about the place."""
    assert clean_note(raw) is None


def test_the_place_still_survives_a_comment_that_is_mostly_process():
    """Verbatim from a vista. Dropping the whole comment would lose the one
    fact in it, which is the reason this module works sentence by sentence."""
    assert clean_note("Hang gliding site; Improvements = Mowed / Brushed") == "Hang gliding site"


def test_punctuation_left_standing_where_a_sentence_was_is_not_a_note():
    """One vista comment reduces to exactly "." once its bookkeeping is gone,
    and "ATC notes: ." is worse than the silence it stands in for."""
    assert clean_note(". Improvements = Trees cut") is None
