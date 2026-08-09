"""Tests for lib/poi_description.py - assembling a shelter's or campsite's
one-line description from ATC's inventory columns.

The attribute dicts here mirror real ATC features (read 2026-08-09), with the
columns the composer reads and nothing else, so a test says which facts drive
which clause.
"""

import pytest

from lib.poi_description import describe_campsite, describe_shelter

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
