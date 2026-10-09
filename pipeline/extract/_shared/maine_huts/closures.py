"""Maine Huts & Trails: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives in _shared/
under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type, held"). Held until
the maintainer approves its trail_orgs.json row in chat (decision 121); then this file moves to the club folder of
the same name.

- `maine_huts_trail_conditions`: the 'Trail Conditions and Updates' page, one PageNotice read through WordPress's
  REST route (page 1851, modified 2026-09-30), which names the closed sections (bridges washed out between Big Eddy
  and Grand Falls). Its title is held to 'Trail Conditions', so a reused page id is refused. mainehuts.org's
  robots.txt asks no Crawl-delay (2026-10-09).

Its 4 huts, the trail's shelters, are pages with no coordinates, which need a page reader nothing has yet.
"""

from extract._notices import page_notice

TYPE = "closures"
CLAIMS = ("maine_huts_trail_conditions",)
RESOURCES = [page_notice("maine_huts_trail_conditions", wp_page=1851, expect_title="Trail Conditions")]
