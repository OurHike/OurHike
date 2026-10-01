"""Benton MacKaye Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c8_regional_5).

Page, plus WP REST for the events. `Disallow: /?` rules out `?page=` paging, so read the sitemap for
the full list. Segment descriptions sit on Hiking Project (third party).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "6 curated pages: `/hikes-with-amazing-views/`, `/hikes-with-waterfalls/`, `/hikes-along-rivers/`, "
        "`/weekend-hikes-with-the-family/`, `/backpacking-hikes/`, `/thru-hikers-guide/`. All 6 are confirmed "
        "in `page-sitemap.xml` (skeptic). Plus `/events/` (monthly club hikes).",
        "Skeptic: the events are machine-readable as WP REST JSON at `/wp-json/wp/v2/mec-events` (10 per page "
        'by default; for example "Amadahy Trail", "BMT: Three Forks to Hickory Flat Cemetery on AT and back", '
        "and maintenance trips) and in `mec-events-sitemap.xml`.",
    ),
    where=("https://bmta.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
