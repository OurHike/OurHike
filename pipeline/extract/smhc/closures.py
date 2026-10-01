"""Smoky Mountains Hiking Club: closures, published, and not landed (coverage audit 2026-10-01, batch
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
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_TRAILS/FeatureServer/0` "
        "(owner `GRSM_GIS`) has 549 features, last edit 2026-08-25. Field `ACCESS`: Open 523, Closed 12, "
        'Caution 10, "Warning (Bears)" 3, with free-text `NOTES`. Closed: Scott Mountain ("closed from campsite'
        ' #6 to Schoolhouse Gap"), Big Creek ("closed beyond the first two miles at Mouse Creek Falls"), Laurel'
        " Falls, Kuwohi, Chimney Tops, Swallow Fork, Gunter Fork and Caldwell Fork (5 segments). The A.T. in "
        "this layer is 27 segments, 71.5 mi, all `Open`. `GRSM_ROADS/FeatureServer/0`: 1,925 features …",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_TRAILS/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_ROADS/FeatureServer/0",
        "https://data.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
