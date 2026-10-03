"""CT DEEP's trail access points and trail points of interest, both CC0.

Read live 2026-10-03 for decision 54's wave 1. The third point layer read, DEEP_Property_Access_Locations
(385 access points with yes/no HIKING, CAMP_BCKPK and OVRLK_TOWR columns; ACCESS_ID is 385 distinct of 385),
is extracted once, as ct_deep_property_access_status in closures.py (decision 34), and a points-of-interest
mart reads that table. CT_Coastal_Public_Access_Sites, which the coverage audit also named, is coastal
access rather than trail points and was not read again; it is not extracted here.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "ct_deep_trail_access",
    "ct_deep_trail_interest",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
