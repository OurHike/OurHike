"""Outdoor Club at Virginia Tech: points of interest, drawn from another folder's resource (coverage
audit 2026-10-01, batch c3_at_clubs_south).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Code 22: shelters 2, privies 2, parking 4, viewpoints 6, bridges 1. The club publishes no POI list.",),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://outdoor.org.vt.edu/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
