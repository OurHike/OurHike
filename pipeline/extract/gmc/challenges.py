"""Green Mountain Club: challenges, the Long Trail Side-to-Side Challenge's 88 side trails read here (decision
54 wave 4, section K, 2026-10-04).

- `gmc_side_to_side`: /wp-content/uploads/2026/04/Long-Trail-Side-to-Side-Tracker.pdf, the tracker's 88 side-trail
  names, held to the 88 the document states. greenmountainclub.org's robots.txt asks `Crawl-delay: 10`.

The reader is extract/_pdf_content.py's ContentPdf with the `gmc_side_to_side` family: a conditional GET with the
file's own validators, one row a place on the challenge's list, its facts and the link, never the club's prose and
never anyone who finished. Its row in sources.json holds the terms as found, the live read and the measured key,
`name`. The Long Trail End-to-Ender certification is a completion award with a roster (more than 7,000 certified),
never read.

The note this replaces read, whole:

Green Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Side-to-Side is a defined trail list, which fits #1780's shape.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Long Trail End-to-Ender Certification
(`/hike/thru-hiking/long-trail-end-to-ender-certification/`): "More than 7,000" certified, certificate
and patch. Side-to-Sider: all 88 side trails (166 mi), with tracker PDF
`/wp-content/uploads/2026/04/Long-Trail-Side-to-Side-Tracker.pdf`.

Its `where`: https://greenmountainclub.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pdf_content import content_pdf

CLAIMS = ("gmc_side_to_side",)
RESOURCES = [content_pdf("gmc_side_to_side", crawl_delay=10.0)]
