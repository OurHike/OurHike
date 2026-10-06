"""Tennessee Eastman Hiking & Canoeing Club: challenges, 1 wiki template read here (decision 54 wave 3,
section C, 2026-10-04).

- `tehcc_wiki_challenge_items`: the 1 page that transcludes `Template:Challenge Item`, South Beyond
  6000 (SB6K), the challenge TEHCC founded and co-sponsors with the Carolina Mountain Club: a wiki
  map of the peaks, of which the page stores 1 point, Roan High Bluff, its longitude missing its
  minus sign (the coverage audit). The peak list itself lives on CMC's site
  (carolinamountainclub.org), a page.

Each row in sources.json holds its live read of 2026-10-04 and its measured key, `pageid`. The
reader is extract/_content.py's MediawikiTemplatePages: extract/_json_apis.py's
MediawikiAnnouncements, which TEHCC's notices already use on this wiki, for another template, its
`part` telling the reads apart. The editor's name is never asked for. The wikitext stops at `base_`
(decision 55). The lane is the type's, monthly.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Tennessee Eastman Hiking & Canoeing Club: challenges, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

One programme, two publishers. Recommendation: extract once, under `cmc` (fuller list), with
`co_publisher: tehcc` (Reasoned). TEHCC's "AT 2000 Miler" and "Smokies 900 Miler" pages are only
rosters of members who finished other programmes.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): South Beyond 6000 (SB6K): 40 peaks above 6,000 ft, founded by
TEHCC and co-sponsored with CMC (`https://tehcc.org/hiking/challenges/south-beyond-6000/`). Details
and the peak list live on CMC's site. The wiki page "South Beyond 6000" holds 1 `Challenge Item`
(Roan High Bluff, stored as `36.0932,82.1455`, longitude missing its minus sign).

Its `where`: https://tehcc.org/hiking/challenges/south-beyond-6000/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import mediawiki_template_pages

CLAIMS = ("tehcc_wiki_challenge_items",)
RESOURCES = [mediawiki_template_pages(key) for key in CLAIMS]
