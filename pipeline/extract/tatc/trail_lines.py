"""Tidewater Appalachian Trail Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "via atc `centerline`. Own: none (all 44 pages listed via REST).",
        'Skeptic: `/wp-content/uploads/2026/01/TATC-Maps-2025.pdf` (2.3 MB) is a "Sketch map. Not a hiking map,'
        ' for reference only" with northbound and southbound distance tables, and `800-Sherando-Map.pdf` is on '
        "`/trail-maintenance/`. Both are PDFs, not geometry",
    ),
    where=("https://tidewateratc.org/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
