"""Tennessee Trails Association: suggested hikes, an events calendar (not this type) and pages and a
PDF (waves 4 and 5) (decision 54 wave 3, section C, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and
not a challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

The Events Calendar is the chapters' dated group hikes and workdays. The 36 Fran Wallas hikes
(`/hikes-events/36-fran-wallas-hikes/`, a page) and Great Hikes in Tennessee State Parks (a PDF) are
suggested hikes in another format, named in section C's hand-back.

The note this replaces read, whole:

Tennessee Trails Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

The events are dated outings, not routes. Terms forbid republishing.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://tennesseetrails.org/wp-json/tribe/events/v1/events?per_page=50 (2026-10-04): HTTP 200, total 75 upcoming; event descriptions carry e-mail addresses (14 of 50) and telephone numbers (39 of 50). tennesseetrails.org's robots.txt asks Crawl-delay 60, honoured.",
        "(the coverage audit, 2026-10-01) `/hikes-events/36-fran-wallas-hikes/` lists 36 named hikes (HTML). PDF of Great Hikes in Tennessee State Parks: `/wp-content/uploads/2021/03/Great_Hikes_Fran-Wallas-2021.pdf`. Events REST `/wp-json/tribe/events/v1/events` (72 upcoming group hikes). `/2025-agm-hike-schedule-and-descriptions/` (page).",
    ),
    where=(
        "https://tennesseetrails.org/wp-json/tribe/events/v1/events",
        "https://tennesseetrails.org/hikes-events/36-fran-wallas-hikes/",
        "https://tennesseetrails.org/",
    ),
    reason="not this type for the events (the lead's ruling, 2026-10-04); the hike list is a page and a PDF, waves 4 and 5",
)
