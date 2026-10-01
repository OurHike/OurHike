"""Friends of the Blue Hills: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

The numbered intersections are the markers hikers navigate by (FBH's hikes cite "marker 4234").

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'DCR\'s "Blue Hills Parking Lots (public)", `…/BlueHillsParkingLotsPublic2024_07_24/FeatureServer/0`: 33'
        ' points with capacity fields. DCR\'s "Blue Hills Numbered Trail Intersections", '
        "`…/BlueHillsNumberedIntersectionsOn2020TrailMap2024_07_24/FeatureServer/1`: 262 points (2024-10-01).",
    ),
    where=(
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services",
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services",
        "https://friendsofthebluehills.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
