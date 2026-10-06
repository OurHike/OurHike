"""Cumberland Trail / Tennessee State Parks: closures, 1 ArcGIS layer extracted here (decision 53 phase
B, 2026-10-03).

- `ctsst_public_hazards_closures`: Cumberland Trail public hazards and closures,
  `PUBLIC_CTSST_2020_gdb/FeatureServer/15`. Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Also drawn from (decision 53 phase B, 2026-10-03, decision 34): _shared/tdec/ `tdec_trail_closures`.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://tnstateparks.com/api/alerts (json_api).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ctsst_public_hazards_closures",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
