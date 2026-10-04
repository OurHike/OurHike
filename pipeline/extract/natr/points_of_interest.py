"""Natchez Trace National Scenic Trail: points of interest, drawn from nps_poi/'s resource.

NATR's share of NPS_Public_POIs (UNITCODE 'NATR'): the coverage audit counted 854, mile markers,
parking, trailheads, restrooms and five springs among them. Extracted once, as nps_points_of_interest,
in nps_poi/points_of_interest.py (decision 34); NATR's portion is assigned in dbt.

Decision 54, wave 3 (2026-10-04): the NPS Data API's records for this trail's park unit are registered
in nps/ and reach this club by park code, so this type is drawn from there.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "via nps `nps_api_campgrounds` (registered 2026-10-04): the NPS Data API's /campgrounds, 665 nationally by its own `total`, extracted once in nps/points_of_interest.py; this club's portion is the campgrounds whose `parkCode` is natr, assigned in dbt (decision 34). It needs NPS_API_KEY in the monthly job, which does not pass it yet.",
        "NPS_Public_POIs/FeatureServer/0, 35,639 points nationwide (read 2026-10-03), registered as nps_points_of_interest and extracted in nps_poi/; UNITCODE 'NATR' held 854 on the coverage audit's read (2026-10-01)",
    ),
    where=(
        "https://developer.nps.gov/api/v1/campgrounds",
        "https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the resource this org's data arrives in",
)
