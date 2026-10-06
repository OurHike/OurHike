"""Georgia Appalachian Trail Club: closures, 2 notice sources read here (decision 53 phase B,
2026-10-03).

- `gatc_alerts`: GATC Alerts, one row an item (FeedNotices). The `alerts` custom post type's feed,
  the only machine-readable route to it (the type is absent from /wp-json/wp/v2/types). Its weak
  ETag and Last-Modified are identical on /feed/ and /alerts/feed/, a site-wide cache stamp, so the
  check is the read. georgia-atclub.org asks `Crawl-delay: 10`.

- `gatc_news_feed`: GATC news, one row an item (FeedNotices). The site feed, the newest 10 of GATC's
  30 posts (X-WP-Total, 2026-10-03), all in the one category `uncategorized`: closures ('Byron
  Herbert Reece Trail Reroute', the January 2026 winter-storm posts) beside club news, so which
  items are notices is decision 7's classifier and a person's review in dbt, never a filter here.
  The REST posts route would be the complete list, but its rendered content carries a person's
  e-mail address and a phone number (measured 2026-10-03), which decision 59 keeps out whole; the
  feed reader lands no prose and no person.

Not wired: the two Forest Service orders GATC republishes as scanned PDFs
(https://georgia-atclub.org/wp-content/uploads/2024/04/Blood_Mountain_Fire_Ban.pdf and
3_day_stay_order.pdf, both Last-Modified 2024-04-11, no text layer). Whether either is in force is
@unvalidated from the file names, and the authority is the Chattahoochee-Oconee NF, whose alerts
page usfs/closures.py reads as `usfs_r08_chattahoochee_oconee_alerts` (decision 34); a page notice
on a 2024 copy would publish an order of unknown standing as present.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import feed_notices

CLAIMS = ("gatc_alerts", "gatc_news_feed")
RESOURCES = [feed_notices("gatc_alerts", crawl_delay=10.0), feed_notices("gatc_news_feed", crawl_delay=10.0)]
