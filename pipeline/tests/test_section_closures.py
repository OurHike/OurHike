"""lib/section_closures.py: an organization's closure notice closes the one line set that carries the section it names.

Shapes from UA's files of 2026-10-15 (release 2026-10-10-2's nearby_trails.geojson, conditions/notices.json):
USFS's "TUSCARORA - DOLL RIDGE" lines, PATC's page notice, and the near-misses measure_section_closures.py listed.
"""

from lib.section_closures import evaluate, line_sets, section_names, words

PROVIDERS = {"usfs_trails": "USFS", "nps_trails": "NPS", "nj_statewide_trails": "NJ DEP"}
DOLL_RIDGE_PAGE = (
    "The Tuscarora Trail section just west of Massanutten Mountain is closed due to loss of landowner permission. "
    "This is the Doll Ridge section from Three Top Mountain to Riverview Drive."
)


def _sets(*rows):
    return line_sets(rows, PROVIDERS)


def _notice(title, *, provider="PATC", steward_kind="club", closing=True, place="unplaced"):
    return {
        "notice_id": f"n:{title[:20]}",
        "title": title,
        "provider": provider,
        "steward_kind": steward_kind,
        "obstructs_trail": closing,
        "place": {"kind": place},
    }


DOLL_RIDGE = _sets(
    ("usfs_trails:10026704", "usfs_trails", "TUSCARORA - DOLL RIDGE", 1.38),
    ("usfs_trails:10027002", "usfs_trails", "TUSCARORA - DOLL RIDGE", 2.04),
    ("usfs_trails:1", "usfs_trails", "TUSCARORA - THREE TOP", 4.0),
)


def test_a_clubs_closing_notice_naming_the_doll_ridge_section_closes_both_lines_of_that_one_set():
    (outcome,) = evaluate([_notice(DOLL_RIDGE_PAGE)], DOLL_RIDGE)

    assert outcome.verdict == "closes"
    (closed,) = outcome.candidates
    assert closed.line_ids == ("usfs_trails:10026704", "usfs_trails:10027002")
    assert round(closed.miles, 2) == 3.42


def test_patcs_notice_as_ua_lands_it_names_no_section_and_closes_nothing():
    # Title, hash and link only (extract/patc/closures.py's PageNotice), and not closing in its own words.
    assert evaluate([_notice("Tuscarora Trail Updates", closing=False)], DOLL_RIDGE) == []


def test_a_section_named_without_its_trail_closes_nothing_and_is_listed_as_no_line():
    # "Doll Ridge" alone could be any trail's: the "<trail> - <section>" name needs its trail named too.
    (outcome,) = evaluate([_notice("The Doll Ridge section is closed")], DOLL_RIDGE)
    assert (outcome.verdict, outcome.candidates) == ("no_line", [])


def test_a_notice_that_does_not_close_the_trail_is_listed_as_not_closing():
    (outcome,) = evaluate([_notice(DOLL_RIDGE_PAGE, closing=False)], DOLL_RIDGE)
    assert outcome.verdict == "not_closing"


def test_a_closing_notice_with_its_own_geometry_is_listed_as_placed_and_closes_nothing_by_name():
    (outcome,) = evaluate([_notice(DOLL_RIDGE_PAGE, place="geometry")], DOLL_RIDGE)
    assert outcome.verdict == "placed"


def test_two_line_sets_carrying_the_name_are_ambiguous():
    sets = _sets(
        ("nps_trails:1", "nps_trails", "Big Creek Trail", 11.12),
        ("nps_trails:2", "nps_trails", "BIG CREEK TRAIL", 7.62),
        ("usfs_trails:3", "usfs_trails", "BIG CREEK TRAIL", 1.0),
    )
    # Case is not a name: "Big Creek Trail" and "BIG CREEK TRAIL" are one set's words, so NPS's two spellings are
    # one line set each and the notice's steward has two.
    (outcome,) = evaluate([_notice("Big Creek Trail", provider="NPS", steward_kind="agency")], sets)
    assert outcome.verdict == "ambiguous"
    assert {s.source_key for s in outcome.candidates} == {"nps_trails"}


def test_a_line_name_found_inside_a_longer_title_is_no_match():
    # "Bass River SF" matched New Jersey's line "River" under a looser rule (measured 2026-10-15).
    sets = _sets(("nj:1", "nj_statewide_trails", "River", 0.37))
    assert evaluate([_notice("Bass River SF", provider="NJ DEP", steward_kind="agency")], sets) == []


def test_another_agencys_notice_closes_nothing_on_a_line_it_does_not_steward():
    sets = _sets(("nps_trails:1", "nps_trails", "Laurel Falls Trail", 3.98))
    assert evaluate([_notice("Laurel Falls Trail", provider="USFS", steward_kind="agency")], sets) == []


def test_a_named_section_no_line_carries_is_listed():
    (outcome,) = evaluate(
        [_notice("Cumberland Trail - North Chickamauga Section", provider="TDEC", steward_kind="agency")], DOLL_RIDGE
    )
    assert (outcome.verdict, outcome.section) == ("no_line", "North Chickamauga")


def test_section_names_are_the_whole_title_and_up_to_four_words_before_section():
    names = section_names("Military Ridge ST Verona Section Closed")
    assert words("Military Ridge ST Verona Section Closed") in names
    assert ("verona",) in names and ("military", "ridge", "st", "verona") in names
    assert ("section",) not in names
