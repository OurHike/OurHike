"""Smoky Mountains Hiking Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c3_at_clubs_south).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`centerline` (76 features, 102.3 mi under `SMHC`). `side_trails` has 0 rows for code 28; GSMNP side "
        "trails come via `nps_trails`. SMHC's own geometry: none. `/Maps-of-the-Smokies` links the NPS PDF map "
        "and historical maps (LoC, tnlandforms.us).",
    ),
    where=("https://tnlandforms.us",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
