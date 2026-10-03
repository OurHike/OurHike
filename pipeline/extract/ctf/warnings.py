"""Colorado Trail Foundation: warnings, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Its water-source half is drought/water conditions, which decision 2 keeps out of `warnings`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same alerts map (obstructions). The post "2026 Wildfires, Water Sources, and Snowpack Outlook" '
        '("extreme fire danger").',
    ),
    where=(
        "https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services",
        "https://coloradotrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
