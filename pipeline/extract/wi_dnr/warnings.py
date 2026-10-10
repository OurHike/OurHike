"""Wisconsin DNR Open Data: warnings, 1 ArcGIS layer extracted here (decision 53 phase B, 2026-10-03).

- `wi_dnr_fire_danger`: Wisconsin DNR current fire danger by county,
  `FR_WIS_BURN/FR_WIS_BURN_MAP_EXT/MapServer/13`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("wi_dnr_fire_danger",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
