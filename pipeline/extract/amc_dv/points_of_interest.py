"""AMC Delaware Valley Chapter: points of interest, drawn from another folder's resource (coverage
audit 2026-10-01, batch c1_at_clubs_north).

Code 8 also decodes to AMC-DV, so a join has to treat both codes as one.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("ATC (code 10): shelters 2, campsites 1, privies 2, parking 4, viewpoints 15.",),
    where=(
        "https://pgcmaps.pa.gov/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://amcdv.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
