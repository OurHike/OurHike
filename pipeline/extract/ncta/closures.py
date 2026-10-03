"""North Country Trail Association: closures, 1 ArcGIS layer and the trail-alerts page extracted here (decision
53 phase B, 2026-10-03).

- `ncta_trail_alerts`: North Country Trail alerts, `trail_alerts/FeatureServer/1`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

- `ncta_trail_alerts_page`: https://northcountrytrail.org/the-trail/trail-alerts/, one PageNotice
  (extract/_notices.py), read live 2026-10-03 after the host's robots.txt, which asks `Crawl-delay: 3`
  and disallows `/*?` for every agent: the reader keeps 3 s and asks the URL with no query. The
  page lists the alerts by state in prose (14,035 characters in its <article>), dated 2026-09-11 by
  its JSON-LD dateModified. It says 'Alerts are posted both here and within the online map', that
  map being the layer above; the two were not compared item by item, so the page is not noted as a
  copy (a SAME_AS needs the comparison), and dbt deduplicates the two after the load. The page
  names a ranger district office's public telephone line; the reader lands only the title, the
  date, a hash and the link.

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

from extract._kinds import arcgis_layer, page_notice

CLAIMS = ("ncta_trail_alerts", "ncta_trail_alerts_page")
RESOURCES = [arcgis_layer("ncta_trail_alerts"), page_notice("ncta_trail_alerts_page", crawl_delay=3)]
