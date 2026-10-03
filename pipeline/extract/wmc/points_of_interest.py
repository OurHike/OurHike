"""Wasatch Mountain Club: points of interest, drawn from utah_sgid/'s resources.

The coverage audit counted 102 of UGRC's Utah trailheads in WMC's box. They are extracted once, as
utah_trailheads, in utah_sgid/points_of_interest.py (decision 34). WMC's own GPX carried no waypoints, and
its KMZ files sat behind a 406 the audit did not get past.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "UtahTrailheads/FeatureServer/0, 568 trailheads statewide (read 2026-10-03), registered as "
        "utah_trailheads and extracted in utah_sgid/; 102 in WMC's box on the coverage audit's read "
        "(2026-10-01)",
    ),
    where=("https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/UtahTrailheads/FeatureServer/0",),
    reason=(
        "drawn from utah_sgid/'s resources, extracted once there (decision 34); checked names the layer this "
        "org's data arrives in"
    ),
)
