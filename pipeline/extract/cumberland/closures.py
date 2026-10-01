"""Cumberland Trail / Tennessee State Parks: closures, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

The strongest closures find in this batch. The closures arrive as segment geometry, already marked
closed, and are edited daily. The `TSP_UID` in every source joins the alerts to parks and trails.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../TDEC_Trail_Closures_Public/FeatureServer/0`: 22 closed trail segments with geometry, `TRSTAT` in "
        '{Temporarily Closed, Closed Repairs}, `Notes` (e.g. "Trail Wash Out", "closed temporarily as of 6/28 '
        'due to flooding"), last edit 2026-09-30 19:50 UTC. Two are CT segments: Cumberland Mountain Section '
        "(3.89 mi) and North Chickamauga Section (1.66 mi). `https://tnstateparks.com/api/alerts` (JSON): 79 "
        "alerts with `type`, `expiration_date`, `parks[].TSP_UID`, `trails[]`, `campgrounds[]`. The JSON:API "
        "trails node's `field_trails_status` reads `partial_closure` on CT North Chickamauga. CTSST …",
    ),
    where=("https://tnstateparks.com/api/alerts",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
