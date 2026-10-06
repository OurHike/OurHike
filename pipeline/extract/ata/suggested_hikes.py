"""Arizona Trail Association: suggested hikes, its 44 passage pages read here (decision 54 wave 5, section K,
2026-10-04).

- `ata_passages`: aztrail.org/explore/passages/ and the 44 passage pages it links, each its location, miles,
  difficulty, seasons and its two ends with their GPS coordinates as the page states them. aztrail.org's robots.txt
  asks `Crawl-delay: 10`, so 45 requests take about eight minutes a month.

The reader is extract/_pages_content.py's ContentPages with the `ata_passages` site parser: the rows hashed for the
change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row in
sources.json holds the terms as found, the live read and the measured key, `link`. The terms, quoted on the row,
require written permission for information "published online or in written form", which restricts publishing and not
reading, so the row is `unresolved` for the maintainer.

Not read: each passage's three GPX files and PDF map (GIS files, for the lead's wave 2 list), its Water and
Notes/Warnings prose, and the Day Hiker's Guide (89 day hikes), a download for ATA members only.

The note this replaces read, whole:

Arizona Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

The passage pages are open. The Guide is gated. Skeptic spot-check: the passage-1 page returns 200.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): 43 passage pages, e.g.
`/explore/passages/passage-1-huachuca-mountains/`, each with a PDF map, a history PDF and 3 GPX files.
The Day Hiker's Guide (89 day hikes) is a members-only download.

Its `where`: https://aztrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("ata_passages",)
RESOURCES = [content_pages("ata_passages", crawl_delay=10.0)]
