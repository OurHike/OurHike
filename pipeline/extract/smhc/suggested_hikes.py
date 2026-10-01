"""Smoky Mountains Hiking Club: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

SOURCE_SURVEY.md's "NEEDS REVIEW" on the handbook is still open. It was not opened here. (skeptic)
Missed channel: the club's own monthly newsletter, `https://smhclub.org/SMHC-Newsletters` (PDFs
`/resources/Documents/smhc_newsletters/<YYYY>/SMHC-<MMYY>.pdf`, 2022–2026; `SMHC-1026.pdf` is
3,623,232 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/Upcoming-Events` (Wild Apricot event list) holds outings with descriptions and locations. The 2026 "
        "Member Handbook (`/page-18237`) is an embedded flipbook.",
    ),
    where=(
        "https://smhclub.org/SMHC-Newsletters",
        "https://smhclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
