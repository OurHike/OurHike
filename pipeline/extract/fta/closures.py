"""Florida Trail Association: closures, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `fta_fnst_closed_segments`: Florida National Scenic Trail master: segments not open,
  `FNST%20Master/FeatureServer/0`. Filtered on the agency's own status field: `Open_Statu <> 'Open'
  OR Open_Statu IS NULL`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

And 5 notice sources read here (decision 53 phase B, 2026-10-03, pages, feeds and WordPress):

- `fta_closures_nth_general`: Florida Trail Closures and NTH General, one row an item (FeedNotices).
  One of the five WordPress categories FTA files its closures and Notices to Hikers under (ids 37,
  40, 41, 42 and 43; X-WP-Total 14 under all five, 2026-10-03), read through the category's RSS
  feed. The REST posts route would be the complete list, but it serves each post's rendered content,
  and that content carries staff e-mail addresses and a phone number (measured 2026-10-03), which
  decision 59 keeps out whole; the feed reader lands no prose and no person. Each category held 1 to
  5 posts, fewer than a feed's 10, so each feed was the whole category on the day it was read, and
  is still a window. The categories mix closures with NTH, so an unclassified row goes to warnings
  (decision 7), and old posts stay published (a 2018 bear policy), so expiry is a dbt rule.

- `fta_closures_nth_panhandle`: Florida Trail Closures and NTH Panhandle, one row an item
  (FeedNotices). One of the five WordPress categories FTA files its closures and Notices to Hikers
  under (ids 37, 40, 41, 42 and 43; X-WP-Total 14 under all five, 2026-10-03), read through the
  category's RSS feed. The REST posts route would be the complete list, but it serves each post's
  rendered content, and that content carries staff e-mail addresses and a phone number (measured
  2026-10-03), which decision 59 keeps out whole; the feed reader lands no prose and no person. Each
  category held 1 to 5 posts, fewer than a feed's 10, so each feed was the whole category on the day
  it was read, and is still a window. The categories mix closures with NTH, so an unclassified row
  goes to warnings (decision 7), and old posts stay published (a 2018 bear policy), so expiry is a
  dbt rule.

- `fta_closures_nth_north`: Florida Trail Closures and NTH North, one row an item (FeedNotices). One
  of the five WordPress categories FTA files its closures and Notices to Hikers under (ids 37, 40,
  41, 42 and 43; X-WP-Total 14 under all five, 2026-10-03), read through the category's RSS feed.
  The REST posts route would be the complete list, but it serves each post's rendered content, and
  that content carries staff e-mail addresses and a phone number (measured 2026-10-03), which
  decision 59 keeps out whole; the feed reader lands no prose and no person. Each category held 1 to
  5 posts, fewer than a feed's 10, so each feed was the whole category on the day it was read, and
  is still a window. The categories mix closures with NTH, so an unclassified row goes to warnings
  (decision 7), and old posts stay published (a 2018 bear policy), so expiry is a dbt rule.

- `fta_closures_nth_central`: Florida Trail Closures and NTH Central, one row an item (FeedNotices).
  One of the five WordPress categories FTA files its closures and Notices to Hikers under (ids 37,
  40, 41, 42 and 43; X-WP-Total 14 under all five, 2026-10-03), read through the category's RSS
  feed. The REST posts route would be the complete list, but it serves each post's rendered content,
  and that content carries staff e-mail addresses and a phone number (measured 2026-10-03), which
  decision 59 keeps out whole; the feed reader lands no prose and no person. Each category held 1 to
  5 posts, fewer than a feed's 10, so each feed was the whole category on the day it was read, and
  is still a window. The categories mix closures with NTH, so an unclassified row goes to warnings
  (decision 7), and old posts stay published (a 2018 bear policy), so expiry is a dbt rule.

- `fta_closures_nth_south`: Florida Trail Closures and NTH South, one row an item (FeedNotices). One
  of the five WordPress categories FTA files its closures and Notices to Hikers under (ids 37, 40,
  41, 42 and 43; X-WP-Total 14 under all five, 2026-10-03), read through the category's RSS feed.
  The REST posts route would be the complete list, but it serves each post's rendered content, and
  that content carries staff e-mail addresses and a phone number (measured 2026-10-03), which
  decision 59 keeps out whole; the feed reader lands no prose and no person. Each category held 1 to
  5 posts, fewer than a feed's 10, so each feed was the whole category on the day it was read, and
  is still a window. The categories mix closures with NTH, so an unclassified row goes to warnings
  (decision 7), and old posts stay published (a 2018 bear policy), so expiry is a dbt rule.

Not read: the five categories' REST posts route, whose rendered content carries staff e-mail
addresses and a phone number (decision 59 keeps such a column out whole; the feeds carry no prose at
all into the raw store), and https://floridatrail.org/hiker-safety/, static guidance (hunting
season, flood-prone rivers).

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import arcgis_layer, feed_notices

CLAIMS = (
    "fta_fnst_closed_segments",
    "fta_closures_nth_general",
    "fta_closures_nth_panhandle",
    "fta_closures_nth_north",
    "fta_closures_nth_central",
    "fta_closures_nth_south",
)
RESOURCES = [
    arcgis_layer("fta_fnst_closed_segments"),
    feed_notices("fta_closures_nth_general"),
    feed_notices("fta_closures_nth_panhandle"),
    feed_notices("fta_closures_nth_north"),
    feed_notices("fta_closures_nth_central"),
    feed_notices("fta_closures_nth_south"),
]
