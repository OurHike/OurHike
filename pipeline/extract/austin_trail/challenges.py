"""The Trail Conservancy (Austin): challenges, the History of the Trail Scavenger Hunt's clue locations read
here (decision 54 wave 5, section K, 2026-10-04).

- `ttc_scavenger_hunt`: /programs/scavenger-hunt/, 15 clue locations on the Butler Trail, each its name and its clue
  sheet's link. thetrailconservancy.org's robots.txt asks `Crawl-delay: 10`.

The reader is extract/_pages_content.py's ContentPages with the `ttc_scavenger_hunt` site parser: the rows hashed
for the change check (no page validator decides FRESH), one row a place on the challenge's list, its facts and the
link, never the club's prose and never anyone who finished. Its row in sources.json holds the terms as found, the
live read and the measured key, `name`.
"""

from extract._pages_content import content_pages

CLAIMS = ("ttc_scavenger_hunt",)
RESOURCES = [content_pages("ttc_scavenger_hunt", crawl_delay=10.0)]
