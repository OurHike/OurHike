"""The rules the challenge routes share (#1780, features/CHALLENGES.md).

`challenge` already means proof-of-work in this backend (`core/challenge.py`,
`ChallengeSpend`), so everything about a club's list of places is named
`trail_challenge` at the module level. The tables keep the design's own
names - `challenge_tags`, `challenge_entries`, `club_challenges` - because
those are what features/CHALLENGES.md and the client call them.

Four things live here rather than in the router because more than one route,
or the pull-request opener, has to agree about them: which strings are ids,
when a window has closed, how small a count is too small to show, and how a
cell in the finishers' CSV is kept from being read as a formula.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time, timedelta

#: A challenge id and an item id are lowercase words joined by hyphens.
#: Reasoned, not picked: it is `pipeline/lib/challenges.py`'s `_ID`, which
#: refuses any other id before it can reach the published artifact - so no
#: phone can hold an id this refuses, and a tag naming one is a tag of nothing.
#: It is also what makes a challenge id safe as a path segment in
#: `pipeline/reference/challenges/<slug>/<id>.json` and as a filename in a
#: Content-Disposition header, which is why it is enforced rather than hoped.
ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
ID_RE = re.compile(ID_PATTERN)

#: The columns are String(120); the id is refused at the wire before it would
#: be refused by Postgres.
ID_MAX_CHARS = 120

#: Below this many distinct hikers, a count the club sees is withheld (`null`)
#: rather than shown.
#:
#: Reasoned: EVENTING.md §6 sets "no published or stored cell below k = 25
#: devices", and this reuses its k for the same reason - a count of three
#: hikers in a club's own challenge is a description of three people the club
#: may well know by name. Reusing it rather than choosing a second number keeps
#: one floor for the whole project. Whether "Hikers in" should be shown at all
#: below the floor is features/CHALLENGES.md's open question, not settled here.
CHALLENGE_COUNT_FLOOR = 25

#: How far past the end of its closing date, in UTC, a window is still open.
#:
#: Reasoned. A window's `closes` is a calendar day in the hiker's own time
#: ("complete at least 25 items by September 1"), and this server compares in
#: UTC. The A.T. is four or five hours behind UTC, so comparing UTC dates
#: straight would refuse an entry sent at 9 p.m. on the closing day and flag a
#: tag written at camp that evening as late. Twelve hours is exactly the
#: furthest offset behind UTC in use (UTC-12), so the closing day has ended
#: everywhere on Earth at the instant this closes, and nowhere before. It was
#: a whole day until the review of 2026-09-30 found that accepted all of the
#: next day's daylight on the A.T. The cost that remains is the other
#: direction: in New York, anything sent before 8 a.m. the day after closing
#: is accepted and not flagged. That is the direction to be wrong in - the club
#: sees `sent_at` in its CSV and applies its own rule, where a hiker refused on
#: the last evening has nothing to appeal to. volunteer_hours' `worked_on`
#: gives the same day of leeway for the same reason.
CLOSE_LEEWAY = timedelta(hours=12)

#: Where a club's reviewed challenge files live. The pipeline reads
#: `reference/challenges/<org>/<id>.json` (pipeline/lib/challenges.py), and the
#: pull-request opener writes one file here and refuses any path outside the
#: club's own directory.
CHALLENGES_DIR = "pipeline/reference/challenges"

#: The characters that make a spreadsheet treat a cell as a formula. The four
#: the design names (= + - @) plus tab and carriage return, which OWASP's CSV
#: injection guidance adds because some spreadsheets strip them and then read
#: what follows as the start of the cell - and line feed, the same whitespace
#: argument, added in the review of 2026-09-30. The schema strips leading
#: whitespace from a name, but this helper is what the CSV actually relies on.
#: Full-width `＝` and its kin are caught by folding the cell with NFKC before
#: the check; whether any spreadsheet would run one is not known here, and
#: the quote costs a legitimate cell nothing.
_FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r", "\n")


def closed_from(closes: date) -> datetime:
    """The first instant (naive UTC) at which a window closing on `closes` is closed.

    One definition, so the entry refusal, the `late` flag on a tag and the
    console's count of late tags cannot draw the line in three places.
    """
    return datetime.combine(closes + timedelta(days=1), time.min) + CLOSE_LEEWAY


def has_closed(closes: date | None, moment: datetime) -> bool:
    """Whether `moment` (naive UTC) falls after the window that `closes` ends.

    `None` never closes: a challenge with no closing date is a record a hiker
    keeps for as long as they like (features/CHALLENGES.md's `window`).
    """
    if closes is None:
        return False
    return moment >= closed_from(closes)


#: Spelled out rather than `%B`, which follows the server process's locale -
#: and this sentence is English whatever the container was started with.
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def closed_sentence(closes: date) -> str:
    """The refusal the phone shows verbatim, with the date as a person writes it."""
    return f"Entries for this challenge closed on {_MONTHS[closes.month - 1]} {closes.day}, {closes.year}."


def challenge_dir(slug: str) -> str:
    """The directory holding one club's reviewed challenge files."""
    return f"{CHALLENGES_DIR}/{slug}"


def challenge_file(slug: str, challenge_id: str) -> str:
    """The one path a club's challenge is written to."""
    return f"{challenge_dir(slug)}/{challenge_id}.json"


def spreadsheet_safe(cell: str) -> str:
    """A cell a spreadsheet will show rather than run.

    The finishers' CSV is opened by an organization in Excel or Google Sheets,
    and every text column in it was typed by somebody else - a name, a mailing
    address. A name of `=HYPERLINK("https://…","click")` would otherwise
    arrive in the club's spreadsheet as a live formula (CSV injection). A
    leading single quote is the convention both spreadsheets read as "this is
    text", and it costs a legitimate cell nothing but the quote.
    """
    # Read the lead after NFKC folding, so a full-width `＝` is judged as the
    # `=` some spreadsheets will fold it to - and write the cell unchanged.
    if cell and unicodedata.normalize("NFKC", cell).startswith(_FORMULA_LEADS):
        return "'" + cell
    return cell
