"""Sheltowee Trace Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

The programme only. The registry PDFs and XLSX are names.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Hiker Challenge (`/hiker-challenge`): "343 Miles. 11 Months.", "Over 650 participants have completed '
        'the Challenge". E2E Registry: certificate, patch, rocker and mileage decal '
        "(`/e2e-awards-and-recognition`).",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://sheltoweetrace.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
