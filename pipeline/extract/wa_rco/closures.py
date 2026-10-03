"""Washington RCO — State Trails Database: closures, drawn from another folder's resource (decision 53
phase B, 2026-10-03).

This club's closures arrive through _shared/wa_state_parks/ `wsprc_winter_rec_closures`, each
extracted once in its steward's folder (decision 34). Its portion is assigned in dbt.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_WildfireDanger/MapServer/1,
WA DNR's Burn Bans layer, not re-read; layer 0, wired in _shared/wa_dnr/, carries BURN_BAN_LEVEL_NM
itself.

Before decision 53 phase B, 2026-10-03, this note read:

Washington RCO — State Trails Database: closures, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

This is not a feed. Load the attribute; do not build a closure source on it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/wa_state_parks/ `wsprc_winter_rec_closures` (decision 53 phase B, 2026-10-03): `wsprc_winter_rec_closures` reads `Temporary_Closure_(Public)/FeatureServer/0`",
        "Attribute only: Trailheads `trailhead_status` reads `closed` 1, `construction` 6, `seasonal` 6, with no dates. `trail_condition` on the trails holds condition grades (A–D, Class 1–5), not closures.",
    ),
    where=(
        "https://services5.arcgis.com/4LKAHwqnBooVDUlX/arcgis/rest/services/Temporary_Closure_(Public)/FeatureServer/0",
        "https://gis.dnr.wa.gov/site1/rest/services",
        "https://gis.dnr.wa.gov/site3/rest/services",
        "https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services",
        "https://trails-wa-rco.hub.arcgis.com/",
    ),
    reason="drawn from _shared/wa_state_parks/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in",
)
