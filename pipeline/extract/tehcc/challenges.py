"""Tennessee Eastman Hiking & Canoeing Club: challenges, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

One programme, two publishers. Recommendation: extract once, under `cmc` (fuller list), with
`co_publisher: tehcc` (Reasoned). TEHCC's "AT 2000 Miler" and "Smokies 900 Miler" pages are only
rosters of members who finished other programmes.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "South Beyond 6000 (SB6K): 40 peaks above 6,000 ft, founded by TEHCC and co-sponsored with CMC "
        "(`https://tehcc.org/hiking/challenges/south-beyond-6000/`). Details and the peak list live on CMC's "
        'site. The wiki page "South Beyond 6000" holds 1 `Challenge Item` (Roan High Bluff, stored as '
        "`36.0932,82.1455`, longitude missing its minus sign).",
    ),
    where=("https://tehcc.org/hiking/challenges/south-beyond-6000/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
