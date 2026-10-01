"""Bartram Trail Conference: warnings, published, and not landed (coverage audit 2026-10-01, batch
q01_persist).

A burn block is a polygon with a status, not a dated notice. "Planned" has no date, so only In
Progress and "Planned for 1-10 days" should ever reach a hiker (R). Licence: USFS item "The USDA
Forest Service makes no warranty, expressed or implied, … for the accuracy, reliability,
completeness or …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Prescribed fire: "
        "`https://services1.arcgis.com/gGHDlz6USftL5Pau/ArcGIS/rest/services/R8_Prescribed_Burn_Status__read_only/FeatureServer/0`"
        " (item `1c7b2e51…`, owner USFSRegion08_FAM, data edited 2026-09-29): 19 burn blocks intersect the "
        "Bartram line (Planned 4, Partially Completed 1, Other 10, Completed 4); 35 within 500 m. Forest-wide "
        "today: Chattahoochee-Oconee (code 03) Planned 85 and Planned for 1-10 days 1; NFs in NC (11) Planned "
        "61 and In Progress 1. Hunting land: NCWRC "
        "`https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services/gamelands_general/FeatureServer/21`,"
        " data edited …",
    ),
    where=(
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/ArcGIS/rest/services/R8_Prescribed_Burn_Status__read_only/FeatureServer/0",
        "https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services/gamelands_general/FeatureServer/21",
        "https://services6.arcgis.com/9QlSLDqa0P1cHLhu/arcgis/rest/services/WRD_WMA_Public/FeatureServer/14",
        "https://bartramtrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
