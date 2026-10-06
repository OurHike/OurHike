"""Bay Area Ridge Trail Council: suggested hikes, 2 WordPress sources read here (decision 54 wave 3,
section C, 2026-10-04).

- `ridgetrail_trail_sections`: the `trail-section` custom post type, 86 sections, each with its
  distance, ends and land manager in its body.
- `ridgetrail_curated_adventures`: category 21, Curated Adventures, 33 posts: multi-day treks, day-
  hike sets and bikepacking routes. `author_info` (a staff member's display name) and
  `jetpack_publicize_connections` never load.

Not read here: `/trip-planning-tools/` (a page) and the 92 regional map PDFs on `/trail-maps/`
(2019), wave 4's and 5's formats.

Each source's row in sources.json holds its terms as found, its live read of 2026-10-04 and its
measured key, `id`. The reader is extract/_kinds.py's WordpressPosts (or a narrower read of it in
extract/_content.py): X-WP-Total is the count and the proof, and the change check is a hash of the
scoped (id, modified) set, one small request, because a WordPress feed's validators are site-wide
(the dlt skill, rule 4). Every request waits the host's Crawl-delay, or 2 s where it asks none.
WP_DROPPED and the row's `person_fields` never load. A post's body, where it loads, stops at
`base_`: a suggested hike publishes its facts and the link, never the club's own description
(decision 55, the round brief's item 3). The lane is the type's, monthly.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Bay Area Ridge Trail Council: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

Section text is a 2019 Wilderness Press guidebook excerpt (see flags).

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): WordPress REST `/wp-json/wp/v2/trail-section`: 86 posts, each
with distance, from/to and land manager. Category "Curated Adventures" has 33 posts. `/trip-
planning-tools/` lists multi-day treks and bikepacking plans. There are 92 regional map PDFs (2019)
on `/trail-maps/`.

Its `where`: https://ridgetrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import DEFAULT_HOST_GAP_SECONDS
from extract._kinds import wordpress_posts

CLAIMS = ("ridgetrail_trail_sections", "ridgetrail_curated_adventures")
RESOURCES = [
    wordpress_posts("ridgetrail_trail_sections", post_type="trail-section", crawl_delay=DEFAULT_HOST_GAP_SECONDS),
    wordpress_posts("ridgetrail_curated_adventures", crawl_delay=DEFAULT_HOST_GAP_SECONDS),
]
