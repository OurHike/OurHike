"""AMC Delaware Valley Chapter: places, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Marginal, and mostly off the A.T.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/leadership/trailheads/` (page, 2021-05-05): Google Maps coordinate links for state-park trailheads "
        "in DE, NJ and PA. The `/assets/hikeparking.kml` it links returns 404.",
    ),
    where=("https://amcdv.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
