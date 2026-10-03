"""National Park Service (POIs): places, drawn from nps/'s resources (decision 54, wave 1, read
2026-10-03).

The NPS API's /places needs a key and waits for wave 3.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via nps `nps_park_boundaries` (NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2, 442 "
        "polygons) and `nps_legislated_wilderness` (61), registered 2026-10-03. The Wilderness count that answered HTTP "
        "500 on 2026-10-01 answered 61.",
        "Not landed yet: the NPS API `/places` (17,483), which needs a key (wave 3).",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2",
        "https://nps.gov/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); the NPS API's places are not landed yet",
)
