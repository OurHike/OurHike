"""Colorado Fourteeners Initiative: places, drawn from another folder's resource (coverage audit
2026-10-01, batch p03_persist).

USFS: open_licence (federal, public domain). COTREX trailheads: none_stated. The wilderness unit
boundaries are in USFS EDW `EDW_Wilderness_02`. The data belongs in `usfs/` and `_shared/cotrex`,
not in `cfi/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "I matched 8 trailheads that CFI's 14er routes start from, by name. COTREX "
        "`CPWAdminData/FeatureServer/14` holds 7 of the 8: Guanella Pass, Quandary (2 records), Kite Lake, "
        "Barr, Grays Peak, McCullough Gulch (2) and South Colony (2). Browns Pass is missing. The loaded "
        "`usfs_rec_sites` TRAILHEAD layer holds 4 of the 8: GUANELLA PASS (2 records), GRAYS PEAK, BROWNS PASS "
        "and SOUTH COLONY. CFI's own 53 peak pages each name a recommended trailhead, in prose only (audit). "
        "Tried: 1 There is no ArcGIS host on 14ers.org. 2 `owner:colorado14ers` holds 6 StoryMaps, and their "
        "item data reference 0 web …",
    ),
    where=(
        "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWAdminData/FeatureServer/14",
        "https://14ers.org",
        "https://14ers.org/",
    ),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
