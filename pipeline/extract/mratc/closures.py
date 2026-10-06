"""Mount Rogers Appalachian Trail Club: closures, 1 notice source read here (decision 53 phase B,
2026-10-03).

- `mratc_trail_alerts`: MRATC home page Trail Alerts, one notice for the page (PageNotice). The Wix
  home page's TRAIL ALERTS block (the 2026 Creeper Trail detour, VDOT lot work, FS 89 closed for
  winter), which sits in Wix's generated `comp-` elements and has no stable address, so the page's
  main region is read whole and its hash moves with anything on it. The block states no date.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("mratc_trail_alerts",)
RESOURCES = [page_notice("mratc_trail_alerts")]
