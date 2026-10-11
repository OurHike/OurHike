"""Maine Appalachian Trail Club: suggested hikes, its page for the Grafton Loop Trail (decision 54's wave 5, section K's
per-site readers, 2026-10-10).

- `matc_grafton_loop_trail`: matc.org/grafton-loop-trail/, one trail, its name and the link. The page's miles are
  driving directions to its two trailheads, so no distance lands, and it states no climb.

The reader is extract/_pages_content.py's ContentPages with the `matc_grafton_loop_trail` site parser: the row hashed
for the change check (no page validator decides FRESH), the name and the link only, never the club's wording.
www.matc.org's robots.txt asks no Crawl-delay (read 2026-10-10). Its row in sources.json holds the terms as found, the
live read and the measured key, the trail's name.
"""

from extract._pages_content import content_pages

CLAIMS = ("matc_grafton_loop_trail",)
RESOURCES = [content_pages("matc_grafton_loop_trail")]
