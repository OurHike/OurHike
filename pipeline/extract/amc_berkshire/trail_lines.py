"""AMC Berkshire Chapter: trail lines, drawn from another folder's resource (coverage audit 2026-10-01,
batch c1_at_clubs_north).

The chapter also co-manages the NET, which is covered by `ct-deep`/`cfpa`/MassGIS rows outside this
batch.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Club polygon "Appalachian Mountain Club - Western Massachusetts Chapter". '
        "`massgis_long_distance_trails` also carries the MA A.T. (87.2 mi per its row). Own geometry: none.",
    ),
    where=(
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://amcberkshire.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
