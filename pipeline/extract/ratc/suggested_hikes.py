"""Roanoke Appalachian Trail Club: suggested hikes, its 14 AT Hikes page read here (section K's hand-back,
2026-10-10).

- `ratc_at_hikes`: /at-hiking/ratcs-14-at-hikes/, the club's 14 day hikes covering its whole section of the A.T.,
  north to south from Black Horse Gap to VA 611, each its number, its two ends, its length in miles and its
  difficulty. Section K could not read it on 2026-10-04: www.ratc.org's robots.txt answered 502, which RFC 9309
  reads as a full disallow. On 2026-10-10 it answered 200, disallowing only /wp-admin/, with no Crawl-delay.

The reader is extract/_pages_content.py's ContentPages with the `ratc_at_hikes` site parser: facts and the link,
never a hike's description (decision 70), and the change check is the rows' own hash. Its row in sources.json holds
the terms as found, the live read and the measured key, the hike's two ends.

Not read, as the cell's earlier note recorded: the routes, which sit in a CalTopo map (`8AEHQUP`) whose data comes
only from caltopo.com/api/, which caltopo.com's robots.txt disallows for every agent (`User-agent: *` / `Disallow:
/api/`, decision 53's inventory, 2026-10-03); the trailheads, which are Google Maps links, Google's places rather
than the club's; and the 113-mile hike list (/at-hiking/113-mile-hike-list/, 2023), which gives the same hikes with
their climbs and 11 per-hike map PDFs, and the top-10 list PDF.
"""

from extract._pages_content import content_pages

CLAIMS = ("ratc_at_hikes",)
RESOURCES = [content_pages("ratc_at_hikes")]
