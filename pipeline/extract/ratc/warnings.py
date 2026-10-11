"""Roanoke Appalachian Trail Club: warnings, 1 notice source read here: decision 53's drafted row, registered
2026-10-10 (section K's hand-back) once www.ratc.org's robots.txt answered 200.

- `ratc_mcafee_page`: 'McAfee Knob and Virginia's Triple Crown', one notice, WordPress page 2821 through its REST
  route (PageNotice): the club's standing rules for the A.T. from VA 624 to US 220 (camping, fires, group sizes)
  and, read 2026-10-10, "There are no natural water sources along the A.T. in the Dragons Tooth area, so bring all
  your water if planning to camp in that area." As every page notice, the page lands as one notice, its title, its
  own date and its link, and none of its sentences (decisions 55, 107 and 141: no rule of its own), so that line
  reaches a hiker only through the link. The water warning on these miles is ATC's own 'Virginia: Triple Crown Dry
  Conditions' (2026-09-03, 'Hiking Safety', NOBO miles 697.5 to 731.1, read 2026-10-10), which atc/closures.py's
  reader of ATC's website lands and int_closures__atc_automatic's gate admits as an unreviewed warning (Reasoned
  from that model's rules; no build ran here).

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-10 and its measured key.
The readers are extract/_kinds.py's WordpressPosts and extract/_notices.py's PageNotice. A page is read every run, one
request, and is FRESH only when what would land hashes as the last committed load did; a category is FRESH only when
its count and its posts' (id, modified_gmt) pairs are unchanged. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("ratc_mcafee_page",)
RESOURCES = [page_notice("ratc_mcafee_page", wp_page=2821)]
