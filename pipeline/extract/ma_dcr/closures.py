"""Massachusetts Department of Conservation and Recreation: closures, hourly. DCR's trail_orgs.json row, `ma-dcr`
(`load: hold`, for its line), was approved on 2026-10-11 (decision 121, review page 02), so its two closures files
moved here from _shared/ma_dcr/ (park_alerts.py and blue_hills_alerts.py), where decision 53 phase B (2026-10-03) had
extracted them once for every club that draws on them, and became this one file; every raw table kept its name. Both
layers have reached hikers since decision 63, which the row's `hold` does not change, and the clubs whose files carry
`via` notes naming them (blue_hills/, amc_berkshire/) draw on them here (decision 34).

- `ma_dcr_park_alerts`: DCR park alerts and advisories, `FACILITYCLOSURE_APPDATA/FeatureServer/0`.
- `ma_dcr_blue_hills_alerts`: https://www.mass.gov/alerts/page/14961, the alerts fragment the Blue Hills
  Reservation's mass.gov page loads (its `data-alerts-path`, node 14961), one PageNotice (extract/_notices.py).

The alerts fragment was read live under our agent on 2026-10-03 after www.mass.gov's robots.txt (no rule matching
/alerts/page/, no Crawl-delay). The fragment is 3,254 bytes with no title of its own, so the row carries the
registry's (`registry_title`); each item is `li > section.ma__action-step` with a headline and an 'Updated <date>'
suffix, and the newest of those is the row's date (2026-09-24 that day, one item: the Blue Hills Fest moved to
October 17, an event notice). The coverage audit's 403 was curl's default agent; ours got 200. Its ETag is Drupal's
page cache and is not trusted. mass.gov's terms forbid copying beyond fair use, which decision 55 names and reads as
facts and a link; nothing of the headline's wording lands, only its hash. Each DCR park has its own node id, so
another park is another registry row. The fragment and the FACILITYCLOSURE_APPDATA layer were not compared item by
item; they are read as two datasets and deduplicated in dbt.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never loads. The ArcGIS
layer's change check is _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS Online, and an
allowed zero only beside the server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer, page_notice

CLAIMS = ("ma_dcr_park_alerts", "ma_dcr_blue_hills_alerts")
RESOURCES = [arcgis_layer("ma_dcr_park_alerts"), page_notice("ma_dcr_blue_hills_alerts", registry_title=True)]
