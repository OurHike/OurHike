"""Santa Clara County Parks: closures, extracted here once for every club that draws on it (decision 53
phase B, 2026-10-03). Its steward has no club folder (decision 18), so it lives in _shared/, and
each club's own file carries a `via` note naming it (decision 34).

- `scc_parks_closed_areas`: Santa Clara County Parks areas closed to the public,
  `Santa_Clara_County_Parks_Closed_Areas_view/FeatureServer/1`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer

TYPE = "closures"
CLAIMS = ("scc_parks_closed_areas",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
