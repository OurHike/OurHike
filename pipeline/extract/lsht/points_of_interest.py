"""Lone Star Hiking Trail Club: points of interest, published, and not landed (coverage audit
2026-10-01, batch c8_regional_5).

Page plus PDF. The guide promises "a LSHT Drought Index monthly". I did not find where that is
published (U). Skeptic: still not found. It is absent from News (1 item), both Blogs, Information,
the Thru Hike page (5 mentions, all of them the rule "D\\R\\O\\P\\S > LSHT Drought Index → that
source should …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Water: the Thru Hike page (`module_id=678717`) rates each water source 1–5 "DROPS" for drought '
        "resistance; the rating appears 59 times, legend included. It also lists primitive and hunter camps (17"
        ' mentions). The same guide is a PDF, `docs.ashx?id=1405781`, "Revised October 31, 2023". Parking: 14 '
        'trailheads with `dd mm.mmm` coordinates (`module_id=676900`; "South Wilderness CLOSED"). Also a '
        'trailheads GeoJSON (`f2f94a950290482997dd2f4da278e6c0`, 2024-06-19) and "LSHT System Waypoints" GPX '
        "(`id=1401147`: 124 waypoints, all mileposts `M01`… with no type) and XLSX (`id=1401146`).",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://lonestartrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
