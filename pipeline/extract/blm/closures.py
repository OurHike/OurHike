"""Bureau of Land Management: closures, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `blm_or_rec_site_status`: BLM Oregon recreation site status,
  `OregonRecreationStatusWebmap20210428/FeatureServer/0`. Its row says why phase C should hold it
  back.

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

Bureau of Land Management: closures, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Format: RSS of mixed press releases, so it needs decision 7's classifier and a closure-keyword
filter. There is no geometry; a release names a county or area. `/alerts` was empty when the server
sent it (skeptic, Measured). That a Drupal view would have rendered items there is Reasoned.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `https://www.blm.gov/alerts`: server-rendered list with region
filter, read "No Results" today. Closures appear in the state press-release RSS feeds (13, listed at
`https://www.blm.gov/info/RSS-feeds`). `https://www.blm.gov/press-release/utah/rss`: 51 items,
newest 2026-09-30, including "BLM to Temporarily Close Public Lands in Iron County for Special
Recreation Events". Federal Register API, BLM agency, 2026: 0 documents matching "temporary
closure". BLM EGIS AGOL search: 138 hits for closure/restriction/alert terms, no closure-order layer
(Colorado "Closed to Fluid Mineral Leasing" is …

Its `where`: https://www.blm.gov/alerts https://www.blm.gov/info/RSS-feeds
https://www.blm.gov/press-release/utah/rss https://gis.blm.gov/arcgis/rest/services https://blm.gov/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("blm_or_rec_site_status",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
