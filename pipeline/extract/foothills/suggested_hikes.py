"""Foothills Trail Conservancy: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

These are a WordPress custom post type (`us_portfolio`). REST could not be checked because
`/wp-json/` returned 503. (Skeptic: re-counted 2026-10-01, still 19 `/portfolio/` links. The 503 is
a human-verification wall, not an outage; see the fetch flags.)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/section-by-section-2/` links 19 pages under `/portfolio/…`: 13 sections from A1 to A14 and 6 spurs. "
        "Each gives distance, difficulty, trailheads and features. Example: `/portfolio/a1/` is 9.7 mi, "
        '"strenuous (ascends 2,000 feet in three miles)".',
    ),
    where=("https://foothillstrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
