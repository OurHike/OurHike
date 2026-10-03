"""North Country Trail Association: closures, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `ncta_trail_alerts`: North Country Trail alerts, `trail_alerts/FeatureServer/1`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://northcountrytrail.org/the-trail/trail-alerts/
(html_page).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

North Country Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

No active flag, so every row is "not reviewed" under decision 7. Rows dated 2021 are still in the
layer, so expiry by `Date` is @unvalidated.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `trail_alerts/FeatureServer/1`: 67 points with `Date`
(2021-01-01 to 2026-09-11), `Location`, `desc_`, `label`. Example: "Trail Alert: Garrison Dam —
…closed the shoreline to all recreation through Nov. 15". Page:
`northcountrytrail.org/the-trail/trail-alerts/` ("Any current North Country Trail closures or
reroutes will be posted here").

Its `where`:
https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/trail_alerts/FeatureServer/1
https://northcountrytrail.org/the-trail/trail-alerts/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ncta_trail_alerts",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
