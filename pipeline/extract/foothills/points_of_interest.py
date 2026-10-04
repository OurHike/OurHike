"""The Foothills Trail Conservancy's 17 access points, its "GPS Coordinates" table, read through WordPress page
603's REST route.

Decision 54, wave 5: read live on 2026-10-04 (robots.txt first, its `Disallow: /*?` and `Crawl-delay: 10`
both honoured, lib/user_agent.py's agent) and registered in sources.json, where the row carries the count, the
measured key and what holds it back.

- `foothills_gps_coordinates`: 17 access points, keyed on the name.

The FAQ says the trail's campsites, bear cables and water posts ("a wooden post with a blue reflector") are
listed only in the paid guidebook and FarOut, so no campsite or water point is published to load (the
coverage audit, 2026-10-01).
"""

from extract._pages_points import page_points

CLAIMS = ("foothills_gps_coordinates",)
RESOURCES = [page_points(key) for key in CLAIMS]
