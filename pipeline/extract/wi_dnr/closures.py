"""Wisconsin DNR Open Data: closures, 1 ArcGIS layer extracted here (decision 53 phase B, 2026-10-03).

- `wi_dnr_park_closures`: Wisconsin DNR property closures and notices,
  `WI_Park_Closures_PUBLIC_VIEW/FeatureServer/0`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("wi_dnr_park_closures",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
