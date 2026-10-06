"""Appalachian Mountain Club: closures, 2 notice sources read here (decision 53 phase B, 2026-10-03).

- `amc_net_closures_notices`: New England Trail Closures & Notices (Massachusetts), one notice,
  WordPress page 27 through its REST route (PageNotice). Massachusetts half of the New England
  Trail's notices (newenglandtrail.org is AMC's and CFPA's joint site; the Connecticut half links
  out to CFPA's own trail notices, cfpa/). Read through WordPress page 27's REST route, which
  carries no query string: newenglandtrail.org's robots.txt disallows every URL with one (`Disallow:
  /*?`) and asks `Crawl-delay: 3`.

- `amc_facility_conditions`: AMC Weather & Trail Conditions (huts, lodges and shelters), one notice
  for the page (PageNotice). One page of per-facility cards (huts, lodges, shelters), each with a
  Status of Open or Closed and a dated conditions note. A hut's status is a facility closure. The
  page's JSON-LD dateModified does not move with the statuses (the inventory: 2026-02-18 above
  facility notes dated 2026-05-30, all 30 destinations re-saved 2026-09-28), so the date this lands
  is the page's own, not the statuses'.

Not wired: AMC's guidebook-updates PDF
(https://cdn.outdoors.org/wp-content/uploads/2025/10/22111417/AMC_BookUpdates_10.8.25-final.pdf, the
10.8.25 edition). Each edition is a new dated file name, the previous edition (10.30.24) still
answers 200, and no page linking the current edition was found by the decision 53 inventory (batch
4), so a resource on one edition would keep serving it as current after the next. It waits on that
page.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("amc_net_closures_notices", "amc_facility_conditions")
RESOURCES = [page_notice("amc_net_closures_notices", wp_page=27, crawl_delay=3.0), page_notice("amc_facility_conditions")]
