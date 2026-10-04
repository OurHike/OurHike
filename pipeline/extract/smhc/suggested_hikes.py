"""Smoky Mountains Hiking Club: suggested hikes, published as dated events, and not landed (decision 54 wave 5,
section K, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and not a
challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

/Upcoming-Events is the club's Wild Apricot event list, outings with registration; the 2026 Member Handbook is an
embedded flipbook.

The note this replaces read, whole:

Smoky Mountains Hiking Club: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

SOURCE_SURVEY.md's "NEEDS REVIEW" on the handbook is still open. It was not opened here. (skeptic)
Missed channel: the club's own monthly newsletter, `https://smhclub.org/SMHC-Newsletters` (PDFs
`/resources/Documents/smhc_newsletters/<YYYY>/SMHC-<MMYY>.pdf`, 2022–2026; `SMHC-1026.pdf` is 3,623,232
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/Upcoming-Events` (Wild Apricot event list) holds outings with
descriptions and locations. The 2026 Member Handbook (`/page-18237`) is an embedded flipbook.

Its `where`: https://smhclub.org/SMHC-Newsletters https://smhclub.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://smhclub.org/Upcoming-Events (HTTP 200, 569,872 bytes, 2026-10-04T17:40:04Z): 'Upcoming events' and 'Past events'",
    ),
    where=("https://smhclub.org/Upcoming-Events",),
    reason="not this type: dated group hikes, which the lead ruled are not suggested hikes (2026-10-04)",
)
