"""National Park Service (POIs): places, drawn from nps/'s resources (decision 54, wave 1, read
2026-10-03).

The NPS API's /places needs a key and waits for wave 3.

Decision 54, wave 3 (2026-10-04): the NPS Data API's records for this trail's park unit are registered
in nps/ and reach this club by park code, so this type is drawn from there.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "via nps `nps_api_places` (registered 2026-10-04): the NPS Data API's /places, 17,505 places nationally by its own `total` (one request with api.data.gov's public demo key), extracted once in nps/places.py; this club's portion is the places whose `relatedParks` list every park code, assigned in dbt (decision 34). It needs NPS_API_KEY in the monthly job, which does not pass it yet.",
        "via nps `nps_park_boundaries` (NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2, 442 polygons) and `nps_legislated_wilderness` (61), registered 2026-10-03. The Wilderness count that answered HTTP 500 on 2026-10-01 answered 61.",
        "Not landed yet: the NPS API `/places` (17,483), which needs a key (wave 3).",
    ),
    where=(
        "https://developer.nps.gov/api/v1/places",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2",
        "https://nps.gov/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the resource this org's data arrives in",
)
