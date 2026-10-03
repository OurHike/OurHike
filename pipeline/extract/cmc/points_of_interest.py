"""Carolina Mountain Club: points of interest, drawn from another folder's resource (coverage audit
2026-10-01, batch c3_at_clubs_south).

The 23 lookout towers are under challenges (no coordinates).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Code 27: shelters 10, campsites 2, privies 10, parking 17, viewpoints 50, bridges 12. CMC publishes no shelter content.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://carolinamountainclub.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
