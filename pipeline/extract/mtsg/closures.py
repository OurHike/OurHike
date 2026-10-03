"""Mountains to Sound Greenway Trust: closures, drawn from another folder's resource (decision 53 phase
B, 2026-10-03).

This club's closures arrive through usfs/ `usfs_r06_fire_closure_points`,
`usfs_r06_fire_closure_lines`, `usfs_r06_fire_closure_areas`, each extracted once in its steward's
folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://mtsgreenway.org/wp-json/wp/v2/posts?search=closure
(wordpress).

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
        "via usfs/ `usfs_r06_fire_closure_points`, `usfs_r06_fire_closure_lines`, `usfs_r06_fire_closure_areas` (decision 53 phase B, 2026-10-03): `usfs_r06_fire_closure_points` reads `R06_FireClosureOrders_PublicView/FeatureServer/0`; `usfs_r06_fire_closure_lines` reads `R06_FireClosureOrders_PublicView/FeatureServer/1`; `usfs_r06_fire_closure_areas` reads `R06_FireClosureOrders_PublicView/FeatureServer/2`",
        'Counted inside the NHA polygon `MTS_Boundary/FeatureServer/0`, generalised at 500 m to 262 vertices. USFS `R06_FireClosureOrders_PublicView`: Three Queens Fire order 06-17-03-2026-44 (Cle Elum RD) has 9 points, 56 lines and 1 polygon, all to 2026-10-31. Order 06-17-03-26-07 has 1 polygon to 2028-11-30. King County `Parks_alert_and_construction_view/FeatureServer/0`: 10 active points (`EndDate IS NULL OR >= now`) inside the NHA. The countywide figures (14 points, 8 lines, 3 areas) are the audit\'s. WA State Parks `Temporary_Closure_(Public)/0` ("PARKS - Winter Rec Temporary Closure"): 47 lines …',
    ),
    where=(
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/R06_FireClosureOrders_PublicView/FeatureServer/0",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/R06_FireClosureOrders_PublicView/FeatureServer/1",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/R06_FireClosureOrders_PublicView/FeatureServer/2",
        "https://services.arcgis.com/b2nA3bRpH9jJyZOr/arcgis/rest/services/MTS_Boundary/FeatureServer/0",
        "https://services.arcgis.com/Ej0PsM5Aw677QF1W/arcgis/rest/services/Parks_alert_and_construction_view/FeatureServer/0",
        "https://mtsgreenway.org/{arcgis,server,gis}/rest/services",
        "https://mtsgreenway.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
