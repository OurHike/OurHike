"""Appalachian Mountain Club (A.T. sections): points of interest, published, and not landed (coverage
audit 2026-10-01, batch c1_at_clubs_north).

Water source and fee per site are what ATC's facility layers do not carry. The off-A.T. points
belong under the `amc` row. Neither source states a licence.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "LOADED via atc (code 1): shelters 19, which includes 8 huts (Zealand Falls, Madison Spring, Lakes of "
        "the Clouds, Carter Notch, Greenleaf, Lonesome Lake, Galehead, Mizpah Spring); campsites 18; privies "
        "20; parking 9; viewpoints 126; bridges 10. Not loaded: (1) "
        "`https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services/AMC_Destinations/FeatureServer/0`,"
        " an ArcGIS point layer with 61 points (fields NAME, TYPE, ACCESS, ELEV, STAT, SEASON). It includes "
        "off-A.T. sites such as Thirteen Falls Tentsite and the Maine Woods campsites and lodges. (2) WP REST …",
    ),
    where=(
        "https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services/AMC_Destinations/FeatureServer/0",
        "https://outdoors.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
