"""North Country Trail Association: warnings, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `ncta_ice_storm_impacts`: North Country Trail March 2025 ice storm impacts,
  `March_2025_Ice_Storm_Impacts/FeatureServer/0`. Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://northcountrytrail.org/the-trail/trail-alerts/
(html_page).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

North Country Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same layer holds cautions, e.g. "Rough road – not mowed.
Use caution while hiking." Also 18 `Ford` points in the POI layer, and
`March_2025_Ice_Storm_Impacts/0` (1 polygon with an `alert` field, last edit 2025-08-08).

Its `where`: https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ncta_ice_storm_impacts",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
