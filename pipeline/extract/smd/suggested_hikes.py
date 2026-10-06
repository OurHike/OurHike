"""Save Mount Diablo: suggested hikes, its field guide 'Hikes in the Diablo Range' read here (decision 54
wave 5, section K, 2026-10-04).

- `smd_diablo_range_hikes`: the field guide's 47 numbered hikes, each its name, its region and the part of it, and
  the post it links; the posts are Save Mount Diablo's writing and are not fetched. savemountdiablo.org's robots.txt
  asks `Crawl-delay: 3`.

The reader is extract/_pages_content.py's ContentPages with the `smd_diablo_range_hikes` site parser: the rows
hashed for the change check (no page validator decides FRESH), facts and the link only, never the club's own
wording. Its row in sources.json holds the terms as found, the live read and the measured key, the region's part and
the hike's name.
"""

from extract._pages_content import content_pages

CLAIMS = ("smd_diablo_range_hikes",)
RESOURCES = [content_pages("smd_diablo_range_hikes", crawl_delay=3.0)]
