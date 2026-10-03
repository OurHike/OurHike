"""Mountains to Sound Greenway Trust: closures, drawn from another folder's resource (decision 53 phase
B, 2026-10-03).

This club's closures arrive through usfs/ `usfs_r06_fire_closure_points`,
`usfs_r06_fire_closure_lines`, `usfs_r06_fire_closure_areas`; _shared/king_county_parks/
`king_county_parks_alerts_points`, `king_county_parks_alerts_lines`,
`king_county_parks_alerts_areas`; _shared/wa_state_parks/ `wsprc_winter_rec_closures`, each
extracted once in its steward's folder (decision 34). Its portion is assigned in dbt.

Read and not wired (the decision 53 inventory, batch 3, 2026-10-03):
https://mtsgreenway.org/wp-json/wp/v2/posts?search=closure, 24 blog posts, none a notice (the newest
2026-01-16, an essay on wildfire resilience). The Trust publishes no notices of its own.

Before decision 53 phase B, 2026-10-03, this note read:

Mountains to Sound Greenway Trust: closures, published, and not landed (coverage audit 2026-10-01,
batch p04_persist).

Licence classes: USFS is none_stated (federal disclaimer, quoted under mazamas). King County is
explicit_restriction, on sale only (see the list at the end). WSPRC is none_stated ("provides these
geographic data "as is"; WSPRC makes no guarantee or warranty"). The data belongs in `usfs` …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/ `usfs_r06_fire_closure_points`, `usfs_r06_fire_closure_lines`, `usfs_r06_fire_closure_areas`; _shared/king_county_parks/ `king_county_parks_alerts_points`, `king_county_parks_alerts_lines`, `king_county_parks_alerts_areas`; _shared/wa_state_parks/ `wsprc_winter_rec_closures` (decision 53 phase B, 2026-10-03): `usfs_r06_fire_closure_points` reads `R06_FireClosureOrders_PublicView/FeatureServer/0`; `usfs_r06_fire_closure_lines` reads `R06_FireClosureOrders_PublicView/FeatureServer/1`; `usfs_r06_fire_closure_areas` reads `R06_FireClosureOrders_PublicView/FeatureServer/2`; `king_county_parks_alerts_points` reads `Parks_alert_and_construction_view/FeatureServer/0`; `king_county_parks_alerts_lines` reads `Parks_alert_and_construction_view/FeatureServer/1`; `king_county_parks_alerts_areas` reads `Parks_alert_and_construction_view/FeatureServer/2`; `wsprc_winter_rec_closures` reads `Temporary_Closure_(Public)/FeatureServer/0`",
        'Counted inside the NHA polygon `MTS_Boundary/FeatureServer/0`, generalised at 500 m to 262 vertices. USFS `R06_FireClosureOrders_PublicView`: Three Queens Fire order 06-17-03-2026-44 (Cle Elum RD) has 9 points, 56 lines and 1 polygon, all to 2026-10-31. Order 06-17-03-26-07 has 1 polygon to 2028-11-30. King County `Parks_alert_and_construction_view/FeatureServer/0`: 10 active points (`EndDate IS NULL OR >= now`) inside the NHA. The countywide figures (14 points, 8 lines, 3 areas) are the audit\'s. WA State Parks `Temporary_Closure_(Public)/0` ("PARKS - Winter Rec Temporary Closure"): 47 lines …',
    ),
    where=(
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/R06_FireClosureOrders_PublicView/FeatureServer/0",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/R06_FireClosureOrders_PublicView/FeatureServer/1",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/R06_FireClosureOrders_PublicView/FeatureServer/2",
        "https://services.arcgis.com/Ej0PsM5Aw677QF1W/arcgis/rest/services/Parks_alert_and_construction_view/FeatureServer/0",
        "https://services.arcgis.com/Ej0PsM5Aw677QF1W/arcgis/rest/services/Parks_alert_and_construction_view/FeatureServer/1",
        "https://services.arcgis.com/Ej0PsM5Aw677QF1W/arcgis/rest/services/Parks_alert_and_construction_view/FeatureServer/2",
        "https://services5.arcgis.com/4LKAHwqnBooVDUlX/arcgis/rest/services/Temporary_Closure_(Public)/FeatureServer/0",
        "https://services.arcgis.com/b2nA3bRpH9jJyZOr/arcgis/rest/services/MTS_Boundary/FeatureServer/0",
        "https://mtsgreenway.org/{arcgis,server,gis}/rest/services",
        "https://mtsgreenway.org/",
    ),
    reason="drawn from usfs/'s and _shared/king_county_parks/'s and _shared/wa_state_parks/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in",
)
