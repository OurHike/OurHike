"""Mountains to Sound Greenway Trust: closures, published, and not landed (coverage audit 2026-10-01,
batch p04_persist).

Licence classes: USFS is none_stated (federal disclaimer, quoted under mazamas). King County is
explicit_restriction, on sale only (see the list at the end). WSPRC is none_stated ("provides these
geographic data "as is"; WSPRC makes no guarantee or warranty"). The data belongs in `usfs` …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Counted inside the NHA polygon `MTS_Boundary/FeatureServer/0`, generalised at 500 m to 262 vertices. "
        "USFS `R06_FireClosureOrders_PublicView`: Three Queens Fire order 06-17-03-2026-44 (Cle Elum RD) has 9 "
        "points, 56 lines and 1 polygon, all to 2026-10-31. Order 06-17-03-26-07 has 1 polygon to 2028-11-30. "
        "King County `Parks_alert_and_construction_view/FeatureServer/0`: 10 active points (`EndDate IS NULL OR"
        " >= now`) inside the NHA. The countywide figures (14 points, 8 lines, 3 areas) are the audit's. WA "
        'State Parks `Temporary_Closure_(Public)/0` ("PARKS - Winter Rec Temporary Closure"): 47 lines …',
    ),
    where=(
        "https://services.arcgis.com/b2nA3bRpH9jJyZOr/arcgis/rest/services/MTS_Boundary/FeatureServer/0",
        "https://services.arcgis.com/Ej0PsM5Aw677QF1W/arcgis/rest/services/Parks_alert_and_construction_view/FeatureServer/0",
        "https://mtsgreenway.org/{arcgis,server,gis}/rest/services",
        "https://mtsgreenway.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
