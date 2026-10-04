"""Ozark Highlands Trail Association: suggested hikes, an events calendar and an outings category (not
this type) and a FAQ page (wave 5) (decision 54 wave 3, section C, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and
not a challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

The Events Calendar lists 2 upcoming basecamps and hike-ins (2026-10-04), and the Outings category
(144 posts, newest 2022-10-17, the coverage audit) is the history of past ones. The FAQ's loop hikes
are a page.

The note this replaces read, whole:

Ozark Highlands Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c8_regional_5).

WP REST JSON. Read the Events Calendar API for current hikes and the Outings category for the
archive.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://ozarkhighlandstrail.com/wp-json/tribe/events/v1/events?per_page=50 (2026-10-04): HTTP 200, total 2.",
        '(the coverage audit, 2026-10-01) WP category "Outings": 144 posts (e.g. "Hare Mountain Hike-in \'22"). `tribe_events` sitemap: 38 events. FAQ loop hikes ("Redding to Spy Rock Loop Trail (8.8 miles)").',
        '(the coverage audit, 2026-10-01) Skeptic: "Outings" is historical. Its newest post is "Hare Mountain Hike-in \'22" (2022-10-17). The live outings are The Events Calendar\'s: `/wp-json/tribe/events/v1/events` lists 3 upcoming, "Fall 2026 OHTA East Basecamp" (2026-10-02), "… North Basecamp" (2026-10-09) and "2026 Hare Mountain Hike-In" (2026-11-07).',
    ),
    where=(
        "https://ozarkhighlandstrail.com/wp-json/tribe/events/v1/events",
        "https://ozarkhighlandstrail.com/",
    ),
    reason="not this type: dated outings, which the lead ruled are not suggested hikes (2026-10-04); the FAQ is wave 5's",
)
