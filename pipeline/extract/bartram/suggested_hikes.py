"""Bartram Trail Conference: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Page for the day hikes; Events Calendar JSON for the group hikes. Workdays are mixed in and have to
be filtered out.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "9 BRBTC day hikes (`crb_dayhike-sitemap.xml`, newest 2026-03-21; e.g. `/dayhike/dicks-creek-falls/`, "
        '"A 2-mile day-hike near the Chattooga River") plus the 13 section guides.',
        "Skeptic, new, machine-readable: BRBTC runs The Events Calendar. `/wp-json/tribe/events/v1/events` "
        '(JSON) lists 5 upcoming events, among them "Walking with Bartram" (2026-10-02, category "Hikes"), '
        '"Bartram Trail Camporee" (2026-10-23) and "Trailhead Tuesday". `tribe_events-sitemap.xml` holds 72 '
        "event pages back to January 2026.",
    ),
    where=("https://bartramtrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
