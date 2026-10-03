"""Bureau of Land Management: warnings, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `blm_shooting_points`: BLM recreational shooting points, `BLM_Qualified_Shooting/FeatureServer/0`.
  Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.blm.gov/alerts (html_page);
https://www.blm.gov/press-release/utah/rss (one of 13 state/office press-release feeds listed at
https://www.blm.gov/info/RSS-feeds, plus /blog/rss) (rss);
https://www.blm.gov/programs/fire/fire-restrictions (html_page).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Bureau of Land Management: warnings, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Shooting points are areas set aside for target shooting. Whether that counts as a hiker hazard
warning is a maintainer call. Skeptic: fire restrictions are page format, one page per state.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same press-release RSS (e.g. Utah "BLM to Reduce Hazardous
Fuels around Grover, Utah"). A "Fire Restrictions" page is linked from blm.gov's navigation.
`https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/BLM_Qualified_Shooting/FeatureServer/0`
("BLM Natl EXPLORE Recreational Shooting Points", owner `an email address`, item modified
2026-04-21): 93 points. | Skeptic (Measured 2026-10-01):
`https://www.blm.gov/programs/fire/fire-restrictions` opened. It is a page of 14 state links, Alaska
through Wyoming; Nevada's goes to `https://www.nevadafireinfo.org/restrictions`, off …

Its `where`:
https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/BLM_Qualified_Shooting/FeatureServer/0
https://www.blm.gov/programs/fire/fire-restrictions https://www.nevadafireinfo.org/restrictions
https://blm.gov https://gis.blm.gov/arcgis/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("blm_shooting_points",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
