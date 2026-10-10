"""Trailkeepers of Oregon: suggested hikes, 1 WordPress category read here, and the Oregon Hikers Field
Guide held on its terms (decision 54 wave 3, section C, 2026-10-04).

- `tko_spring_fundraiser_hike_posts`: TKO's own blog, category 40 (`oregon-hikers-spring-
  fundraiser`), 12 posts: 6 hike-description posts from 2026 and 6 'Trailkeeper Spotlight' profiles
  of named volunteers. Because half are profiles, `content` and `excerpt` never load for any post
  (decision 59, Reasoned); each row is a post's title, link, dates and taxonomy ids.

HELD ON ITS TERMS: the Oregon Hikers Field Guide (www.oregonhikers.org/field_guide/, a MediaWiki,
`Category:Hikes` 1,736 pages, the coverage audit 2026-10-01) is not extracted. Its robots.txt (read
2026-10-04) allows /w/api.php for our agent; its Copyright Notice
(https://www.oregonhikers.org/field_guide/Oregon_Hikers_Field_Guide:Copyright_Notice, last modified
2018-02-01, read 2026-10-04) says, verbatim: "Content posted on the Oregon Hikers website and wiki,
including text and maps, becomes the property of Trailkeepers of Oregon. Content may not be
reprinted without attribution, or used for commercial purposes without express permission from
Trailkeepers of Oregon. Photos posted on the Oregon Hikers website and wiki are used with the
permission of individual users who retain copyright to them. They may not be used, altered or
duplicated without express permission of individual users." and its footer: "All content posted on
the field guide becomes the property of Trailkeepers of Oregon, and may not be used without
permission." That is permission-gated, so it is a note until TKO answers (the dlt skill: note now,
load on permission), and the maintainer sends the ask. OCT `/day-hiking/` (about 8 named hikes) is a
page, wave 5.

Each source's row in sources.json holds its terms as found, its live read of 2026-10-04 and its
measured key, `id`. The reader is extract/_kinds.py's WordpressPosts (or a narrower read of it in
extract/_content.py): X-WP-Total is the count and the proof, and the change check is a hash of the
scoped (id, modified) set, one small request, because a WordPress feed's validators are site-wide
(the dlt skill, rule 4). Every request waits the host's Crawl-delay, or 2 s where it asks none.
WP_DROPPED and the row's `person_fields` never load. A post's body, where it loads, stops at
`base_`: a suggested hike publishes its facts and the link, never the club's own description
(decision 55, the round brief's item 3). The lane is the type's, monthly.
"""

from extract._content import DEFAULT_HOST_GAP_SECONDS
from extract._kinds import wordpress_posts

CLAIMS = ("tko_spring_fundraiser_hike_posts",)
RESOURCES = [wordpress_posts("tko_spring_fundraiser_hike_posts", crawl_delay=DEFAULT_HOST_GAP_SECONDS)]
