"""Old Dominion Appalachian Trail Club: suggested hikes, its two circuit hikes near its A.T. section (decision 54's
wave 4, section K's per-site readers, 2026-10-10).

- `odatc_circuit_hikes`: odatc.org/page-1503143, 'Circuit Hikes Near Our Section of the AT', two hikes, each its name,
  its 'Description' link and its 'Printable map' link, as a loop because the page calls them circuit hikes. The page
  states no distance.

The reader is extract/_pages_content.py's ContentPages with the `odatc_circuit_hikes` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the links only. www.odatc.org's robots.txt asks
`Crawl-delay: 10` (read 2026-10-10), so the one request waits it. Its row in sources.json holds the terms as found,
the live read and the measured key, the hike's name.
"""

from extract._pages_content import content_pages

CLAIMS = ("odatc_circuit_hikes",)
RESOURCES = [content_pages("odatc_circuit_hikes", crawl_delay=10.0)]
