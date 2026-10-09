"""Eastern Trail Alliance: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives in _shared/
under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type, held"). Held until
the maintainer approves its trail_orgs.json row in chat (decision 121); then this file moves to the club folder of
the same name.

- `eastern_trail_conditions`: the 'Trail Conditions' page, one PageNotice read through WordPress's REST route
  (page 62, modified 2026-08-29), which lists alerts by area. Its title is held to 'Trail Conditions', so a reused
  page id is refused rather than read as the conditions. www.easterntrail.org's robots.txt asks no Crawl-delay
  (2026-10-09).
"""

from extract._notices import page_notice

TYPE = "closures"
CLAIMS = ("eastern_trail_conditions",)
RESOURCES = [page_notice("eastern_trail_conditions", wp_page=62, expect_title="Trail Conditions")]
