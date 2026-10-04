"""AMC Connecticut Chapter: points of interest, published with no coordinate, and not landed (decision 54,
wave 5, read live 2026-10-04).

The chapter's camping page is a table of its A.T. campsites south to north, each with its sleeping area, water
source (brook or spring), toilet and bear box, and no coordinate. ATC's layers place the same sites (atc, code 6:
shelters 7, campsites 16, privies 19, the coverage audit 2026-10-01), so the page's facts need a join to those
points by name, which a person reviews. Needs a per-site reader, not built in this pull request. Its own words,
from /trails/trails-hiking-on-the-at/ (the coverage audit): "Some campsite water sources may dry up at certain
times of year", which says which sources, not when.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (disallows /wp-admin/ only, no Crawl-delay), then /trails/trails-camping/, read 2026-10-04 under "
        "lib/user_agent.py's agent: 200, 69,551 bytes, the campsite table and no coordinate, decimal or DDM, in "
        "the page.",
        "the coverage audit (2026-10-01, batch c1_at_clubs_north): the page is a WordPress page modified "
        "2022-04-04, a 12-site table; Northwest Camp is the chapter's cabin (/nwcamp/); ATC code 6 places the "
        "A.T. sites.",
    ),
    where=("https://ct-amc.org/trails/trails-camping/", "https://ct-amc.org/"),
    reason="needs a per-site reader, not built in this pull request: the campsite table names water and privies and gives no coordinate",
)
