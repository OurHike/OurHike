"""Arizona Trail Association: closures, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `ata_closures_reroutes`: Arizona Trail: Current Closures, Restrictions, and Reroutes, one row a
  post (WordpressPosts). WordPress category 251, read through the REST API with X-WP-Total as the
  count. Each post's categories carry ATA's passage terms ('Passage 38'), a closed vocabulary that
  can place a notice by passage once reviewed. aztrail.org asks `Crawl-delay: 10`. The category's
  RSS feed carries 10 of its posts, so the feed is not read.

Not wired: https://aztrail.org/category/closures-reroutes/feed/, the category's RSS feed, a window
of 10 of the 13 posts the REST route reads whole; and
https://aztrail.org/explore/hazards-considerations/, static guidance whose Last-Modified is the
request time, not a notice. azgeo/ draws on this resource by a via note.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import wordpress_posts

CLAIMS = ("ata_closures_reroutes",)
RESOURCES = [wordpress_posts("ata_closures_reroutes", crawl_delay=10.0)]
