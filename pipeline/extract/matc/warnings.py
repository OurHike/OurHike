"""Maine Appalachian Trail Club: warnings, 2 notice sources read here (decision 53 phase B,
2026-10-03).

- `matc_hazard_posts`: MATC Hazard posts, one row a post (WordpressPosts). WordPress category 157
  `hazard`, read through the REST API with X-WP-Total as the count. Dormant since 2023-09 (2 posts),
  kept because it is where the club files hazards.

- `matc_kennebec_ferry`: Kennebec River Ferry Service, one notice, WordPress page 474 through its
  REST route (PageNotice). The Kennebec ferry's season and hours and 'Do not attempt to wade or swim
  across Maine's Kennebec River' (two hikers are known to have died fording it), read through
  WordPress page 474. The page carries the ferry operator's phone number and personal e-mail
  address; the reader lands only the title, the date, the link and a hash of the text, so neither
  reaches the raw store.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice, wordpress_posts

CLAIMS = ("matc_hazard_posts", "matc_kennebec_ferry")
RESOURCES = [wordpress_posts("matc_hazard_posts"), page_notice("matc_kennebec_ferry", wp_page=474)]
