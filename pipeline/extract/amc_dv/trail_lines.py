"""AMC Delaware Valley Chapter: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c1_at_clubs_north).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Club polygon "Appalachian Mountain Club - Delaware Valley Chapter". Own geometry: none. The sections '
        'are stated on `https://amcdv.org/volunteer/trail-work/`. ArcGIS search for "AMC Delaware Valley" '
        "returned 0.",
    ),
    where=("https://amcdv.org/volunteer/trail-work/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
