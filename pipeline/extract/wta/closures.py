"""Washington Trails Association: closures, from the Signpost blog's listing, hourly (decision 53 phase B and
decision 55, 2026-10-03).

`wta_signpost` reads https://www.wta.org/news/signpost as one PageNotice (extract/_notices.py), read live
under our agent on 2026-10-03 after www.wta.org's robots.txt, which asks `Crawl-delay: 60` and
disallows `/*?` for every agent: the reader keeps 60 s and asks the URL with no query, one request an
hour. WTA's weekly 'Hiker Headlines' posts relay agency closures ('Hiker Headlines: New ADA trail,
Newhalem visitor center closed for winter, now hiring', 2026-10-01; 'Summerland trailhead will be
closed Sept. 28–Oct. 31', 2026-09-24), each at a new URL, so the blog's listing is the channel; it
also moves with every other blog post. The row lands the listing's title, a hash of its first
<article> and the link. The footer's Signpost RSS link (/trail-news/signpost/the-signpost/RSS)
answered 404 (the inventory, batch 4).

WTA's terms restrict its content to "internal informational purposes" (quoted on the sources.json
row), which decision 55 names and reads as facts and a link. The inventory recommended not
registering it, because WTA relays the agencies (NPS, USFS Region 6) that nps/ and usfs/ extract
first-hand; decision 55 publishes WTA's notices on that split, so it lands, held by reaches_hikers, and
the agencies stay the authoritative channel. not_available.toml [wta.warnings] shares this file.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c7_regional_4): "Page. WTA relays agency closures, so the authoritative channel is the agency
(NPS/USFS). Restricted by the ToS."
"""

from extract._kinds import page_notice

CLAIMS = ("wta_signpost",)
RESOURCES = [page_notice("wta_signpost", crawl_delay=60)]
