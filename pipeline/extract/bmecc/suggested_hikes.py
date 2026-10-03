"""Blue Mountain Eagle Climbing Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

None of the 3 is on the A.T. Low value.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/activities/local-hikes` (page): 3 member-written hikes (Nolde Forest/Painted Turtle Pond, Gring's "
        "Mill, Tom Lowe Trail)",
    ),
    where=("https://bmecc.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
