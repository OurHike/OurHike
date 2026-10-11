"""Rachel Carson Trails Conservancy: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives
in _shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type,
held"). Held until the maintainer approves the conservancy's trail_orgs.json row in chat (decision 121); then this
file moves to the club folder of the same name.

Three trail pages, each a PageNotice: the conservancy posts its alerts in a 'Trail Alerts' section of each trail's
page, which has no element of its own, so the whole page is the notice. Each title is held to the trail's name (the
page's og:title, as no <h1> sits inside <main>). www.rachelcarsontrails.org's robots.txt asks no Crawl-delay
(2026-10-09).

THE DATE IS THE NEWEST ALERT'S, as NBATC's is its newest item's (extract/nbatc/closures.py). The pages state no
"Updated" stamp, and each alert ends in its own date in parentheses, day first ('(14 August 2026)'), which DATE has
read since P13 (the maintainer, 2026-10-11: "Fix the dates!"); ALERT_DATE is that date alone in its parentheses.
Measured 2026-10-11, one read of each page's <main>: 31 such dates on the Rachel Carson Trail's (newest
'(11 March 2026)'), 14 on the Baker Trail's ('(14 August 2026)') and 1 on the Harmony Trail's ('(14 February
2024)'). Nine of them name a month and no day ('(October 2013)', '(May 2024)'), which is no day, and are not read.
A date more than a day ahead is not a page's date either (page_stated_date()).

- `rctc_rachel_carson_trail_alerts`: /trails/rachel-carson-trail.
- `rctc_baker_trail_alerts`: /trails/baker-trail.
- `rctc_harmony_trail_alerts`: /trails/harmony-trail.
"""

from extract._notices import DATE, page_notice

# An alert's own date, the whole of its parentheses: '(14 August 2026)'.
ALERT_DATE = r"\(" + DATE + r"\)"

TYPE = "closures"
CLAIMS = ("rctc_rachel_carson_trail_alerts", "rctc_baker_trail_alerts", "rctc_harmony_trail_alerts")
RESOURCES = [
    page_notice("rctc_rachel_carson_trail_alerts", expect_title="Rachel Carson Trail", date_pattern=ALERT_DATE),
    page_notice("rctc_baker_trail_alerts", expect_title="Baker Trail", date_pattern=ALERT_DATE),
    page_notice("rctc_harmony_trail_alerts", expect_title="Harmony Trail", date_pattern=ALERT_DATE),
]
