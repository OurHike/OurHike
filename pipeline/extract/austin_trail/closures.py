"""The Trail Foundation (Austin): closures, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Each entry has a start and a duration, so a parser can carry an end date.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/visit-the-trail/detours/` via REST `?slug=detours` (modified 2026-07-27), HTML with detour PNGs. "
        "Entries: Barton Creek short-term detour (2026-07-13, 2 days). Waller Beach reroute (June 2026 to March"
        " 2027). I-35 east pedestrian crossing closed from the week of 2026-02-09, for about a year. Riverside "
        "Dr pedestrian ramp closed 2026-02-16 through 2029. I-35 Capital Express Central detours to 2033.",
    ),
    where=("https://thetrailfoundation.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
