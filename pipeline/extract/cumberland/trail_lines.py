"""Cumberland Trail / Tennessee State Parks: trail lines, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

The CTSST owner a personal ArcGIS account and its org `ctsst.maps.arcgis.com` are not identified as
TDEC staff or as the Friends of the Cumberland Trail. Its hazard rows link to
friendsofthecumberlandtrail.org. Steward identity Unvalidated.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../TDEC_Public_Trails/FeatureServer/0`: 2,261 lines, of which 112 are Cumberland Trail segments "
        "totalling 306 mi (`PRIMARY_NAME__LONG_ LIKE '%Cumberland Trail%'`). "
        "`.../Tennessee_State_Park_Trails_2024_(View_Only)/FeatureServer/0`: 2,729 lines, of which 158 "
        "Cumberland-Trail-named lines in the CT park total 278 mi; last edit 2026-09-30. "
        "`.../TN_State_Parks_Public_Trails`: 649. Also the trail's own map service, "
        "`services3.arcgis.com/GOLEtC5IsWKPPb0t/.../PUBLIC_CTSST_2020_gdb/FeatureServer` (behind web app "
        "`ae4ff34c…` in `org_channels.json`): Open CT Trail Sections (10) 33 lines, edited …",
    ),
    where=(
        "https://ctsst.maps.arcgis.com",
        "https://friendsofthecumberlandtrail.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
