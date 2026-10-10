"""The Maah Daah Hey Trail Association's trail guide points: trailheads, campgrounds, water cache boxes, river
crossings and points of interest, the `data-lat`/`data-long` anchors its own map plots.

Decision 54, wave 5: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where the row carries the count, the measured
key, the terms and what holds it back.

- `mdhta_trail_guide_points`: 50 points (19 trailheads, 11 campgrounds, 8 waterboxes, 6 river crossings, 6
  points of interest), keyed on each point's own page.

A WATERBOX IS A CACHE, NEVER A WATER SOURCE: the association's FAQ says its eight water cache sites were
added by volunteers and that a hiker's surest plan is to cache water before the trip. The campgrounds' hand
pumps are seasonal ('Pump handles are removed about November 10 through April'), which the row's notes carry
for decision 65's caution. The same page's trail lines are mdhta/trail_lines.py's `mdhta_trail_guide`, read
from the GeoJSON files the page links: one page, two datasets.
"""

from extract._pages_points import page_points

CLAIMS = ("mdhta_trail_guide_points",)
RESOURCES = [page_points(key) for key in CLAIMS]
