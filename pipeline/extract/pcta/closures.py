"""Pacific Crest Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Neither layer has an active flag or an end date. "Current" can only be inferred from `Year` plus the
CMS page, which is @unvalidated. What would settle it is asking PCTA which layer its closures page
renders.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`PCT_Fires_and_Trail_Closures_public_view/FeatureServer/0`: 144 points, last edit 2026-09-28. Fields: "
        "`Year`, `Closure_Name`, `Type`, `Agency_Unit`, `Miles_of_PCT_in_Closure_Area`. Year 2026: 13 "
        "`Wildfire` + 10 `Other Closure`. `Closure_Data_view/FeatureServer/0,1,2`: Closure Point 111, Line 138,"
        " Polygon 127, last edit 2026-09-24. Those are cartographic: `Type` holds symbol names (`Crossed out "
        'line` 54, `Purple` 47…), `Label_Text` reads "PCT Closed", and `CMS_ID` links to `closures.pcta.org`. '
        "The page itself returns HTTP 429 (Vercel checkpoint).",
    ),
    where=(
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/PCT_Fires_and_Trail_Closures_public_view/FeatureServer/0",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/Closure_Data_view/FeatureServer/0",
        "https://closures.pcta.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
