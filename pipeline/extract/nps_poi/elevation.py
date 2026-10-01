"""National Park Service: elevation, published, and not landed (coverage audit 2026-10-01, batch
p06_persist).

Licence: GRSM and DETO licenseInfo is NPS's standard disclaimer ("The National Park Service shall
not be held liable for improper or incorrect use of the data… It is strongly recommended that these
data are directly acquired from an NPS server…"). That is a recommendation, not a restriction.
GRSM's …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "GRSM_CONTOURS: "
        "`services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_CONTOURS/FeatureServer` (item "
        "`9bdc57b4448e4bc1bd39a0ac024e072b`, modified 2025-09-23). 29 per-quad layers of 40 ft contours, "
        "121,095 polylines. They include Clingmans Dome (6,937), Silers Bald, Thunderhead Mountain and Mt "
        "Guyot, which is the A.T. corridor through the Smokies.; IRMA DataStore: "
        "`irmaservices.nps.gov/datastore/v7/rest/QuickSearch?q=digital elevation model` returns 503 references."
        ' The first 200 hold 68 Geospatial Datasets and 18 Raster Datasets. Examples: `2203879` "Harpers Ferry '
        "Digital Elevation …",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_CONTOURS/FeatureServer",
        "https://irmaservices.nps.gov/datastore/v7/rest/QuickSearch?q=digital",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
