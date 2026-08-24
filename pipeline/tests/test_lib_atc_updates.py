"""What makes a reviewed ATC update publishable, and what must stop the bake.

The rows in `reference/atc_updates.json` are typed by hand and validated by
nothing else - they never reach the closures table, so no database constraint
ever sees them. These are the checks that stand in for one, and the cases
below are the ones features/ATC_TRAIL_UPDATES.md measured rather than
imagined.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.atc_scrape import MileReference, ParsedUpdate
from lib.atc_updates import (
    REVIEWED,
    TRAIL_MILE_MAX,
    UNREVIEWED,
    auto_publish_refusal,
    auto_row,
    file_problems,
    is_reviewed,
    published_rows,
    row_problems,
)

REVIEWED_FILE = Path(__file__).resolve().parents[1] / "reference" / "atc_updates.json"


def row(**overrides) -> dict:
    """One real update from ATC's page (measured 2026-08-09), as a base."""
    return {
        "atc_id": "va-creeper-trail-closure-detour",
        "title": "SW Virginia: VA Creeper Trail Closure/Detour",
        "category": "Closure",
        "states": ["VA"],
        "start_mile_marker": 476.6,
        "end_mile_marker": 485.8,
        "obstructs_trail": True,
        "updated_at": "2026-07-17T00:00:00Z",
        "source_url": "https://appalachiantrail.org/trail-updates/va-creeper/",
        **overrides,
    }


def test_a_real_atc_update_passes():
    assert row_problems(row()) == []


def test_a_point_closure_is_not_a_broken_range():
    """ATC publishes several - a shelter, a footbridge. Both markers hold the
    same mile, and lib/closureSpan.ts reads that as a zero-length span."""
    assert row_problems(row(start_mile_marker=1503.6, end_mile_marker=1503.6)) == []


# --- The failure that actually happened ------------------------------------


def test_a_mile_off_the_end_of_the_trail_is_refused():
    """The thousands-separator bug, caught as data rather than as a parse.

    `NOBO mile 1,503.6` read without the comma is mile 1: a Connecticut
    shelter drawn in Georgia. That value is *inside* the trail extent, so
    this check does not catch that one - what it catches is the other half of
    the same class, a decimal-point slip that lands off the trail entirely,
    where the alternative is a band drawn in the ocean.
    """
    problems = row_problems(row(start_mile_marker=15036.0, end_mile_marker=15036.0))

    assert any("outside the trail's own extent" in problem for problem in problems)


def test_the_far_end_of_the_trail_is_still_on_it():
    """A boundary that excluded Katahdin would refuse the one update nobody
    would think to re-check."""
    assert row_problems(row(start_mile_marker=TRAIL_MILE_MAX, end_mile_marker=TRAIL_MILE_MAX)) == []


def test_a_reversed_range_is_refused_rather_than_swapped():
    """Silently swapping would draw a band that looks right and was entered
    wrong, and the range the reviewer meant is not recoverable from it."""
    problems = row_problems(row(start_mile_marker=485.8, end_mile_marker=476.6))

    assert any("before start_mile_marker" in problem for problem in problems)


def test_a_javascript_url_is_refused():
    """chrome/ClosureSheet.tsx enforces this on the way out; refusing it here
    means the client's guard is a second line rather than the only one."""
    problems = row_problems(row(source_url="javascript:alert(1)"))

    assert any("not an http(s) URL" in problem for problem in problems)


def test_a_category_atc_does_not_publish_is_refused():
    """Their page changing shape is a thing to look at, not a word to pass
    through to a hiker."""
    problems = row_problems(row(category="Emergency"))

    assert any("is not one ATC publishes" in problem for problem in problems)


@pytest.mark.parametrize(
    "category",
    ["Water", "Relocation", "Permits", "Construction", "Fire", "Conservation"],
)
def test_the_categories_only_page_ten_ever_showed_are_accepted(category):
    """The six words the page-one reviews never saw (#945).

    Read off ATC's live listing on 2026-08-24, all ten pages: every one of
    these appears on at least one of the 89 updates that were up that day.
    They are pinned here because the reason they were missing is the reason
    worth not repeating - not that the list was too short, but that nobody
    had read past the first page of nine.

    `Water` and `Fire` are the two that matter most: a closed well and a burn
    ban are the water and fire paths CLAUDE.md names, and a category refusal
    on either would have stopped the whole file baking.
    """
    assert not row_problems(row(category=category))


