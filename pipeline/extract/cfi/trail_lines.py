"""Colorado Fourteeners Initiative: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c5_regional_2).

Checked on 3 routes only, not all 56.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Name matches on the live COTREX layer: `name LIKE '%BIERSTADT%'` 10 segments, `'%QUANDARY%'` 1, "
        "`'%BARR TRAIL%'` 6. CFI's own geometry is not published. The report-card page describes a \"GIS "
        'database containing more than 20,350 data points" (2011–2013), but it is not released. ArcGIS '
        "`owner:colorado14ers` holds 6 StoryMaps and nothing else.",
    ),
    where=("https://14ers.org/",),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
