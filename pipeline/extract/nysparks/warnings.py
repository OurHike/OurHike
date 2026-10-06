"""NY State Parks / NYS GIS Clearinghouse: warnings, 1 ArcGIS layer extracted here (decision 53 phase
B, 2026-10-03).

- `oprhp_hunting_areas`: NY State Parks hunting areas,
  `NY_State_Parks_Hunting_Areas_2_view/FeatureServer/1`. Its row says why phase C should hold it
  back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("oprhp_hunting_areas",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
