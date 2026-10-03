"""Pacific Northwest Trail Association: warnings, from the trail-conditions page and the Trail Conditions posts,
hourly (decision 53 phase B, 2026-10-03).

Both read live under our agent on 2026-10-03 (www.pnt.org's robots.txt disallows nothing they reach):

- `pnta_trail_conditions`: the trail-conditions page as one PageNotice (extract/_notices.py), dated by
  its own 'Last Updated: August 1, 2025'. FOURTEEN MONTHS OLD: it must carry its date and never render
  as current.
- `pnta_trail_conditions_posts`: the 'Trail Conditions' category (id 188, slug 'trail-conditions', a
  child of 'trail-topics', so the resource names the slug and the url is the page a person reads)
  through WordpressPosts, 4 posts by X-WP-Total, the newest modified 2024-09-16: dated history. The
  posts' `content` and `excerpt` never load (the row's person_fields): they held no contact details
  that day, but they are the same free text that, on three other clubs' sites read the same day, did
  (decision 59).

The static pages the coverage audit named (`/bears/`, `/challenges-and-risks/`, `/snow/`) are guidance,
not notices, and are not read.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c10_nst_rest): "The conditions page is 14 months stale. Carry its own date and never render it as
current."
"""

from extract._kinds import page_notice, wordpress_posts

CLAIMS = ("pnta_trail_conditions", "pnta_trail_conditions_posts")
RESOURCES = [
    page_notice("pnta_trail_conditions"),
    wordpress_posts("pnta_trail_conditions_posts", category_slugs=("trail-conditions",)),
]
