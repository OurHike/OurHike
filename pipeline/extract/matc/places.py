"""Maine Appalachian Trail Club: places, drawn from another folder's resource (coverage audit
2026-10-01, batch c1_at_clubs_north).

The Baxter page is about permits and transport, not places with coordinates.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`communities` (ATC A.T. Communities) and `trail_club_sections`. MATC's own: "
        "`https://www.matc.org/baxter-state-park-information/` is a page of links and handouts.",
    ),
    where=("https://www.matc.org/baxter-state-park-information/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
