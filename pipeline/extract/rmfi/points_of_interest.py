"""Rocky Mountain Field Institute: points of interest, published, and not landed (coverage audit
2026-10-01, batch p07_persist).

Licence: `CPWAdminData` reads "This map is a product and property of the Colorado Parks and
Wildlife… The Colorado Department of Natural Resources is not responsible…". That is a property
claim plus a disclaimer, so none_stated. COTREX's app terms (b7) govern the app, not this service.
Folders: …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "CPW's `services5.arcgis.com/ttNGmDvKQA7oeDQ3/ArcGIS/rest/services/CPWAdminData/FeatureServer/14` "
        '"COTREX Trailheads" (2,585 statewide, edited 2026-08-27): 109 in the envelope. By manager: the City '
        "48, El Paso County 18, Mueller SP 12, USFS Pikes Peak RD 12. By `water`: yes 14, seasonally 10, "
        "conditional 1, no 71, blank 13. Loaded `usfs_rec_sites` in the envelope: trailheads 26, campgrounds 5,"
        " observation sites 6, picnic sites 4. CPW Facilities (`/0`) also has points in the envelope (largest "
        "`FAC_TYPE` groups: code 4050, 24 points; code 3120, 19). The codes are not labelled in the query. …",
    ),
    where=("https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/ArcGIS/rest/services/CPWAdminData/FeatureServer/14",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
