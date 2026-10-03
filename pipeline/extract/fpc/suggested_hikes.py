"""Forest Park Conservancy: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The "nine recommended hiking and running trails" are in the paper Visitor\'s Guide only. REST search '
        "`hike` returns guided-hike events (`mec-events`).",
        "Skeptic (stands): the `trail-recommendations` category holds 2 posts, both Trail Tip Tuesdays from "
        '2021. "Plan Ahead: One-Way Trail Loops in Forest Park" (2020-08-14) describes PP&R\'s COVID one-way '
        'loops, now withdrawn. "Explore Forest Park by Public Transportation" (2021-07-29) is a travel post. '
        "None is a current route description.",
    ),
    where=(
        "https://www.portlandmaps.com/od/rest/services",
        "https://forestparkconservancy.org/",
    ),
)
