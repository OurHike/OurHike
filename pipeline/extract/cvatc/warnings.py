"""Cumberland Valley Appalachian Trail Club: warnings, 1 notice source read here (decision 53 phase B,
2026-10-03).

- `cvatc_news`: CVATC News, one row an item (FeedNotices). The club's Weebly news feed, every item
  'Uncategorized': notice-shaped posts are about one a year (2025-06-13 'Break-Ins at A.T. Parking
  Lots'), so its items are warnings until decision 7's classifier reads them. Weebly sends no ETag
  and a Last-Modified equal to the request time, so the check is the read. Its items' prose carries
  a personal e-mail address and phone numbers (measured 2026-10-03); FeedNotices lands no prose.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import feed_notices

CLAIMS = ("cvatc_news",)
RESOURCES = [feed_notices("cvatc_news")]
