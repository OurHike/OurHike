"""Buckeye Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Restricted. Every row needs decision 7's `obstructs_trail` classifier.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same blocks carry non-closure notices: "Aggressive Dogs" (Sinking Spring, 2024-10-22), "Potential '
        'Flooding" (Caesar Creek, 2025-02-26), "Challenging Conditions" (Old Man\'s Cave, 2024-07-30), "Hiking '
        'Guidance in East Fork State Park based on Lake Levels" (2025-05-13).',
    ),
    where=(
        "https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services",
        "https://buckeyetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
