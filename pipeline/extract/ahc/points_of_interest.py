"""Allentown Hiking Club: points of interest, drawn from another folder's resource (coverage audit
2026-10-01, batch c2_at_clubs_mid).

The club publishes no POI data of its own.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("via atc `shelters` (Allentown Shelter, capacity 8 in `shelter_capacity.json`)",),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://allentownhikingclub.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
