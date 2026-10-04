"""AMC Berkshire Chapter's A.T. parking areas in Massachusetts, with each area's capacity, overnight grade,
winter plowing, map kiosk and fee, from its "A.T. Parking Areas and Trailhead" page.

Decision 54, wave 5: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent) and registered in
sources.json, where the row carries the count, the measured key and what holds it back.

- `amc_wma_at_parking_points`: 28 parking areas, 27 with a coordinate, keyed on the name.

The same page is amc_berkshire/closures.py's notice `amc_wma_at_parking`, one page-notice row; this resource
reads its parking areas, a second dataset of one page.

NOT LANDED, read 2026-10-01 by the coverage audit and not re-read: "Campsites and Shelters on the
Massachusetts A.T." (https://www.amc-wma.org/documents-more.cgi?id=13, dated 04-Jan-2025), shelter capacity,
tent platforms, privy, bear box and water source per site, with no coordinate on any. ATC's layers place the
same sites (atc, code 5: shelters 11, campsites 19), so the page's facts need a join to those points by name,
which a person reviews; needs a per-site reader, not built in this pull request. It is a notice too,
`amc_wma_at_campsites`.
"""

from extract._pages_points import page_points

CLAIMS = ("amc_wma_at_parking_points",)
RESOURCES = [page_points(key) for key in CLAIMS]
