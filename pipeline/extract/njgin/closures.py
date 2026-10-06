"""NJDEP / NJGIN — Statewide Trails: closures, 2 ArcGIS layers extracted here (decision 53 phase B,
2026-10-03).

- `njdep_park_status`: NJ State Park Service live park status,
  `New_Jersey_State_Park_Service_Live_Status_Updates_(Public_View)/FeatureServer/0`.
- `njdep_wma_restrictions`: NJ Fish & Wildlife WMA closures and restrictions,
  `Wildlife_Management_Area_WMA_Restrictions_in_New_Jersey/FeatureServer/41`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

NJDEP / NJGIN — Statewide Trails: closures, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

These are park-level and area-level closures, not trail-level ones. Trail-level closures live only
on the walled advisories page, which the trail data's own terms tell hikers to check. So trail
closures for NJ stay UNKNOWN in substance until someone with a browser reads that page, or NJDEP is
asked …

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01):
`https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/New_Jersey_State_Park_Service_Live_Status_Updates_(Public_View)/FeatureServer/0`:
53 park points with `Status` Open 51 / Closed 2 (Indian King Tavern and Walt Whitman House historic
sites), `Park_Hours`, `Swimming`, and `EditDate` from 2026-01-28 to 2026-09-30.
`Wildlife_Management_Area_WMA_Restrictions_in_New_Jersey/FeatureServer/41`: 206 polygons, edited
2026-09-29. Its `TYPE` field has Closed 20 (No Access 11, Law Enforcement 8, No Hunting 1), and 12
of those are current by `EDATE`. Each has `SDATE`/`EDATE` and prose, for …

Its `where`:
https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/New_Jersey_State_Park_Service_Live_Status_Updates_(Public_View)/FeatureServer/0
https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/Wildlife_Management_Area_WMA_Restrictions_in_New_Jersey/FeatureServer/41
https://mapsdep.nj.gov/arcgis/rest/services https://njogis-newjersey.opendata.arcgis.com/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("njdep_park_status", "njdep_wma_restrictions")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
