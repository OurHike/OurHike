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
"""

from extract._pages_content import content_pages

CLAIMS = ("cmc_lookout_towers",)
RESOURCES = [content_pages("cmc_lookout_towers", crawl_delay=10.0)]
