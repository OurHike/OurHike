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

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Cumberland Valley Appalachian Trail Club: warnings, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Same RSS: 2025-06-13 "Break-Ins at A.T. Parking Lots" (two
cars broken into at Trindle Road). `/protect-yourself-on-the-trail.html` is evergreen tick and Lyme
advice

Its `where`: https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services https://cvatclub.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import feed_notices

CLAIMS = ("cvatc_news",)
RESOURCES = [feed_notices("cvatc_news")]
