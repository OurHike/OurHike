"""Colorado Fourteeners Initiative: suggested hikes, the route each of its peak pages recommends (decision 54's wave 4,
section K's per-site readers, 2026-10-10).

- `cfi_recommended_routes`: 14ers.org's page sitemap lists 53 peak pages; the 22 whose 'Recommended Route'
  paragraph opens with the route's name before a dash land a row each, the peak's name, the route's name and the
  link. The other 31 peaks (no such heading, or an update in its place) land none. No page states a class, a
  difficulty, a distance or a climb for its route in a form read here.

The reader is extract/_pages_content.py's ContentPages with the `cfi_recommended_routes` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the link only, never CFI's wording. www.14ers.org's
robots.txt asks no Crawl-delay (read 2026-10-10), so the 54 requests keep DEFAULT_HOST_GAP_SECONDS between them,
about two minutes. Its row in sources.json holds the terms as found, the live read and the measured key, the link.
"""

from extract._pages_content import content_pages

CLAIMS = ("cfi_recommended_routes",)
RESOURCES = [content_pages("cfi_recommended_routes")]
