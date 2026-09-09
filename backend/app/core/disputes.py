"""When the field contradicts upstream on upstream's own ground (#876).

features/FIELD_NOTES.md §4: ATC says there is a spring here, and there is no
spring here. A dispute is an observation VALUE - `not_found` sits beside
`dry` and `flowing` - and this module is the rule that turns a handful of
those into the one thing a card and a pin can say: *reported missing*.

WHY THE RULE LIVES ON THE SERVER, WHEN THE REST OF THE ROLL-UP DOES NOT

`client/src/lib/noteRollup.ts` computes the headline, the contested pair and
`last confirmed` at render time, from the public notes, on purpose. This one
cannot follow it, and the reason is a privacy decision rather than an
architectural preference: corroboration turns on **distinct accounts**, and
`FieldNoteOut` withholds `reporter_id` from everyone but the author and a
moderator. Many dated notes along a corridor from one identifier reconstruct
a hike (§6, and #252 for what removing that pair from reports cost).

So the identities never leave this process. What leaves is a verdict.

WHAT CORROBORATES, AND WHAT DECAYS

The doc's own rule, transcribed:

  enter   two `not_found` notes from distinct accounts on distinct days, or
          one from a maintainer whose assignment covers that mile
  leave   two independent confirming observations, or one maintainer's
  decay   to normal - never to *confirmed* - after a window with no
          corroboration, so one stale claim cannot mark a place forever

An upstream republish does not clear it: nothing in this module reads the
POI export at all, which is what makes that true by construction rather than
by discipline. ATC re-publishing its shelters layer says nothing about
whether the spring is there, and treating a rebuild as evidence would
quietly erase every dispute on a schedule.

WHY A THRESHOLD IS ACCEPTABLE HERE AT ALL

Value #4 normally argues for saying nothing rather than saying something
wrong, and any threshold invites gaming. The doc names what an attacker can
actually buy, and it is the reason this is affordable: the only state that
can be manufactured is **disputed** - never *removed*, never *confirmed
present*. The worst outcome of a successful attack on a water source is a
hiker who carries extra water. The reverse mistake is not symmetric, and is
the failure FEATURES.md calls wikitrail.org's founding story.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# --- The thresholds, and what would settle them ---------------------------
#
# @unvalidated Every number here is the design's own shape rather than a
# measurement, and there is nothing to measure yet: no hiker has filed a
# `not_found` note, because the client's picker deliberately does not offer
# one until this rule exists (client/src/lib/fieldNotes.ts records why). What
# would settle them is the first fifty real disputes and how many of them a
# source steward went on to confirm - the same corpus that settles
# staleness.ts's tiers, gathered the same way.

#: How many distinct accounts, on distinct days, enter the state.
CORROBORATING_NOTES = 2

#: The same, in the other direction. Symmetric on purpose: it should not be
#: harder to clear a mistaken dispute than it was to raise it, or the safe
#: direction the whole threshold rests on stops being safe.
CLEARING_NOTES = 2

#: How long a dispute stands with nothing new corroborating it. Decays to
#: NORMAL rather than to confirmed - the place goes back to whatever
#: upstream and the staleness tiers say, which is not a claim that the
#: spring is there.
#:
#: 180 days is the doc's "a window", picked to span a season: a spring
#: reported missing in April and never mentioned again should not still be
#: marked in October, and a stretch nobody walks between November and May
#: should not lose a live dispute to the winter.
DISPUTE_DECAY_DAYS = 180


@dataclass(frozen=True)
class DisputeInput:
    """One note, reduced to what the rule reads.

    `reporter_id` never leaves this process - see the module docstring. It is
    here because distinctness is the whole rule, and it is *hashed nowhere*:
    a per-POI pseudonym would be a second identifier on the wire, and this
    design does not need one.
    """

    reporter_id: str
    observed_at: datetime
    #: True for `not_found`; False for any observation that says the place is
    #: there. A note with no observation at all is neither and is not passed.
    disputes: bool
    #: Whether this reporter's maintainer assignment covers the note's mile.
    #: One of these outweighs the count in both directions - a maintainer is
    #: the person who would know.
    maintainer: bool = False


@dataclass(frozen=True)
class DisputeState:
    """What a card and a pin are entitled to say about a place."""

    #: True when the place is *reported missing* - the third value on
    #: WIREFRAMES.md §11's existence axis, never a fourth channel.
    reported_missing: bool
    #: How many distinct accounts have said so within the window. The card
    #: prints this ("2 hikers reported this missing"), so it counts ACCOUNTS
    #: rather than notes: two notes from one person is one observation.
    accounts: int
    #: The most recent disputing observation, for the card's "most recently
    #: 4 days ago". Null when nothing disputes this place.
    latest: datetime | None
    #: True when a covering maintainer is among the disputers - the card
    #: says so, because "the person who looks after this stretch says it is
    #: gone" is a different sentence from "two hikers did".
    maintainer_said: bool


def _distinct_accounts(notes: list[DisputeInput]) -> int:
    """How many independent observations these notes really are: one per account.

    THE DAY IS NOT PART OF THIS RULE, and used to look like it was. This
    function built a `(reporter, day)` set and then counted reporters out of
    it, which is arithmetically identical to counting reporters - collapsing
    on the pair first cannot change how many distinct reporters remain. The
    docstring claimed the pairing collapsed "two from hikers walking together
    on the same afternoon"; it never did, and
    `test_two_hikers_on_one_afternoon_are_close_to_one` has asserted the real
    behaviour (two accounts, one day, counts as 2) the whole time.

    So the dead half is gone rather than completed, and that is a decision
    rather than a tidy-up (maintainer, 2026-08-27). Requiring distinct DAYS
    would have made the rule stricter, and stricter is the dangerous direction
    for water: two hikers finding one spring dry on one afternoon in a drought
    is exactly the signal a map should act on, and suppressing it leaves a pin
    promising water that is not there. features/FIELD_NOTES.md §4 said
    "distinct accounts on distinct days" and now says what this does.

    What the rule still refuses is the thing it was always for: two notes from
    one account are one observation, however many days apart - see
    `test_the_same_account_twice_is_one_observation`.
    """
    return len({note.reporter_id for note in notes})


def dispute_state(notes: list[DisputeInput], now: datetime) -> DisputeState:
    """The verdict for one place, from every note about it.

    Ordering of the two rules is deliberate: clearing is checked against the
    notes that came AFTER the last dispute, so a place that was disputed,
    confirmed twice, and then disputed again is disputed - the most recent
    round of evidence wins, rather than a total tally that a place can never
    escape once it accumulates enough of either.
    """
    disputing = [note for note in notes if note.disputes]
    if not disputing:
        return DisputeState(reported_missing=False, accounts=0, latest=None, maintainer_said=False)

    latest = max(note.observed_at for note in disputing)

    # Decay first: past the window with nothing new, the place goes back to
    # normal. Not to confirmed - nobody said the spring is there.
    if now - latest > timedelta(days=DISPUTE_DECAY_DAYS):
        return DisputeState(reported_missing=False, accounts=0, latest=latest, maintainer_said=False)

    live = [note for note in disputing if now - note.observed_at <= timedelta(days=DISPUTE_DECAY_DAYS)]
    accounts = _distinct_accounts(live)
    maintainer_said = any(note.maintainer for note in live)
    entered = maintainer_said or accounts >= CORROBORATING_NOTES

    # Then clearing, and only from evidence NEWER than the last dispute: an
    # older confirmation is not an answer to a claim made after it.
    confirming = [note for note in notes if not note.disputes and note.observed_at > latest]
    cleared = any(note.maintainer for note in confirming) or (_distinct_accounts(confirming) >= CLEARING_NOTES)

    return DisputeState(
        reported_missing=entered and not cleared,
        accounts=accounts,
        latest=latest,
        maintainer_said=maintainer_said,
    )
