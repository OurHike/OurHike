"""Bartram Trail Conference: suggested hikes, an events calendar (not this type) and pages (wave 5)
(decision 54 wave 3, section C, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and
not a challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

The Events Calendar on blueridgebartram.org lists 4 upcoming events (workdays and walks). The 9 day
hikes are a `crb_dayhike` post type that the site's REST API does not expose (its types route lists
only post and page, read 2026-10-04), so they are pages, wave 5's format. bartramtrail.org,
trail_orgs.json's website for this folder, is a Wild Apricot site whose robots.txt asks Request-rate
1/60 and Crawl-delay 10.

The note this replaces read, whole:

Bartram Trail Conference: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Page for the day hikes; Events Calendar JSON for the group hikes. Workdays are mixed in and have to
be filtered out.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://blueridgebartram.org/wp-json/tribe/events/v1/events?per_page=50 (2026-10-04): HTTP 200, total 4.",
        "https://blueridgebartram.org/wp-json/wp/v2/types (2026-10-04): post and page only.",
        '(the coverage audit, 2026-10-01) 9 BRBTC day hikes (`crb_dayhike-sitemap.xml`, newest 2026-03-21; e.g. `/dayhike/dicks-creek-falls/`, "A 2-mile day-hike near the Chattooga River") plus the 13 section guides.',
        '(the coverage audit, 2026-10-01) Skeptic, new, machine-readable: BRBTC runs The Events Calendar. `/wp-json/tribe/events/v1/events` (JSON) lists 5 upcoming events, among them "Walking with Bartram" (2026-10-02, category "Hikes"), "Bartram Trail Camporee" (2026-10-23) and "Trailhead Tuesday". `tribe_events-sitemap.xml` holds 72 event pages back to January 2026.',
    ),
    where=(
        "https://blueridgebartram.org/wp-json/tribe/events/v1/events",
        "https://blueridgebartram.org/wp-json/wp/v2/types",
        "https://bartramtrail.org/",
    ),
    reason="not this type for the events (the lead's ruling, 2026-10-04); the day hikes are wave 5's format",
)
