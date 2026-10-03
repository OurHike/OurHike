"""Colorado Mountain Club: points of interest, could not be told (coverage audit 2026-10-01, batch
p06_persist).

Gated, not absent, so it stays UNKNOWN. Only CMC can say whether RIMS data will be served again.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The RIMS campsite and trail-assessment data exists but is gated. The 10 of 10 services above answer "
        '499. The skeptic found 6 of 6 items answering "Subscription is disabled, the item is not accessible". '
        'ArcGIS Online `"Recreation Impact Monitoring System"`: 0. `RIMS campsite inventory`: 1, and it is not '
        "CMC's (ATC Conservancy's \"Campsite Sustainability Index\"). No land-manager copy of the Hartman Rocks, "
        "Dominguez-Escalante NCA or Decalibron assessments was found. Tried: 1, 2, 4 (searched for the managers"
        " those items name), 5 (data.gov `Colorado Mountain Club campsite` 0), 6 (not fetched).",
    ),
    where=("https://data.gov",),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
