"""Wisconsin DNR Open Data: closures, 1 ArcGIS layer extracted here (decision 53 phase B, 2026-10-03).

- `wi_dnr_park_closures`: Wisconsin DNR property closures and notices,
  `WI_Park_Closures_PUBLIC_VIEW/FeatureServer/0`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Wisconsin DNR Open Data: closures, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

The public view exposes `Reporter_email` and `Internal_Contact`, which are staff addresses. Drop
those columns at extract. `Impact=Low` rows are candidates for warnings under decision 7. Skeptic
adds a terms finding (Measured, item `2a0f013583dc452e938aead18cbf71f3` "PR: WI Park Closures PUBLIC
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `WI_Park_Closures_PUBLIC_VIEW/FeatureServer/0`: 69 points, all
`Active_Flag = Yes` (Impact High 25, Moderate 16, Low 28). Fields: `Closure_Name`, `Reason`,
`Description`, `Exp_End_Date`; last edit 2026-09-29. Example: "Governor Knowles SF Cedar Hiking
Trail Section From Mile 25 to 26 Closed", storm damage. Also `LF_DNR_MGD_PROP_WTM_Ext/6`: 1
closed-area polygon (`CLOSE_DATE` 2016-03-08).

Its `where`:
https://services5.arcgis.com/Ul9AyFFeFTjf08DW/arcgis/rest/services/WI_Park_Closures_PUBLIC_VIEW/FeatureServer/0
https://dnrmaps.wi.gov/arcgis/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("wi_dnr_park_closures",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
