"""Carolina Mountain Club: challenges, the Lookout Tower Challenge's towers read here, and its seven other
challenges not landed (decision 54 wave 5, section K, 2026-10-04).

- `cmc_lookout_towers`: /hiking/hiking-challenges/lookout-tower-challenge-ltc/, 23 fire lookout towers in western
  North Carolina, each its name and forest. carolinamountainclub.org's robots.txt asks `Crawl-delay: 10`.

The reader is extract/_pages_content.py's ContentPages with the `cmc_lookout_towers` site parser: the rows hashed
for the change check (no page validator decides FRESH), one row a place on the challenge's list, its facts and the
link, never the club's prose and never anyone who finished. Its row in sources.json holds the terms as found, the
live read and the measured key, `name`.

Not landed, each read 2026-10-04: the South Beyond 6000's 40 peaks are in prose on its page (a peak's elevation
written two ways, 'Blackstock Knob (6320 feet)' and 'Blackstock Knob, 6359'), and its Ascent Record is a PDF form;
the Waterfall & Cascade 100's list is a PDF (Waterfall-WC100-Challenge-Hikes-02182024.pdf), not opened, and its
page lists its completers by name, never read; the 100 Favorite Trails are a published map's; the Pisgah 400 is
every trail of a ranger district; the AT/MST, Centennial and Art Loeb challenges are completion awards with no list
of places. Each needs its own reader, not built in this pull request.

The note this replaces read, whole:

Carolina Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

The peak and tower lists give names and elevations, not coordinates. Places would come from a join
(GNIS, OSM; @unvalidated). These fit the shape #1780 — Let a club publish a challenge — places on its
own trails that hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List …

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): 8 programmes under
`https://carolinamountainclub.org/hiking/hiking-challenges/` (pages modified 2026-08-14 to 2026-08-30):
100 Favorite Trails (FH100); AT/MST (~94 mi A.T. + ~150 mi MST, log `AT-MST-Log-240213.pdf`); Art Loeb
Trail (30.1 mi, with The Pisgah Conservancy); Centennial (50 hiked miles + 50 trail-work hours); Lookout
Tower Challenge (23 WNC lookout towers, with directions and one-way mileages); Pisgah 400 (every
official trail in the Pisgah Ranger District); South Beyond 6000 (40 peaks; ascent record
`SB6KAscentRecord-062325.pdf`); Waterfall & Cascade 100 (100+ waterfalls, list …

Its `where`: https://carolinamountainclub.org/hiking/hiking-challenges/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("cmc_lookout_towers",)
RESOURCES = [content_pages("cmc_lookout_towers", crawl_delay=10.0)]
