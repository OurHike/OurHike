"""National Park Service: photos, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Licence is per asset, so filter on `constraintsInfo.constraint == 'Public domain'`. NPGallery was
not opened.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "API `/multimedia/galleries`: 10,507 galleries. Each has `constraintsInfo` (all 3 sampled read `Public "
        'domain`) and a copyright line: "Permission must be secured from the individual copyright owners…".',
    ),
    where=("https://nps.gov/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
