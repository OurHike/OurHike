"""Illinois DNR: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives in _shared/ under the
folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type, held"). Held until the
maintainer approves its trail_orgs.json row in chat (decision 121); then this file moves to the club folder of the
same name.

- `il_dnr_closures_page`: 'Current Closures of DNR Sites and Areas', one PageNotice over the HTML page. It states a
  'Last updated' date per region, and the row lands the newest (10/2/26 on 2026-10-09). Its title is held to
  'Closures', so a page that turned into something else is refused. dnr.illinois.gov's robots.txt asks no
  Crawl-delay (2026-10-09).
"""

from extract._notices import page_notice

TYPE = "closures"
CLAIMS = ("il_dnr_closures_page",)
RESOURCES = [page_notice("il_dnr_closures_page", expect_title="Closures")]
