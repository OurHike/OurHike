"""Adirondack Mountain Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

NWS is already `_shared`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same report\'s "Regulations & Advisories": the Eastern High Peaks bear-can requirement through Nov.'
        ' 30, "Low Fire Risk", a link to NWS advisories.',
    ),
    where=(
        "https://gisservices.dec.ny.gov/arcgis/rest/services",
        "https://adk.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
