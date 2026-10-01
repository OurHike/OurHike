"""Maine Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c1_at_clubs_north).

Thin: one route. The A.T. Guide to Maine is sold, not published.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.matc.org/grafton-loop-trail/` (page): one route, southern and northern trailheads with "
        "driving directions, the distance between them (7.3 mi), and the first campsite 5 mi in.",
    ),
    where=("https://www.matc.org/grafton-loop-trail/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
