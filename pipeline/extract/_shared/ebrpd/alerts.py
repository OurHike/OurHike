"""East Bay Regional Park District: alerts and closures, hourly, extracted here once for every club that draws
on it (decision 53 phase B, 2026-10-03). EBRPD has no club folder (decision 18), so it lives in _shared/,
and ridgetrail/closures.py carries the `via` note naming it (decision 34); 52.1 Bay Area Ridge Trail
miles are EBRPD's.

- `ebrpd_alerts_closures`: https://www.ebparks.org/alerts-closures, one PageNotice (extract/_notices.py).

Read live under our agent on 2026-10-03 after www.ebparks.org's robots.txt, which asks `Crawl-delay: 10`
and disallows `/*?*` for every agent: the reader keeps 10 s and asks the URL with no query. Its <main>
lists about 70 posted items by level (Trail Closure 24, Area Closure 12, Danger Advisory 5, Caution
Advisory 5, No Water 2, Water Advisory 1, Fire Warnings 1, the inventory), each with its park, title
and an 'Updated <date>'; the newest of those is the row's date (2026-10-03 that day: Tilden's Wildcat
Gorge and Lake Anza trails closed from Monday 2026-10-05). Its Last-Modified is the response time. The
'No Water' and 'Water Advisory' items are water facts a hiker needs, which the water path does not
read yet. EBRPD's terms forbid redistributing "any information ... obtained from this website" beyond
personal use; they do not name automated access, so this is decision 55's case (the Bay Area Ridge
Trail is named there): facts and a link, the terms quoted on the row.
"""

from extract._kinds import page_notice

TYPE = "closures"
CLAIMS = ("ebrpd_alerts_closures",)
RESOURCES = [page_notice("ebrpd_alerts_closures", crawl_delay=10)]
