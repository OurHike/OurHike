"""Natural Bridge Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

These are points, not routes.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`MapData/FavoriteHikes_2020-08-25.kml` (46 hike points: Apple Orchard Falls, Cold Mountain, Crabtree "
        "Falls…) and `FavoriteHikes_2017-11-02.gpx`",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://nbatc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
