"""Benton MacKaye Trail Association: suggested hikes, an events post type (not this type) and pages
(wave 5) (decision 54 wave 3, section C, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and
not a challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

The `mec-events` post type (Modern Events Calendar, exposed at `/wp-json/wp/v2/mec-events`) is the
monthly club hikes and maintenance trips. The 6 curated hike pages (`/hikes-with-amazing-views/` and
the rest) are pages, wave 5's format. bmta.org's robots.txt asks Crawl-delay 60.

The note this replaces read, whole:

Benton MacKaye Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c8_regional_5).

Page, plus WP REST for the events. `Disallow: /?` rules out `?page=` paging, so read the sitemap for
the full list. Segment descriptions sit on Hiking Project (third party).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://bmta.org/wp-json/wp/v2/types (2026-10-04): post, page, product and mec-events among others.",
        "(the coverage audit, 2026-10-01) 6 curated pages: `/hikes-with-amazing-views/`, `/hikes-with-waterfalls/`, `/hikes-along-rivers/`, `/weekend-hikes-with-the-family/`, `/backpacking-hikes/`, `/thru-hikers-guide/`. All 6 are confirmed in `page-sitemap.xml` (skeptic). Plus `/events/` (monthly club hikes).",
        '(the coverage audit, 2026-10-01) Skeptic: the events are machine-readable as WP REST JSON at `/wp-json/wp/v2/mec-events` (10 per page by default; for example "Amadahy Trail", "BMT: Three Forks to Hickory Flat Cemetery on AT and back", and maintenance trips) and in `mec-events-sitemap.xml`.',
    ),
    where=(
        "https://bmta.org/wp-json/wp/v2/types",
        "https://bmta.org/hikes-with-amazing-views/",
        "https://bmta.org/",
    ),
    reason="not this type for the events (the lead's ruling, 2026-10-04); the curated pages are wave 5's format",
)
