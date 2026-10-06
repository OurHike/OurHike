"""The Bartram Trail's section trailheads, from the Blue Ridge Bartram Trail Conservancy's 13 section pages: each
section's number, name and length, and the fix of the trailhead it starts at.

Decision 54, wave 5: read live on 2026-10-04 (robots.txt first, a Crawl-delay of 10 s honoured,
lib/user_agent.py's agent) and registered in sources.json, where the row carries the count, the measured key
and what holds it back.

- `brbtc_section_trailheads`: 13 trailheads, keyed on the section number; the pages are the ones the
  Conservancy's trail-section sitemap lists, so a section it adds is read without a registry edit.

The Conservancy is the trail's steward; this folder is named for the Bartram Trail Conference, the umbrella
the coverage audit found in its row (2026-10-01, c8_regional_5). Water and camping are prose on the pages
("Campsites and water are sparse and in gaps"), so no water point is published to load. Each page's map also
loads a GeoJSON of the section's line, a GIS file not_available.toml [bartram.trail_lines] does not read yet.
"""

from extract._pages_points import page_points

CLAIMS = ("brbtc_section_trailheads",)
RESOURCES = [page_points(key) for key in CLAIMS]
