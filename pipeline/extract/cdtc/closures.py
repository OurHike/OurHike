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
"""

from extract._kinds import arcgis_layer

CLAIMS = ("cdtc_alert_points", "cdtc_alert_lines", "cdtc_area_closures")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
