"""Mountains to Sound Greenway Trust: suggested hikes, 1 post type read here with its terms (decision
54 wave 3, section C, 2026-10-04).

- `mtsg_itineraries`: the `itinerary` custom post type, 28 itineraries, read whole. Not all are
  hikes: its `itinerary_type` taxonomy (5 terms: Trails, Parks, and Recreation; Walking Tours;
  Scenic Drives; Culture and History; Nature, Plants, and Wildlife) says which, and lands with
  `itinerary_tag` and `cm_priority_areas` as `raw_mtsg__mtsg_itineraries_terms`. dbt keeps a scenic
  drive from becoming a suggested hike.

Each source's row in sources.json holds its terms as found, its live read of 2026-10-04 and its
measured key, `id`. The reader is extract/_kinds.py's WordpressPosts (or a narrower read of it in
extract/_content.py): X-WP-Total is the count and the proof, and the change check is a hash of the
scoped (id, modified) set, one small request, because a WordPress feed's validators are site-wide
(the dlt skill, rule 4). Every request waits the host's Crawl-delay, or 2 s where it asks none.
WP_DROPPED and the row's `person_fields` never load. A post's body, where it loads, stops at
`base_`: a suggested hike publishes its facts and the link, never the club's own description
(decision 55, the round brief's item 3). The lane is the type's, monthly.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Mountains to Sound Greenway Trust: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

HTML bodies come through REST.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): WordPress REST `/wp-json/wp/v2/itinerary`: `X-WP-Total` = 28.
9 are typed "Trails, Parks, and Recreation", e.g. "10 Scenic Middle Fork Hikes Near Seattle That
Aren't Mailbox Peak or Mount Si" (2026-04-17). The others are walking tours and scenic drives.

Its `where`: https://mtsgreenway.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import DEFAULT_HOST_GAP_SECONDS, site_terms
from extract._kinds import wordpress_posts

CLAIMS = ("mtsg_itineraries",)
RESOURCES = [
    wordpress_posts("mtsg_itineraries", post_type="itinerary", crawl_delay=DEFAULT_HOST_GAP_SECONDS),
    site_terms("mtsg_itineraries", ("itinerary_tag", "itinerary_type", "cm_priority_areas")),
]
