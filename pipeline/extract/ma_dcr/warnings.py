"""Massachusetts Department of Conservation and Recreation: warnings (decision 53 phase B's load, here since DCR's
row; closures.py says how this folder came to be). Each club's own file carries a `via` note naming it (decision 34).

- `ma_dcr_blue_hills_hunt_areas`: DCR Blue Hills hunt areas, `HuntAreas_BH_PGC_FM/FeatureServer/18`.
  Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never loads. Its change check
is _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS Online, and an allowed zero only beside
the server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ma_dcr_blue_hills_hunt_areas",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
