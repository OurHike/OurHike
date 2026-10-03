"""Tennessee Eastman Hiking & Canoeing Club: closures, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

The Watauga banner looks stale. The Cherokee NF alerts page (`fs.usda.gov/r08/cherokee/alerts`, read
2026-10-01) lists no Watauga, Wilbur Dam or US 321 A.T. closure (Reasoned that it has lapsed;
whether it still stands is @unvalidated). So club banners must carry `as_of` and land as "not
reviewed" …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "(1) WP category Appalachian Trail (id 3, 87 posts), RSS "
        "`https://tehcc.org/category/appalachian-trail/feed/`. Titles are public, bodies members-only (12 of "
        '87, every one since 2022-01-18). The titles carry facts: "Overmountain Shelter retired" (2023-12-01); '
        '"Roan High Knob shelter closed for repairs to be made in 2025" (2024-09-07); "Laurel Fork Shelter '
        'damaged by fire" (2024-08-15); "Update: Clyde Smith Shelter reopened after temporarily closed due to '
        'bear activity" (2025-05-30); two 2023-02-23 "A.T. Camping Closure" posts. (2) Wiki '
        "`Template:Announcement` boxes on 9 pages, for example …",
    ),
    where=(
        "https://tehcc.org/category/appalachian-trail/feed/",
        "https://fs.usda.gov/r08/cherokee/alerts",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
