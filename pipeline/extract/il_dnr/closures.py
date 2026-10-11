"""Illinois DNR: closures. IL DNR's trail_orgs.json row, `il-dnr` (`load: via`), was approved on 2026-10-11 (decision
121, review page 02), so this file moved here from _shared/il_dnr/, where decision 122 had loaded it held, and its raw
table kept its name. The Grand Illinois Trail's only line is IDOT's bicycle inventory, which idot/trail_lines.py
extracts, and IL DNR's row points to IDOT's (the same poll, P10).

- `il_dnr_closures_page`: 'Current Closures of DNR Sites and Areas', one PageNotice over the HTML page. It states a
  'Last updated' date per region, and the row lands the newest (10/2/26 on 2026-10-09). Its title is held to
  'Closures', so a page that turned into something else is refused. dnr.illinois.gov's robots.txt asks no
  Crawl-delay (2026-10-09).
"""

from extract._notices import page_notice

CLAIMS = ("il_dnr_closures_page",)
RESOURCES = [page_notice("il_dnr_closures_page", expect_title="Closures")]
