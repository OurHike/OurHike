"""NY State Parks / NYS GIS Clearinghouse: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch b4_oprhp_mohonk_gatc).

First Day Hikes are one-day guided events, and each year gets a new service, so the extractor has to
find the year's view by name. The route geometry is not published, only a meet-up point. Whether the
birding-trail list is hike-shaped is @unvalidated. The events feed is the richer find: dated …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`First_Day_Hikes_2026_view/0`: 136 points, edited 2026-01-01. Fields `Facility`, `Description`, "
        "`StartTime`, `MeetupLocation`, `Mileage`, `RegistrationURL`, `Host`. Sample: Saratoga Spa SP, "
        '"moderate 1.5-mile hike". Blog post "Best Loved Hikes in New York State Parks" (nystateparks.blog, '
        '2016-08-30, page). 15 StoryMaps on the org, e.g. "OPRHP Trails Program Summary" (2021-12-01). '
        'data.ny.gov "Birding Trail Locations" (`dpe3-6uw2`, updated 2025-10-28). Per-park trail pages on '
        "parks.ny.gov are unreachable today. Skeptic find: a live RSS feed. "
        "`https://content.parks.ny.gov/feeds/events.ashx` …",
    ),
    where=(
        "https://content.parks.ny.gov/feeds/events.ashx",
        "https://data.ny.gov",
        "https://parks.ny.gov",
        "https://parks.ny.gov/feeds/events.ashx",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
