"""E Mau Na Ala Hele: points of interest, drawn from nps_poi/'s resource.

Inside the Ala Kahakai corridor the coverage audit counted 38 NPS points (KAHO 22, PUHO 2, PUHE 3). They
are extracted once, as nps_points_of_interest, in nps_poi/points_of_interest.py (decision 34). Hawaii
State Parks' campsites (8 at Kiholo, on geodata.hawaii.gov) belong to a steward with no folder, which
waits on decision 54's wave 6.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "NPS_Public_POIs/FeatureServer/0, 35,639 points nationwide (read 2026-10-03), registered as "
        "nps_points_of_interest and extracted in nps_poi/",
        "Hawaii State Parks' campsites, 8 at Kiholo State Park Reserve on the coverage audit's read "
        "(2026-10-01): its steward has no club folder, so they wait on decision 54's wave 6",
    ),
    where=("https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs/FeatureServer/0",),
    reason=(
        "drawn from nps_poi/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
