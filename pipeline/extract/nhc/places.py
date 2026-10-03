"""Nantahala Hiking Club: places, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

A trail-town shuttle is the useful part. ATC `communities` is LOADED.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/thru-hiker/` (modified 2026-07-21): Franklin as the first A.T. Community, and Macon County Transit "
        'shuttles "to and from Winding Stair Gap and Deep Gap three times a day, Monday through Friday". '
        "`https://www.nantahalahikingclub.org/wp-content/uploads/2025/10/SOBO-by-Sections.pdf` (PDF, "
        "2025-10-15) names 23 maintenance-section points with miles, from NOC to the GA/NC line.",
    ),
    where=(
        "https://www.nantahalahikingclub.org/wp-content/uploads/2025/10/SOBO-by-Sections.pdf",
        "https://nantahalahikingclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
