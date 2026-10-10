"""Finger Lakes Trail Conference: suggested hikes, its Special Places (decision 54's wave 5, section K's per-site
readers, 2026-10-10).

- `fltc_special_places`: fingerlakestrail.org's Special Places page links 8 pages in its sidebar, places and themed
  hike pages, each landing its title and link. The pages describe their hikes in prose and are not fetched, so no
  distance lands. The Passport Hikes booklets and the 21 PassportHikes waypoints are not read here.

The reader is extract/_pages_content.py's ContentPages with the `fltc_special_places` site parser: the rows hashed for
the change check (no page validator decides FRESH), the names and links only, never the conference's wording.
fingerlakestrail.org's robots.txt disallows /REF/ and /FLTC/ and asks no Crawl-delay (read 2026-10-10). Its row in
sources.json holds the terms as found, the live read and the measured key, the link.
"""

from extract._pages_content import content_pages

CLAIMS = ("fltc_special_places",)
RESOURCES = [content_pages("fltc_special_places")]
