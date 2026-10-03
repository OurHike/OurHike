"""Smoky Mountains Hiking Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

The page says "the 900 Miler Club is a separate entity" that SMHC hosts. Recommendation: keep it in
`smhc/challenges.py` with `publisher: 900 Miler Club (hosted by SMHC)`. Its items join `nps_trails`
by name (@unvalidated: name match rate). The member list is a roster, so exclude it. (skeptic) …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Great Smoky Mountains 900 Miler Club, `https://smhclub.org/900-Miler-Club`: hike every official GSMNP "
        "trail; 938 members as of 2026-09-08. The trail list is an Excel file, "
        "`/resources/Documents/900%20Mile%20Spreadsheet%20for%20Website%20Final%20Version%20Revision%20with%20Primary%20Source%20Data%20in%20Feet%2009212024.xls`"
        ' (83,968 bytes; last-modified 2024-09-21), machine-readable. The page notes "Scott Mountain Trail, '
        'while closed for most of the trail, is OPEN and required from Crooked Arm Trail to CS# 6".',
    ),
    where=(
        "https://smhclub.org/900-Miler-Club",
        "https://smhclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
