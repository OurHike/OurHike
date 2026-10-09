"""Tahoe-Pyramid Trail: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives in _shared/
under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type, held"). Held
until the maintainer approves its trail_orgs.json row in chat (decision 121); then this file moves to the club
folder of the same name.

- `tahoe_pyramid_trail_alerts`: the 'Trail Alerts' page, one PageNotice read through WordPress's REST route
  (page 20392, modified 2026-10-03). Its title is held to 'Trail Alerts', so a reused page id is refused rather
  than read as the alerts. tahoepyramidtrail.org's robots.txt asks no Crawl-delay (2026-10-09).
"""

from extract._notices import page_notice

TYPE = "closures"
CLAIMS = ("tahoe_pyramid_trail_alerts",)
RESOURCES = [page_notice("tahoe_pyramid_trail_alerts", wp_page=20392, expect_title="Trail Alerts")]
