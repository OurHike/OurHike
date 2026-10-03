"""National Park Service: trail lines, drawn from another folder's resource (coverage audit 2026-10-01,
batch c9_federal_state_rest).

Registered and not shipped: `reaches_hikers` waits for batch 4 of #1778 — Register the 17
organisations the catalogue cleared, with what opening each endpoint actually found.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`nps_trails` in sources.json, `mapservices.nps.gov/.../NPS_Public_Trails/FeatureServer/0`. The "
        "`_Geographic` twin holds 31,484 polylines today; the registry recorded 31,485 on 2026-09-30.",
    ),
    where=("https://nps.gov/",),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
