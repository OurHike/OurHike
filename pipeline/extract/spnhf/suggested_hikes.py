"""Society for the Protection of NH Forests: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

A page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Property pages carry hike descriptions (Mount Major: "round trip hike ranging from 3 to 3.9 miles"), across 184 pages.',
    ),
    where=(
        "https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services",
        "https://forestsociety.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
