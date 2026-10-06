"""Continental Divide Trail Coalition: closures, 3 ArcGIS layers extracted here (decision 53 phase B,
2026-10-03).

- `cdtc_alert_points`: CDT alert points, `CDT_Alerts_view/FeatureServer/1`.
- `cdtc_alert_lines`: CDT alert lines, `CDT_Alerts_view/FeatureServer/2`.
- `cdtc_area_closures`: CDT area closures, `Area_Closures_view/FeatureServer/1`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Read and not wired (decision 53 phase B, 2026-10-03): https://cdtcoalition.org/closures-and-alerts/,
a page embedding the ArcGIS Instant app over the layers above (app
1ddce45fa58b4ba39a2125c61fd394e8), so the layers are the data. Its terms page (/terms-of-service/)
is a Termly JavaScript embed whose text is not in the server's HTML; no prohibition was read, and
none is assumed.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Continental Divide Trail Coalition: closures, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

The best-shaped feed in this batch. `Type` plus `Active` maps straight onto decision 7's
`obstructs_trail` split, and `Milepost` is present.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `CDT_Alerts_view/FeatureServer/1` Alert Points: 149, with
`Active=Yes` on 12 `Closure` and 15 `Alert`. `/2` Alert Lines: 76, with `Active=Yes` on 6 `Closure`
and 6 `Alert`. `Area_Closures_view/1`: 4 polygons, 1 active. `Reroutes_view/1`: 30, 7 active. Last
edit 2026-09-24. Page: `cdtcoalition.org/closures-and-alerts/`.

Its `where`:
https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/CDT_Alerts_view/FeatureServer/1
https://cdtcoalition.org/closures-and-alerts/ https://services.wygisc.org/HostGIS/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("cdtc_alert_points", "cdtc_alert_lines", "cdtc_area_closures")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