@pytest.mark.parametrize(
    "field",
    ["atc_id", "title", "category", "states", "start_mile_marker", "end_mile_marker", "updated_at", "source_url"],
)
def test_every_field_is_required(field):
    missing = row()
    del missing[field]

    assert any(f"missing {field}" in problem for problem in row_problems(missing))


def test_a_missing_mile_is_not_reported_twice():
    """Once as missing, not again as un-placeable. A person fixing the file
    should see one problem per problem."""
    missing = row()
    del missing["start_mile_marker"]

    problems = row_problems(missing)
    assert problems == ["missing start_mile_marker"]


def test_a_row_reports_everything_wrong_with_it_at_once():
    """Peeling one message per run is how a five-minute fix becomes five."""
    problems = row_problems(row(category="Emergency", source_url="ftp://example.test/x"))

    assert len(problems) == 2


def test_an_atc_id_used_twice_is_refused():
    """It keys a band on the map and finds the row again in review. Two rows
    sharing one renders as one update quietly replacing another."""
    problems = file_problems({"updates": [row(), row()]})

    assert any("appears more than once" in problem for problem in problems)


def test_a_bad_row_is_named_by_its_atc_id():
    """The message has to say which row, or a nine-row file is a hunt."""
    problems = file_problems({"updates": [row(category="Emergency")]})

    assert problems[0].startswith("va-creeper-trail-closure-detour: ")


def test_a_file_with_no_updates_list_is_refused_outright():
    assert file_problems({}) == ["`updates` is missing or is not a list"]


# --- Reviewed, versus merely present ---------------------------------------


def test_an_empty_file_with_no_review_date_is_not_reviewed():
    """ "Nobody has looked" and "we looked and ATC has nothing placeable" are
    different claims, and only the second may be published."""
    assert not is_reviewed({"reviewed_at": None, "updates": []})


def test_an_empty_file_a_person_dated_is_reviewed():
    assert is_reviewed({"reviewed_at": "2026-08-12", "updates": []})


def test_a_blank_review_date_does_not_count():
    assert not is_reviewed({"reviewed_at": "   ", "updates": []})


# --- What actually ships ---------------------------------------------------


def test_only_the_published_fields_reach_the_artifact():
    """A note a reviewer left themselves - or ATC body text somebody pasted
    in while working - must not reach the bucket because it was in the file.
    What ships is the field list, and nothing else."""
    rows = published_rows({"updates": [row(note_to_self="check this against the detour map", body="ATC's paragraph")]})

    assert set(rows[0]) == {
        "atc_id",
        "title",
        "category",
        "states",
        "start_mile_marker",
        "end_mile_marker",
        "obstructs_trail",
        "updated_at",
        "source_url",
        # Added by the projection rather than read from the file (#963). A row
        # in the reviewed file is reviewed by definition - that is what the
        # file IS - so a reviewer never types this, and a stale or mistyped
        # value can never claim a row was checked when it was not.
        "review_state",
    }
    assert rows[0]["review_state"] == REVIEWED


# --- The file this repository actually ships -------------------------------


def test_the_shipped_reviewed_file_is_valid_json_with_the_expected_shape():
    document = json.loads(REVIEWED_FILE.read_text())

    assert isinstance(document["updates"], list)
    assert "source_marker" in document, "check_freshness.py reads this to know when to ask for a re-review"


def test_the_shipped_reviewed_file_has_no_unpublishable_rows():
    """Whatever it holds - none today, nine after somebody reviews - has to
    pass. This is the test that fails on the pull request that adds the rows,
    which is the moment it is worth failing."""
    assert file_problems(json.loads(REVIEWED_FILE.read_text())) == []


# --- The field ATC's own categories cannot answer -------------------------


def test_obstructs_trail_is_required():
    """Not defaulted, because the default would be a guess about whether a
    hiker can walk through."""
    missing = row()
    del missing["obstructs_trail"]

    assert any("missing obstructs_trail" in problem for problem in row_problems(missing))


def test_obstructs_trail_must_be_a_real_boolean():
    problems = row_problems(row(obstructs_trail="yes"))

    assert any("must be true or false" in problem for problem in problems)


