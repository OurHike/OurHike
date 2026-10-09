"""Maricopa County Parks: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives in _shared/
under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type, held"). Held until
the maintainer approves the county's trail_orgs.json row in chat (decision 121); then this file moves to the club
folder of the same name.

The news feed of each of the 14 parks the site's /rss/ page lists, one FeedNotices each. The county posts a
systemwide notice (a fire ban, a no-burn day) into every park's feed, so the 14 feeds' 110 items on 2026-10-09 were
24 distinct notices, and which parks a notice concerns is which feeds carry it. Each feed mixes notices with news.
www.maricopacountyparks.net's robots.txt asks no Crawl-delay and refuses no query string (2026-10-09). Each park's
events feed is not a notice and is not loaded.
"""

from extract._notices import feed_notices

TYPE = "closures"
CLAIMS = (
    "maricopa_adobe_dam_news",
    "maricopa_buckeye_hills_news",
    "maricopa_cave_creek_news",
    "maricopa_desert_outdoor_center_news",
    "maricopa_estrella_mountain_news",
    "maricopa_hassayampa_river_news",
    "maricopa_lake_pleasant_news",
    "maricopa_maricopa_trail_news",
    "maricopa_mcdowell_mountain_news",
    "maricopa_san_tan_mountain_news",
    "maricopa_spur_cross_ranch_news",
    "maricopa_usery_mountain_news",
    "maricopa_vulture_mountains_news",
    "maricopa_white_tank_mountain_news",
)
RESOURCES = [feed_notices(key) for key in CLAIMS]
