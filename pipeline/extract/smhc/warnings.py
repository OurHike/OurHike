"""Smoky Mountains Hiking Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

About a month's lag and prose-only. Better as reviewed warnings than as an automated feed. Downloads
redirect to signed `cdn.wildapricot.com` URLs. (skeptic) Spot-checked: the newest is `ATMC-0926.pdf`
(3,187,809 bytes, last-modified 2026-08-26); the page links 60 month slots to 2026-12 and the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
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
