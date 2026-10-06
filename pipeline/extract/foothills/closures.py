"""Foothills Trail Conservancy: closures, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `foothills_trail_conditions`: Foothills Trail Conservancy Trail Conditions, one notice, WordPress
  page 25 through its REST route (PageNotice). One hand-edited page, read through WordPress page
  25's REST route: foothillstrail.org's robots.txt disallows every URL with a query string
  (`Disallow: /*?`) and asks `Crawl-delay: 10`. Its newest entry, 'Trail Update 4/13', carries no
  year, so the stated-date step is off (`date_pattern=None`) and the page's modified_gmt
  (2025-04-13) dates it: read on, the older 'Update Mar 12, 2025' would have dated the page a month
  early.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("foothills_trail_conditions",)
RESOURCES = [page_notice("foothills_trail_conditions", wp_page=25, crawl_delay=10.0, date_pattern=None)]
