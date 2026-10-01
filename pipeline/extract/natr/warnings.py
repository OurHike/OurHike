"""Natchez Trace NST (NPS-administered): warnings, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

The endpoint exists and may be empty, which decision 14 allows for warnings. Skeptic spot-check: 0
confirmed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("The NPS alerts API Caution and Danger categories: 0 for `natr` today.",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/natr/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
