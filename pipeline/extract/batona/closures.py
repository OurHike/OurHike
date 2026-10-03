"""Batona Hiking Club: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through njgin/ `njdep_park_status`, each extracted once in its steward's
folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://batona.wildapricot.org/RSS (rss).

Before decision 53 phase B, 2026-10-03, this note read:

Batona Hiking Club: closures, published, and not landed (coverage audit 2026-10-01, batch
p03_persist).

attribution_only (conditional). The item licenseInfo reads: "New Jersey Department of Environmental
Protection (NJDEP) Data Distribution Agreement. The data provided herein are distributed subject to
the following conditions and restrictions: NJDEP assumes no responsibility to maintain them…". This
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via njgin/ `njdep_park_status` (decision 53 phase B, 2026-10-03): `njdep_park_status` reads `New_Jersey_State_Park_Service_Live_Status_Updates_(Public_View)/FeatureServer/0`",
        '`services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/New_Jersey_State_Park_Service_Live_Status_Updates_(Public_View)/FeatureServer/0` covers 53 parks, with `Status`, `Park_Hours` and `EditDate`. Wharton State Forest reads "Open" (edited 2026-04-08), Brendan T. Byrne "Open" (2026-07-10) and Bass River "Open" (2026-08-16). Those three forests and Franklin Parker Preserve are the 4 `Open Space (State Owned) Generalized` polygons within 10 m of the Batona Trail\'s 21 segments in `njdep_park_trails` (`Features/Land/MapServer/63`). For the Pennsylvania A.T. section, the loaded …',
    ),
    where=(
        "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/New_Jersey_State_Park_Service_Live_Status_Updates_(Public_View)/FeatureServer/0",
        "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/New_Jersey_State_Park_Service_Live_Status_Updates_",
        "https://mapsdep.nj.gov/arcgis/rest/services",
        "https://mapservices.pasda.psu.edu/server/rest/services/pasda",
    ),
    reason="drawn from njgin/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
