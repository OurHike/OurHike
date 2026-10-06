"""Foothills Trail Conservancy: suggested hikes, its section-by-section pages read here (decision 54 wave 5,
section K, 2026-10-04).

- `foothills_sections`: the section-by-section index and its 19 /portfolio/ pages, 13 sections and 6 spurs, each its
  distance, difficulty (per direction where the page gives two), blazes and the trailheads at its ends.
  foothillstrail.org's robots.txt asks `Crawl-delay: 10` and disallows every URL with a query string, so 20 requests
  a month, none with a query.

The reader is extract/_pages_content.py's ContentPages with the `foothills_sections` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its
row in sources.json holds the terms as found, the live read and the measured key, `link`.
"""

from extract._pages_content import content_pages

CLAIMS = ("foothills_sections",)
RESOURCES = [content_pages("foothills_sections", crawl_delay=10.0)]
