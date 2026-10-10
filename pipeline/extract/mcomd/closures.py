"""Mountain Club of Maryland: closures, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `mcomd_club_news_feed`: Mountain Club of Maryland: Club News & Announcements, one row an item
  (FeedNotices). The feed of WordPress category 216, the club's only news stream: the newest 10 of
  its 94 posts (X-WP-Total, 2026-10-03), one of them a closure ('James Fry Shelter on the AT
  Reopened but Harpers Ferry Footbridge Closed!', 2026-09-25) among club news. No category or tag
  isolates notices, so which items are notices is a reviewed per-item list in dbt; the category
  never publishes whole. The REST posts route would be the complete list, but its rendered content
  carries members' personal e-mail addresses (gmail.com, outlook.com) and a phone number (measured
  2026-10-03), which decision 59 keeps out whole; the feed reader lands no prose and no person.

Not read: the category's REST posts route, the complete list of 94, whose rendered content carries
members' personal e-mail addresses (decision 59 keeps such a column out whole), and the site feed
(https://www.mcomd.org/feed/), which mixes every category.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import feed_notices

CLAIMS = ("mcomd_club_news_feed",)
RESOURCES = [feed_notices("mcomd_club_news_feed")]
