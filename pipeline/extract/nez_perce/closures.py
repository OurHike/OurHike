"""Nez Perce (Nee-Me-Poo) Trail Foundation: closures, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Format is a page. No feed was found (Unvalidated whether the new fs.usda.gov site exposes one)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.fs.usda.gov/trails/nez-perce-nht/alerts` (page). Key: Critical / Fire Restriction / "
        'Caution / Information. "No Featured Alerts at this Time" on 2026-10-01',
    ),
    where=(
        "https://www.fs.usda.gov/trails/nez-perce-nht/alerts",
        "https://fs.usda.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
