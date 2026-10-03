"""Friends of the Blue Hills: points of interest, drawn from massgis/'s resources.

The Blue Hills' public parking and numbered trail intersections are MA DCR's layers, extracted once as
ma_dcr_blue_hills_parking and ma_dcr_blue_hills_intersections in massgis/points_of_interest.py (decision 34).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "BlueHillsParkingLotsPublic2024_07_24/FeatureServer/0, 33 points, and "
        "BlueHillsNumberedIntersectionsOn2020TrailMap2024_07_24/FeatureServer/1, 262 points, on DCR's org "
        "(read 2026-10-03), registered as ma_dcr_blue_hills_parking and ma_dcr_blue_hills_intersections and "
        "extracted in massgis/",
    ),
    where=(
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/BlueHillsParkingLotsPublic2024_07_24/FeatureServer/0",
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/BlueHillsNumberedIntersectionsOn2020TrailMap2024_07_24/FeatureServer/1",
    ),
    reason=(
        "drawn from massgis/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in"
    ),
)
