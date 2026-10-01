"""Tennessee Eastman Hiking & Canoeing Club: places, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

A trailhead directory with coordinates, for regional (non-A.T.) trails.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Wiki `Template:Park` on 40 pages (for example Roan Mountain State Park and Warriors' Path State Park, "
        "edited 2026-09-22) and `Template:Region` on 53 pages (towns and states). `Template:Trail` carries "
        "`Parking location` and `Trailhead location` coordinates.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://tehcc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
