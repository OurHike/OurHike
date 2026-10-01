"""AMC Delaware Valley Chapter: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The verdict holds (Reasoned: a report of one past outing is not a published hike).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The only write-up linked, `/assets/mohican-area-hikes.pdf`, returns 404. Hiking and backpacking pages describe events.",
        'Skeptic, 2026-10-01: the posts in `activities` include trip reports of past led trips, e.g. "Bucktail '
        'Path" (2022-07-07, a photo report of an Elk State Forest backpack) and "Exploring the Tunnels of '
        'Conestoga" (2022-03-19). They are reports, not routes.',
    ),
    where=("https://amcdv.org/",),
)
