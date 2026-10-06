"""Colorado Parks & Wildlife — COTREX: closures, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `cotrex_seasonal_closures`: COTREX seasonal wildlife closures,
  `SCs_All_COTREX_Sept2025_Final/FeatureServer/0`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Read and not wired (decision 53 phase B, 2026-10-03): https://cpw.state.co.us/hunting/big-game (now
/activities/hunting/big-game) and https://cpw.state.co.us/living-bears, evergreen guidance pages
(JSON-LD dateModified 2026-09-29 and 2026-08-14), not notices; season dates are in brochures.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Colorado Parks & Wildlife — COTREX: closures, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

The layer was last built for the 2025–26 season. Whether a 2026–27 rebuild is coming is
@unvalidated; what would settle it is CPW's schedule.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `SCs_All_COTREX_Sept2025_Final/FeatureServer/0`: 128 seasonal
wildlife closure polygons with `Agency`, `Closure_Period`, `Start_Date`, `End_Date`,
`Restricted_Use_Types`, `URL`; last edit 2025-10-09. The points version holds 127. The Experience
app is "COTREX Seasonal Wildlife Closures". `Fishing_Closures` also exists.

Its `where`:
https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/SCs_All_COTREX_Sept2025_Final/FeatureServer/0
https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("cotrex_seasonal_closures",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
