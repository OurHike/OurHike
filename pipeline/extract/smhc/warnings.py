"""Smoky Mountains Hiking Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

About a month's lag and prose-only. Better as reviewed warnings than as an automated feed. Downloads
redirect to signed `cdn.wildapricot.com` URLs. (skeptic) Spot-checked: the newest is `ATMC-0926.pdf`
(3,187,809 bytes, last-modified 2026-08-26); the page links 60 month slots to 2026-12 and the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://smhclub.org/resources/Documents/atmc_newsletters/2026/ATMC-0926.pdf (pdf).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_ROADS/FeatureServer/0,
GRSM's roads, 697 of 1,925 'Temporarily Closed' and unedited since 2025-11-13: a seasonal road
attribute, not a current notice.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
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
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
