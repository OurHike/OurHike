"""Central Iowa Trail Association: challenges, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The "Dirty Duathlon & Trail Fest" is a race event, not a challenge. (Skeptic: none of the 121 sitemap '
        "URLs is a challenge, patch or award page.)",
    ),
    where=(
        "https://services.arcgis.com/HT7H9QGiZQoRJDpJ/arcgis/rest/services",
        "https://bikecita.org/",
    ),
)
