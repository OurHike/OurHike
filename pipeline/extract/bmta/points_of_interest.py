"""The Benton MacKaye Trail Association's access points and trailheads: 49 rows, each a BMT mile and its text,
and a fix for 47, from the PDF table the association publishes.

Decision 54, wave 4: read live on 2026-10-04 (robots.txt first, `Crawl-delay: 60` honoured,
lib/user_agent.py's agent) and registered in sources.json, where the row carries the count, the validators,
the measured key and what holds it back.

- `bmta_access_points`: 49 access points, keyed on the mile and the text.

The table is dated 5/24/2020 on every page. The Thru-Hikers' Guide names the one BMT shelter ('on the Sisson
property at mile 50.3') in prose, with no fix, so it is not a point here (the coverage audit, 2026-10-01).
"""

from extract._pdf_points import pdf_points

CLAIMS = ("bmta_access_points",)
RESOURCES = [pdf_points(key) for key in CLAIMS]
