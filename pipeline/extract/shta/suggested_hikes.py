"""Superior Hiking Trail Association: suggested hikes, an events calendar (not this type) and pages
(wave 5) (decision 54 wave 3, section C, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and
not a challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

The Events Calendar's guided hikes are dated (2 upcoming on 2026-10-04). The 6 trail-section pages
are a `trail-section` post type that the site's REST API does not expose (`/wp-json/wp/v2/types`
lists no such type, read 2026-10-04), so they are pages, wave 5's format.

The note this replaces read, whole:

Superior Hiking Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Pages, plus the Events Calendar REST API. Skeptic: the 34 are all past.
`/wp-json/tribe/events/v1/events?categories=206` returns `"total":0` for 2026-09-30 to 2028-10-01.
The trail-section pages carry the verdict, not the events. (M)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://superiorhiking.org/wp-json/tribe/events/v1/events?per_page=50 (2026-10-04): HTTP 200, total 2.",
        "https://superiorhiking.org/wp-json/wp/v2/types (2026-10-04): post, page, tribe_events and plugin types; no trail-section.",
        '(the coverage audit, 2026-10-01) 6 `/trail-section/` pages (custom post type in `trail-section-sitemap.xml`). Each sub-section has length, campsite count, directions and a description. Plus `/day-hiking/`, `/backpacking/` and `/thru-hiking/`, and 34 "Guided Hike" events (`/wp-json/tribe/events/v1/`, category id 206).',
    ),
    where=(
        "https://superiorhiking.org/wp-json/tribe/events/v1/events",
        "https://superiorhiking.org/wp-json/wp/v2/types",
        "https://superiorhiking.org/",
    ),
    reason="not this type for the events (the lead's ruling, 2026-10-04); the section pages are wave 5's format",
)
