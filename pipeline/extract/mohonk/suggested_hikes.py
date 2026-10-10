"""Mohonk Preserve: suggested hikes, its Suggested Hikes page read here (decision 54 wave 5, section K,
2026-10-04).

- `mohonk_suggested_hikes`: 13 hikes, 8 by trailhead and 5 that continue onto neighbouring lands, each its name, its
  trailhead and its printable PDF map. The page states no single distance for any hike, so none lands. The PDF maps
  (the coverage audit's five, and seven more) are linked from the rows and are drawings, not read.
  mohonkpreserve.org's robots.txt asks `Crawl-delay: 10`.

The reader is extract/_pages_content.py's ContentPages with the `mohonk_suggested_hikes` site parser: the rows
hashed for the change check (no page validator decides FRESH), facts and the link only, never the club's own
wording. Its row in sources.json holds the terms as found, the live read and the measured key, the trailhead and the
hike's name.
"""

from extract._pages_content import content_pages

CLAIMS = ("mohonk_suggested_hikes",)
RESOURCES = [content_pages("mohonk_suggested_hikes", crawl_delay=10.0)]
