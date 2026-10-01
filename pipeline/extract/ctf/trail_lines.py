"""Colorado Trail Foundation: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c7_regional_4).

No CTF-owned ArcGIS.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The Colorado Trail is 159 features in COTREX (catalogue, 2026-09-17). The CTF's own geometry, per "
        'search: the FarOut app (`/product/farout-app/`), the Map Book and a "CT 11x17 Map – Digital Download".'
        " All paid.",
    ),
    where=("https://coloradotrail.org/",),
    reason="drawn from cotrex/'s resources, extracted once there (decision 34); checked names the layer this org's "
    "data arrives in",
)
