"""Bartram Trail Conference: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c8_regional_5).

The BTC's KMLs (see `places`) draw Bartram's 18th-century route, not the footpath. Loading them as
trail lines would repeat the route-only mistake.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Via `usfs` → `usfs_trails`: 7 features, 126.42 mi. By segment: `BARTRAM` 080107, 2 / 7.75 mi; 080306, "
        "1 / 35.90 mi; `BARTRAM CHATTOOGA CONNECTOR`, 0.76 mi; `BARTRAM NRT - CHEOAH RD`, 4.91 mi; `BARTRAM NRT"
        " - NANTAHALA RD`, 68.58 mi; `BARTRAM TRAIL EXTENSION`, 8.53 mi. Own geometry: none. BRBTC's FAQ: \"Do "
        "You Have Digital Maps? We are currently working with FarOut … We do not have an estimated access date."
        ' In the meantime, plenty of sections are available on AllTrails and OnX."',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/ArcGIS/rest/services",
        "https://bartramtrail.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
