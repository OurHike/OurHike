"""Tennessee Eastman Hiking & Canoeing Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

Structured through the API. Whether `Template:Trail` fields are SMW properties (and so `ask`-able)
is untested. `Challenge Item` is.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Template:Trail` on 148 pages (distance, round trip, hike time, difficulty, route description); "
        "`Template:Hike` on 52; 2 Hike Plans; `Report:` namespace with 141 trip reports (newest 2026-03-10, but"
        " 105 of 141 are from 2019–2021). WP category Hikes (id 212, 18 posts).",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://tehcc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
