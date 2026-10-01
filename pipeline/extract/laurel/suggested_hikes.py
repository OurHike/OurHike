"""Laurel Highlands Hiking Trail (PA DCNR): suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`BSP_StateParksTrails.TrailDescription`; "
        "`https://www.pa.gov/agencies/dcnr/recreation/what-to-do/hiking/laurel-highlands-hiking-trail`; Explore"
        " PA Trails `trails.dcnr.pa.gov/trails/trail/trailview?trailkey=90`.",
    ),
    where=(
        "https://www.pa.gov/agencies/dcnr/recreation/what-to-do/hiking/laurel-highlands-hiking-trail",
        "https://trails.dcnr.pa.gov/trails/trail/trailview?trailkey=90",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
