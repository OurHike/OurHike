"""Sheltowee Trace Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/alerts`: "Dogs on the Trace" (Southbound miles 103.1 to 118.7). The Red River high-water route ("If '
        'the water is high, fording the river becomes unsafe"). Thru-hikers FAQ: fire restrictions.',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://sheltoweetrace.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
