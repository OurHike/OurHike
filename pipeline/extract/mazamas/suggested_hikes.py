"""Mazamas: suggested hikes, the Hike List View read here (decision 54 wave 5, section K, 2026-10-04).

- `mazamas_hike_list`: mazamas.org/hikelist/, one page, 162 hikes in four regions (Columbia River Gorge, Mt. Hood,
  Clackamas River, Oregon Coast), each its name, round-trip miles, cumulative elevation gain, driving miles from the
  park-and-ride the page names, and whether the trailhead charges a fee. mazamas.org's robots.txt asks
  `Crawl-delay: 15`, honoured on every request.

The reader is extract/_pages_content.py's ContentPages with the `mazamas_hike_list` site parser: one request a
month, the rows hashed for the change check (no page validator decides FRESH), facts and the link only. Its row in
sources.json holds the terms as found, the live read and the measured key, `name`. The street rambles
(`/streetrambles/routes-maps/`, urban walks) and the climbing routes (`/climbroutes/`) are not hikes and are not
read.

The note this replaces read, whole:

Mazamas: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch c6_regional_3).

A page, not machine-readable. The terms are unknown (see the flags above).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/hikelist/`: 161 hikes, each with miles, elevation gain, driving
miles and a trailhead-fee flag, in an HTML list, e.g. "Angels Rest 4.6 miles 1,540 feet 42 miles, no".
`/streetrambles/routes-maps/` has "A COLLECTION OF 50 STREET RAMBLE HIKES" (urban walks, Sept 2019).
`/climbroutes/` lists climbing routes by region.

Its `where`: https://mazamas.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("mazamas_hike_list",)
RESOURCES = [content_pages("mazamas_hike_list", crawl_delay=15.0)]
