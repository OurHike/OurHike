"""Superior Hiking Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Pages, plus the Events Calendar REST API. Skeptic: the 34 are all past.
`/wp-json/tribe/events/v1/events?categories=206` returns `"total":0` for 2026-09-30 to 2028-10-01.
The trail-section pages carry the verdict, not the events. (M)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "6 `/trail-section/` pages (custom post type in `trail-section-sitemap.xml`). Each sub-section has "
        "length, campsite count, directions and a description. Plus `/day-hiking/`, `/backpacking/` and "
        '`/thru-hiking/`, and 34 "Guided Hike" events (`/wp-json/tribe/events/v1/`, category id 206).',
    ),
    where=("https://superiorhiking.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
