"""Bay Area Ridge Trail Council: points of interest, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

Do not read `STATUS` as live. It is 20 months old, and would mark six camps closed on 2023 evidence.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`CampsiteData/FeatureServer/0` ("Campsites: Bay Area Ridge Trail"): 192 points, typed Group 43, '
        "Campground 31, RV 31, Trail Camp 21, Hostel 13, Cabin 10, Equestrian 10 and others. `STATUS` reads "
        "OPEN 160, RESTRICTED 16, OPEN WITH RESTRICTIONS 8, CLOSED 6. Data last edited 2024-02-13. Its "
        'description says the data was "current as of 06/2023". `Trail_Marker_for_Explorer_Dashboard` has 126 '
        "section-divider points.",
    ),
    where=("https://services5.arcgis.com/6iLCtMhqIxD1wlgk/arcgis/rest/services/CampsiteData/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
