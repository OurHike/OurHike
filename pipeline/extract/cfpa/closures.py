"""Connecticut Forest & Park Association: closures, 2 notice sources read here (decision 53 phase B,
2026-10-03).

- `cfpa_trail_notices`: CFPA Trail Notices, one notice for the page (PageNotice). The complete
  listing of CFPA's trail notices (30 on 2026-10-03, 2018-07-19 to 2026-07-17, typed closure,
  relocation or notice), one notice for the page. It is the list the feed beside it is a window of,
  so a notice that ages out of the feed is still on it. ctwoodlands.org asks `Crawl-delay: 10`.

- `cfpa_trail_notices_feed`: CFPA Trail Notices feed, one row an item (FeedNotices). The
  trail-notices post type's RSS feed, one row an item: the newest 10 of the 30 the listing shows.
  The post type has no REST route (absent from /wp-json/wp/v2/types), so this feed is the only
  per-item read. 'CLEARED' titles are reopenings and must not render as hazards.

The listing and the feed are two upstreams and two tables. Phase C reads the feed's items as notices
and the listing as the complete list, so an item that ages out of the feed is never read as lifted
while the listing still carries it. CFPA's 2021 TrailNotices ArcGIS layer stays unused (the coverage
audit).

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import feed_notices, page_notice

CLAIMS = ("cfpa_trail_notices", "cfpa_trail_notices_feed")
RESOURCES = [page_notice("cfpa_trail_notices", crawl_delay=10.0), feed_notices("cfpa_trail_notices_feed", crawl_delay=10.0)]
