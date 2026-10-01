"""Tennessee Trails Association: photos, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Photos appear only in the Facebook group and on YouTube, with no licence.",),
    where=(
        "https://services.arcgis.com/lvPBAGXeSupVUvx2/arcgis/rest/services",
        "https://services1.arcgis.com/YuVBSS7Y1of2Qud1/arcgis/rest/services",
        "https://services3.arcgis.com/PWXNAH2YKmZY7lBq/arcgis/rest/services",
        "https://services5.arcgis.com/bPacKTm9cauMXVfn/arcgis/rest/services",
        "https://tennesseetrails.org/",
    ),
)
