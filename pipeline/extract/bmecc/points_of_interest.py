"""Blue Mountain Eagle Climbing Club: points of interest, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Shelters and parking overlap ATC's loaded layers, so dedupe in intermediates (Round 5). The springs
are the new data: no ATC layer we load has springs (Reasoned from the sources.json key list). The
501 and Windsor Furnace findings above come from this page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Same KML (machine-readable): Parking 20, Shelters 9, Campsites 4, Springs 16, Vistas 34, Access Points"
        " 7. Plus `https://www.bmecc.org/appalachian-trail/shelters` (HTML page): 8 shelters with build year, "
        'water ("Yeich Spring", "3 springs… not very reliable… usually reliable except extreme drought"), '
        'privy, caretaker, and "sleeps N" for 5 of them',
    ),
    where=("https://www.bmecc.org/appalachian-trail/shelters",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
