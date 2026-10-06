"""Blue Mountain Eagle Climbing Club: warnings, 2 notice sources read here (decision 53 phase B,
2026-10-03).

- `bmecc_fluorescent_orange`: BMECC: Fluorescent Orange, one notice for the page (PageNotice).
  Pennsylvania Game Commission's fluorescent-orange rule for State Game Lands (Nov 15 - Dec 15), as
  the club restates it. The authority is the PGC. The page states no date of its own.

- `bmecc_appalachian_trail`: BMECC: Appalachian Trail hiker information, one notice for the page
  (PageNotice). The club's A.T. page, whose parking notes carry 'Hamburg Reservoir parking lot has
  NO overnight parking'. The page states no date of its own.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("bmecc_fluorescent_orange", "bmecc_appalachian_trail")
RESOURCES = [page_notice("bmecc_fluorescent_orange"), page_notice("bmecc_appalachian_trail")]
