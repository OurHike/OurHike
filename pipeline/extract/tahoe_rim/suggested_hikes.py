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

The note this replaces read, whole:

Tahoe Rim Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Format page: `tahoerimtrail.org/day-hiking/` ("Day Hike
Itineraries": Alpine Lakes, Wildflower, Peaks & Vistas, Waterfall) and "How to break the Tahoe Rim Trail
into 14 Day Hikes".

Its `where`: https://tahoerimtrail.org/day-hiking/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("tahoe_rim_day_hikes",)
RESOURCES = [content_pages("tahoe_rim_day_hikes")]
