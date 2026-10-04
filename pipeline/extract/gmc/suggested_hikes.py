"""Green Mountain Club: suggested hikes, 1 post type read here with its terms (decision 54 wave 3,
section C, 2026-10-04).

- `gmc_hikes`: the `hikes` custom post type, 57 hikes (newest modified 2026-09-30), read whole, one
  row a hike. Its facts are taxonomy ids, so a second resource lands the post type's six taxonomies
  (difficulty, distance, hike-feature, hike-status, hike-type, region; 32 terms) as
  `raw_gmc__gmc_hikes_terms`, on the same monthly lane. greenmountainclub.org's robots.txt opens
  with `Crawl-delay: 10`, honoured on every request.

The ArcGIS dashboards 'Suggested Day Hikes' and 'Suggested Section Hikes' and their web maps draw a
featured hike from TRAIL_MASTER (gmc_trail_master, gmc/trail_lines.py), so they are views of a
registered layer and not a dataset of their own.

Each source's row in sources.json holds its terms as found, its live read of 2026-10-04 and its
measured key, `id`. The reader is extract/_kinds.py's WordpressPosts (or a narrower read of it in
extract/_content.py): X-WP-Total is the count and the proof, and the change check is a hash of the
scoped (id, modified) set, one small request, because a WordPress feed's validators are site-wide
(the dlt skill, rule 4). Every request waits the host's Crawl-delay, or 2 s where it asks none.
WP_DROPPED and the row's `person_fields` never load. A post's body, where it loads, stops at
`base_`: a suggested hike publishes its facts and the link, never the club's own description
(decision 55, the round brief's item 3). The lane is the type's, monthly.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Green Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The REST content is prose with no GPX (2 of 57 mention a map or coordinates). The route may be
recoverable from the web maps' "Featured" layer definition (@unvalidated).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): WP REST `https://greenmountainclub.org/wp-json/wp/v2/hikes`:
57 hikes (newest 2026-09-30). Taxonomies: `difficulty`, `distance`, `hike-type`, `region`, `hike-
feature` (11 terms, e.g. Day Hiking 48, Views 48, Summits 27, 4,000 Footers 18). Also the ArcGIS
dashboards "Suggested Day Hikes" (`f86d3dfc…`) and "Suggested Section Hikes" (`d0fa7da2…`), and the
web maps Day Hikes and Section Hikes, which draw a featured hike from `TRAIL_MASTER`.

Its `where`: https://greenmountainclub.org/wp-json/wp/v2/hikes https://greenmountainclub.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import site_terms
from extract._kinds import wordpress_posts

CLAIMS = ("gmc_hikes",)
RESOURCES = [
    wordpress_posts("gmc_hikes", post_type="hikes", crawl_delay=10.0),
    site_terms("gmc_hikes", ("difficulty", "distance", "hike-feature", "hike-status", "hike-type", "region"), crawl_delay=10.0),
]
