"""Mount Rogers Appalachian Trail Club: warnings, 1 notice source read here (decision 53 phase B,
2026-10-03).

- `mratc_blog_feed`: MRATC weekly blog, one row an item (FeedNotices). The club's weekly 'Activities
  and Information' posts, which carry hunting-season dates among events: warnings at most, by
  decision 7's classifier. Cloudflare serves the feed up to 7 days stale (max-age 604800), so a
  notice can reach it late. Its descriptions carry personal e-mail addresses (measured 2026-10-03),
  and FeedNotices lands no description.

The feed's items carry `dc:creator`, a person's name, and an `<enclosure>` image; FeedNotices lands
neither.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import feed_notices

CLAIMS = ("mratc_blog_feed",)
RESOURCES = [feed_notices("mratc_blog_feed")]
