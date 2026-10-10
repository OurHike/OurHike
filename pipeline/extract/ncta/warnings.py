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
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ncta_ice_storm_impacts",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
