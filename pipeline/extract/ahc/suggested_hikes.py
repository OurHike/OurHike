"""Allentown Hiking Club: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

These are events, not lasting hike descriptions. The call is mine; reverse it if the hikes mart
should hold past outings.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`?job=ahcevent_list` holds dated outings from 2006 to 2026 with route text",),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://allentownhikingclub.org/",
    ),
)
