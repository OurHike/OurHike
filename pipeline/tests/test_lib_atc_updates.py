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

from lib.atc_updates import (
    TRAIL_MILE_MAX,
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
    }


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


def test_two_closures_can_disagree_about_obstructing_the_trail():
    """The live case that removed the category-based rule (2026-08-12). ATC
    files both of these as `Closure`, and they are opposite answers to the only
    question a band asks - the trail past Limestone Spring is open and the
    shelter is shut, while the way across the Potomac is gone."""
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
        category="Closure",
        states=["WV"],
        start_mile_marker=1026.7,
        end_mile_marker=1026.7,
        obstructs_trail=True,
    )

    assert row_problems(shelter) == []
    assert row_problems(footbridge) == []
    assert shelter["category"] == footbridge["category"]
    assert shelter["obstructs_trail"] != footbridge["obstructs_trail"]
