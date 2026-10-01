"""Colorado Trail Foundation: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('The same segment pages (33 segments; e.g. Segment 1, "16.8 miles with 2,830 feet of elevation gain").',),
    where=(
        "https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services",
        "https://coloradotrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