def test_atcs_category_does_not_answer_whether_the_trail_is_passable():
    """The live case that removed the category-based rule, as ATC actually
    filed it on 2026-08-12.

    The two rows below are the whole argument. The only notice ATC files as
    `Closure` is a closed SHELTER, with the trail past it open; the one thing
    that genuinely stops a hiker - the way across the Potomac - is filed as
    `Detour`. So the old rule ("draw `Closure` and `Detour`") was wrong in
    both directions at once: it would have barred open trail at Limestone
    Spring, and it caught the real obstruction only because `Detour` happened
    to be on its list.

    Written from the live page rather than from memory of it. The first
    version of this test said both were `Closure`, which is the tidier story
    and not the one ATC published.
    """
    shelter = row(
        atc_id="connecticut-limestone-spring-shelter-closed",
        title="Connecticut: Limestone Spring Shelter Closed",
        category="Closure",
        states=["CT"],
        start_mile_marker=1503.6,
        end_mile_marker=1503.6,
        obstructs_trail=False,
    )
    footbridge = row(
        atc_id="harpers-ferry-footbridge-closure",
        title="Harpers Ferry: Footbridge Closure",
        category="Detour",
        states=["MD", "WV"],
        start_mile_marker=1026.7,
        end_mile_marker=1026.7,
        obstructs_trail=True,
    )

    assert row_problems(shelter) == []
    assert row_problems(footbridge) == []
    # The `Closure` is the one that does NOT obstruct, which is the whole
    # point: sorting on the category gets both of these backwards.
    assert shelter["category"] == "Closure" and not shelter["obstructs_trail"]
    assert footbridge["category"] == "Detour" and footbridge["obstructs_trail"]


# --- The auto-publish gate (#963) -------------------------------------------
#
# What these are about: `reference/atc_updates.json` only moves when a pull
# request merges, so a notice ATC posted on a Wednesday reached a hiker
# whenever somebody next happened to look. The gate below is what lets the
# hourly job publish the unambiguous ones without a person, and every case
# here is a way that could go wrong on a safety surface.


def parsed(**overrides) -> ParsedUpdate:
    """One update as `lib/atc_scrape.py` hands it over - ATC's real War Spur
    notice, which is the simplest true example there is: one mile, a category
    this build knows, and prose that announces a condition rather than its
    end."""
    fields = {
        "slug": "central-va-war-spur-bridge-closed",
        "title": "Central VA: War Spur Bridge Closed",
        "category": "Closure",
        "states": ["VA"],
        "date_modified": "2026-08-19T16:22:50-04:00",
        "date_published": "2026-08-19T16:22:50-04:00",
        "miles": [MileReference("NOBO", 670.2, None, "NOBO mile 670.2")],
        "text": "The War Spur Branch Bridge is closed due to structural failure.",
        **overrides,
    }
    return ParsedUpdate(**fields)


def test_an_update_atc_posted_since_the_review_publishes_itself():
    assert auto_publish_refusal(parsed(), set(), "2026-08-12") is None


def test_an_update_older_than_the_review_is_refused():
    """The rule the whole gate turns on, and the one measurement that put it
    there.

    Run against ATC's real 89 updates on 2026-08-24 WITHOUT this rule, the
    gate published 22 rows - and they were very nearly the exact set the
    reviewer had just decided to leave out: twelve bear incidents from 2024
    and 2025, a hunting season its own text ends on 2025-12-31, four vehicle
    break-ins, a duplicate of a closure already carried.

    That is structural rather than unlucky. After a review, everything still
    unreviewed IS the reject pile, so "publish what parses and is not
    reviewed" is a rule for publishing rejects.
    """
    refusal = auto_publish_refusal(parsed(), set(), "2026-08-24")

    assert refusal is not None and "not since the review" in refusal


def test_a_reviewed_slug_is_never_overwritten_by_a_parse():
    """A person may have corrected the mile, given it a band, or decided it
    does not belong. None of that survives being overwritten."""
    refusal = auto_publish_refusal(parsed(), {"central-va-war-spur-bridge-closed"}, "2026-08-12")

    assert refusal is not None and "already reviewed" in refusal


