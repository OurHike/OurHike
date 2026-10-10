"""Mid State Trail Association (PA): suggested hikes, the Mid State Trail's sections as its Section Updates page lists
them (decision 54's wave 5, section K's per-site readers, 2026-10-10).

- `msta_sections`: hike-mst.org/index.php/the-trail/section-updates, 23 sections (20 numbered and three spurs, A to
  C), each its name, the span it covers ('MD to PA 326 @ Rainsburg Gap') and its link. No page states a section's
  length, so no distance lands; the region pages, which name a regional manager with a telephone number, are not
  read.

The reader is extract/_pages_content.py's ContentPages with the `msta_sections` site parser: the rows hashed for the
change check (no page validator decides FRESH), facts and the link only. The pages it links are each section's
alerts, which this folder's closures resource reads (msta_section_<n>), so they are not fetched here.
hike-mst.org's robots.txt asks no Crawl-delay (read 2026-10-10). Its row in sources.json holds the terms as found,
the live read and the measured key, the section.
"""

from extract._pages_content import content_pages

CLAIMS = ("msta_sections",)
RESOURCES = [content_pages("msta_sections")]
