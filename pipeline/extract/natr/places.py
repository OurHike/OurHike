"""Natchez Trace NST (NPS-administered): places, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Deduplicate the 21 shared with `natt` against the NST unit's own places.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "API `/places`: 42. `/visitorcenters`: 4.",
        "Skeptic: not reproduced. `/places?parkCode=natr` returns `total` 125 today (all 125 fetched): 101 list"
        " only `natr`, 21 also list `natt` (Natchez Trace National Scenic Trail), and 3 also list `trte`.",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/natr/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
