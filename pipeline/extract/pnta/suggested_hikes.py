"""Pacific Northwest Trail Association: suggested hikes, 1 WordPress category read here (decision 54
wave 3, section C, 2026-10-04).

- `pnta_day_hikes_posts`: category 117, `day-hikes` (a child of `trail-topics`), 1 post today,
  'Winter Trips on the Pacific Northwest Trail' (2024-09-16). The archive sits under
  /category/trail-topics/, so the resource names the slug.

Not read here: the 10 section pages under `/pnta/sections-of-the-pnt/`, a page format (wave 5).

Each source's row in sources.json holds its terms as found, its live read of 2026-10-04 and its
measured key, `id`. The reader is extract/_kinds.py's WordpressPosts (or a narrower read of it in
extract/_content.py): X-WP-Total is the count and the proof, and the change check is a hash of the
scoped (id, modified) set, one small request, because a WordPress feed's validators are site-wide
(the dlt skill, rule 4). Every request waits the host's Crawl-delay, or 2 s where it asks none.
WP_DROPPED and the row's `person_fields` never load. A post's body, where it loads, stops at
`base_`: a suggested hike publishes its facts and the link, never the club's own description
(decision 55, the round brief's item 3). The lane is the type's, monthly.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Pacific Northwest Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

Page. Skeptic: `/pnta/sections-of-the-pnt/` now 301s to `/pnta/know-before-you-go/` ("Sections of
the PNT" in `llms.txt`). Use the target URL.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/pnta/sections-of-the-pnt/`: 10 section pages. WP category
`day-hikes`: 1 post.

Its `where`: https://pnt.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import DEFAULT_HOST_GAP_SECONDS
from extract._kinds import wordpress_posts

CLAIMS = ("pnta_day_hikes_posts",)
RESOURCES = [wordpress_posts("pnta_day_hikes_posts", category_slugs=("day-hikes",), crawl_delay=DEFAULT_HOST_GAP_SECONDS)]
