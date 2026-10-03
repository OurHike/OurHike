"""NC Division of Parks & Recreation — NC Trails: suggested hikes, published, and not landed (coverage
audit 2026-10-01, batch c9_federal_state_rest).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`ncparks.gov/state-parks/<park>/trails` pages; `trails.nc.gov/state-trails/<trail>` (15 trail pages); "
        "the `WEBLINK` field on `State_Trails`.",
    ),
    where=(
        "https://ncparks.gov/state-parks/",
        "https://trails.nc.gov/state-trails/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
