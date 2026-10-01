"""Ozark Highlands Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c8_regional_5).

WP REST JSON. Read the Events Calendar API for current hikes and the Outings category for the
archive.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'WP category "Outings": 144 posts (e.g. "Hare Mountain Hike-in \'22"). `tribe_events` sitemap: 38 '
        'events. FAQ loop hikes ("Redding to Spy Rock Loop Trail (8.8 miles)").',
        'Skeptic: "Outings" is historical. Its newest post is "Hare Mountain Hike-in \'22" (2022-10-17). The '
        "live outings are The Events Calendar's: `/wp-json/tribe/events/v1/events` lists 3 upcoming, \"Fall 2026"
        ' OHTA East Basecamp" (2026-10-02), "… North Basecamp" (2026-10-09) and "2026 Hare Mountain Hike-In" '
        "(2026-11-07).",
    ),
    where=("https://ozarkhighlandstrail.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
