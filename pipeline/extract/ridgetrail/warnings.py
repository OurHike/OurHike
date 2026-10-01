"""Bay Area Ridge Trail Council: warnings, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Do not load: it is personal data. It is listed only so the record is complete.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("The Survey123 hazard-report layer (7 records, 2024).",),
    where=(
        "https://services5.arcgis.com/6iLCtMhqIxD1wlgk/arcgis/rest/services",
        "https://ridgetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
