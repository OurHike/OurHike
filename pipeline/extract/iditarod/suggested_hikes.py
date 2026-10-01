"""Iditarod Historic Trail Alliance: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Prose and PDF, not routes

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`plan-your-trip.html` names the summer-usable sections (Chugach State Park, Chugach NF, Girdwood, "
        "Eagle River). The Visitor Guide PDF has regional sections (Kenai Mountains, Turnagain Arm, Anchorage, "
        "Wasilla)",
    ),
    where=(
        "https://gis.blm.gov/arcgis/rest/services",
        "https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services",
        "https://iditarod100.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
