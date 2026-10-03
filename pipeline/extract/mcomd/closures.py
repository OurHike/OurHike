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

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Mountain Club of Maryland: closures, published, and not landed (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

This channel is ahead of our loaded ATC copy (finding 1). The posts carry dates and `modified`, so
an ETag/`modified` freshness marker would work here.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `https://www.mcomd.org/wp-json/wp/v2/posts` (JSON; category
216 "Club News & Announcements", 94 posts) and `/feed/` (RSS). Search hits: "closed" 6, "closure" 3,
"detour" 1. Among them: post 72468 (date 2026-09-25, modified 2026-09-26), James Fry reopened
09/24/2026 plus the Harpers Ferry footbridge still closed; "Route MD-77 Detour Affecting Access to
Catoctin Mountain Park" (2024-01-08); PVSP Grist Mill Trail closures (2022)

Its `where`: https://www.mcomd.org/wp-json/wp/v2/posts https://mcomd.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import feed_notices

CLAIMS = ("mcomd_club_news_feed",)
RESOURCES = [feed_notices("mcomd_club_news_feed")]
