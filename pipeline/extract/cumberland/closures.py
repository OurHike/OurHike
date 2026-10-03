"""Cumberland Trail / Tennessee State Parks: closures, drawn from another folder's resource (decision
53 phase B, 2026-10-03).

This club's closures arrive through _shared/tdec/ `tdec_trail_closures`, each extracted once in its
steward's folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://tnstateparks.com/api/alerts (json_api).

Before decision 53 phase B, 2026-10-03, this note read:

Cumberland Trail / Tennessee State Parks: closures, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

The strongest closures find in this batch. The closures arrive as segment geometry, already marked
closed, and are edited daily. The `TSP_UID` in every source joins the alerts to parks and trails.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/tdec/ `tdec_trail_closures` (decision 53 phase B, 2026-10-03): `tdec_trail_closures` reads `TDEC_Trail_Closures_Public/FeatureServer/0`",
        '`.../TDEC_Trail_Closures_Public/FeatureServer/0`: 22 closed trail segments with geometry, `TRSTAT` in {Temporarily Closed, Closed Repairs}, `Notes` (e.g. "Trail Wash Out", "closed temporarily as of 6/28 due to flooding"), last edit 2026-09-30 19:50 UTC. Two are CT segments: Cumberland Mountain Section (3.89 mi) and North Chickamauga Section (1.66 mi). `https://tnstateparks.com/api/alerts` (JSON): 79 alerts with `type`, `expiration_date`, `parks[].TSP_UID`, `trails[]`, `campgrounds[]`. The JSON:API trails node\'s `field_trails_status` reads `partial_closure` on CT North Chickamauga. CTSST …',
    ),
    where=(
        "https://services5.arcgis.com/bPacKTm9cauMXVfn/arcgis/rest/services/TDEC_Trail_Closures_Public/FeatureServer/0",
        "https://tnstateparks.com/api/alerts",
    ),
    reason="drawn from _shared/tdec/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
