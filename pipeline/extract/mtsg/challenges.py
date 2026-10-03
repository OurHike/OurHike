"""Mountains to Sound Greenway Trust: challenges, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Neither is a place-based challenge in the shape of #1780 — Let a club publish a challenge — places
on its own trails that hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket
List.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/get-involved/volunteer/passport/` is a Volunteer Passport that stamps volunteer events. "
        "`/neighborhood-nature-scavenger-hunt/` is a 2020 PDF.",
        "Skeptic: REST searches for `challenge` (a Bike to Work Month donor page and trail news), `bingo` (1 "
        "school post) and `passport` (the volunteer pages) find no hiker programme.",
    ),
    where=("https://mtsgreenway.org/",),
)
