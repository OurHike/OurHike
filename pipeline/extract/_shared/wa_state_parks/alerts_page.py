"""Washington State Parks and Recreation Commission: its alerts page, held. The commission has no trail_orgs.json row
yet, and decision 122 (the maintainer's poll, 2026-10-09: "Every type, held") loads a candidate steward's layers now,
held until its row is approved in chat (decision 121); its winter closures layer is winter_closures.py's.

- `wsprc_alerts_page`: https://parks.wa.gov/about/news-announcements/alerts, every park's alerts in one Drupal
  listing (the coverage audit counted 234 on 2026-10-01), one PageNotice. The listing has no feed and no JSON, so the
  whole page is one notice and any alert's edit reads as a new version of it. Its title is held to 'Alerts'.
  parks.wa.gov's robots.txt asks no Crawl-delay (2026-10-09).
"""

from extract._notices import page_notice

TYPE = "closures"
CLAIMS = ("wsprc_alerts_page",)
RESOURCES = [page_notice("wsprc_alerts_page", expect_title="Alerts")]
