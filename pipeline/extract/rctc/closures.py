"""Rachel Carson Trails Conservancy: closures. The conservancy's trail_orgs.json row, `rctc` (`load: ship`), was
approved on 2026-10-11 (decision 121, review page 02), so these files moved here from _shared/rctc/, where decision 122
had loaded them held, and every raw table kept its name.

Three trail pages, each a PageNotice: the conservancy posts its alerts in a 'Trail Alerts' section of each trail's
page, which has no element of its own, so the whole page is the notice. Each title is held to the trail's name (the
page's og:title, as no <h1> sits inside <main>). The alerts date themselves day first ('(14 August 2026)'), which the
reader does not read, so the rows land no date. www.rachelcarsontrails.org's robots.txt asks no Crawl-delay
(2026-10-09).

- `rctc_rachel_carson_trail_alerts`: /trails/rachel-carson-trail.
- `rctc_baker_trail_alerts`: /trails/baker-trail.
- `rctc_harmony_trail_alerts`: /trails/harmony-trail.
"""

from extract._notices import page_notice

CLAIMS = ("rctc_rachel_carson_trail_alerts", "rctc_baker_trail_alerts", "rctc_harmony_trail_alerts")
RESOURCES = [
    page_notice("rctc_rachel_carson_trail_alerts", expect_title="Rachel Carson Trail"),
    page_notice("rctc_baker_trail_alerts", expect_title="Baker Trail"),
    page_notice("rctc_harmony_trail_alerts", expect_title="Harmony Trail"),
]
