"""Tahoe Rim Trail Association: suggested hikes, the Day Hike Itineraries read here (decision 54 wave 5, section K,
2026-10-04).

- `tahoe_rim_day_hikes`: tahoerimtrail.org/day-hiking/ and the four theme pages it links (Alpine Lakes, Wildflower
  Hikes, Peaks & Vistas, Waterfall Hikes), 15 hikes, each its classification, round-trip distance, trailhead,
  whether bikes are allowed and the shore it is reached from. Five requests a month; tahoerimtrail.org's
  robots.txt asks no Crawl-delay, so 2 s is kept between them.

The reader is extract/_pages_content.py's ContentPages with the `tahoe_rim_day_hikes` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the link only, never the association's
highlights or descriptions. Its row in sources.json holds the terms as found, the live read and the measured key,
`name`. The index's "How to break the Tahoe Rim Trail into 14 Day Hikes" is a PDF of instructions (73,592 bytes,
ETag "69c66de4-11f78", 2026-03-27) and is not read here.
"""

from extract._pages_content import content_pages

CLAIMS = ("tahoe_rim_day_hikes",)
RESOURCES = [content_pages("tahoe_rim_day_hikes")]
