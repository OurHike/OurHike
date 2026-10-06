"""Wisconsin DNR Open Data: warnings, 1 ArcGIS layer extracted here (decision 53 phase B, 2026-10-03).

- `wi_dnr_fire_danger`: Wisconsin DNR current fire danger by county,
  `FR_WIS_BURN/FR_WIS_BURN_MAP_EXT/MapServer/13`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Wisconsin DNR Open Data: warnings, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Daily fire danger is the hourly or daily lane's, not the monthly one (decision 1).

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `FR_WIS_BURN/FR_WIS_BURN_MAP_EXT/MapServer/13` "Current Fire
Danger": 72 county polygons with `DANGER_RATING_NAME`, `NO_BURN_FLAG`, `PERMIT_RESTRICTIONS`. Newest
`LAST_CHANGED_DATE` is 2026-09-30 11:53 UTC; all 72 read LOW today. `/0` Wildfires (Today) holds 0
rows.

Its `where`:
https://dnrmaps.wi.gov/arcgis/rest/services/FR_WIS_BURN/FR_WIS_BURN_MAP_EXT/MapServer/13

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("wi_dnr_fire_danger",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
