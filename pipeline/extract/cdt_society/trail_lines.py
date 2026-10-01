"""Continental Divide Trail Society: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c10_nst_rest).

`via` is null in the catalogue. The geometry is CDTC's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The CDT itself arrives as `cdtc_centerline` (CDTC, 8 polylines, registered 2026-09-30). The Society "
        "publishes no geometry of its own that I could reach.",
    ),
    where=("https://cdtsociety.org/",),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
