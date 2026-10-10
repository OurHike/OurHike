"""The Trail Foundation (Austin): closures, 1 notice source read here (decision 53 phase B,
2026-10-03).

- `ttc_butler_trail_detours`: Butler Trail Detours, one notice, WordPress page 5616 through its REST
  route (PageNotice). One page of dated detour entries (I-35 Capital Express to 2033, Waller Beach,
  Lou Neff Road), read through WordPress page 5616. thetrailconservancy.org asks `Crawl-delay: 10`
  above its first User-agent line, honoured anyway. trail_orgs.json's thetrailfoundation.org is dead
  (404): the club renamed.

The registry row and this folder use thetrailconservancy.org: trail_orgs.json's
thetrailfoundation.org answers 404 since the club renamed (the decision 53 inventory, batch 5).

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("ttc_butler_trail_detours",)
RESOURCES = [page_notice("ttc_butler_trail_detours", wp_page=5616, crawl_delay=10.0)]
