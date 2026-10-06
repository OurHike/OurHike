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

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Mount Rogers Appalachian Trail Club: warnings, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

The RSS `description` is a truncated summary, so full text needs the post page. A naive keyword
filter matches "closure" inside `<enclosure>` on every item, as this audit found. ATC LOADED carries
Rhododendron Gap bears and the Mt Rogers fire restrictions.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Weekly "MRATC Activities and Information" posts, RSS
`https://www.mratc.org/blog-feed.xml` (20 items; newest 2026-09-27; weekly since 2025-12). For
example, 2026-09-27 lists hunting seasons with dates ("Deer archery: 10/3 to 11/13 … Rifle: 11/14 to
11/28") and points to `dwr.virginia.gov`. `/backpacking-rules`: camping prohibited on the A.T. in
Grayson Highlands SP except inside Wise Shelter; group size limits (10 in Lewis Fork, Raccoon Branch
and Little Wilson Creek Wilderness); bear food storage.

Its `where`: https://www.mratc.org/blog-feed.xml https://dwr.virginia.gov

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import feed_notices

CLAIMS = ("mratc_blog_feed",)
RESOURCES = [feed_notices("mratc_blog_feed")]
