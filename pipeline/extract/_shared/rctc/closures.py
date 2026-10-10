"""Rachel Carson Trails Conservancy: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives
in _shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type,
held"). Held until the maintainer approves the conservancy's trail_orgs.json row in chat (decision 121); then this
file moves to the club folder of the same name.

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

TYPE = "closures"
CLAIMS = ("rctc_rachel_carson_trail_alerts", "rctc_baker_trail_alerts", "rctc_harmony_trail_alerts")
RESOURCES = [
    page_notice("rctc_rachel_carson_trail_alerts", expect_title="Rachel Carson Trail"),
    page_notice("rctc_baker_trail_alerts", expect_title="Baker Trail"),
    page_notice("rctc_harmony_trail_alerts", expect_title="Harmony Trail"),
]
