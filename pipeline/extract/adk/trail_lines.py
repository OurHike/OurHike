"""Adirondack Mountain Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c4_regional_1).

No ADK-owned ArcGIS items. Lean-to items found are owned by a personal ArcGIS account, a personal
ArcGIS account and a personal ArcGIS account, all personal.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`dec_hiking_trails`: 117 segments matching `NAME LIKE '%NORTHVILLE%'`, re-measured today. The High "
        "Peaks trails are DEC's too. ADK's own: maps sold (`/shop/high-peaks-adirondack-trail-map/`). "
        "`nptrail.org` has a GPX per a web search, behind the Sucuri wall.",
    ),
    where=(
        "https://nptrail.org",
        "https://adk.org/",
    ),
    reason="drawn from nysdec/'s resources, extracted once there (decision 34); checked names the layer this org's "
    "data arrives in",
)
