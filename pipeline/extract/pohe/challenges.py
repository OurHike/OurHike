"""Potomac Heritage Trail Association: challenges, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

Belongs in the `nps` folder. Skeptic spot-check: `total` 16.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("NPS `/passportstamplocations`: 16 for `pohe`.",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/pohe/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
