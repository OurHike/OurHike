"""Smoky Mountains Hiking Club: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through nps/ `grsm_trails_access`, each extracted once in its steward's
folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://smhclub.org/resources/Documents/atmc_newsletters/2026/ATMC-0926.pdf (pdf).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_ROADS/FeatureServer/0,
GRSM's roads, 697 of 1,925 'Temporarily Closed' and unedited since 2025-11-13: a seasonal road
attribute, not a current notice.

Before decision 53 phase B, 2026-10-03, this note read:

Smoky Mountains Hiking Club: closures, published, and not landed (coverage audit 2026-10-01, batch
p02_persist).

Licence: open_licence, public domain as a federal work. data.gov labels GSMNP Trails
`http://www.usa.gov/publicdomain/label/1.0/`. The item text is a disclaimer: "The National Park
Service shall not be held liable for improper or incorrect use of the data…". GRSM_ROADS adds a
condition: "If a road …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via nps/ `grsm_trails_access` (decision 53 phase B, 2026-10-03): `grsm_trails_access` reads `GRSM_TRAILS/FeatureServer/0`",
        '`https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_TRAILS/FeatureServer/0` (owner `GRSM_GIS`) has 549 features, last edit 2026-08-25. Field `ACCESS`: Open 523, Closed 12, Caution 10, "Warning (Bears)" 3, with free-text `NOTES`. Closed: Scott Mountain ("closed from campsite #6 to Schoolhouse Gap"), Big Creek ("closed beyond the first two miles at Mouse Creek Falls"), Laurel Falls, Kuwohi, Chimney Tops, Swallow Fork, Gunter Fork and Caldwell Fork (5 segments). The A.T. in this layer is 27 segments, 71.5 mi, all `Open`. `GRSM_ROADS/FeatureServer/0`: 1,925 features …',
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_TRAILS/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_ROADS/FeatureServer/0",
        "https://data.gov",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
