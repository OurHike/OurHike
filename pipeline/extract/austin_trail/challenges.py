"""The Trail Conservancy (Austin): challenges, the History of the Trail Scavenger Hunt's clue locations read
here (decision 54 wave 5, section K, 2026-10-04).

- `ttc_scavenger_hunt`: /programs/scavenger-hunt/, 15 clue locations on the Butler Trail, each its name and its clue
  sheet's link. thetrailconservancy.org's robots.txt asks `Crawl-delay: 10`.

The reader is extract/_pages_content.py's ContentPages with the `ttc_scavenger_hunt` site parser: the rows hashed
for the change check (no page validator decides FRESH), one row a place on the challenge's list, its facts and the
link, never the club's prose and never anyone who finished. Its row in sources.json holds the terms as found, the
live read and the measured key, `name`.

The note this replaces read, whole:

The Trail Foundation (Austin): challenges, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Places on the club's own trail that a hiker visits in loops. It is the closest fit to #1780 — Let a club
publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the
ATC's A.T. Summer Bucket List in this batch, though it has no opt-in or tagging. No …

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "History of the Trail Scavenger Hunt",
`https://thetrailconservancy.org/programs/scavenger-hunt/` (REST `?slug=scavenger-hunt`, modified
2023-09-21). It has 3 loops of 5 clue locations, 15 places in all, along the Butler Trail: Johnson Creek
Trailhead, Clay Pit, Opossum Temple & Voodoo Pew, Lou Neff Point, Oldest Tree on the Trail, Miro Rivera
Restroom, Vista Point, Seaholm Intake, Stevie Ray Vaughan, Town Lake Gazebo, Longhorn Dam, Peace Point,
Boardwalk, Lake Full and Holly Area. Hikers "scan the QR code at each location to reveal your clue".
There are 16 PDFs: the printable map …

Its `where`: https://thetrailconservancy.org/programs/scavenger-hunt/ https://thetrailfoundation.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("ttc_scavenger_hunt",)
RESOURCES = [content_pages("ttc_scavenger_hunt", crawl_delay=10.0)]
