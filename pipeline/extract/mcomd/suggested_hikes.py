"""Mountain Club of Maryland: suggested hikes, published as dated club hikes and reports of them, and
not landed (decision 54 wave 3, section C, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and
not a challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

The Events Calendar (`/wp-json/tribe/events/v1/events`, read 2026-10-04: total 182 upcoming, 47 of
the first 50 in category Hiking) is the club's dated schedule, and category 218 (Mountain Club Of
Maryland Hike Reports, 19 posts) reports past outings: neither is a hike a hiker can take on another
day.

The note this replaces read, whole:

Mountain Club of Maryland: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

Weak: these are trip narratives and events, not curated routes.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://mcomd.org/wp-json/tribe/events/v1/events?per_page=50 (2026-10-04): HTTP 200, total 182, total_pages 4; each event's `organizer` carries a leader's name, e-mail address and telephone number, a person field that a reader would leave out by explicit field list.",
        "https://mcomd.org/wp-json/wp/v2/categories/218 (2026-10-04): 'Mountain Club Of Maryland Hike Reports', count 19.",
        '(the coverage audit, 2026-10-01) WP REST category 218 "Mountain Club Of Maryland Hike Reports" (19 posts); `/wp-json/tribe/events/v1/events` (the dated schedule)',
    ),
    where=(
        "https://mcomd.org/wp-json/tribe/events/v1/events",
        "https://mcomd.org/wp-json/wp/v2/categories/218",
        "https://mcomd.org/",
    ),
    reason="not this type: dated group hikes and their reports, which the lead ruled are not suggested hikes (2026-10-04)",
)
