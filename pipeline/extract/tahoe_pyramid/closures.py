"""Tahoe-Pyramid Trail: closures. Its trail_orgs.json row, `tahoe-pyramid` (`load: hold`, for its line: no line source
is chosen, and much of the route is road), was approved on 2026-10-11 (decision 121, review page 01), so this file moved
here from _shared/tahoe_pyramid/, where decision 122 had loaded it held, and its raw table kept its name. Its row in
sources.json still holds the page back.

- `tahoe_pyramid_trail_alerts`: the 'Trail Alerts' page, one PageNotice read through WordPress's REST route
  (page 20392, modified 2026-10-03). Its title is held to 'Trail Alerts', so a reused page id is refused rather
  than read as the alerts. tahoepyramidtrail.org's robots.txt asks no Crawl-delay (2026-10-09).
"""

from extract._notices import page_notice

CLAIMS = ("tahoe_pyramid_trail_alerts",)
RESOURCES = [page_notice("tahoe_pyramid_trail_alerts", wp_page=20392, expect_title="Trail Alerts")]
