"""Maine Huts & Trails: closures. Its trail_orgs.json row, `maine-huts` (`load: hold`, for its line: it publishes no
machine-readable line), was approved on 2026-10-11 (decision 121, review page 02), so this file moved here from
_shared/maine_huts/, where decision 122 had loaded it held, and its raw table kept its name. Its row in sources.json
still holds the page back.

- `maine_huts_trail_conditions`: the 'Trail Conditions and Updates' page, one PageNotice read through WordPress's
  REST route (page 1851, modified 2026-09-30), which names the closed sections (bridges washed out between Big Eddy
  and Grand Falls). Its title is held to 'Trail Conditions', so a reused page id is refused. mainehuts.org's
  robots.txt asks no Crawl-delay (2026-10-09).

Its 4 huts, the trail's shelters, are pages with no coordinates; the maintainer asked for a page reader that places
them (the same poll, P12), which waits on what the pages carry.
"""

from extract._notices import page_notice

CLAIMS = ("maine_huts_trail_conditions",)
RESOURCES = [page_notice("maine_huts_trail_conditions", wp_page=1851, expect_title="Trail Conditions")]
