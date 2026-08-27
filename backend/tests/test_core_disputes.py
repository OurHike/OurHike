"""The corroboration rule (#876, features/FIELD_NOTES.md §4).

Pure, so these cases are the rule itself rather than a route exercising it.
What they hold, in the doc's own order:

  - **Distinctness beats count, and distinctness means ACCOUNTS.** Two notes
    from one account is one observation, however many days apart. Two from
    hikers walking together on one afternoon are two - correlated, and the
    rule does not try to detect a group. FIELD_NOTES.md §4 described a
    distinct-DAYS rule until 2026-08-27; no code ever implemented one, and
    the doc was corrected to match these tests rather than the reverse.
  - **A covering maintainer outweighs the count**, in both directions. They
    are the person who would know.
  - **Decay goes to normal, never to confirmed.** One stale claim cannot
    mark a place forever, and its expiry is not evidence the spring is back.
  - **Clearing reads only what came after the last dispute.** An older
    confirmation is not an answer to a claim made after it.
"""

from datetime import datetime, timedelta, timezone

from app.core.disputes import DISPUTE_DECAY_DAYS, DisputeInput, dispute_state

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def note(reporter: str, *, days_ago: int, disputes: bool = True, maintainer: bool = False) -> DisputeInput:
    return DisputeInput(
        reporter_id=reporter,
        observed_at=NOW - timedelta(days=days_ago),
        disputes=disputes,
        maintainer=maintainer,
    )


def test_a_place_nobody_disputes_says_nothing():
    state = dispute_state([note("a", days_ago=1, disputes=False)], NOW)

    assert state.reported_missing is False
    assert state.accounts == 0
    assert state.latest is None


def test_one_hiker_is_not_enough():
    """One person saying a spring is gone is a note, not a state. The card
    still shows the note - this is only about the pin."""
    assert dispute_state([note("a", days_ago=1)], NOW).reported_missing is False


def test_two_distinct_accounts_enter_it():
    state = dispute_state([note("a", days_ago=5), note("b", days_ago=1)], NOW)

    assert state.reported_missing is True
    assert state.accounts == 2
    assert state.latest == NOW - timedelta(days=1)
    assert state.maintainer_said is False


def test_the_same_account_twice_is_one_observation():
    """Distinctness matters more than count - the doc's own words, and the
    difference between a corroboration rule and a click counter."""
    assert dispute_state([note("a", days_ago=5), note("a", days_ago=1)], NOW).reported_missing is False


def test_two_hikers_on_one_afternoon_are_close_to_one():
    """Two people walking together see one spring once. Collapsed by counting
    a (reporter, day) pair once and then counting accounts, which needs no
    knowledge of who walked with whom."""
    assert dispute_state([note("a", days_ago=1), note("b", days_ago=1)], NOW).accounts == 2
    # ^ they are still two accounts; what the pairing collapses is the same
    # account reporting twice in a day. The doc says "close to one" rather
    # than "one", and this rule deliberately does not try to detect a group.


def test_the_day_is_not_part_of_the_rule():
    """Pins the shape rather than only the outcome.

    `_distinct_accounts` used to collect a `(reporter, day)` pair and then
    count reporters out of it - the same number by construction, dead
    arithmetic that read like a distinct-days rule and was documented as one
    for months. These two cases have identical accounts and a different
    spread of days, so they part company the moment somebody restores it.
    """
    one_afternoon = [note("a", days_ago=1), note("b", days_ago=1)]
    two_days = [note("a", days_ago=5), note("b", days_ago=1)]

    assert dispute_state(one_afternoon, NOW).accounts == 2
    assert dispute_state(two_days, NOW).accounts == 2
    assert dispute_state(one_afternoon, NOW).reported_missing is True
    assert dispute_state(two_days, NOW).reported_missing is True


def test_one_covering_maintainer_is_enough_on_their_own():
    state = dispute_state([note("m", days_ago=2, maintainer=True)], NOW)

    assert state.reported_missing is True
    assert state.maintainer_said is True


def test_two_confirmations_clear_it():
    state = dispute_state(
        [
            note("a", days_ago=10),
            note("b", days_ago=9),
            note("c", days_ago=2, disputes=False),
            note("d", days_ago=1, disputes=False),
        ],
        NOW,
    )

    assert state.reported_missing is False


def test_one_maintainer_clears_it_alone():
    state = dispute_state(
        [note("a", days_ago=10), note("b", days_ago=9), note("m", days_ago=1, disputes=False, maintainer=True)],
        NOW,
    )

    assert state.reported_missing is False


def test_a_confirmation_older_than_the_dispute_does_not_answer_it():
    """The ordering rule. Somebody confirming a spring in June says nothing
    about two hikers finding it gone in August."""
    state = dispute_state(
        [
            note("c", days_ago=30, disputes=False),
            note("d", days_ago=29, disputes=False),
            note("a", days_ago=5),
            note("b", days_ago=4),
        ],
        NOW,
    )

    assert state.reported_missing is True


def test_a_place_disputed_again_after_being_cleared_is_disputed():
    """The most recent round of evidence wins, rather than a total tally a
    place can never escape once it accumulates enough of either."""
    state = dispute_state(
        [
            note("a", days_ago=40),
            note("b", days_ago=39),
            note("c", days_ago=30, disputes=False),
            note("d", days_ago=29, disputes=False),
            note("e", days_ago=3),
            note("f", days_ago=2),
        ],
        NOW,
    )

    assert state.reported_missing is True


def test_it_decays_to_normal_rather_than_to_confirmed():
    state = dispute_state(
        [note("a", days_ago=DISPUTE_DECAY_DAYS + 10), note("b", days_ago=DISPUTE_DECAY_DAYS + 9)],
        NOW,
    )

    # Not marked - one stale claim cannot mark a place forever.
    assert state.reported_missing is False
    # And decidedly not a claim that the spring is back: the expiry of a
    # dispute is not evidence of anything.
    assert state.accounts == 0


def test_a_dispute_refreshed_inside_the_window_stands():
    state = dispute_state(
        [note("a", days_ago=DISPUTE_DECAY_DAYS + 10), note("b", days_ago=2), note("c", days_ago=1)],
        NOW,
    )

    assert state.reported_missing is True
    # The stale one does not count toward the two; the two recent ones do.
    assert state.accounts == 2
