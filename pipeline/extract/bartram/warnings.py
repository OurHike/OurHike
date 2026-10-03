"""Bartram Trail Conference: warnings, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's warnings arrive through usfs/ `usfs_r08_prescribed_burns`, each extracted once in its
steward's folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.fs.usda.gov/r08/chattahoochee-oconee/alerts
(html_page); https://www.fs.usda.gov/r08/northcarolina/alerts (html_page).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services/gamelands_general/FeatureServer/21,
NCWRC's 95 game-land boundaries with no season dates: a places geography, not a notice;
https://services6.arcgis.com/9QlSLDqa0P1cHLhu/arcgis/rest/services/WRD_WMA_Public/FeatureServer/14,
Georgia WRD's 222 WMA boundaries with no dates: a places geography, not a notice.

Before decision 53 phase B, 2026-10-03, this note read:

Bartram Trail Conference: warnings, published, and not landed (coverage audit 2026-10-01, batch
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
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/ `usfs_r08_prescribed_burns` (decision 53 phase B, 2026-10-03): `usfs_r08_prescribed_burns` reads `R8_Prescribed_Burn_Status__read_only/FeatureServer/0`",
        "Prescribed fire: `https://services1.arcgis.com/gGHDlz6USftL5Pau/ArcGIS/rest/services/R8_Prescribed_Burn_Status__read_only/FeatureServer/0` (item `1c7b2e51…`, owner USFSRegion08_FAM, data edited 2026-09-29): 19 burn blocks intersect the Bartram line (Planned 4, Partially Completed 1, Other 10, Completed 4); 35 within 500 m. Forest-wide today: Chattahoochee-Oconee (code 03) Planned 85 and Planned for 1-10 days 1; NFs in NC (11) Planned 61 and In Progress 1. Hunting land: NCWRC `https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services/gamelands_general/FeatureServer/21`, data edited …",
    ),
    where=(
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/ArcGIS/rest/services/R8_Prescribed_Burn_Status__read_only/FeatureServer/0",
        "https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services/gamelands_general/FeatureServer/21",
        "https://services6.arcgis.com/9QlSLDqa0P1cHLhu/arcgis/rest/services/WRD_WMA_Public/FeatureServer/14",
        "https://bartramtrail.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
