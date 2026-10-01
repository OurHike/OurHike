"""Santa Fe Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("NTIR POIs `safe` 120. `NPSAGOL/SAFE_place_names_20170420`: 170 points",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://santafetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
