"""US Army Corps of Engineers: warnings, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `usace_garrison_hunting_restrictions`: USACE Garrison Project hunting and trapping restrictions
  (2026), `GarrisonHuntingAndTrappingRestrictions20260424/FeatureServer/21`. Its row says why phase
  C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

US Army Corps of Engineers: warnings, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

One district.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Omaha District
`services5.arcgis.com/6AHfZAoqk1VUqQpS/.../GarrisonHuntingAndTrappingRestrictions20260424/FeatureServer`
(hunting and trapping restrictions 2026, Lake Sakakawea / Garrison). Skeptic counted it: layer 21
"Restriction", 24 polygons (`Restriction`, `AreaName`, `AreaDescription`, `ContactOffice`), last
edited 2026-05-29.

Its `where`: https://usace.army.mil/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("usace_garrison_hunting_restrictions",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
