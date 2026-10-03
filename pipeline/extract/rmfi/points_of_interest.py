"""Rocky Mountain Field Institute: points of interest, drawn from cotrex/'s resources.

The coverage audit counted 109 of CPW's COTREX trailheads in RMFI's envelope, and CPW Facilities points there
too. Both are extracted once, as cotrex_trailheads and cpw_facilities, in cotrex/points_of_interest.py
(decision 34); RMFI's portion is assigned in dbt.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "CPWAdminData/FeatureServer/14, 2,585 trailheads statewide (read 2026-10-03), registered as "
        "cotrex_trailheads and extracted in cotrex/; 109 in RMFI's envelope on the coverage audit's read "
        "(2026-10-01)",
        "CPWAdminData/FeatureServer/0, 5,520 facilities statewide (read 2026-10-03), registered as "
        "cpw_facilities and extracted in cotrex/",
    ),
    where=("https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/ArcGIS/rest/services/CPWAdminData/FeatureServer/14",),
    reason=(
        "drawn from cotrex/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in"
    ),
)
