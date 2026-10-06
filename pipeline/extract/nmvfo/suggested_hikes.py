"""New Mexico Volunteers for the Outdoors: suggested hikes, 1 WordPress source read here (decision 54
wave 3, section C, 2026-10-04).

- `nmvfo_hike_new_mexico`: the Hike New Mexico trail guide, the 38 child pages of page 2040
  (`/trails/`), read through the pages route with `parent=2040` (extract/_content.py's
  WordpressChildPages). Each page's body embeds named volunteers' own telephone numbers and e-mail
  addresses (18 of 38, read 2026-10-04), so `content` and `excerpt` never load (decision 59): each
  row is a trail's title, link and dates. The CONDITIONS sections the bodies held were 2020 to 2023
  snapshots, and nothing of this row feeds a closure or a warning.

NMVFO's scouting map on CalTopo is refused by caltopo.com's robots.txt (`User-agent: *` / `Disallow:
/api/`, decision 53's inventory, batch 3, 2026-10-03), and is not read here or anywhere.

Each source's row in sources.json holds its terms as found, its live read of 2026-10-04 and its
measured key, `id`. The reader is extract/_kinds.py's WordpressPosts (or a narrower read of it in
extract/_content.py): X-WP-Total is the count and the proof, and the change check is a hash of the
scoped (id, modified) set, one small request, because a WordPress feed's validators are site-wide
(the dlt skill, rule 4). Every request waits the host's Crawl-delay, or 2 s where it asks none.
WP_DROPPED and the row's `person_fields` never load. A post's body, where it loads, stops at
`base_`: a suggested hike publishes its facts and the link, never the club's own description
(decision 55, the round brief's item 3). The lane is the type's, monthly.
"""

from extract._content import DEFAULT_HOST_GAP_SECONDS, wordpress_child_pages

CLAIMS = ("nmvfo_hike_new_mexico",)
RESOURCES = [wordpress_child_pages("nmvfo_hike_new_mexico", parent=2040, crawl_delay=DEFAULT_HOST_GAP_SECONDS)]
