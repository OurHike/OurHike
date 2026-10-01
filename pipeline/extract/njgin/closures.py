"""NJDEP / NJGIN — Statewide Trails: closures, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

These are park-level and area-level closures, not trail-level ones. Trail-level closures live only
on the walled advisories page, which the trail data's own terms tell hikers to check. So trail
closures for NJ stay UNKNOWN in substance until someone with a browser reads that page, or NJDEP is
asked …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/New_Jersey_State_Park_Service_Live_Status_Updates_(Public_View)/FeatureServer/0`:"
        " 53 park points with `Status` Open 51 / Closed 2 (Indian King Tavern and Walt Whitman House historic "
        "sites), `Park_Hours`, `Swimming`, and `EditDate` from 2026-01-28 to 2026-09-30. "
        "`Wildlife_Management_Area_WMA_Restrictions_in_New_Jersey/FeatureServer/41`: 206 polygons, edited "
        "2026-09-29. Its `TYPE` field has Closed 20 (No Access 11, Law Enforcement 8, No Hunting 1), and 12 of "
        "those are current by `EDATE`. Each has `SDATE`/`EDATE` and prose, for …",
    ),
    where=(
        "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/New_Jersey_State_Park_Service_Live_Status_Updates_(Public_View)/FeatureServer/0",
        "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/Wildlife_Management_Area_WMA_Restrictions_in_New_Jersey/FeatureServer/41",
        "https://mapsdep.nj.gov/arcgis/rest/services",
        "https://njogis-newjersey.opendata.arcgis.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
