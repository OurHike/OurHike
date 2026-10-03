"""Friends of the Blue Hills: places, drawn from massgis/'s resources (decision 54, wave 1, read
2026-10-03).

DCR's boundaries, inside MassGIS's open-space compilation.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via massgis `massgis_openspace` (AGOL/openspace/MapServer/0, 61,486 polygons), registered 2026-10-03; 94 of its "
        "rows match `SITE_NAME LIKE '%Blue Hills%'` (coverage audit).",
    ),
    where=(
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/openspace/MapServer/0",
        "https://friendsofthebluehills.org/",
    ),
    reason=(
        "drawn from massgis/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
