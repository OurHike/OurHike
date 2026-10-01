"""Batona Hiking Club: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

An event calendar is not a published hike description. Reconsider only if events ever get their own
mart.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://batona.wildapricot.org/RSS` is an RSS feed of upcoming events (group outings; "the '
        'description of the hike includes the meeting place, often accompanied by the GPS coordinates"). '
        "`/page-1652511` (Hiking Guide) is a liability and etiquette statement.",
    ),
    where=("https://batona.wildapricot.org/RSS",),
)
