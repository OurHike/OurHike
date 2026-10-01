"""NH GRANIT (University of New Hampshire): closures, nothing published (coverage audit 2026-10-01,
batch p07_persist).

A clearinghouse issues no closures. Quoted in the dated NOT_AVAILABLE note: the two roots, 1,293
layers, the 17 owner hits, and the 913-URL sitemap.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nothing in any GRANIT root is a closure. Tried:; (1) `/nhgeodata/rest/services`: 15 folders and 124 "
        "services. I keyword-scanned 1,293 layer names for hunt, WMU, fire, burn, closure, closed, hazard, "
        "avalanche, alert, danger and bear. The only hits were FEMA flood-hazard layers, fire and EMS stations,"
        " and lidar. 22 services reset the connection and were not read.; `/hosting/rest/services` (a second "
        "root the audit did not walk): 4 folders, 144 services; names scanned, and the only hazard-like one is "
        "`CV_FloodRIskModel_2026_VectorLayers`. `/image/rest/services`: imagery. `/arcgis` and `/server`: …",
    ),
    where=("https://granit.unh.edu/",),
)
