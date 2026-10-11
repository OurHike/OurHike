"""Eastern Trail Alliance: closures. The alliance's trail_orgs.json row, `eastern-trail` (`load: hold`, for its line: it
publishes no readable line of its own), was approved on 2026-10-11 (decision 121, review page 02), so this file moved
here from _shared/eastern_trail/, where decision 122 had loaded it held, and its raw table kept its name. Its row in
sources.json still holds the page back.

- `eastern_trail_conditions`: the 'Trail Conditions' page, one PageNotice read through WordPress's REST route
  (page 62, modified 2026-08-29), which lists alerts by area. Its title is held to 'Trail Conditions', so a reused
  page id is refused rather than read as the conditions. www.easterntrail.org's robots.txt asks no Crawl-delay
  (2026-10-09).
"""

from extract._notices import page_notice

CLAIMS = ("eastern_trail_conditions",)
RESOURCES = [page_notice("eastern_trail_conditions", wp_page=62, expect_title="Trail Conditions")]
