"""Colorado Parks & Wildlife — COTREX: closures, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

The layer was last built for the 2025–26 season. Whether a 2026–27 rebuild is coming is
@unvalidated; what would settle it is CPW's schedule.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`SCs_All_COTREX_Sept2025_Final/FeatureServer/0`: 128 seasonal wildlife closure polygons with `Agency`,"
        " `Closure_Period`, `Start_Date`, `End_Date`, `Restricted_Use_Types`, `URL`; last edit 2025-10-09. The "
        'points version holds 127. The Experience app is "COTREX Seasonal Wildlife Closures". '
        "`Fishing_Closures` also exists.",
    ),
    where=(
        "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/SCs_All_COTREX_Sept2025_Final/FeatureServer/0",
        "https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
