"""Tennessee Trails Association: elevation, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

USGS 3DEP is the elevation source for TN.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same pages.",),
    where=(
        "https://services.arcgis.com/lvPBAGXeSupVUvx2/arcgis/rest/services",
        "https://services1.arcgis.com/YuVBSS7Y1of2Qud1/arcgis/rest/services",
        "https://services3.arcgis.com/PWXNAH2YKmZY7lBq/arcgis/rest/services",
        "https://services5.arcgis.com/bPacKTm9cauMXVfn/arcgis/rest/services",
        "https://tennesseetrails.org/",
    ),
)
