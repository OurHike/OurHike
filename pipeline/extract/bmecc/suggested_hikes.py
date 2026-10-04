"""Blue Mountain Eagle Climbing Club: suggested hikes, the page the coverage audit read is gone (decision 54
wave 5, section K, 2026-10-04).

/activities/local-hikes, three member-written hikes on 2026-10-01, answered 404 on 2026-10-04.

The note this replaces read, whole:

Blue Mountain Eagle Climbing Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

None of the 3 is on the A.T. Low value.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/activities/local-hikes` (page): 3 member-written hikes (Nolde
Forest/Painted Turtle Pond, Gring's Mill, Tom Lowe Trail)

Its `where`: https://bmecc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://bmecc.org/activities/local-hikes: HTTP 404 (10 bytes), 2026-10-04T15:31:51Z; bmecc.org's robots.txt answers 404 (no rule)",
    ),
    where=("https://bmecc.org/",),
    reason="not found: the local hikes page answers HTTP 404",
)
