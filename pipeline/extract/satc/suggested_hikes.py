"""Susquehanna Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Only the three A.T. entries are the club's own ground.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/hiking-in-central-pennsylvania.html` (page): about 30 entries. Three describe SATC's own A.T. "
        "segments with distances (Clarks Ferry–PA-225 6.3 mi, PA-225–PA-325 9.7 mi, PA-325–PA-443 15.8 mi). The"
        " rest are other organisations' parks and trails",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://satc-hike.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
