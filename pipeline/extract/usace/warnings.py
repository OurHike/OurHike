"""US Army Corps of Engineers: warnings, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `usace_garrison_hunting_restrictions`: USACE Garrison Project hunting and trapping restrictions
  (2026), `GarrisonHuntingAndTrappingRestrictions20260424/FeatureServer/21`. Its row says why phase
  C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("usace_garrison_hunting_restrictions",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
