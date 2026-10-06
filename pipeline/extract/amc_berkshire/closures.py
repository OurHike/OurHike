"""AMC Berkshire Chapter: closures, 2 notice sources read here (decision 53 phase B, 2026-10-03).

- `amc_wma_at_parking`: AMC Berkshire Chapter: A.T. Parking Areas and Trailheads, one notice for the
  page (PageNotice). Standing seasonal access closures at the Massachusetts A.T.'s trailheads
  ("Summit is closed in winter (late Oct to late May)"), dated 11-Jan-2025 in its own text.

- `amc_wma_at_campsites`: AMC Berkshire Chapter: Campsites and Shelters on the Massachusetts A.T.,
  one notice for the page (PageNotice). Standing facility notes for the chapter's campsites and
  shelters (Upper Goose Pond Cabin 'closed when no caretaker is present'), dated 04-Jan-2025 in its
  own text.

Also drawn from _shared/ma_dcr/'s `ma_dcr_park_alerts` (DCR's FACILITYCLOSURE_APPDATA layer),
extracted once there (decision 34); which DCR PARK_SITE values lie on the Massachusetts A.T. is
still unchecked.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("amc_wma_at_parking", "amc_wma_at_campsites")
RESOURCES = [page_notice("amc_wma_at_parking"), page_notice("amc_wma_at_campsites")]
