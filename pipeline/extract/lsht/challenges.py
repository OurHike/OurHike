"""Lone Star Hiking Trail Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

The programme only. The list holds names and emails "if permitted".

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Honor Roll": "Congratulations on completing your journey of the entire Lone Star Hiking Trail! Join '
        'our Honor Roll…", with a form at `content.aspx?page_id=1478&club_id=738078&item_id=10519`.',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://lonestartrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
