"""National Park Service: elevation, published as park contour sets and DEMs, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. Contours are vectors, so decision 35 does not cover them, but no mart reads them
and they are background-map material: decision 54's wave 1 registers none, and loading them is the
maintainer's call (decided 2026-10-03). GRSM_CONTOURS is the same item nps/elevation.py notes: one
dataset, so one folder would hold it.

Licence: GRSM and DETO licenseInfo is NPS's standard disclaimer ("The National Park Service shall
not be held liable for improper or incorrect use of the data… It is strongly recommended that these
data are directly acquired from an NPS server…"). That is a recommendation, not a restriction.
GRSM's …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `GRSM_CONTOURS/FeatureServer` (item 9bdc57b4448e4bc1bd39a0ac024e072b) still lists 29 layers",
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
    reason=(
        "raster and vector contours, not landed: decision 35 lands no raster, and decision 54's wave 1 "
        "registers no contours, which are the maintainer's call; checked gives the measured counts"
    ),
)
