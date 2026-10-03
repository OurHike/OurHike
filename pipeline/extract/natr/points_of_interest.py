"""Natchez Trace National Scenic Trail: points of interest, drawn from nps_poi/'s resource.

NATR's share of NPS_Public_POIs (UNITCODE 'NATR'): the coverage audit counted 854, mile markers,
parking, trailheads, restrooms and five springs among them. Extracted once, as nps_points_of_interest,
in nps_poi/points_of_interest.py (decision 34); NATR's portion is assigned in dbt.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "NPS_Public_POIs/FeatureServer/0, 35,639 points nationwide (read 2026-10-03), registered as "
        "nps_points_of_interest and extracted in nps_poi/; UNITCODE 'NATR' held 854 on the coverage audit's "
        "read (2026-10-01)",
    ),
    where=("https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs/FeatureServer/0",),
    reason=(
        "drawn from nps_poi/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
