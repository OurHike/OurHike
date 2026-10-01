"""E Mau Na Ala Hele: points of interest, published, and not landed (coverage audit 2026-10-01, batch
p01_persist).

Licence:; • NPS: open_licence, public domain (federal work). copyrightText: "Points of Interest
(POI) data are contributed, reviewed, and maintained by individual park units…".; • Hawaii State
Parks campsites: open_licence, public domain by state declaration (not a federal work). licenseInfo:
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Inside the ALKA corridor:",
        "NPS Public POIs "
        "`mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs/FeatureServer/0`: 38 "
        "(Restroom 4, Parking Lot 4, Visitor Center 4, Entrance/Exit 4, Viewpoint 3, Picnic Area 2, Campground "
        "1, Ranger Station 1…). By unit: KAHO 22, PUHO 2, PUHE 3, ALKA 0.",
        "Hawaii State Parks campsites `geodata.hawaii.gov/.../Infrastructure/MapServer/31`: 8, all at Kīholo "
        "State Park Reserve, which is the site of E Mau's National Trails Day 2026 Kīholo Bay walk.",
        'Na Ala Hele trails (`Terrestrial/MapServer/34`): 5. Four carry `amenities` "Toilet, Parking …',
    ),
    where=("https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
