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
"""

from extract._kinds import arcgis_layer

CLAIMS = ("njdep_park_status", "njdep_wma_restrictions")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
