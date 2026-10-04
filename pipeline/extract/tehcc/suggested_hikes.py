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

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Tennessee Eastman Hiking & Canoeing Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

Structured through the API. Whether `Template:Trail` fields are SMW properties (and so `ask`-able)
is untested. `Challenge Item` is.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `Template:Trail` on 148 pages (distance, round trip, hike
time, difficulty, route description); `Template:Hike` on 52; 2 Hike Plans; `Report:` namespace with
141 trip reports (newest 2026-03-10, but 105 of 141 are from 2019–2021). WP category Hikes (id 212,
18 posts).

Its `where`: https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services https://tehcc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import mediawiki_template_pages

CLAIMS = ("tehcc_wiki_trails", "tehcc_wiki_hikes")
RESOURCES = [mediawiki_template_pages(key) for key in CLAIMS]
