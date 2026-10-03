"""Texas Trail Tamers: points of interest, published, and not landed (coverage audit 2026-10-01, batch
p05_persist).

explicit_restriction, the same sentence, item `3d25602d20844752a23f233207d19718`; copyrightText
`TPWD | SP | NR | PGR`. Folder `tpwd/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://services1.arcgis.com/1mtXwieMId59thmg/arcgis/rest/services/Texas_State_Parks_Public_Areas/FeatureServer`,"
        " `ParkName LIKE 'McKinney%'`: layer 0 headquarters 1; layer 1 buildings 13 (Comfort Station 6, "
        "Restroom 3, and one each of Playground, Visitor Center, Dining Hall and Amphitheater); layer 2 "
        "campground areas 7; layer 3 day-use areas 4. I found no water-source or trailhead layer. Tried: 1–6 as"
        " trail_lines.",
    ),
    where=("https://services1.arcgis.com/1mtXwieMId59thmg/arcgis/rest/services/Texas_State_Parks_Public_Areas/FeatureServer",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
