"""Smoky Mountains Hiking Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

About a month's lag and prose-only. Better as reviewed warnings than as an automated feed. Downloads
redirect to signed `cdn.wildapricot.com` URLs. (skeptic) Spot-checked: the newest is `ATMC-0926.pdf`
(3,187,809 bytes, last-modified 2026-08-26); the page links 60 month slots to 2026-12 and the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

NOT WIRED, decision 53 phase B (2026-10-03): the ATMC newsletter is a new PDF at a new URL every month
(`ATMC-<MMYY>.pdf`; the inventory, batch 2, found ATMC-0926.pdf the newest and ATMC-1026.pdf a 404), and
the `/ATMC-Newsletters` page links 60 month slots to 2026-12 ahead of the files, so neither one fixed URL
nor the listing's hash follows the newest issue. A reader that probes next month's slot is what the
inventory proposed and is not built. smhclub.org's robots.txt (Wild Apricot) asks `Crawl-delay: 10` and
`Request-rate: 1/60`, one request a minute, which such a reader would keep. The newsletters are prose
trip reports a month behind; the coverage audit judged them better as reviewed warnings than an
automated feed.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_ROADS/FeatureServer/0,
GRSM's roads, 697 of 1,925 'Temporarily Closed' and unedited since 2025-11-13: a seasonal road
attribute, not a current notice.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(decision 53 inventory, batch 2, 2026-10-03) HEAD of ATMC-0926.pdf: 200, Last-Modified Wed, 26 Aug 2026 "
        "00:29:32 GMT; ATMC-1026.pdf: 404. robots.txt: Crawl-delay 10, Request-rate 1/60, nothing disallowed under "
        "/resources/Documents/.",
        "ATMC monthly newsletters, "
        "`https://smhclub.org/resources/Documents/atmc_newsletters/<YYYY>/ATMC-<MMYY>.pdf` (PDF; 2022 to 2026, "
        "linked from `/ATMC-Newsletters`). August 2026 (6 pages) holds maintainer trip reports with hazards: a "
        '"rootball blow out ~0.25 mile south of Low Gap … Put up caution tape near the edge of the failing '
        'trail"; hornets "near the Lower Mt Cammerer trailhead".',
    ),
    where=(
        "https://smhclub.org/resources/Documents/atmc_newsletters/",
        "https://cdn.wildapricot.com",
    ),
    reason=(
        "published and not landed: each month's newsletter is a new URL, and no reader that follows the newest slot exists yet"
    ),
)
