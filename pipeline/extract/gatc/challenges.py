"""Georgia Appalachian Trail Club: challenges, the Georgia 4000's peaks read here (decision 54 wave 5,
section K, 2026-10-04).

- `gatc_georgia_4000`: /for-hikers/georgia-4000/georgia-4000-foot-peaks/, the 32 peaks of 4,000 feet or more, each
  its elevation, land area and trails (a bushwhack where no trail reaches it). georgia-atclub.org's robots.txt asks
  `Crawl-delay: 10`.

The reader is extract/_pages_content.py's ContentPages with the `gatc_georgia_4000` site parser: the rows hashed for
the change check (no page validator decides FRESH), one row a place on the challenge's list, its facts and the link,
never the club's prose and never anyone who finished. Its row in sources.json holds the terms as found, the live
read and the measured key, `name`. The peaks' notes, the CalTopo map 'GA 4000 Challenge' and the patch's application
are not read.

The note this replaces read, whole:

Georgia Appalachian Trail Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

It fits #1780's shape (places a hiker opts into and tags). But several peaks are bushwhacks ("Dicks Knob
… Trail(s): Bushwhack"), so a challenge pin there invites a hiker off-trail. The card would have to say
so. The completers list is personal data and must not be loaded. Skeptic additions: the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Georgia 4000 Challenge. `/for-hikers/georgia-4000/` (`modified`
2026-09-02): "North Georgia boasts 32 mountain peaks that are 4,000 feet or higher. Climb all 32 … and
can sport our patch". `/for-hikers/georgia-4000/georgia-4000-foot-peaks/` (`modified` 2023-11-09) lists
each peak with elevation, land area, trails and notes (e.g. "Brasstown Bald - 4,784 ft. Land Area:
Brasstown Wilderness"). CalTopo `caltopo.com/m/0H89` "GA 4000 Challenge" ("GATC Map of 32 Georgia
mountain peaks of 4000' or more elevation and 120' prominence"). PDFs:
`2023/04/Georgia_4000_Challenge.pdf` (24,189,940 bytes) and …

Its `where`: https://caltopo.com/m/0H89 https://georgia-atclub.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("gatc_georgia_4000",)
RESOURCES = [content_pages("gatc_georgia_4000", crawl_delay=10.0)]
