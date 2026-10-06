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
"""

from extract._pages_content import content_pages

CLAIMS = ("gatc_georgia_4000",)
RESOURCES = [content_pages("gatc_georgia_4000", crawl_delay=10.0)]