def test_mile_references_that_disagree_are_refused_rather_than_guessed_between():
    """Iron Mtn Gap states five ranges accumulated over months of edits, and
    the current one is not mechanically distinguishable from its own history
    (#463). Taking the first would be a coin toss with a hiker's location."""
    refusal = auto_publish_refusal(
        parsed(
            miles=[
                MileReference("NOBO", 360.6, 364.8, "NOBO mile 360.6 to 364.8"),
                MileReference("NOBO", 361.2, None, "NOBO mile 361.2"),
            ]
        ),
        set(),
        "2026-08-12",
    )

    assert refusal is not None and "do not agree" in refusal


def test_the_gate_refuses_a_mile_off_the_end_of_the_trail():
    """The same class as the reviewed-file check far above, on the automatic
    path: a decimal-point slip that lands past Katahdin is not a location, and
    the alternative is a pin drawn in the ocean with nobody having read it."""
    refusal = auto_publish_refusal(
        parsed(miles=[MileReference("NOBO", TRAIL_MILE_MAX + 10, None, "NOBO mile 2207.5")]),
        set(),
        "2026-08-12",
    )

    assert refusal is not None and "outside the trail's own extent" in refusal


@pytest.mark.parametrize(
    "wording",
    [
        "The gap has reopened and the trail is passable.",
        "The relocation is complete and the new route is open.",
        "The burn ban has been lifted for the season.",
    ],
)
def test_an_all_clear_publishes_rather_than_being_refused(wording):
    """The refusal this replaced was wrong about live notices more often than
    it was right about dead ones.

    Measured against the 22 updates ATC had edited in the previous 90 days it
    caught two, and BOTH were current: Andy Layne's "is complete" sits above a
    live road-walk, and Max Patch's "has been completed" is inside a camping
    closure running to 2029. The VA Creeper - nine miles of A.T. shut until
    2027 - says "will reopen" and would have gone too.

    Dropping it is safe because an automatic row carries ATC's own headline
    verbatim, so an all-clear publishes as one, and `auto_row` forces
    `obstructs_trail` false whatever the words say.
    """
    assert auto_publish_refusal(parsed(text=wording), set(), "2026-08-12") is None


def test_the_same_mile_stated_twice_is_not_a_disagreement():
    """ATC restates a location as they edit, and the rule this replaced could
    not tell repetition from ambiguity: the Harpers Ferry footbridge closure
    carries `NOBO mile 1,026.7` in both its 2026 and 2025 sections, and was
    held back as though the two pointed somewhere different."""
    twice = parsed(
        miles=[
            MileReference("NOBO", 1026.7, None, "NOBO mile 1,026.7"),
            MileReference("NOBO", 1026.7, None, "NOBO mile 1,026.7"),
        ]
    )

    assert auto_publish_refusal(twice, set(), "2026-08-12") is None
    assert auto_row(twice)["start_mile_marker"] == 1026.7


def test_a_category_this_build_does_not_know_is_refused():
    """A new word means ATC changed the shape of their page - which is how
    six categories went unnoticed until #945 read past page one."""
    refusal = auto_publish_refusal(parsed(category="Emergency"), set(), "2026-08-12")

    assert refusal is not None and "not one this build knows" in refusal


def test_an_automatic_row_can_never_draw_a_band():
    """`obstructs_trail` is forced false and read from nothing, even on a row
    ATC files as `Closure`.

    Whether a hiker is STOPPED is the judgement `lib/atc_updates.py` measured
    as underivable from ATC's category: their only `Closure` on 2026-08-12 was
    a shelter with open trail past it, while the Harpers Ferry footbridge,
    which genuinely stops a hiker, is filed `Detour`. So an unread notice gets
    a dot and a banner, and a barrier stays something a person puts there.
    """
    built = auto_row(parsed(category="Closure", text="The trail is closed here."))

    assert built["obstructs_trail"] is False
    assert built["review_state"] == UNREVIEWED


def test_an_automatic_rows_timestamp_is_utc_like_every_reviewed_one():
    """ATC's JSON-LD carries a local offset; a reviewed row carries UTC
    because a person converted it. Two spellings of one instant in a single
    artifact would make `updated_at` sortable only by accident."""
    assert auto_row(parsed())["updated_at"] == "2026-08-19T20:22:50Z"
