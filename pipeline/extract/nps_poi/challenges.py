"""National Park Service: challenges, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

The Passport booklet is sold by a partner. The stamp locations are free API data. Skeptic correction
(Measured): a `/passportstamplocations` row has no coordinates of its own, only `label`, `parks[]`
and a `type` such as `visitorcenters`. To place a stamp, join it to `/visitorcenters` or …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "API `/passportstamplocations`: 1,092 stamp locations. Park pages such as "
        "`nps.gov/neri/planyourvisit/new-river-gorge-100-mile-challenge.htm`.",
    ),
    where=("https://nps.gov/neri/planyourvisit/new-river-gorge-100-mile-challenge.htm",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
