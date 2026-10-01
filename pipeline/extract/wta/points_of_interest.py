"""Washington Trails Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Page. Restricted by the ToS.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'One trailhead coordinate per hike page (Mount Si: `latitude 47.4879799075`). The Hiking Guide lists "4268 Hikes".',
    ),
    where=(
        "https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services",
        "https://wta.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
