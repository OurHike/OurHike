"""Massachusetts DCR: the Blue Hills Reservation's notices and alerts, hourly, extracted here once for every club
that draws on it (decision 53 phase B, 2026-10-03); blue_hills/ carries the `via` note naming it.

- `ma_dcr_blue_hills_alerts`: https://www.mass.gov/alerts/page/14961, the alerts fragment the park's
  mass.gov page loads (its `data-alerts-path`, node 14961), one PageNotice (extract/_notices.py).

Read live under our agent on 2026-10-03 after www.mass.gov's robots.txt (no rule matching
/alerts/page/, no Crawl-delay). The fragment is 3,254 bytes with no title of its own, so the row carries
the registry's (`registry_title`); each item is `li > section.ma__action-step` with a headline and an
'Updated <date>' suffix, and the newest of those is the row's date (2026-09-24 that day, one item: the
Blue Hills Fest moved to October 17, an event notice). The coverage audit's 403 was curl's default
agent; ours got 200. Its ETag is Drupal's page cache and is not trusted. mass.gov's terms forbid
copying beyond fair use, which decision 55 names and reads as facts and a link; nothing of the
headline's wording lands, only its hash.

Each DCR park has its own node id, so another park is another registry row. The fragment and
ma_dcr_park_alerts.py's ArcGIS layer (`FACILITYCLOSURE_APPDATA`) were not compared item by item; they
are read as two datasets and deduplicated in dbt.
"""

from extract._kinds import page_notice

TYPE = "closures"
CLAIMS = ("ma_dcr_blue_hills_alerts",)
RESOURCES = [page_notice("ma_dcr_blue_hills_alerts", registry_title=True)]
