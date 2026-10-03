"""Black Hills Trails: challenges, nothing published (coverage audit 2026-10-01, batch c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Same pages. (Skeptic, 2026-10-01: none of the 7 wp/v2 categories or 27 pages is a challenge. New find,"
        ' another publisher: Black Hills Parks & Forests Association ran the "2023 South Dakota Centennial '
        'Trail Hike Challenge" '
        "(`blackhillsparks.org/news-events/calendar/south-dakota-centennial-trail-hike-challenge/`, posted "
        "2023-04-13). It asked for 128 virtual miles logged on Challenge Hound between 2023-05-29 and "
        "2023-09-04, walked anywhere, and its registration is closed. It was a one-off by an org that is not in"
        " `trail_orgs.json`, so it gives no reason to change this row.)",
    ),
    where=("https://blackhillsparks.org/news-events/calendar/south-dakota-centennial-trail-hike-challenge/",),
)
