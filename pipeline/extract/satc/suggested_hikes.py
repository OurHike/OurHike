"""Susquehanna Appalachian Trail Club: suggested hikes, its 'Hiking In Central Pennsylvania' directory (decision 54's
wave 5, section K's per-site readers, 2026-10-10).

- `satc_central_pa_hikes`: satc-hike.org/hiking-in-central-pennsylvania.html, 28 places on 2026-10-10: SATC's three
  A.T. sections and 25 other organisations' parks and trails, each its name and the link the page gives it (the
  owner's site, linked and never fetched; the page itself for the A.T. sections). A distance lands only where the
  entry's own sentence gives its length in one figure ('on this 6.3-mile segment'); the prose is otherwise not read.

The reader is extract/_pages_content.py's ContentPages with the `satc_central_pa_hikes` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the link only, never the club's own wording.
satc-hike.org's robots.txt asks no Crawl-delay (read 2026-10-10). Its row in sources.json holds the terms as found,
the live read and the measured key, the place's name.
"""

from extract._pages_content import content_pages

CLAIMS = ("satc_central_pa_hikes",)
RESOURCES = [content_pages("satc_central_pa_hikes")]
