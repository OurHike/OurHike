"""Tennessee Eastman Hiking & Canoeing Club: suggested hikes, 2 wiki templates read here (decision 54
wave 3, section C, 2026-10-04).

- `tehcc_wiki_trails`: the 148 pages that transclude `Template:Trail` (park, land owner, marking,
  difficulty, hike time, distance, round trip, elevation gain and loss, parking location, route
  description).
- `tehcc_wiki_hikes`: the 52 pages that transclude `Template:Hike` (51 articles and the template's
  own documentation page). A page may carry both templates; dbt deduplicates by `pageid`.

Not read here: the WordPress category Hikes (id 212, 18 posts, 2014 to 2021) is a dated group hike's
announcement, which is not a suggested hike (the lead's ruling, 2026-10-04); the `Report:`
namespace's 141 trip reports are reports of past outings, the same; the 2 Hike Plans were not
located.

Each row in sources.json holds its live read of 2026-10-04 and its measured key, `pageid`. The
reader is extract/_content.py's MediawikiTemplatePages: extract/_json_apis.py's
MediawikiAnnouncements, which TEHCC's notices already use on this wiki, for another template, its
`part` telling the reads apart. The editor's name is never asked for. The wikitext stops at `base_`
(decision 55). The lane is the type's, monthly.
"""

from extract._content import mediawiki_template_pages

CLAIMS = ("tehcc_wiki_trails", "tehcc_wiki_hikes")
RESOURCES = [mediawiki_template_pages(key) for key in CLAIMS]
