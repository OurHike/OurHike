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
"""

from extract._content import mediawiki_template_pages

CLAIMS = ("tehcc_wiki_challenge_items",)
RESOURCES = [mediawiki_template_pages(key) for key in CLAIMS]
