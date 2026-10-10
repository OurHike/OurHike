"""Green Mountain Club: closures, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `gmc_trail_alerts`: GMC Trail Updates, one row a post (WordpressPosts, post type `alert`). The
  `alert` custom post type, read whole through its REST route with X-WP-Total as the count; its
  `alert-category` taxonomy (Trail Changes and Closures, Parking and Trailhead Access Alerts,
  General Guidelines and Seasonal Closures, Important Alert) splits closures from the rest without
  reading prose. 'Now Open:' titles are reopenings and must not render as closures. Fills the Long
  Trail's gap: atc_updates.json carries no Vermont rows.

WordPressPosts drops `uagb_author_info`, whose `display_name` is a staff member's, and
`spectra_custom_meta` (edit locks, Yoast meta), as it drops `author` (extract/_kinds.py's
WP_DROPPED).

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import wordpress_posts

CLAIMS = ("gmc_trail_alerts",)
RESOURCES = [wordpress_posts("gmc_trail_alerts", post_type="alert", crawl_delay=10.0)]
