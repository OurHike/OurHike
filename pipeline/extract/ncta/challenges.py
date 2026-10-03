"""North Country Trail Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Format page. The Hike 100 Challenge: `northcountrytrail.org/hike-100/26signup/` and `/26completion/` "
        '(2026 pages exist). Long-distance hiker recognition: the "NCNST Long Distance Hiker" posts (`/ldh-`).',
        'Skeptic adds: `/the-trail/hike-resources/` (WebFetch) reads "Spend 100 miles on the North Country '
        'Trail in the calendar year to earn a collectable patch" and links `/hike-100-challenge`. It also '
        "mentions the NPS Passport stamp at NCTA's Lowell HQ, which is the Park Service's programme, not "
        "NCTA's. ArcGIS also holds two old Hike 100 map tours (2016, 2017).",
    ),
    where=(
        "https://northcountrytrail.org/hike-100/26signup/",
        "https://northcountrytrail.org/",
        "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
